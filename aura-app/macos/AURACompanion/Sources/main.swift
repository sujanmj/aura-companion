Warning: truncated output (original token count: 18628)
Total output lines: 1465

import SwiftUI
import AppKit
@preconcurrency import AVFoundation
@preconcurrency import Speech
import Vision
import Security

@main
struct AURAAmbientApp: App {
    @NSApplicationDelegateAdaptor(AURAAppDelegate.self) private var appDelegate
    var body: some Scene {
        MenuBarExtra {
            MenuView(monitor: appDelegate.monitor)
        } label: {
            Label("AURA", systemImage: appDelegate.monitor.isActive ? "waveform.circle.fill" : "waveform.circle")
        }
        .menuBarExtraStyle(.window)
    }
}

@MainActor final class AURAAppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    let monitor = AmbientMonitor()
    private var window: NSWindow?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        let frame = NSRect(x: 0, y: 0, width: 430, height: 570)
        let window = NSWindow(contentRect: frame, styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "AURA Ambient Companion"
        window.center()
        window.contentView = NSHostingView(rootView: MenuView(monitor: monitor))
        window.isReleasedWhenClosed = false
        window.delegate = self
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        self.window = window
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        guard let window else { return false }
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        return true
    }

    func windowWillClose(_ notification: Notification) {
        guard notification.object as? NSWindow === window else { return }
        monitor.stop()
    }

    func applicationWillTerminate(_ notification: Notification) {
        monitor.terminate()
    }
}

@MainActor final class AmbientMonitor: NSObject, ObservableObject {
    @Published var isActive = false
    @Published var isStarting = false
    @Published var isPairing = false
    @Published var isCheckingPairing = false
    @Published var isClearingPairing = false
    @Published var canRetrySavedPairing = false
    @Published var canUseSessionOnlyPairing = false
    @Published var isPaired = false
    @Published var microphoneOn = false
    @Published var microphoneStopping = false
    @Published var cameraOn = false
    @Published var cameraStopping = false
    @Published var isPersonPresent = false
    @Published var status = "Pair AURA using the session code from its terminal."
    @Published var code = ""
    @Published var recentResponse = ""
    @Published var scene = ""
    @Published private(set) var followupsEnabled = false
    @Published private(set) var followupDurationSeconds = 30
    @Published private(set) var privateRepliesEnabled = false
    @Published private(set) var isSpeaking = false
    private var conversationTurns = ConversationTurnGate()
    private var speechPlaybackGeneration = SpeechPlaybackGeneration()

    private var camera: LocalCamera?
    private var lifecycle = AmbientLifecycle()
    private var pairingGeneration = PairingGeneration()
    private var replyTask: Task<Void, Never>?
    private var startupTimeoutTask: Task<Void, Never>?
    private let audioCapture = LocalAudioCapture()
    private let synthesizer = AVSpeechSynthesizer()
    private var speechOutputSuppression = SpeechOutputSuppression()
    private var audioConfigurationObserver: NSObjectProtocol?
    private var transcriber: (any AmbientTranscriber)?
    private var cookie: String?
    private var pendingSessionOnlyCookie: String?
    private var contextLabels: [String] = []
    private var wakeResume = WakeResumeState()
    private var sceneObservationKey: String?
    private var lastSceneObservationAttempt = Date.distantPast
    private var sceneObservationInFlight = false
    private var localCheckinTask: Task<Void, Never>?
    private var personPresenceNoticeTracker = PersonPresenceNoticeTracker()
    private var keepMacAwake = UserDefaults.standard.bool(forKey: AmbientPowerSettings.keepAwakePreferenceKey)
    private var sleepPreventionActivity: NSObjectProtocol?
    private var sleepPreventionState = SleepPreventionState()

    override init() {
        super.init()
        let generation = pairingGeneration.issue()
        isCheckingPairing = true
        Task { [weak self] in
            let readResult = await Keychain.read()
            guard let self, self.pairingGeneration.isCurrent(generation) else { return }
            if readResult.timedOut {
                self.isCheckingPairing = false
                self.status = "macOS Keychain did not respond. Pairing will remain available, but saved pairing could not be checked."
                return
            }
            let savedCookie = readResult.value
            guard let savedCookie else { self.isCheckingPairing = false; return }
            self.cookie = savedCookie
            await self.validatePairing(cookie: savedCookie, generation: generation)
        }
        let center = NSWorkspace.shared.notificationCenter
        center.addObserver(forName: NSWorkspace.willSleepNotification, object: nil, queue: .main) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in
                self.wakeResume.willSleep(wasActive: self.isActive)
                self.stop(preservingWakeResume: true)
            }
        }
        center.addObserver(forName: NSWorkspace.didWakeNotification, object: nil, queue: .main) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in
                if self.wakeResume.didWake(cameraReady: !self.cameraStopping) {
                    await self.start()
                }
            }
        }
    }

    private func validatePairing(cookie: String, generation: UInt64) async {
        defer {
            if pairingGeneration.isCurrent(generation) { isCheckingPairing = false }
        }
        guard let url = URL(string: "http://127.0.0.1:8790/api/status") else { return }
        var request = URLRequest(url: url)
        request.setValue(cookie, forHTTPHeaderField: "Cookie")
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            guard pairingGeneration.isCurrent(generation) else { return }
            let statusCode = (response as? HTTPURLResponse)?.statusCode
            switch PairingValidationDecision.classify(statusCode: statusCode) {
            case .verified:
                isPaired = true
                status = "Paired securely. Opted-in local reminders can run while this app is open; microphone and camera stay off until started."
                canRetrySavedPairing = false
                startLocalCheckins()
            case .expired:
                _ = await Keychain.delete()
                guard pairingGeneration.isCurrent(generation) else { return }
                self.cookie = nil; isPaired = false
                status = "Pair with the current AURA session code from its terminal."
                canRetrySavedPairing = false
            case .temporarilyUnavailable:
                isPaired = false
                canRetrySavedPairing = true
                status = "AURA could not verify the saved pairing. Your secure pairing is kept; start the web app and retry."
            }
        } catch {
            guard pairingGeneration.isCurrent(generation) else { return }
            isPaired = false
            canRetrySavedPairing = true
            status = "AURA did not respond while checking the saved pairing. Your secure pairing is kept; start the web app and retry."
        }
    }

    func retrySavedPairing() async {
        guard let cookie, canRetrySavedPairing, !isCheckingPairing, !isPairing else { return }
        let generation = pairingGeneration.issue()
        isCheckingPairing = true
        await validatePairing(cookie: cookie, generation: generation)
    }

    func pair() async {
        guard !isPairing else { return }
        let generation = pairingGeneration.issue()
        isPairing = true
        isCheckingPairing = false
        defer {
            if pairingGeneration.isCurrent(generation) { isPairing = false }
        }
        let candidate = code.trimmingCharacters(in: .whitespacesAndNewlines)
        guard candidate.count >= 24 else { status = "Enter the session code from the AURA terminal."; return }
        guard let url = URL(string: "http://127.0.0.1:8790/api/login") else { return }
        do {
            var request = URLRequest(url: url); request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("http://127.0.0.1:8790", forHTTPHeaderField: "Origin")
            request.httpBody = try JSONSerialization.data(withJSONObject: ["token": candidate])
            let (_, response) = try await URLSession.shared.data(for: request)
            guard pairingGeneration.isCurrent(generation) else { return }
            guard let http = response as? HTTPURLResponse, http.statusCode == 200,
                  let value = http.value(forHTTPHeaderField: "Set-Cookie")?.components(separatedBy: ";").first else {
                status = "Couldn’t pair. Check the current AURA session code and that the web app is running."; return
            }
            let saveResult = await Keychain.save(value)
            guard pairingGeneration.isCurrent(generation) else { return }
            guard saveResult.saved else {
                if saveResult.timedOut {
                    pendingSessionOnlyCookie = value
                    canUseSessionOnlyPairing = true
                }
                status = saveResult.timedOut
                    ? "macOS Keychain did not respond. AURA cannot confirm whether this pairing was saved. You can continue for this run; check Keychain Access before sharing this Mac."
                    : "Couldn’t save the secure AURA pairing in Keychain. Check macOS Keychain access and try again."
                return
            }
            cookie = value; isPaired = true; code = ""; canRetrySavedPairing = false
            canUseSessionOnlyPairing = false; pendingSessionOnlyCookie = nil
            status = "Paired securely. Opted-in local reminders can run while this app is open; microphone and camera stay off until started."
            startLocalCheckins()
        } catch {
            guard pairingGeneration.isCurrent(generation) else { return }
            status = "AURA is not reachable on this Mac yet."
        }
    }

    func useSessionOnlyPairing() {
        guard let value = pendingSessionOnlyCookie else { return }
        cookie = value; isPaired = true; code = ""
        canUseSessionOnlyPairing = false; pendingSessionOnlyCookie = nil
        status = "Paired in memory for this run. Keychain may still contain the token; use Clear pairing and verify it in Keychain Access."
        startLocalCheckins()
    }

    func start() async {
        guard isPaired, cookie != nil else { status = "Pair with the AURA web app first."; return }
        guard !microphoneStopping else { status = "The microphone is still stopping. Try again in a moment."; return }
        guard !cameraStopping else { status = "The camera is still stopping. Try again in a moment."; return }
        guard let generation = lifecycle.begin() else { return }
        isStarting = true
        status = "Checking microphone access…"
        startupTimeoutTask?.cancel()
        startupTimeoutTask = StartupWatchdog.schedule(afterNanoseconds: 60_000_000_000) { [weak self] in
            guard let self else { return }
            let timedOutStage = self.status
            _ = StartupWatchdog.expire(
                token: generation,
                lifecycle: self.lifecycle,
                isStarting: self.isStarting
            ) {
                self.stop()
                self.status = StartupWatchdog.timeoutMessage(for: timedOutStage)
            }
        }
        defer {
            if lifecycle.contains(generation) {
                startupTimeoutTask?.cancel()
                startupTimeoutTask = nil
                isStarting = false
                if !isActive { lifecycle.pause() }
            }
        }
        do {
            let mic = await requestCapturePermission(for: .audio)
            guard lifecycle.contains(generation) else { return }
            guard mic else { status = "Microphone access is off. Allow it in System Settings."; return }
            let onFinal: @Sendable (String) -> Void = { [weak self] text in
                Task { @MainActor in
                    guard let self, self.lifecycle.contains(generation) else { return }
                    self.status = "Speech recognized locally. Only direct requests or explicit support phrases get a reply."
                    self.handle(text)
                }
            }
#if compiler(>=6.4)
            if #available(macOS 27.0, *) {
                status = "Preparing private on-device English speech recognition…"
                self.transcriber = try await SpeechAnalyzerTranscriber.make(
                    onFinal: onFinal,
                    onStage: { [weak self] stage in
                        Task { @MainActor in
                            guard let self, self.lifecycle.contains(generation) else { return }
                            self.status = stage
                        }
                    }
                )
            } else {
                status = "Checking Speech Recognition permission…"
                let authorization = SFSpeechRecognizer.authorizationStatus()
                let authorized: Bool
                switch authorization {
                case .authorized:
                    authorized = true
                case .notDetermined:
                    authorized = await withCheckedContinuation { continuation in
                        SFSpeechRecognizer.requestAuthorization { continuation.resume(returning: $0 == .authorized) }
                    }
                case .denied, .restricted:
                    authorized = false
                @unknown default:
                    authorized = false
                }
                guard lifecycle.contains(generation) else { return }
                guard authorized else { status = "Allow Speech Recognition in System Settings to use local listening."; return }
                status = "Checking on-device English speech support…"
                guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US")), recognizer.isAvailable, recognizer.supportsOnDeviceRecognition else {
                    status = "On-device English speech recognition isn’t available on this Mac. AURA won’t send ambient audio to a server."; return
       …11128 tokens truncated…d with direct requests. Turn off camera context to exclude labels from requests, or turn off room perception to disable camera processing entirely."
        }
        if saveSceneSummaries {
            return "AURA checks speech and the room on this Mac. Scene summaries may be stored in local SQLite, but camera labels and person presence are excluded from direct requests. Turn off room perception to disable camera processing entirely."
        }
        return "AURA checks speech and the room on this Mac using on-device processing. Camera labels and person presence are excluded from direct requests, and periodic summaries are not sent to local Memory. Turn off room perception to disable camera processing entirely."
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if monitor.isPaired {
                Button(monitor.isStarting ? "Cancel startup" : monitor.isActive ? "Pause listening and camera" : "Start local ambient mode") { if monitor.isActive || monitor.isStarting { monitor.stop() } else { Task { await monitor.start() } } }.keyboardShortcut(.space, modifiers: []).disabled(monitor.cameraStopping || monitor.microphoneStopping)
            }
            ScrollView {
                VStack(alignment: .leading, spacing: 15) {
            HStack { Text("✳ AURA").font(.system(size: 22, weight: .medium)); Spacer(); Text(monitor.isActive ? "LIVE" : "PAUSED").font(.caption2).tracking(2).foregroundStyle(monitor.isActive ? .green : .secondary) }
            Text("Ambient companion").font(.headline)
            Text(ambientPrivacyDescription)
                .font(.system(size: 12)).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 8) { Label(monitor.microphoneStopping ? "Microphone stopping" : monitor.microphoneOn ? "Microphone on" : "Microphone off", systemImage: "mic.fill").foregroundStyle(monitor.microphoneOn || monitor.microphoneStopping ? .orange : .secondary); Label(monitor.cameraStopping ? "Camera stopping" : monitor.cameraOn ? "Camera on" : "Camera off", systemImage: "camera.fill").foregroundStyle(monitor.cameraOn || monitor.cameraStopping ? .orange : .secondary) }.font(.caption)
            Toggle("Enable room perception (camera)", isOn: $ambientCameraEnabled)
                .disabled(monitor.isActive || monitor.isStarting || monitor.cameraStopping)
            Text("Saved on this Mac. Turn it off before starting ambient mode to use the microphone only; no camera permission is requested and no scene or person summaries are created.")
                .font(.system(size: 10)).foregroundStyle(.tertiary).fixedSize(horizontal: false, vertical: true)
            Toggle("Save periodic scene summaries to Memory", isOn: $saveSceneSummaries)
                .disabled(!ambientCameraEnabled || monitor.isActive || monitor.isStarting || monitor.cameraStopping)
            Text("Off stops periodic summaries from being sent to AURA's memory service. Recent camera labels can still be included with direct requests; turn off room perception to disable camera context entirely.")
                .font(.system(size: 10)).foregroundStyle(.tertiary).fixedSize(horizontal: false, vertical: true)
            Toggle("Include camera context in replies", isOn: $useCameraContext)
                .disabled(!ambientCameraEnabled || monitor.isActive || monitor.isStarting || monitor.cameraStopping)
            Text("Off excludes recent labels and person presence from new direct requests. Camera processing and opted-in summary storage can continue; pause ambient mode before changing this setting.")
                .font(.system(size: 10)).foregroundStyle(.tertiary).fixedSize(horizontal: false, vertical: true)
            Toggle("Use private replies for this session", isOn: Binding(
                get: { monitor.privateRepliesEnabled },
                set: { monitor.setPrivateRepliesEnabled($0) }
            ))
            .disabled(!monitor.isActive)
            Text("New addressed phrases use no saved AURA memories, camera context, or saved chat history. They still go to your configured provider, which may retain requests under its policy. Pause clears this session-only choice; it cannot change requests already sent.")
                .font(.system(size: 10)).foregroundStyle(.tertiary).fixedSize(horizontal: false, vertical: true)
            Button("Stop speaking") { monitor.stopSpeaking() }
                .disabled(!monitor.isSpeaking)
            Group {
                Picker("Spoken voice", selection: $speechVoiceIdentifier) {
                    Text("English (US) default").tag("")
                    ForEach(englishVoices, id: \.identifier) { voice in
                        Text("\(voice.name) · \(voice.language)").tag(voice.identifier)
                    }
                }
                Slider(value: $speechRate, in: SpeechOutputSettings.rateRange) {
                    Text("Speech pace")
                }
                HStack {
                    Text("Slower")
                    Spacer()
                    Text("Speech pace")
                    Spacer()
                    Text("Faster")
                }.font(.caption2).foregroundStyle(.secondary)
            }
            Text("Voice and pace stay on this Mac and apply to AURA’s spoken replies and opted-in reminders.")
                .font(.system(size: 10)).foregroundStyle(.tertiary).fixedSize(horizontal: false, vertical: true)
            Toggle("Speak when a person enters view", isOn: $personPresenceNoticesEnabled)
                .disabled(!ambientCameraEnabled)
            Text("Off by default. AURA may also notice you; it cannot identify anyone or tell whether someone is a visitor. Detection stays on this Mac and only runs while ambient mode is on.")
                .font(.system(size: 10)).foregroundStyle(.tertiary).fixedSize(horizontal: false, vertical: true)
            Toggle("Keep Mac and display awake while listening", isOn: $keepMacAwake)
                .onChange(of: keepMacAwake) { enabled in monitor.setKeepMacAwake(enabled) }
            Text("Off by default. Prevents idle system and display sleep only during live ambient mode; Pause releases it. This does not change password or automatic-lock settings and may use more energy.")
                .font(.system(size: 10)).foregroundStyle(.tertiary).fixedSize(horizontal: false, vertical: true)
            if !monitor.isPaired {
                if monitor.canRetrySavedPairing {
                    Button(monitor.isCheckingPairing ? "Checking saved pairing…" : "Retry saved pairing") {
                        Task { await monitor.retrySavedPairing() }
                    }
                    .disabled(monitor.isCheckingPairing || monitor.isPairing)
                }
                SecureField("Session code from AURA terminal", text: $monitor.code)
                Button(monitor.isPairing ? "Pairing securely…" : "Pair with AURA") { Task { await monitor.pair() } }
                    .disabled(monitor.code.isEmpty || monitor.isPairing || monitor.isClearingPairing)
                if monitor.canUseSessionOnlyPairing {
                    Button("Continue for this run only") { monitor.useSessionOnlyPairing() }
                        .disabled(monitor.isPairing || monitor.isClearingPairing)
                }
            } else {
                Toggle("Allow solo follow-ups for this session", isOn: Binding(get: { monitor.followupsEnabled }, set: { monitor.setFollowups($0) }))
                    .disabled(!monitor.isActive)
                Picker("Follow-up window", selection: Binding(get: { monitor.followupDurationSeconds }, set: { monitor.setFollowupDuration($0) })) {
                    ForEach(ConversationTurnGate.supportedFollowupDurations, id: \.self) { seconds in
                        Text("\(seconds) seconds").tag(seconds)
                    }
                }
                .disabled(!monitor.isActive)
                Text("Only enable when everyone nearby agrees. After a direct reply, one phrase within this window is sent to your configured companion and saved in your conversation. AURA cannot identify the speaker. Pause, sleep or closing the window clears this choice.")
                    .font(.system(size: 10)).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                Text("Paired, opted-in reminders are checked every five minutes while AURA is running. They can speak while the microphone and camera are off; Pause controls capture.")
                    .font(.system(size: 11)).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                if !monitor.recentResponse.isEmpty { Divider(); Text("AURA").font(.caption).foregroundStyle(.secondary); Text(monitor.recentResponse).font(.system(size: 12)).textSelection(.enabled) }
                if !monitor.scene.isEmpty { Text("Local camera: \(monitor.scene)").font(.caption).foregroundStyle(.secondary) }
                Button("Clear pairing") { monitor.forgetPairing() }.font(.caption).foregroundStyle(.secondary)
            }
            Text(monitor.status).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            if ambientCameraEnabled && saveSceneSummaries && useCameraContext {
                Text("While ambient mode is live, AURA may send a short scene summary to local Memory when the view changes (at most once a minute). Photos and audio are not saved.")
                    .font(.system(size: 10)).foregroundStyle(.tertiary).fixedSize(horizontal: false, vertical: true)
            } else if ambientCameraEnabled && saveSceneSummaries {
                Text("Periodic summaries may be saved to local Memory; camera context is excluded from direct replies. Photos and audio are not saved.")
                    .font(.system(size: 10)).foregroundStyle(.tertiary).fixedSize(horizontal: false, vertical: true)
            } else if ambientCameraEnabled && useCameraContext {
                Text("Camera labels may be included in direct replies, but periodic scene summaries are not sent to local Memory. Photos and audio are not saved.")
                    .font(.system(size: 10)).foregroundStyle(.tertiary).fixedSize(horizontal: false, vertical: true)
            } else if ambientCameraEnabled {
                Text("Camera context is excluded from direct replies, and periodic summaries are not sent to local Memory. Photos and audio are not saved.")
                    .font(.system(size: 10)).foregroundStyle(.tertiary).fixedSize(horizontal: false, vertical: true)
            }
            if monitor.permissionSettingsURL != nil {
                Button("Open Privacy Settings") { monitor.openPermissionSettings() }
                    .buttonStyle(.bordered)
            }
            Divider(); Text("Closing this window or pressing Pause stops local listening and camera capture.").font(.system(size: 10)).foregroundStyle(.tertiary)
                }.padding(12)
            }
        }.padding(12).frame(width: 386, height: 530)
    }
}

private enum Keychain {
    private static let account = "aura-companion-cookie"
    private static let timeout: TimeInterval = 8

    static func read() async -> (value: String?, timedOut: Bool) {
        await withCheckedContinuation { continuation in
            let gate = KeychainCompletionGate<(value: String?, timedOut: Bool)>()
            // Security.framework can stall inside SecItemCopyMatching on a damaged
            // or unavailable keychain. Keep each call independent so one blocked
            // request cannot starve later save or clear attempts.
            DispatchQueue.global(qos: .utility).async {
                guard !gate.isCompleted else { return }
                var result: CFTypeRef?
                let status = SecItemCopyMatching([kSecClass: kSecClassGenericPassword, kSecAttrService: "AURA Companion", kSecAttrAccount: account, kSecReturnData: true] as CFDictionary, &result)
                let value = status == errSecSuccess ? (result as? Data).flatMap { String(data: $0, encoding: .utf8) } : nil
                gate.resolve((value, false), continuation)
            }
            DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + timeout) {
                gate.resolve((nil, true), continuation)
            }
        }
    }

    static func save(_ value: String) async -> (saved: Bool, timedOut: Bool) {
        await withCheckedContinuation { continuation in
            let gate = KeychainCompletionGate<(saved: Bool, timedOut: Bool)>()
            DispatchQueue.global(qos: .utility).async {
                guard !gate.isCompleted else { return }
                let identity: [String: Any] = [
                    kSecClass as String: kSecClassGenericPassword,
                    kSecAttrService as String: "AURA Companion",
                    kSecAttrAccount as String: account
                ]
                let attributes: [String: Any] = [
                    kSecValueData as String: Data(value.utf8),
                    kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
                ]
                var item = identity
                attributes.forEach { item[$0.key] = $0.value }
                let saved = KeychainPersistence.save(
                    update: { SecItemUpdate(identity as CFDictionary, attributes as CFDictionary) },
                    add: { SecItemAdd(item as CFDictionary, nil) }
                )
                gate.resolve((saved, false), continuation)
            }
            DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + timeout) {
                gate.resolve((false, true), continuation)
            }
        }
    }

    static func delete() async -> Bool {
        await withCheckedContinuation { continuation in
            let gate = KeychainCompletionGate<Bool>()
            DispatchQueue.global(qos: .utility).async {
                guard !gate.isCompleted else { return }
                let status = SecItemDelete([kSecClass: kSecClassGenericPassword, kSecAttrService: "AURA Companion", kSecAttrAccount: account] as CFDictionary)
                gate.resolve(status == errSecSuccess || status == errSecItemNotFound, continuation)
            }
            DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + timeout) {
                gate.resolve(false, continuation)
            }
        }
    }
}

private final class KeychainCompletionGate<Value>: @unchecked Sendable {
    private let lock = NSLock()
    private var completed = false

    var isCompleted: Bool {
        lock.lock()
        defer { lock.unlock() }
        return completed
    }

    func resolve(_ value: Value, _ continuation: CheckedContinuation<Value, Never>) {
        lock.lock()
        guard !completed else { lock.unlock(); return }
        completed = true
        lock.unlock()
        continuation.resume(returning: value)
    }
}
