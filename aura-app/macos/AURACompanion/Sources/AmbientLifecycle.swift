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
