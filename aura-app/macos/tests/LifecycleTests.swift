import Security

@main
struct LifecycleTests {
    @MainActor
    static func main() async {
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
        precondition(!state.acceptsCaptureEvent(second), "Capture events before activation must be ignored")
        precondition(state.activate(second))
        precondition(state.acceptsCaptureEvent(second), "The active capture generation may process audio and camera events")
        precondition(state.phase == .active)
        precondition(!state.activate(second), "Activation must only happen once")
        precondition(state.begin() == nil)
        state.pause()
        state.pause()
        precondition(!state.contains(second), "Repeated Pause must remain safe")
        precondition(!state.acceptsCaptureEvent(second), "Audio and camera events after Pause must be ignored")
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

        var pairing = PairingGeneration()
        let storedCookieValidation = pairing.issue()
        let explicitPair = pairing.issue()
        precondition(!pairing.isCurrent(storedCookieValidation), "A stale validation cannot overwrite a newer pairing")
        precondition(pairing.isCurrent(explicitPair), "The newest pairing operation remains current")
        precondition(PairingValidationDecision.classify(statusCode: 200) == .verified)
        precondition(PairingValidationDecision.classify(statusCode: 401) == .expired)
        precondition(PairingValidationDecision.classify(statusCode: 503) == .temporarilyUnavailable)
        precondition(PairingValidationDecision.classify(statusCode: nil) == .temporarilyUnavailable)

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

        var personNotice = PersonPresenceNoticeTracker()
        for _ in 0..<3 {
            precondition(!personNotice.observe(isPresent: true, enabled: true), "Initial presence must not be announced as an arrival")
        }
        for _ in 0..<9 {
            precondition(!personNotice.observe(isPresent: false, enabled: true), "A brief false negative must not re-arm an arrival notice")
        }
        precondition(!personNotice.observe(isPresent: false, enabled: true))
        precondition(!personNotice.observe(isPresent: true, enabled: false), "Opt-out must suppress a stabilized arrival notice")
        precondition(!personNotice.observe(isPresent: true, enabled: false))
        precondition(!personNotice.observe(isPresent: true, enabled: false))
        for _ in 0..<10 { _ = personNotice.observe(isPresent: false, enabled: false) }
        precondition(!personNotice.observe(isPresent: true, enabled: true))
        precondition(!personNotice.observe(isPresent: true, enabled: true))
        precondition(personNotice.observe(isPresent: true, enabled: true), "Opted-in stable re-entry may trigger one notice")
        precondition(!personNotice.observe(isPresent: true, enabled: true), "A continuously visible person must not trigger repeated notices")

        var sleepPrevention = SleepPreventionState()
        precondition(sleepPrevention.update(isActive: false, enabled: true) == nil, "A saved preference must not prevent sleep while capture is paused")
        precondition(sleepPrevention.update(isActive: true, enabled: false) == nil, "Sleep prevention stays off until explicitly enabled")
        precondition(sleepPrevention.update(isActive: true, enabled: true) == true, "The opt-in assertion starts only for live ambient capture")
        precondition(sleepPrevention.update(isActive: true, enabled: true) == nil, "Repeated live updates must not create duplicate assertions")
        precondition(sleepPrevention.update(isActive: false, enabled: true) == false, "Pause releases the assertion even if the preference remains enabled")
        precondition(!sleepPrevention.isPreventingSleep)

        precondition(
            PermissionSettings.target(for: "Allow Speech Recognition in System Settings") == "Privacy_SpeechRecognition",
            "Speech permission denial must link to its privacy pane"
        )
        precondition(
            StartupWatchdog.timeoutMessage(for: "Checking Speech Recognition permission…").hasPrefix("Speech Recognition permission check timed out") &&
                PermissionSettings.target(for: StartupWatchdog.timeoutMessage(for: "Checking Speech Recognition permission…")) == "Privacy_SpeechRecognition",
            "A stalled Speech Recognition permission request must identify the stage and offer its privacy pane"
        )
        precondition(
            StartupWatchdog.timeoutMessage(for: "Waiting for macOS microphone permission…").hasPrefix("Microphone permission request timed out") &&
                PermissionSettings.target(for: StartupWatchdog.timeoutMessage(for: "Waiting for macOS microphone permission…")) == "Privacy_Microphone",
            "A stalled macOS microphone prompt must explain recovery and link to its privacy pane"
        )
        precondition(
            PermissionSettings.target(for: StartupWatchdog.timeoutMessage(for: "Waiting for macOS camera permission…")) == "Privacy_Camera",
            "A stalled macOS camera prompt must explain recovery and link to its privacy pane"
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

        var timeoutFired = false
        _ = StartupWatchdog.schedule(afterNanoseconds: 1_000_000) {
            timeoutFired = true
        }
        try? await Task.sleep(nanoseconds: 20_000_000)
        precondition(timeoutFired, "A stalled permission callback must reach its startup deadline")

        var stalledLifecycle = AmbientLifecycle()
        let stalledToken = stalledLifecycle.begin()!
        var stalledStartup = true
        var stalledTimedOut = false
        var permissionContinuation: CheckedContinuation<Void, Never>?
        let stalledPermission = Task { @MainActor in
            await withCheckedContinuation { continuation in
                permissionContinuation = continuation
            }
            if stalledLifecycle.contains(stalledToken) {
                _ = stalledLifecycle.activate(stalledToken)
            }
        }
        _ = StartupWatchdog.schedule(afterNanoseconds: 1_000_000) {
            let didExpire = StartupWatchdog.expire(
                token: stalledToken,
                lifecycle: stalledLifecycle,
                isStarting: stalledStartup
            ) {
                stalledLifecycle.pause()
                stalledStartup = false
                stalledTimedOut = true
            }
            precondition(didExpire, "The live startup session must expire while permission remains pending")
        }
        try? await Task.sleep(nanoseconds: 20_000_000)
        precondition(stalledTimedOut, "A suspended permission callback must trigger startup recovery")
        precondition(stalledLifecycle.phase == .paused, "A timed-out startup must leave capture paused")
        permissionContinuation?.resume()
        await stalledPermission.value
        precondition(stalledLifecycle.phase == .paused, "A late permission callback must not restart timed-out capture")

        var completedLifecycle = AmbientLifecycle()
        let completedToken = completedLifecycle.begin()!
        var completedStartup = true
        precondition(completedLifecycle.activate(completedToken), "A valid callback may complete the current startup")
        completedStartup = false
        precondition(
            !StartupWatchdog.expire(
                token: completedToken,
                lifecycle: completedLifecycle,
                isStarting: completedStartup,
                onTimeout: { completedLifecycle.pause() }
            ),
            "The watchdog must not expire after startup has completed"
        )
        precondition(completedLifecycle.phase == .active, "A completed startup must remain active")

        var cancelledTimeoutFired = false
        let cancelledWatchdog = StartupWatchdog.schedule(afterNanoseconds: 20_000_000) {
            cancelledTimeoutFired = true
        }
        cancelledWatchdog.cancel()
        try? await Task.sleep(nanoseconds: 30_000_000)
        precondition(!cancelledTimeoutFired, "A completed or cancelled startup must not run its timeout")

        print("PASS: capture lifecycle, pairing and audio/camera callback generations, 1000 restart cycles, speech output echo suppression, Keychain save failures, suspended-permission startup timeout and late callback recovery, sleep/wake ordering, and privacy settings recovery")
    }
}
