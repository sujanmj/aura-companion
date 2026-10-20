@main
struct LifecycleTests {
    static func main() {
        var state = AmbientLifecycle()
        precondition(state.phase == .paused)
        let first = state.begin()!
        precondition(state.begin() == nil, "Double start must not create a second capture session")
        state.pause()
        precondition(!state.activate(first), "A permission/camera callback after Pause must not activate capture")
        precondition(!state.contains(first), "Late replies and transcripts after Pause must be ignored")
        let second = state.begin()!
        precondition(second != first)
        precondition(!state.contains(first), "Old callbacks must not affect a restarted session")
        precondition(state.activate(second))
        precondition(state.phase == .active)
        precondition(!state.activate(second), "Activation must only happen once")
        precondition(state.begin() == nil)
        state.pause()
        state.pause()
        precondition(!state.contains(second), "Repeated Pause must remain safe")
        let stopGeneration = state.generation
        precondition(state.canCompleteStop(stopGeneration), "A stopped camera may report completion while paused")
        let restarted = state.begin()!
        precondition(!state.canCompleteStop(stopGeneration), "A late camera-stop callback must not overwrite restarted state")
        precondition(state.activate(restarted))
        state.pause()
        // Exercise long sequences of cancel/restart as can occur across sleep/wake.
        for _ in 0..<1000 {
            let token = state.begin()!
            state.pause()
            let replacement = state.begin()!
            precondition(!state.activate(token))
            precondition(state.activate(replacement))
            precondition(!state.contains(token))
            state.pause()
        }

        var recognition = RecognitionGeneration()
        let oldUtterance = recognition.issue()
        let currentUtterance = recognition.issue()
        precondition(!recognition.isCurrent(oldUtterance), "A stale recognition error must not reset a newer utterance")
        precondition(recognition.isCurrent(currentUtterance))
        recognition.invalidate()
        precondition(!recognition.isCurrent(currentUtterance), "Stopping recognition must invalidate queued callbacks")

        print("PASS: capture lifecycle, 1000 sleep/wake-style cycles, and stale camera/speech callback isolation")
    }
}
