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
                self.transcriber = try await SpeechAnalyzerTranscriber.make(onFinal: onFinal)
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
                }
                self.transcriber = LegacySpeechPipeline(recognizer: recognizer, onFinal: onFinal)
            }
#else
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
            }
            self.transcriber = LegacySpeechPipeline(recognizer: recognizer, onFinal: onFinal)
#endif
            guard lifecycle.contains(generation) else { self.transcriber?.stop(); self.transcriber = nil; return }
            status = "Checking camera access…"
            let cameraAllowed = await requestCapturePermission(for: .video)
            guard lifecycle.contains(generation) else { return }
            guard cameraAllowed else {
                self.transcriber?.stop(); self.transcriber = nil
                status = "Camera access is off. Allow it in System Settings."; return
            }
            let camera = LocalCamera(
                onScene: { [weak self] labels, confidence, present in
                    Task { @MainActor in
                        guard let self, self.lifecycle.acceptsCaptureEvent(generation) else { return }
                        self.contextLabels = labels; self.scene = labels.joined(separator: ", ")
                        self.isPersonPresent = present
                        self.saveSceneSummaryIfNeeded(
                            labels: labels,
                            confidence: confidence,
                            humanPresent: present,
                            generation: generation
                        )
                    }
                },
                onFailure: { [weak self] message in
                    Task { @MainActor in
                        guard let self, self.lifecycle.acceptsCaptureEvent(generation) else { return }
                        self.stop()
                        self.status = message
                    }
                }
            )
            self.camera = camera
            status = "Starting local camera classification…"
            try await camera.start()
            guard lifecycle.contains(generation) else { camera.stop(); return }
            status = "Starting local microphone recognition…"
            try await audioCapture.start(transcriber: transcriber)
            guard lifecycle.contains(generation) else { audioCapture.stop(); return }
            guard lifecycle.activate(generation) else { return }
            observeAudioConfigurationChange(generation: generation)
            isActive = true; microphoneOn = true; microphoneStopping = false; cameraOn = true; cameraStopping = false
            status = "Listening locally. Direct replies are phrase-triggered; scheduled check-ins stay off until enabled in Setup."
        } catch {
            guard lifecycle.contains(generation) else { return }
            stop(); status = "Couldn’t start the local microphone and camera: \(error.localizedDescription)"
        }
    }

    private func requestCapturePermission(for mediaType: AVMediaType) async -> Bool {
        if mediaType == .audio, #available(macOS 14.0, *) {
            switch AVAudioApplication.shared.recordPermission {
            case .granted:
                return true
            case .undetermined:
                status = "Waiting for macOS microphone permission…"
                return await AVAudioApplication.requestRecordPermission()
            case .denied:
                return false
            @unknown default:
                return false
            }
        }
        switch AVCaptureDevice.authorizationStatus(for: mediaType) {
        case .authorized:
            return true
        case .notDetermined:
            status = mediaType == .video
                ? "Waiting for macOS camera permission…"
                : "Waiting for macOS microphone permission…"
            return await AVCaptureDevice.requestAccess(for: mediaType)
        case .denied, .restricted:
            return false
        @unknown default:
            return false
        }
    }

    private func observeAudioConfigurationChange(generation: UInt64) {
        audioConfigurationObserver = audioCapture.observeConfigurationChanges { [weak self] in
            Task { @MainActor in
                guard let self, self.lifecycle.acceptsCaptureEvent(generation) else { return }
                self.stop()
                self.status = "The Mac audio configuration changed. AURA paused ambient mode; check connected audio devices, then start it again."
            }
        }
    }

    private func saveSceneSummaryIfNeeded(
        labels: [String],
        confidence: Float,
        humanPresent: Bool,
        generation: UInt64
    ) {
        guard lifecycle.acceptsCaptureEvent(generation), !sceneObservationInFlight,
              let cookie, (!labels.isEmpty || humanPresent) else { return }
        let key = labels.joined(separator: "|") + "|human=\(humanPresent)"
        let now = Date()
        guard key != sceneObservationKey,
              now.timeIntervalSince(lastSceneObservationAttempt) >= 60 else { return }

        sceneObservationKey = key
        lastSceneObservationAttempt = now
        sceneObservationInFlight = true
        Task { [weak self] in
            guard let self,
                  self.lifecycle.acceptsCaptureEvent(generation),
                  let url = URL(string: "http://127.0.0.1:8790/api/ambient/observation") else {
                self?.sceneObservationInFlight = false
                return
            }
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("http://127.0.0.1:8790", forHTTPHeaderField: "Origin")
            request.setValue(cookie, forHTTPHeaderField: "Cookie")
            request.httpBody = try? JSONSerialization.data(withJSONObject: [
                "labels": Array(labels.prefix(4)),
                "human_present": humanPresent,
                "confidence": min(1.0, max(0.0, Double(confidence))),
            ])
            request.timeoutInterval = 5
            do {
                let (_, response) = try await URLSession.shared.data(for: request)
                await MainActor.run {
                    self.sceneObservationInFlight = false
                    if (response as? HTTPURLResponse)?.statusCode != 200 {
                        self.sceneObservationKey = nil
                    }
                }
            } catch {
                await MainActor.run {
                    self.sceneObservationInFlight = false
                    self.sceneObservationKey = nil
                }
            }
        }
    }

    private func startLocalCheckins() {
        guard isPaired, localCheckinTask == nil else { return }
        let generation = pairingGeneration.value
        localCheckinTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled, self.isPaired,
                  self.pairingGeneration.isCurrent(generation) {
                await self.checkForDueCheckin(pairingGeneration: generation)
                do {
                    try await Task.sleep(nanoseconds: 300_000_000_000)
                } catch {
                    break
                }
            }
            if self.pairingGeneration.isCurrent(generation) {
                self.localCheckinTask = nil
            }
        }
    }

    private func checkForDueCheckin(pairingGeneration generation: UInt64) async {
        guard isPaired, pairingGeneration.isCurrent(generation), !Task.isCancelled,
              replyTask == nil, !synthesizer.isSpeaking,
              let cookie,
              let url = URL(string: "http://127.0.0.1:8790/api/checkin") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("http://127.0.0.1:8790", forHTTPHeaderField: "Origin")
        request.setValue(cookie, forHTTPHeaderField: "Cookie")
        request.httpBody = Data("{}".utf8)
        request.timeoutInterval = 5
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard isPaired, pairingGeneration.isCurrent(generation), !Task.isCancelled,
                  let httpResponse = response as? HTTPURLResponse else { return }
            if httpResponse.statusCode == 401 {
                forgetPairing()
                status = "AURA restarted. Pair with the current session code."
                return
            }
            guard httpResponse.statusCode == 200 else { return }
            let checkin = try JSONDecoder().decode(CheckinResponse.self, from: data)
            guard checkin.due, let message = checkin.response, !message.isEmpty,
                  replyTask == nil, !synthesizer.isSpeaking else { return }
            speakLocalCheckin(message)
        } catch {
            // Local check-ins are optional; transient service errors do not affect capture.
        }
    }

    private func speakLocalCheckin(_ text: String) {
        guard !text.isEmpty, !synthesizer.isSpeaking else { return }
        if isActive {
            speakLocally(text, generation: lifecycle.generation)
            return
        }
        recentResponse = text
        status = "AURA is speaking an opted-in check-in or reminder. Microphone and camera are off."
        synthesizer.speak(SpeechOutputSettings.utterance(text))
        let generation = pairingGeneration.value
        Task { [weak self] in
            guard let self else { return }
            while self.synthesizer.isSpeaking,
                  self.pairingGeneration.isCurrent(generation) {
                try? await Task.sleep(nanoseconds: 100_000_000)
            }
            guard self.pairingGeneration.isCurrent(generation), !self.isActive else { return }
            self.status = "Paired. Opted-in reminders are active; microphone and camera are off."
        }
    }

    private func handle(_ transcript: String) {
        guard isActive, replyTask == nil, !synthesizer.isSpeaking else { return }
        let text = transcript.trimmingCharacters(in: .whitespacesAndNewlines)
        guard shouldRespond(text) else { return }
        status = "AURA heard a direct request. Preparing a reply."
        let generation = lifecycle.generation
        replyTask = Task { [weak self] in
            guard let self else { return }
            await self.sendToCompanion(text, generation: generation)
            if self.lifecycle.contains(generation) { self.replyTask = nil }
        }
    }

    private func shouldRespond(_ text: String) -> Bool {
        let s = text.lowercased()
        let addressed = s.range(of: #"\b(hey\s+)?aura\b"#, options: .regularExpression) != nil
        let support = ["i need help", "i need support", "i feel overwhelmed", "i'm overwhelmed", "im overwhelmed", "i feel panicked", "i'm panicking", "im panicking", "i feel unsafe", "i'm scared", "im scared"]
            .contains { s.contains($0) }
        let direct = ["can you help", "what do you think", "are you there", "talk to me", "please listen"]
            .contains { s.contains($0) }
        return addressed || support || direct
    }

    private func sendToCompanion(_ transcript: String, generation: UInt64) async {
        guard lifecycle.contains(generation), !Task.isCancelled else { return }
        guard let cookie, let url = URL(string: "http://127.0.0.1:8790/api/ambient") else { return }
        let label = contextLabels.prefix(5).joined(separator: ", ")
        let observation = label.isEmpty ? "" : "Local camera context: \(label). Person present: \(isPersonPresent ? "yes" : "no")."
        do {
            var request = URLRequest(url: url); request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("http://127.0.0.1:8790", forHTTPHeaderField: "Origin")
            request.setValue(cookie, forHTTPHeaderField: "Cookie")
            request.httpBody = try JSONSerialization.data(withJSONObject: ["message": transcript, "observation": observation])
            request.timeoutInterval = 45
            let (data, httpResponse) = try await URLSession.shared.data(for: request)
            guard lifecycle.contains(generation), !Task.isCancelled else { return }
            guard let http = httpResponse as? HTTPURLResponse, http.statusCode == 200 else {
                if (httpResponse as? HTTPURLResponse)?.statusCode == 401 {
                    forgetPairing(); status = "AURA restarted. Pair with the current session code."
                } else { status = "AURA could not complete this request. Check the conversation before retrying." }
                return
            }
            let response = try JSONDecoder().decode(CompanionResponse.self, from: data)
            await MainActor.run { speakLocally(response.response, generation: generation) }
        } catch {
            guard lifecycle.contains(generation), !Task.isCancelled else { return }
            status = "AURA’s reply was interrupted. Check the conversation before retrying; it may already be saved."
        }
    }

    private func speakLocally(_ text: String, generation: UInt64) {
        guard lifecycle.acceptsCaptureEvent(generation), isActive,
              !text.isEmpty, !synthesizer.isSpeaking else { return }
        recentResponse = text
        let utterance = SpeechOutputSettings.utterance(text)
        let outputGeneration = speechOutputSuppression.begin()
        let sessionGeneration = lifecycle.generation
        transcriber?.setOutputSuppressed(true)
        status = "AURA is speaking locally. Microphone transcription pauses during playback."
        synthesizer.speak(utterance)
        Task { [weak self] in
            guard let self else { return }
            while speechOutputSuppression.contains(outputGeneration), synthesizer.isSpeaking {
                try? await Task.sleep(nanoseconds: 100_000_000)
            }
            guard speechOutputSuppression.contains(outputGeneration) else { return }
            try? await Task.sleep(nanoseconds: 800_000_000)
            guard speechOutputSuppression.finish(outputGeneration) else { return }
            transcriber?.setOutputSuppressed(false)
            guard lifecycle.contains(sessionGeneration) else { return }
            status = "AURA finished speaking. Listening locally."
        }
    }

    func stop(preservingWakeResume: Bool = false) {
        startupTimeoutTask?.cancel()
        startupTimeoutTask = nil
        speechOutputSuppression.cancel()
        if !cameraStopping { lifecycle.pause() }
        let stoppedGeneration = lifecycle.generation
        if !preservingWakeResume { wakeResume.cancel() }
        microphoneStopping = microphoneOn || microphoneStopping
        isStarting = false; isActive = false; microphoneOn = false; cameraOn = false
        replyTask?.cancel(); replyTask = nil
        if let audioConfigurationObserver {
            NotificationCenter.default.removeObserver(audioConfigurationObserver)
            self.audioConfigurationObserver = nil
        }
        audioCapture.stop { [weak self] in
            Task { @MainActor in
                guard let self, self.lifecycle.canCompleteStop(stoppedGeneration) else { return }
                self.microphoneStopping = false
                self.refreshPausedStatus()
            }
        }
        transcriber?.stop(); transcriber = nil
        let cameraToStop = camera
        camera = nil
        cameraStopping = cameraToStop != nil || cameraStopping
        contextLabels = []; scene = ""; isPersonPresent = false
        synthesizer.stopSpeaking(at: .immediate)
        status = cameraStopping
            ? microphoneStopping ? "Paused. Microphone and camera are stopping."
                : "Paused. Microphone is off; camera is stopping."
            : microphoneStopping ? "Paused. Microphone is stopping; camera is off."
                : "Paused. Microphone and camera are off."
        cameraToStop?.stop { [weak self] in
            Task { @MainActor in
                guard let self, self.lifecycle.canCompleteStop(stoppedGeneration) else { return }
                self.cameraOn = false
                self.cameraStopping = false
                self.refreshPausedStatus()
                if self.wakeResume.cameraStopped() {
                    Task { await self.start() }
                }
            }
        }
    }

    private func refreshPausedStatus() {
        guard status.hasPrefix("Paused. Microphone") else { return }
        switch (microphoneStopping, cameraStopping) {
        case (true, true): status = "Paused. Microphone and camera are stopping."
        case (true, false): status = "Paused. Microphone is stopping; camera is off."
        case (false, true): status = "Paused. Microphone is off; camera is stopping."
        case (false, false): status = "Paused. Microphone and camera are off."
        }
    }

    func forgetPairing() {
        _ = pairingGeneration.issue()
        localCheckinTask?.cancel(); localCheckinTask = nil
        isPairing = false; isCheckingPairing = false; canRetrySavedPairing = false
        canUseSessionOnlyPairing = false; pendingSessionOnlyCookie = nil
        isClearingPairing = true
        stop(); cookie = nil; isPaired = false; status = "Clearing saved pairing…"
        Task { [weak self] in
            let removed = await Keychain.delete()
            guard let self else { return }
            self.isClearingPairing = false
            self.status = removed
                ? "Session pairing cleared."
                : "AURA could not confirm removal from Keychain. Remove AURA Companion from Keychain Access before pairing again."
        }
    }

    func terminate() {
        _ = pairingGeneration.issue()
        localCheckinTask?.cancel(); localCheckinTask = nil
        stop()
    }

    var permissionSettingsURL: URL? {
        guard let target = PermissionSettings.target(for: status) else { return nil }
        return URL(string: "x-apple.systempreferences:com.apple.preference.security?\(target)")
    }

    func openPermissionSettings() {
        let permissionStatus = status
        guard let url = permissionSettingsURL else { return }
        if !NSWorkspace.shared.open(url),
           let fallback = PermissionSettings.fallbackMessage(for: permissionStatus) {
            status = fallback
        }
    }
}

// All camera configuration, start/stop and frames belong to one serial queue.
// A new instance per ambient session prevents old callbacks stopping a new camera.
private final class LocalCamera: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate, @unchecked Sendable {
    private let queue = DispatchQueue(label: "aura.ambient.capture")
    private let session = AVCaptureSession()
    private let output = AVCaptureVideoDataOutput()
    private var lastVisionTime = Date.distantPast
    private var stopped = false
    private let onScene: @Sendable ([String], Float, Bool) -> Void
    private let onFailure: @Sendable (String) -> Void
    private var failureObservers: [NSObjectProtocol] = []

    init(
        onScene: @escaping @Sendable ([String], Float, Bool) -> Void,
        onFailure: @escaping @Sendable (String) -> Void
    ) {
        self.onScene = onScene
        self.onFailure = onFailure
    }

    func start() async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            queue.async {
                do {
                    guard !self.stopped else { throw CancellationError() }
                    try self.configure()
                    self.observeSessionFailures()
                    self.session.startRunning()
                    guard self.session.isRunning else { throw CaptureError.startFailed }
                    continuation.resume()
                } catch { continuation.resume(throwing: error) }
            }
        }
    }

    private func configure() throws {
        session.beginConfiguration()
        defer { session.commitConfiguration() }
        session.sessionPreset = .low
        guard let device = AVCaptureDevice.default(for: .video) else { throw CaptureError.noCamera }
        let input = try AVCaptureDeviceInput(device: device)
        guard session.canAddInput(input) else { throw CaptureError.inputConfiguration }
        session.addInput(input)
        output.alwaysDiscardsLateVideoFrames = true
        output.setSampleBufferDelegate(self, queue: queue)
        guard session.canAddOutput(output) else { throw CaptureError.outputConfiguration }
        session.addOutput(output)
    }

    private func observeSessionFailures() {
        let center = NotificationCenter.default
        let interrupted = center.addObserver(
            forName: .AVCaptureSessionWasInterrupted,
            object: session,
            queue: nil
        ) { [weak self] _ in
            self?.reportFailure("macOS interrupted AURA’s camera. Ambient mode paused; close other camera apps, then start it again.")
        }
        let runtimeError = center.addObserver(
            forName: .AVCaptureSessionRuntimeError,
            object: session,
            queue: nil
        ) { [weak self] notification in
            let detail = (notification.userInfo?[AVCaptureSessionErrorKey] as? Error)?.localizedDescription
            let message = detail.map { "AURA’s camera stopped: \($0). Ambient mode paused; check camera access, then start it again." }
                ?? "AURA’s camera stopped unexpectedly. Ambient mode paused; check camera access, then start it again."
            self?.reportFailure(message)
        }
        failureObservers = [interrupted, runtimeError]
    }

    private func reportFailure(_ message: String) {
        queue.async { [weak self] in
            guard let self, !self.stopped else { return }
            self.onFailure(message)
        }
    }

    func stop(completion: @escaping @Sendable () -> Void = {}) {
        queue.async {
            guard !self.stopped else { completion(); return }
            self.stopped = true
            self.failureObservers.forEach(NotificationCenter.default.removeObserver)
            self.failureObservers.removeAll()
            self.output.setSampleBufferDelegate(nil, queue: nil)
            if self.session.isRunning { self.session.stopRunning() }
            completion()
        }
    }

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        guard !stopped else { return }
        let now = Date()
        guard now.timeIntervalSince(lastVisionTime) >= 1, let image = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        lastVisionTime = now
        let request = VNClassifyImageRequest()
        let humans = VNDetectHumanRectanglesRequest()
        do {
            try VNImageRequestHandler(cvPixelBuffer: image).perform([request, humans])
            let results = request.results.map { Array($0.prefix(4)) } ?? []
            onScene(
                results.map { $0.identifier },
                results.first?.confidence ?? 0,
                !(humans.results?.isEmpty ?? true)
            )
        } catch { }
    }
}

private struct CompanionResponse: Decodable { let response: String }
private struct CheckinResponse: Decodable { let due: Bool; let response: String? }
private enum CaptureError: LocalizedError {
    case noCamera, noMicrophone, inputConfiguration, outputConfiguration, startFailed
    var errorDescription: String? { switch self { case .startFailed: "The camera session did not start. Check camera access and other camera apps."; case .noCamera: "No camera was found."; case .noMicrophone: "No microphone was found."; case .inputConfiguration: "macOS could not add the camera input. Check camera access and close apps using the camera."; case .outputConfiguration: "macOS could not add the local video classifier." } }
}

// Keep AVAudioEngine setup, start, tap removal, and stop off the main actor.
// Device reconfiguration can stall audio startup; the UI and its watchdog must
// remain responsive so Pause can invalidate that startup generation safely.
private final class LocalAudioCapture: @unchecked Sendable {
    private let queue = DispatchQueue(label: "aura.ambient.audio")
    private let engine = AVAudioEngine()
    private var hasTap = false

    func start(transcriber: (any AmbientTranscriber)?) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            queue.async {
                do {
                    let input = self.engine.inputNode
                    let format = input.outputFormat(forBus: 0)
                    guard format.channelCount > 0 else { throw CaptureError.noMicrophone }
                    guard !self.hasTap else { throw CaptureError.startFailed }
                    input.installTap(onBus: 0, bufferSize: 2048, format: format) { buffer, time in
                        transcriber?.consume(buffer, at: time)
                    }
                    self.hasTap = true
                    self.engine.prepare()
                    try self.engine.start()
                    continuation.resume()
                } catch {
                    if self.hasTap {
                        self.engine.inputNode.removeTap(onBus: 0)
                        self.hasTap = false
                    }
                    self.engine.stop()
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    func stop(completion: @escaping @Sendable () -> Void = {}) {
        queue.async {
            if self.hasTap {
                self.engine.inputNode.removeTap(onBus: 0)
                self.hasTap = false
            }
            self.engine.stop()
            completion()
        }
    }

    func observeConfigurationChanges(_ action: @escaping @Sendable () -> Void) -> NSObjectProtocol {
        NotificationCenter.default.addObserver(
            forName: .AVAudioEngineConfigurationChange,
            object: engine,
            queue: nil
        ) { _ in action() }
    }
}

private protocol AmbientTranscriber: AnyObject, Sendable {
    func consume(_ buffer: AVAudioPCMBuffer, at time: AVAudioTime)
    func stop()
    func setOutputSuppressed(_ suppressed: Bool)
}

// Compatibility path for older macOS releases. Recognition is explicitly
// restricted to on-device models; it never falls back to Apple server capture.
private final class LegacySpeechPipeline: AmbientTranscriber, @unchecked Sendable {
    private let queue = DispatchQueue(label: "aura.local.speech")
    private let recognizer: SFSpeechRecognizer
    private let onFinal: @Sendable (String) -> Void
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var inSpeech = false
    private var quietBuffers = 0
    private var stopped = false
    private var outputSuppressed = false
    private var requestGeneration = RecognitionGeneration()

    init(recognizer: SFSpeechRecognizer, onFinal: @escaping @Sendable (String) -> Void) {
        self.recognizer = recognizer
        self.onFinal = onFinal
    }

    func consume(_ buffer: AVAudioPCMBuffer, at time: AVAudioTime) {
        // The audio engine owns and may reuse tap buffers as soon as this call
        // returns. Keep an owned copy before handing the data to our queue.
        guard let source = buffer.floatChannelData,
              let owned = AVAudioPCMBuffer(pcmFormat: buffer.format, frameCapacity: buffer.frameLength),
              let destination = owned.floatChannelData else { return }
        let channels = Int(buffer.format.channelCount)
        let frames = Int(buffer.frameLength)
        guard channels > 0, frames > 0 else { return }
        owned.frameLength = buffer.frameLength
        for channel in 0..<channels {
            destination[channel].update(from: source[channel], count: frames)
        }
        queue.async { [weak self] in
            guard let self, !self.stopped, !self.outputSuppressed,
                  let channel = owned.floatChannelData?[0] else { return }
            let count = Int(owned.frameLength)
            guard count > 0 else { return }
            let step = max(1, count / 512)
            var squares: Float = 0
            var samples = 0
            for i in stride(from: 0, to: count, by: step) { squares += channel[i] * channel[i]; samples += 1 }
            let speaking = sqrt(squares / Float(max(1, samples))) > 0.018
            if speaking {
                self.quietBuffers = 0
                if self.request == nil { self.beginRequest() }
                self.inSpeech = true
                self.request?.append(owned)
            } else if self.inSpeech {
                self.quietBuffers += 1
                self.request?.append(owned)
                if self.quietBuffers >= 9 {
                    self.inSpeech = false
                    self.quietBuffers = 0
                    self.request?.endAudio()
                    self.request = nil
                    self.task = nil
                }
            }
        }
    }

    private func beginRequest() {
        let generation = requestGeneration.issue()
        let current = SFSpeechAudioBufferRecognitionRequest()
        current.shouldReportPartialResults = true
        current.requiresOnDeviceRecognition = true
        request = current
        task = recognizer.recognitionTask(with: current) { [weak self] result, error in
            guard let self else { return }
            if let result, result.isFinal {
                let text = result.bestTranscription.formattedString
                self.queue.async {
                    guard !self.stopped, !self.outputSuppressed,
                          self.requestGeneration.isCurrent(generation) else { return }
                    self.onFinal(text)
                }
            }
            if error != nil {
                self.queue.async {
                    guard self.requestGeneration.isCurrent(generation) else { return }
                    self.requestGeneration.invalidate()
                    self.request = nil; self.task = nil; self.inSpeech = false; self.quietBuffers = 0
                }
            }
        }
    }

    func stop() {
        queue.async {
            self.stopped = true
            self.requestGeneration.invalidate()
            self.request?.endAudio()
            self.task?.cancel()
            self.request = nil
            self.task = nil
        }
    }

    func setOutputSuppressed(_ suppressed: Bool) {
        queue.async {
            guard self.outputSuppressed != suppressed, !self.stopped else { return }
            self.outputSuppressed = suppressed
            guard suppressed else { return }
            self.requestGeneration.invalidate()
            self.request?.endAudio()
            self.task?.cancel()
            self.request = nil; self.task = nil
            self.inSpeech = false; self.quietBuffers = 0
        }
    }
}

#if compiler(>=6.4)
@available(macOS 27.0, *)
private final class SpeechAnalyzerTranscriber: AmbientTranscriber, @unchecked Sendable {
    private static let maximumBufferedInputs = 128
    private let queue = DispatchQueue(label: "aura.local.speech-analyzer")
    private let analyzer: SpeechAnalyzer
    private let module: SpeechTranscriber
    private let converter: AnalyzerInputConverter
    private let inputContinuation: AsyncStream<AnalyzerInput>.Continuation
    private let onFinal: @Sendable (String) -> Void
    private var resultTask: Task<Void, Never>?
    private var stopped = false
    private var outputSuppressed = false

    private init(
        analyzer: SpeechAnalyzer,
        module: SpeechTranscriber,
        converter: AnalyzerInputConverter,
        inputContinuation: AsyncStream<AnalyzerInput>.Continuation,
        onFinal: @escaping @Sendable (String) -> Void
    ) {
        self.analyzer = analyzer
        self.module = module
        self.converter = converter
        self.inputContinuation = inputContinuation
        self.onFinal = onFinal
    }

    static func make(onFinal: @escaping @Sendable (String) -> Void) async throws -> SpeechAnalyzerTranscriber {
        guard SpeechTranscriber.isAvailable,
              let locale = await SpeechTranscriber.supportedLocale(equivalentTo: Locale(identifier: "en-US")) else {
            throw SpeechPipelineError.onDeviceEnglishUnavailable
        }
        let module = SpeechTranscriber(locale: locale, preset: .progressiveTranscription)
        if let request = try await AssetInventory.assetInstallationRequest(supporting: [module]) {
            try await request.downloadAndInstall()
        }
        guard let format = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [module]) else {
            throw SpeechPipelineError.onDeviceEnglishUnavailable
        }
        let converter = AnalyzerInputConverter(analyzerFormat: format)
        let analyzer = SpeechAnalyzer(modules: [module])
        let (inputSequence, inputContinuation) = AsyncStream<AnalyzerInput>.makeStream(
            of: AnalyzerInput.self,
            bufferingPolicy: .bufferingNewest(maximumBufferedInputs)
        )
        try await analyzer.start(inputSequence: inputSequence)
        let pipeline = SpeechAnalyzerTranscriber(
            analyzer: analyzer,
            module: module,
            converter: converter,
            inputContinuation: inputContinuation,
            onFinal: onFinal
        )
        pipeline.startResults()
        return pipeline
    }

    private func startResults() {
        resultTask = Task { [weak self, module] in
            do {
                for try await result in module.results {
                    guard result.isFinal else { continue }
                    let text = String(result.text.characters).trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !text.isEmpty else { continue }
                    self?.deliver(text)
                }
            } catch is CancellationError {
                return
            } catch {
                // Do not expose framework diagnostics or audio-related details in UI/logs.
            }
        }
    }

    private func deliver(_ text: String) {
        queue.async { [weak self] in
            guard let self, !self.stopped, !self.outputSuppressed else { return }
            self.onFinal(text)
        }
    }

    func consume(_ buffer: AVAudioPCMBuffer, at time: AVAudioTime) {
        guard let source = buffer.floatChannelData,
              let owned = AVAudioPCMBuffer(pcmFormat: buffer.format, frameCapacity: buffer.frameLength),
              let destination = owned.floatChannelData else { return }
        let channels = Int(buffer.format.channelCount)
        let frames = Int(buffer.frameLength)
        guard channels > 0, frames > 0 else { return }
        owned.frameLength = buffer.frameLength
        for channel in 0..<channels {
            destination[channel].update(from: source[channel], count: frames)
        }
        queue.async { [weak self] in
            guard let self, !self.stopped, !self.outputSuppressed else { return }
            do {
                for input in try self.converter.convert(owned, at: time) {
                    self.inputContinuation.yield(input)
                }
            } catch {
                // A later valid audio buffer may restore conversion; never forward raw audio.
            }
        }
    }

    func stop() {
        queue.async {
            guard !self.stopped else { return }
            self.stopped = true
            self.inputContinuation.finish()
            self.resultTask?.cancel()
            self.resultTask = nil
            Task { await self.analyzer.cancelAndFinishNow() }
        }
    }

    func setOutputSuppressed(_ suppressed: Bool) {
        queue.async {
            guard !self.stopped else { return }
            self.outputSuppressed = suppressed
        }
    }
}

private enum SpeechPipelineError: LocalizedError {
    case onDeviceEnglishUnavailable

    var errorDescription: String? {
        switch self {
        case .onDeviceEnglishUnavailable:
            "Private on-device English speech recognition is unavailable on this Mac."
        }
    }
}
#endif

private struct MenuView: View {
    @ObservedObject var monitor: AmbientMonitor
    @AppStorage(SpeechOutputSettings.voicePreferenceKey) private var speechVoiceIdentifier = ""
    @AppStorage(SpeechOutputSettings.ratePreferenceKey) private var speechRate = 0.48

    private var englishVoices: [AVSpeechSynthesisVoice] {
        AVSpeechSynthesisVoice.speechVoices()
            .filter { $0.language.lowercased().hasPrefix("en") }
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            HStack { Text("✳ AURA").font(.system(size: 22, weight: .medium)); Spacer(); Text(monitor.isActive ? "LIVE" : "PAUSED").font(.caption2).tracking(2).foregroundStyle(monitor.isActive ? .green : .secondary) }
            Text("Ambient companion").font(.headline)
            Text("AURA checks speech and the room on this Mac. Speech recognition uses supported on-device models only; raw audio and frames are never saved or sent. While ambient mode is on, changed scene summaries may be stored in local SQLite. Only direct requests and explicit support phrases reach your AURA companion.").font(.system(size: 12)).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 8) { Label(monitor.microphoneStopping ? "Microphone stopping" : monitor.microphoneOn ? "Microphone on" : "Microphone off", systemImage: "mic.fill").foregroundStyle(monitor.microphoneOn || monitor.microphoneStopping ? .orange : .secondary); Label(monitor.cameraStopping ? "Camera stopping" : monitor.cameraOn ? "Camera on" : "Camera off", systemImage: "camera.fill").foregroundStyle(monitor.cameraOn || monitor.cameraStopping ? .orange : .secondary) }.font(.caption)
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
                Button(monitor.isStarting ? "Cancel startup" : monitor.isActive ? "Pause listening and camera" : "Start local ambient mode") { if monitor.isActive || monitor.isStarting { monitor.stop() } else { Task { await monitor.start() } } }.keyboardShortcut(.space, modifiers: []).disabled(monitor.cameraStopping || monitor.microphoneStopping)
                Text("Paired, opted-in reminders are checked every five minutes while AURA is running. They can speak while the microphone and camera are off; Pause controls capture.")
                    .font(.system(size: 11)).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                if !monitor.recentResponse.isEmpty { Divider(); Text("AURA").font(.caption).foregroundStyle(.secondary); Text(monitor.recentResponse).font(.system(size: 12)).textSelection(.enabled) }
                if !monitor.scene.isEmpty { Text("Local camera: \(monitor.scene)").font(.caption).foregroundStyle(.secondary) }
                Button("Clear pairing") { monitor.forgetPairing() }.font(.caption).foregroundStyle(.secondary)
            }
            Text(monitor.status).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            Text("While ambient mode is live, AURA may save a short on-device scene summary locally when the view changes (at most once a minute). Photos and audio are not saved.")
                .font(.system(size: 10)).foregroundStyle(.tertiary).fixedSize(horizontal: false, vertical: true)
            if monitor.permissionSettingsURL != nil {
                Button("Open Privacy Settings") { monitor.openPermissionSettings() }
                    .buttonStyle(.bordered)
            }
            Divider(); Text("Closing this window or pressing Pause stops local listening and camera capture.").font(.system(size: 10)).foregroundStyle(.tertiary)
        }.padding(18).frame(width: 350)
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
