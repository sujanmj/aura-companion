import Security

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
        precondition(!state.acceptsCameraEvent(second), "Camera events before capture activates must be ignored")
        precondition(state.activate(second))
        precondition(state.acceptsCameraEvent(second), "The active capture generation may process camera events")
        precondition(state.phase == .active)
        precondition(!state.activate(second), "Activation must only happen once")
        precondition(state.begin() == nil)
        state.pause()
        state.pause()
        precondition(!state.contains(second), "Repeated Pause must remain safe")
        precondition(!state.acceptsCameraEvent(second), "Camera events after Pause must not affect the stopped session")
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

        var output = SpeechOutputSuppression()
        let firstOutput = output.begin()
        precondition(output.contains(firstOutput), "Microphone recognition must be suppressed while AURA speaks")
        let nextOutput = output.begin()
        precondition(!output.finish(firstOutput), "A stale speech completion must not resume microphone recognition")
        precondition(output.finish(nextOutput), "Recognition resumes after the current utterance finishes")
        precondition(!output.isSuppressed)
        let interruptedOutput = output.begin()
        output.cancel()
        precondition(!output.finish(interruptedOutput), "Pause must cancel delayed recognition resume")

        var addWasCalled = false
        precondition(
            KeychainPersistence.save(update: { errSecSuccess }, add: { addWasCalled = true; return errSecSuccess }),
            "Updating a stored credential should succeed"
        )
        precondition(!addWasCalled, "A successful update should not create a second item")
        precondition(
            KeychainPersistence.save(update: { errSecItemNotFound }, add: { errSecSuccess }),
            "A missing credential should be added"
        )
        precondition(
            !KeychainPersistence.save(update: { errSecInteractionNotAllowed }, add: { addWasCalled = true; return errSecSuccess }),
            "Keychain access failure must not be reported as a successful save"
        )
        precondition(!addWasCalled, "An update error must not delete or replace an existing item")
        precondition(
            !KeychainPersistence.save(update: { errSecItemNotFound }, add: { errSecDuplicateItem }),
            "A failed add must be reported to the pairing flow"
        )

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
        precondition(
            PermissionSettings.fallbackMessage(for: "Camera access is off. Allow it in System Settings.")?.contains("Privacy & Security") == true,
            "A failed settings shortcut must leave clear manual recovery directions"
        )
        precondition(
            PermissionSettings.fallbackMessage(for: "Listening locally") == nil,
            "Normal status must not show permission recovery directions"
        )

        print("PASS: capture lifecycle, camera callback generations, 1000 restart cycles, speech output echo suppression, Keychain save failures, sleep/wake ordering, and privacy settings recovery")
    }
}
