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

final class AmbientMonitor: NSObject, ObservableObject {
    @Published var isActive = false
    @Published var isPaired = false
    @Published var microphoneOn = false
    @Published var cameraOn = false
    @Published var isPersonPresent = false
    @Published var status = "Pair AURA using the session code from its terminal."
    @Published var code = ""
    @Published var recentResponse = ""
    @Published var scene = ""

    private let captureQueue = DispatchQueue(label: "aura.ambient.capture")
    private let session = AVCaptureSession()
    private let videoOutput = AVCaptureVideoDataOutput()
    private let engine = AVAudioEngine()
    private let synthesizer = AVSpeechSynthesizer()
    private var transcriber: LocalSpeechPipeline?
    private var cookie: String?
    private var lastVisionTime = Date.distantPast
    private var contextLabels: [String] = []
    private var isConfigured = false
    private var resumeAfterWake = false

    override init() {
        cookie = Keychain.read()
        super.init()
        if cookie != nil { Task { await validatePairing() } }
        let center = NSWorkspace.shared.notificationCenter
        center.addObserver(forName: NSWorkspace.willSleepNotification, object: nil, queue: .main) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in self.resumeAfterWake = self.isActive; self.stop() }
        }
        center.addObserver(forName: NSWorkspace.didWakeNotification, object: nil, queue: .main) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in if self.resumeAfterWake { self.resumeAfterWake = false; await self.start() } }
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
        guard !isActive else { return }
        do {
            let authorized = await withCheckedContinuation { continuation in
                SFSpeechRecognizer.requestAuthorization { continuation.resume(returning: $0 == .authorized) }
            }
            guard authorized else { status = "Allow Speech Recognition in System Settings to use local listening."; return }
            let mic = await AVCaptureDevice.requestAccess(for: .audio)
            guard mic else { status = "Microphone access is off. Allow it in System Settings."; return }
            let camera = await AVCaptureDevice.requestAccess(for: .video)
            guard camera else { status = "Camera access is off. Allow it in System Settings."; return }
            guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US")), recognizer.isAvailable, recognizer.supportsOnDeviceRecognition else {
                status = "On-device English speech recognition isn’t available on this Mac. AURA won’t send ambient audio to a server."; return
            }
            self.transcriber = LocalSpeechPipeline(recognizer: recognizer) { [weak self] text in
                Task { @MainActor in self?.handle(text) }
            }
            try configureCamera()
            try startAudio()
            isActive = true; microphoneOn = true; cameraOn = true
            status = "Listening locally. Only Hey AURA, direct requests, or explicit support phrases get a reply."
        } catch { stop(); status = "Couldn’t start the local microphone and camera: \(error.localizedDescription)" }
    }

    private func configureCamera() throws {
        if !isConfigured {
            session.beginConfiguration()
            session.sessionPreset = .low
            guard let device = AVCaptureDevice.default(for: .video) else {
                session.commitConfiguration()
                throw CaptureError.noCamera
            }
            let input = try AVCaptureDeviceInput(device: device)
            guard session.canAddInput(input) else {
                session.commitConfiguration()
                throw CaptureError.configuration
            }
            session.addInput(input)
            videoOutput.alwaysDiscardsLateVideoFrames = true
            videoOutput.setSampleBufferDelegate(self, queue: captureQueue)
            guard session.canAddOutput(videoOutput) else {
                session.commitConfiguration()
                throw CaptureError.configuration
            }
            session.addOutput(videoOutput)
            session.commitConfiguration()
            isConfigured = true
        }
        captureQueue.async { [session] in session.startRunning() }
    }

    private func startAudio() throws {
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.channelCount > 0 else { throw CaptureError.noMicrophone }
        let transcriber = self.transcriber
        input.installTap(onBus: 0, bufferSize: 2048, format: format) { buffer, _ in
            transcriber?.consume(buffer)
        }
        engine.prepare(); try engine.start()
    }

    private func handle(_ transcript: String) {
        guard isActive else { return }
        let text = transcript.trimmingCharacters(in: .whitespacesAndNewlines)
        guard shouldRespond(text) else { return }
        status = "AURA heard a direct request. Preparing a reply locally."
        Task { await sendToCompanion(text) }
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

    private func sendToCompanion(_ transcript: String) async {
        guard let cookie, let url = URL(string: "http://127.0.0.1:8790/api/ambient") else { return }
        let label = contextLabels.prefix(5).joined(separator: ", ")
        let observation = label.isEmpty ? "" : "Local camera context: \(label). Person present: \(isPersonPresent ? "yes" : "no")."
        do {
            var request = URLRequest(url: url); request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("http://127.0.0.1:8790", forHTTPHeaderField: "Origin")
            request.setValue(cookie, forHTTPHeaderField: "Cookie")
            request.httpBody = try JSONSerialization.data(withJSONObject: ["message": transcript, "observation": observation])
            let (data, _) = try await URLSession.shared.data(for: request)
            let response = try JSONDecoder().decode(CompanionResponse.self, from: data)
            await MainActor.run {
                recentResponse = response.response; status = "AURA replied. Still listening locally."
                let utterance = AVSpeechUtterance(string: response.response); utterance.voice = AVSpeechSynthesisVoice(language: "en-US"); utterance.rate = 0.48
                synthesizer.speak(utterance)
            }
        } catch { status = "Couldn’t reach AURA. The transcript was not saved here." }
    }

    func stop() {
        guard isActive || isConfigured else { return }
        isActive = false; microphoneOn = false; cameraOn = false
        engine.inputNode.removeTap(onBus: 0); engine.stop()
        transcriber?.stop(); transcriber = nil
        captureQueue.async { if self.session.isRunning { self.session.stopRunning() } }
        synthesizer.stopSpeaking(at: .immediate)
        status = "Paused. Microphone and camera are off."
    }

    func forgetPairing() { stop(); cookie = nil; Keychain.delete(); isPaired = false; status = "Session pairing cleared." }
}

extension AmbientMonitor: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        let now = Date()
        guard now.timeIntervalSince(lastVisionTime) >= 1, let image = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        lastVisionTime = now
        let request = VNClassifyImageRequest()
        let humans = VNDetectHumanRectanglesRequest()
        do {
            try VNImageRequestHandler(cvPixelBuffer: image).perform([request, humans])
            let labels = request.results?.prefix(4).map { $0.identifier } ?? []
            let present = !(humans.results?.isEmpty ?? true)
            Task { @MainActor in self.contextLabels = Array(labels); self.scene = Array(labels).joined(separator: ", "); self.isPersonPresent = present }
        } catch { }
    }
}

private struct CompanionResponse: Decodable { let response: String }
private enum CaptureError: LocalizedError {
    case noCamera, noMicrophone, configuration
    var errorDescription: String? { switch self { case .noCamera: "No camera was found."; case .noMicrophone: "No microphone was found."; case .configuration: "Couldn’t configure local capture." } }
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

    init(recognizer: SFSpeechRecognizer, onFinal: @escaping @Sendable (String) -> Void) {
        self.recognizer = recognizer
        self.onFinal = onFinal
    }

    func consume(_ buffer: AVAudioPCMBuffer) {
        queue.async { [weak self] in
            guard let self, !self.stopped, let channel = buffer.floatChannelData?[0] else { return }
            let count = Int(buffer.frameLength)
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
                self.request?.append(buffer)
            } else if self.inSpeech {
                self.quietBuffers += 1
                self.request?.append(buffer)
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
                self.queue.async { self.request = nil; self.task = nil; self.inSpeech = false; self.quietBuffers = 0 }
            }
        }
    }

    func stop() {
        queue.async {
            self.stopped = true
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
            HStack(spacing: 8) { Label(monitor.microphoneOn ? "Microphone on" : "Microphone off", systemImage: "mic.fill").foregroundStyle(monitor.microphoneOn ? .orange : .secondary); Label(monitor.cameraOn ? "Camera on" : "Camera off", systemImage: "camera.fill").foregroundStyle(monitor.cameraOn ? .orange : .secondary) }.font(.caption)
            if !monitor.isPaired {
                SecureField("Session code from AURA terminal", text: $monitor.code)
                Button("Pair with AURA") { Task { await monitor.pair() } }.disabled(monitor.code.isEmpty)
            } else {
                Button(monitor.isActive ? "Pause listening and camera" : "Start local ambient mode") { if monitor.isActive { monitor.stop() } else { Task { await monitor.start() } } }.keyboardShortcut(.space, modifiers: [])
                if !monitor.recentResponse.isEmpty { Divider(); Text("AURA").font(.caption).foregroundStyle(.secondary); Text(monitor.recentResponse).font(.system(size: 12)).textSelection(.enabled) }
                if !monitor.scene.isEmpty { Text("Local camera: \(monitor.scene)").font(.caption).foregroundStyle(.secondary) }
                Button("Clear pairing") { monitor.forgetPairing() }.font(.caption).foregroundStyle(.secondary)
            }
            Text(monitor.status).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
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
