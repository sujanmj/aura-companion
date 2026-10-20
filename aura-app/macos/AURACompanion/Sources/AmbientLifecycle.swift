import Security

enum StartupWatchdog {
    @MainActor
    static func schedule(
        afterNanoseconds nanoseconds: UInt64,
        onTimeout: @escaping @MainActor () -> Void
    ) -> Task<Void, Never> {
        Task { @MainActor in
            do {
                try await Task.sleep(nanoseconds: nanoseconds)
            } catch {
                return
            }
            guard !Task.isCancelled else { return }
            onTimeout()
        }
    }

    @MainActor
    static func expire(
        token: UInt64,
        lifecycle: AmbientLifecycle,
        isStarting: Bool,
        onTimeout: @MainActor () -> Void
    ) -> Bool {
        guard lifecycle.contains(token), isStarting else { return false }
        onTimeout()
        return true
    }
}

// Pure session state, shared by the native helper and its hardware-free tests.
struct AmbientLifecycle {
    enum Phase { case paused, starting, active }
    private(set) var phase: Phase = .paused
    private(set) var generation: UInt64 = 0

    mutating func begin() -> UInt64? {
        guard phase == .paused else { return nil }
        generation &+= 1
        phase = .starting
        return generation
    }

    func contains(_ token: UInt64) -> Bool {
        generation == token && phase != .paused
    }

    func canCompleteStop(_ token: UInt64) -> Bool {
        generation == token && phase == .paused
    }

    func acceptsCaptureEvent(_ token: UInt64) -> Bool {
        generation == token && phase == .active
    }

    mutating func activate(_ token: UInt64) -> Bool {
        guard contains(token), phase == .starting else { return false }
        phase = .active
        return true
    }

    mutating func pause() {
        generation &+= 1
        phase = .paused
    }
}

// Recognition callbacks can arrive after a newer utterance has begun. Tokens
// let the pipeline ignore stale errors without dropping a valid late transcript.
struct RecognitionGeneration {
    private(set) var value: UInt64 = 0

    mutating func issue() -> UInt64 {
        value &+= 1
        return value
    }

    func isCurrent(_ token: UInt64) -> Bool {
        value == token
    }

    mutating func invalidate() {
        value &+= 1
    }
}

// A delayed pairing validation must not clear a newer user-authorized pairing.
struct PairingGeneration {
    private(set) var value: UInt64 = 0

    mutating func issue() -> UInt64 {
        value &+= 1
        return value
    }

    func isCurrent(_ token: UInt64) -> Bool {
        value == token
    }
}

enum PairingValidationDecision: Equatable {
    case verified
    case expired
    case temporarilyUnavailable

    static func classify(statusCode: Int?) -> Self {
        switch statusCode {
        case 200: .verified
        case 401: .expired
        default: .temporarilyUnavailable
        }
    }
}

// Keep AURA's own speech from becoming a new ambient microphone request. A
// generation prevents a delayed completion from re-opening recognition after
// a newer utterance or a manual Pause.
struct SpeechOutputSuppression {
    private(set) var generation: UInt64 = 0
    private(set) var isSuppressed = false

    mutating func begin() -> UInt64 {
        generation &+= 1
        isSuppressed = true
        return generation
    }

    func contains(_ token: UInt64) -> Bool {
        generation == token && isSuppressed
    }

    mutating func finish(_ token: UInt64) -> Bool {
        guard contains(token) else { return false }
        isSuppressed = false
        return true
    }

    mutating func cancel() {
        generation &+= 1
        isSuppressed = false
    }
}

// Replace an existing credential in place; add only when no item exists. The
// injected operations let the native tests verify failure handling without
// modifying the user's real Keychain.
enum KeychainPersistence {
    static func save(update: () -> OSStatus, add: () -> OSStatus) -> Bool {
        let updateStatus = update()
        if updateStatus == errSecSuccess { return true }
        guard updateStatus == errSecItemNotFound else { return false }
        return add() == errSecSuccess
    }
}

// Preserve an active ambient session across sleep, regardless of whether the
// camera's serialized stop callback runs before or after the wake notification.
struct WakeResumeState {
    private(set) var shouldResume = false
    private(set) var isSleeping = false

    mutating func willSleep(wasActive: Bool) {
        isSleeping = true
        shouldResume = wasActive
    }

    mutating func didWake(cameraReady: Bool) -> Bool {
        isSleeping = false
        return takeResumeIfReady(cameraReady: cameraReady)
    }

    mutating func cameraStopped() -> Bool {
        takeResumeIfReady(cameraReady: true)
    }

    mutating func cancel() {
        shouldResume = false
    }

    private mutating func takeResumeIfReady(cameraReady: Bool) -> Bool {
        guard shouldResume, !isSleeping, cameraReady else { return false }
        shouldResume = false
        return true
    }
}

enum PermissionSettings {
    static func target(for status: String) -> String? {
        if status.hasPrefix("Allow Speech Recognition") {
            return "Privacy_SpeechRecognition"
        }
        if status.hasPrefix("Microphone access is off") {
            return "Privacy_Microphone"
        }
        if status.hasPrefix("Camera access is off") {
            return "Privacy_Camera"
        }
        return nil
    }

    static func fallbackMessage(for status: String) -> String? {
        guard target(for: status) != nil else { return nil }
        return "\(status) Open System Settings > Privacy & Security and allow AURA Companion to use the denied service."
    }
}
