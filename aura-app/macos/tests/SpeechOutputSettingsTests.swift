import AVFoundation
import Foundation

@main
struct SpeechOutputSettingsTests {
    static func main() {
        let suiteName = "aura-speech-settings-tests-\(UUID().uuidString)"
        guard let preferences = UserDefaults(suiteName: suiteName) else {
            fatalError("Could not create isolated speech preferences")
        }
        defer { preferences.removePersistentDomain(forName: suiteName) }

        let defaultUtterance = SpeechOutputSettings.utterance("AURA test", preferences: preferences)
        precondition(defaultUtterance.speechString == "AURA test")
        precondition(defaultUtterance.voice?.language == "en-US")
        precondition(abs(defaultUtterance.rate - 0.48) < 0.001)

        if let englishVoice = AVSpeechSynthesisVoice.speechVoices().first(where: {
            $0.language.lowercased().hasPrefix("en")
        }) {
            preferences.set(englishVoice.identifier, forKey: SpeechOutputSettings.voicePreferenceKey)
            preferences.set(0.55, forKey: SpeechOutputSettings.ratePreferenceKey)
            let personalized = SpeechOutputSettings.utterance("AURA test", preferences: preferences)
            precondition(personalized.voice?.identifier == englishVoice.identifier)
            precondition(abs(personalized.rate - 0.55) < 0.001)
        }

        preferences.set("missing-voice", forKey: SpeechOutputSettings.voicePreferenceKey)
        preferences.set(0.1, forKey: SpeechOutputSettings.ratePreferenceKey)
        let safelyBounded = SpeechOutputSettings.utterance("AURA test", preferences: preferences)
        precondition(safelyBounded.voice?.language == "en-US")
        precondition(abs(safelyBounded.rate - Float(SpeechOutputSettings.rateRange.lowerBound)) < 0.001)

        preferences.set(Double.nan, forKey: SpeechOutputSettings.ratePreferenceKey)
        let invalidRate = SpeechOutputSettings.utterance("AURA test", preferences: preferences)
        precondition(abs(invalidRate.rate - 0.48) < 0.001)
        print("PASS: local speech voice preferences, fallback voice, and bounded pace")
    }
}
