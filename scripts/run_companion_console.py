import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from companion.memory_extractor import MemoryExtractor
from companion.people_registry import PeopleRegistry
from companion.reaction_engine import CompanionReactionEngine
from config.env_loader import load_env_file
from devices.event_bus import DeviceEventBus
from memory.sqlite_store import AuraMemoryStore
from perception.camera import CameraObserver, get_default_camera_observer
from perception.stt import WindowsSpeechRecognizer
from perception.tts import WindowsTTSSpeaker, get_speaker_from_env
from safety.safety_engine import SafetyEngine


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


def _infer_trust_level(relation: str | None) -> str:
    if not relation:
        return "guest"
    rel = relation.lower()
    family_keywords = (
        "mother", "father", "brother", "sister", "cousin",
        "wife", "husband", "son", "daughter",
    )
    if any(keyword in rel for keyword in family_keywords):
        return "family"
    caretaker_keywords = ("caretaker", "nurse", "helper")
    if any(keyword in rel for keyword in caretaker_keywords):
        return "caretaker"
    if "friend" in rel:
        return "friend"
    return "guest"


def print_known_people(store: AuraMemoryStore, user_id: int) -> None:
    people = store.get_known_people(user_id)
    if not people:
        print("(no known people)")
        return
    for person in people:
        consent = "yes" if person.get("consent_to_remember") else "no"
        last_seen = person.get("last_seen_at") or "never"
        print(
            f"- {person['display_name']} | {person.get('relation') or '-'} | "
            f"{person.get('trust_level')} | consent={consent} | last_seen={last_seen}"
        )


def introduce_person_flow(
    store: AuraMemoryStore,
    user_id: int,
    room: str | None = None,
) -> dict | None:
    display_name = input("Guest name: ").strip()
    if not display_name:
        print("Introduction cancelled.")
        return None

    relation = input("Relation: ").strip() or None
    notes = input("Notes: ").strip() or None
    consent_raw = input("Consent to remember this person? [y/N]: ").strip().lower()
    consent_to_remember = consent_raw in {"y", "yes"}
    trust_level = _infer_trust_level(relation)

    registry = PeopleRegistry(store)
    result = registry.introduce_person(
        user_id,
        display_name=display_name,
        relation=relation,
        notes=notes,
        trust_level=trust_level,
        consent_to_remember=consent_to_remember,
        room=room,
    )

    print("AURA_PERSON_INTRODUCED")
    print(f"name={result['display_name']}")
    print(f"relation={result.get('relation') or '-'}")
    print(f"trust_level={result['trust_level']}")

    store.add_conversation(
        user_id,
        role="system",
        message=f"AURA learned a new known person: {result['display_name']}.",
    )
    return result


def unknown_person_flow(
    store: AuraMemoryStore,
    user_id: int,
    speaker: WindowsTTSSpeaker | None = None,
) -> None:
    event_bus = DeviceEventBus(store)
    safety_engine = SafetyEngine(store)

    published = event_bus.publish_event(
        user_id,
        event_type="unknown_person_detected",
        event_summary="Unknown person detected near front door.",
        source="manual_console",
        room="front_door",
        severity="medium",
        confidence=0.7,
        requires_action=True,
    )
    evaluation = safety_engine.evaluate_event(user_id, published)

    print("Safety action:")
    print(f"- type={evaluation.get('action_type')}")
    print(f"  summary={evaluation.get('action_summary')}")
    print(f"  requires_action={evaluation.get('requires_action')}")

    prompt = (
        "Looks like we may have a guest near the front door. "
        "Would you like to introduce them to me?"
    )
    print(f"\nAURA: {prompt}")
    if speaker is not None and speaker.enabled:
        speaker.speak(prompt)

    choice = input("Introduce now? [y/N]: ").strip().lower()
    if choice in {"y", "yes"}:
        introduce_person_flow(store, user_id, room="front_door")


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
    print("Commands: /people, /introduce, /unknown-person")

    while True:
        message = get_user_message(recognizer, mic_enabled)
        if message.lower() == "exit":
            break

        command = message.strip().lower()
        if command == "/people":
            print_known_people(store, user_id)
            continue
        if command == "/introduce":
            introduce_person_flow(store, user_id)
            continue
        if command == "/unknown-person":
            unknown_person_flow(
                store,
                user_id,
                speaker if voice_enabled else None,
            )
            continue

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
