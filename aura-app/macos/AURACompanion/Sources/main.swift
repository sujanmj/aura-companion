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

@MainActor final class AURAAppDelegate: NSObject, NSApplicationDelegate {
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
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        self.window = window
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
}

@MainActor final class AmbientMonitor: NSObject, ObservableObject {
    @Published var isActive = false
    @Published var isStarting = false
    @Published var isPaired = false
    @Published var microphoneOn = false
    @Published var cameraOn = false
    @Published var cameraStopping = false
    @Published var isPersonPresent = false
    @Published var status = "Pair AURA using the session code from its terminal."
    @Published var code = ""
    @Published var recentResponse = ""
    @Published var scene = ""

    private var camera: LocalCamera?
    private var lifecycle = AmbientLifecycle()
    private var replyTask: Task<Void, Never>?
    private var hasAudioTap = false
    private let engine = AVAudioEngine()
    private let synthesizer = AVSpeechSynthesizer()
    private var transcriber: LocalSpeechPipeline?
    private var cookie: String?
    private var contextLabels: [String] = []
    private var wakeResume = WakeResumeState()

    override init() {
        cookie = Keychain.read()
        super.init()
        if cookie != nil { Task { await validatePairing() } }
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

    private func validatePairing() async {
        guard let cookie, let url = URL(string: "http://127.0.0.1:8790/api/status") else { return }
        var request = URLRequest(url: url)
        request.setValue(cookie, forHTTPHeaderField: "Cookie")
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            if (response as? HTTPURLResponse)?.statusCode == 200 {
                isPaired = true; status = "Paired securely with this AURA session."
            } else {
                Keychain.delete(); self.cookie = nil; isPaired = false
                status = "Pair with the current AURA session code from its terminal."
            }
        } catch {
            isPaired = false
            status = "Start the AURA web app, then pair using its current session code."
        }
    }

    func pair() async {
        let candidate = code.trimmingCharacters(in: .whitespacesAndNewlines)
        guard candidate.count >= 24 else { status = "Enter the session code from the AURA terminal."; return }
        guard let url = URL(string: "http://127.0.0.1:8790/api/login") else { return }
        do {
            var request = URLRequest(url: url); request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("http://127.0.0.1:8790", forHTTPHeaderField: "Origin")
            request.httpBody = try JSONSerialization.data(withJSONObject: ["token": candidate])
            let (_, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200,
                  let value = http.value(forHTTPHeaderField: "Set-Cookie")?.components(separatedBy: ";").first else {
                status = "Couldn’t pair. Check the current AURA session code and that the web app is running."; return
            }
            cookie = value; Keychain.save(value); isPaired = true; code = ""
            status = "Paired securely with this AURA session."
        } catch { status = "AURA is not reachable on this Mac yet." }
    }

    func start() async {
        guard isPaired, cookie != nil else { status = "Pair with the AURA web app first."; return }
        guard !cameraStopping else { status = "The camera is still stopping. Try again in a moment."; return }
        guard let generation = lifecycle.begin() else { return }
        isStarting = true
        defer {
            if lifecycle.contains(generation) {
                isStarting = false
                if !isActive { lifecycle.pause() }
            }
        }
        do {
            let authorized = await withCheckedContinuation { continuation in
                SFSpeechRecognizer.requestAuthorization { continuation.resume(returning: $0 == .authorized) }
            }
            guard lifecycle.contains(generation) else { return }
            guard authorized else { status = "Allow Speech Recognition in System Settings to use local listening."; return }
            let mic = await AVCaptureDevice.requestAccess(for: .audio)
            guard lifecycle.contains(generation) else { return }
            guard mic else { status = "Microphone access is off. Allow it in System Settings."; return }
            let cameraAllowed = await AVCaptureDevice.requestAccess(for: .video)
            guard lifecycle.contains(generation) else { return }
            guard cameraAllowed else { status = "Camera access is off. Allow it in System Settings."; return }
            guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US")), recognizer.isAvailable, recognizer.supportsOnDeviceRecognition else {
                status = "On-device English speech recognition isn’t available on this Mac. AURA won’t send ambient audio to a server."; return
            }
            self.transcriber = LocalSpeechPipeline(recognizer: recognizer) { [weak self] text in
                Task { @MainActor in
                    guard let self, self.lifecycle.contains(generation) else { return }
                    self.handle(text)
                }
            }
            let camera = LocalCamera { [weak self] labels, present in
                Task { @MainActor in
                    guard let self, self.lifecycle.contains(generation), self.isActive else { return }
                    self.contextLabels = labels; self.scene = labels.joined(separator: ", ")
                    self.isPersonPresent = present
                }
            }
            self.camera = camera
            try await camera.start()
            guard lifecycle.contains(generation) else { camera.stop(); return }
            try startAudio()
            guard lifecycle.activate(generation) else { return }
            isActive = true; microphoneOn = true; cameraOn = true; cameraStopping = false
            status = "Listening locally. Only Hey AURA, direct requests, or explicit support phrases get a reply."
        } catch {
            guard lifecycle.contains(generation) else { return }
            stop(); status = "Couldn’t start the local microphone and camera: \(error.localizedDescription)"
        }
    }

    private func startAudio() throws {
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.channelCount > 0 else { throw CaptureError.noMicrophone }
        let transcriber = self.transcriber
        input.installTap(onBus: 0, bufferSize: 2048, format: format) { buffer, _ in
            transcriber?.consume(buffer)
        }
        hasAudioTap = true
        engine.prepare(); try engine.start()
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
            await MainActor.run {
                guard lifecycle.contains(generation), isActive, !Task.isCancelled else { return }
                recentResponse = response.response; status = "AURA replied. Still listening locally."
                let utterance = AVSpeechUtterance(string: response.response); utterance.voice = AVSpeechSynthesisVoice(language: "en-US"); utterance.rate = 0.48
                synthesizer.speak(utterance)
            }
        } catch {
            guard lifecycle.contains(generation), !Task.isCancelled else { return }
            status = "AURA’s reply was interrupted. Check the conversation before retrying; it may already be saved."
        }
    }

    func stop(preservingWakeResume: Bool = false) {
        if !cameraStopping { lifecycle.pause() }
        let stoppedGeneration = lifecycle.generation
        if !preservingWakeResume { wakeResume.cancel() }
        isStarting = false; isActive = false; microphoneOn = false; cameraOn = false
        replyTask?.cancel(); replyTask = nil
        if hasAudioTap { engine.inputNode.removeTap(onBus: 0); hasAudioTap = false }
        engine.stop()
        transcriber?.stop(); transcriber = nil
        let cameraToStop = camera
        camera = nil
        cameraStopping = cameraToStop != nil || cameraStopping
        contextLabels = []; scene = ""; isPersonPresent = false
        synthesizer.stopSpeaking(at: .immediate)
        status = cameraStopping
            ? "Paused. Microphone is off; camera is stopping."
            : "Paused. Microphone and camera are off."
        cameraToStop?.stop { [weak self] in
            Task { @MainActor in
                guard let self, self.lifecycle.canCompleteStop(stoppedGeneration) else { return }
                self.cameraOn = false
                self.cameraStopping = false
                if self.status == "Paused. Microphone is off; camera is stopping." {
                    self.status = "Paused. Microphone and camera are off."
                }
                if self.wakeResume.cameraStopped() {
                    Task { await self.start() }
                }
            }
        }
    }

    func forgetPairing() { stop(); cookie = nil; Keychain.delete(); isPaired = false; status = "Session pairing cleared." }

    var permissionSettingsURL: URL? {
        guard let target = PermissionSettings.target(for: status) else { return nil }
        return URL(string: "x-apple.systempreferences:com.apple.preference.security?\(target)")
    }

    func openPermissionSettings() {
        guard let url = permissionSettingsURL else { return }
        NSWorkspace.shared.open(url)
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
    private let onScene: @Sendable ([String], Bool) -> Void

    init(onScene: @escaping @Sendable ([String], Bool) -> Void) { self.onScene = onScene }

    func start() async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            queue.async {
                do {
                    guard !self.stopped else { throw CancellationError() }
                    try self.configure()
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

    func stop(completion: @escaping @Sendable () -> Void = {}) {
        queue.async {
            guard !self.stopped else { completion(); return }
            self.stopped = true
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
            onScene(request.results?.prefix(4).map { $0.identifier } ?? [], !(humans.results?.isEmpty ?? true))
        } catch { }
    }
}

private struct CompanionResponse: Decodable { let response: String }
private enum CaptureError: LocalizedError {
    case noCamera, noMicrophone, inputConfiguration, outputConfiguration, startFailed
    var errorDescription: String? { switch self { case .startFailed: "The camera session did not start. Check camera access and other camera apps."; case .noCamera: "No camera was found."; case .noMicrophone: "No microphone was found."; case .inputConfiguration: "macOS could not add the camera input. Check camera access and close apps using the camera."; case .outputConfiguration: "macOS could not add the local video classifier." } }
}

private final class LocalSpeechPipeline: @unchecked Sendable {
    private let queue = DispatchQueue(label: "aura.local.speech")
    private let recognizer: SFSpeechRecognizer
    private let onFinal: @Sendable (String) -> Void
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var inSpeech = false
    private var quietBuffers = 0
    private var stopped = false
    private var requestGeneration = RecognitionGeneration()

    init(recognizer: SFSpeechRecognizer, onFinal: @escaping @Sendable (String) -> Void) {
        self.recognizer = recognizer
        self.onFinal = onFinal
    }

    func consume(_ buffer: AVAudioPCMBuffer) {
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
            guard let self, !self.stopped, let channel = owned.floatChannelData?[0] else { return }
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
                self.onFinal(text)
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
}

private struct MenuView: View {
    @ObservedObject var monitor: AmbientMonitor
    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            HStack { Text("✳ AURA").font(.system(size: 22, weight: .medium)); Spacer(); Text(monitor.isActive ? "LIVE" : "PAUSED").font(.caption2).tracking(2).foregroundStyle(monitor.isActive ? .green : .secondary) }
            Text("Ambient companion").font(.headline)
            Text("AURA checks speech and the room on this Mac. Raw audio and frames are never saved or sent. Speech recognition runs on-device; only direct requests and explicit support phrases reach your AURA companion.").font(.system(size: 12)).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 8) { Label(monitor.microphoneOn ? "Microphone on" : "Microphone off", systemImage: "mic.fill").foregroundStyle(monitor.microphoneOn ? .orange : .secondary); Label(monitor.cameraStopping ? "Camera stopping" : monitor.cameraOn ? "Camera on" : "Camera off", systemImage: "camera.fill").foregroundStyle(monitor.cameraOn || monitor.cameraStopping ? .orange : .secondary) }.font(.caption)
            if !monitor.isPaired {
                SecureField("Session code from AURA terminal", text: $monitor.code)
                Button("Pair with AURA") { Task { await monitor.pair() } }.disabled(monitor.code.isEmpty)
            } else {
                Button(monitor.isStarting ? "Cancel startup" : monitor.isActive ? "Pause listening and camera" : "Start local ambient mode") { if monitor.isActive || monitor.isStarting { monitor.stop() } else { Task { await monitor.start() } } }.keyboardShortcut(.space, modifiers: []).disabled(monitor.cameraStopping)
                if !monitor.recentResponse.isEmpty { Divider(); Text("AURA").font(.caption).foregroundStyle(.secondary); Text(monitor.recentResponse).font(.system(size: 12)).textSelection(.enabled) }
                if !monitor.scene.isEmpty { Text("Local camera: \(monitor.scene)").font(.caption).foregroundStyle(.secondary) }
                Button("Clear pairing") { monitor.forgetPairing() }.font(.caption).foregroundStyle(.secondary)
            }
            Text(monitor.status).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            if monitor.permissionSettingsURL != nil {
                Button("Open Privacy Settings") { monitor.openPermissionSettings() }
                    .buttonStyle(.bordered)
            }
            Divider(); Text("Close camera covers to pause vision. Press Pause before leaving your Mac.").font(.system(size: 10)).foregroundStyle(.tertiary)
        }.padding(18).frame(width: 350)
    }
}

private enum Keychain {
    private static let account = "aura-companion-cookie"
    static func read() -> String? {
        var result: CFTypeRef?
        let status = SecItemCopyMatching([kSecClass: kSecClassGenericPassword, kSecAttrService: "AURA Companion", kSecAttrAccount: account, kSecReturnData: true] as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
    static func save(_ value: String) {
        delete(); let data = Data(value.utf8)
        SecItemAdd([kSecClass: kSecClassGenericPassword, kSecAttrService: "AURA Companion", kSecAttrAccount: account, kSecValueData: data, kSecAttrAccessible: kSecAttrAccessibleAfterFirstUnlock] as CFDictionary, nil)
    }
    static func delete() { SecItemDelete([kSecClass: kSecClassGenericPassword, kSecAttrService: "AURA Companion", kSecAttrAccount: account] as CFDictionary) }
}
