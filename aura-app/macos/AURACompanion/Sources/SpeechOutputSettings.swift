import AVFoundation
import Foundation

enum SpeechOutputSettings {
    static let voicePreferenceKey = "auraSpeechVoiceIdentifier"
    static let ratePreferenceKey = "auraSpeechRate"
    static let rateRange = 0.42...0.60

    static func utterance(
        _ text: String,
        preferences: UserDefaults = .standard
    ) -> AVSpeechUtterance {
        let utterance = AVSpeechUtterance(string: text)
        let selectedIdentifier = preferences.string(forKey: voicePreferenceKey) ?? ""
        let installedVoices = AVSpeechSynthesisVoice.speechVoices()
        utterance.voice = installedVoices.first(where: { $0.identifier == selectedIdentifier })
            ?? AVSpeechSynthesisVoice(language: "en-US")
        let storedRate = preferences.object(forKey: ratePreferenceKey) as? Double ?? 0.48
        utterance.rate = storedRate.isFinite
            ? Float(min(max(storedRate, rateRange.lowerBound), rateRange.upperBound))
            : 0.48
        return utterance
    }
}
