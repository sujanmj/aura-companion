import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from companion.memory_extractor import MemoryExtractor
from companion.reaction_engine import CompanionReactionEngine
from config.env_loader import load_env_file
from memory.sqlite_store import AuraMemoryStore
from perception.camera import CameraObserver, get_default_camera_observer
from perception.stt import WindowsSpeechRecognizer
from perception.tts import WindowsTTSSpeaker, get_speaker_from_env


def _ask_typed_message() -> str:
    return input("\nUser message: ").strip()


def _confirm_transcript(recognizer: WindowsSpeechRecognizer, transcript: str) -> str | None:
    while True:
        print(f"You said: {transcript}")
        choice = input("Use this transcript? [Y/edit/retry/n]: ").strip().lower()

        if choice in {"", "y", "yes"}:
            return transcript

        if choice == "edit":
            corrected = input("Corrected message: ").strip()
            if corrected:
                return corrected
            continue

        if choice == "retry":
            retry_text = recognizer.listen_once()
            if retry_text:
                transcript = retry_text
                continue
            print("No speech recognized. Please type your message instead.")
            typed = _ask_typed_message()
            return typed if typed else None

        if choice == "n":
            typed = _ask_typed_message()
            return typed if typed else None


def get_user_message(recognizer: WindowsSpeechRecognizer | None, mic_enabled: bool) -> str:
    if not mic_enabled or recognizer is None:
        return _ask_typed_message()

    while True:
        raw = input("\nPress Enter and speak, or type message directly: ").strip()
        if raw:
            return raw

        text = recognizer.listen_once()
        if not text:
            print("No speech recognized. Please type your message instead.")
            typed = _ask_typed_message()
            if typed:
                return typed
            continue

        confirmed = _confirm_transcript(recognizer, text)
        if confirmed:
            return confirmed


def get_observation(
    store: AuraMemoryStore,
    user_id: int,
    camera_enabled: bool,
    camera_observer: CameraObserver | None,
) -> str:
    if not camera_enabled or camera_observer is None:
        return input("Observation optional: ").strip()

    raw = input(
        "\nPress Enter to capture camera observation, or type observation manually: "
    ).strip()

    if raw:
        store.add_observation(
            user_id,
            event_type="manual_observation",
            event_summary=raw,
            confidence=0.7,
            source="console",
        )
        return raw

    result = camera_observer.capture_observation()
    if result.get("ok"):
        store.add_observation(
            user_id,
            event_type=result["event_type"],
            event_summary=result["event_summary"],
            confidence=float(result["confidence"]),
            source="camera",
        )
        summary = str(result["event_summary"])
        print(f"Camera observation: {summary}")
        return summary

    print("Camera unavailable. Type observation manually if needed.")
    manual = input("Observation optional: ").strip()
    if manual:
        store.add_observation(
            user_id,
            event_type="manual_observation",
            event_summary=manual,
            confidence=0.7,
            source="console",
        )
    return manual


def main(enable_microphone: bool | None = None) -> None:
    load_env_file()

    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    extractor = MemoryExtractor(store)

    provider = os.environ.get("AURA_BRAIN_PROVIDER", "local")
    tts_provider = os.environ.get("AURA_TTS_PROVIDER", "windows")
    print(f"AURA_BRAIN_PROVIDER={provider}")
    print(f"AURA_TTS_PROVIDER={tts_provider}")

    use_brain = input("Use configured cloud/local brain? [y/N]: ").strip().lower() == "y"
    engine = CompanionReactionEngine(store, use_llm=use_brain)

    voice_enabled = input("Enable voice output? [y/N]: ").strip().lower() == "y"
    speaker = get_speaker_from_env() if voice_enabled else WindowsTTSSpeaker(enabled=False)

    if enable_microphone is None:
        mic_enabled = input("Enable microphone input? [y/N]: ").strip().lower() == "y"
    else:
        mic_enabled = enable_microphone

    recognizer = WindowsSpeechRecognizer() if mic_enabled else None

    camera_enabled = input("Enable camera observation? [y/N]: ").strip().lower() == "y"
    camera_observer = get_default_camera_observer() if camera_enabled else None

    print("AURA_COMPANION_CONSOLE_READY")
    print("Type 'exit' to stop.")

    while True:
        message = get_user_message(recognizer, mic_enabled)
        if message.lower() == "exit":
            break

        get_observation(store, user_id, camera_enabled, camera_observer)

        memory_actions = extractor.process_user_message(user_id, message)
        result = engine.generate_reaction(user_id)
        response = result["response"]
        tone = result["tone"]

        store.add_conversation(
            user_id,
            role="assistant",
            message=response,
            emotion_tag=tone,
        )

        print("\nAURA:")
        print(response)
        if voice_enabled:
            speaker.speak(response)
        print(f"Situation: {result['situation']}")
        print(f"Emotional need: {result['emotional_need']}")
        print(f"Tone: {tone}")
        print("Memory actions:")
        for action in memory_actions:
            print(f"- {action}")

        rating = input("\nFeedback optional [good/bad/neutral or Enter]: ").strip().lower()
        if rating in {"good", "bad", "neutral"}:
            feedback_note = input("Feedback note optional: ").strip()
            store.add_response_feedback(
                user_id,
                response_text=response,
                rating=rating,
                feedback_text=feedback_note or None,
                situation=result["situation"],
                tone=tone,
            )
            if rating == "bad" and feedback_note:
                note_lower = feedback_note.lower()
                if "robotic" in note_lower or "fake" in note_lower:
                    store.remember_fact(
                        user_id,
                        fact_key="avoid_robotic_replies",
                        fact_value="User specifically disliked a response because it felt robotic or fake. AURA should respond more naturally and contextually.",
                        confidence=0.9,
                        source="feedback",
                    )
                    print("Memory updated: avoid_robotic_replies")

    store.close()


if __name__ == "__main__":
    main()
