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

        var wake = WakeResumeState()
        wake.willSleep(wasActive: true)
        precondition(!wake.cameraStopped(), "Do not restart while the Mac is still asleep")
        precondition(wake.didWake(cameraReady: true), "Wake restarts when camera teardown already finished")
        precondition(!wake.shouldResume)
        wake.willSleep(wasActive: true)
        precondition(!wake.didWake(cameraReady: false), "Wake must wait for camera teardown")
        precondition(wake.cameraStopped(), "A late stop callback resumes a session after wake")
        wake.willSleep(wasActive: false)
        precondition(!wake.didWake(cameraReady: true), "Paused sessions stay paused after sleep")
        wake.willSleep(wasActive: true)
        wake.cancel()
        precondition(!wake.didWake(cameraReady: true), "Manual Pause cancels automatic wake resume")

        precondition(
            PermissionSettings.target(for: "Allow Speech Recognition in System Settings") == "Privacy_SpeechRecognition",
            "Speech permission denial must link to its privacy pane"
        )
        precondition(
            PermissionSettings.target(for: "Microphone access is off. Allow it in System Settings.") == "Privacy_Microphone",
            "Microphone denial must link to its privacy pane"
        )
        precondition(
            PermissionSettings.target(for: "Camera access is off. Allow it in System Settings.") == "Privacy_Camera",
            "Camera denial must link to its privacy pane"
        )
        precondition(
            PermissionSettings.target(for: "Listening locally") == nil,
            "Normal status must not offer a misleading permission shortcut"
        )

        print("PASS: capture lifecycle, 1000 restart cycles, stop isolation, sleep/wake ordering, and privacy settings recovery")
    }
}
