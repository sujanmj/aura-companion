import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from companion.memory_extractor import MemoryExtractor
from companion.reaction_engine import CompanionReactionEngine
from config.env_loader import load_env_file
from memory.sqlite_store import AuraMemoryStore
from perception.tts import WindowsTTSSpeaker


def main() -> None:
    load_env_file()

    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    extractor = MemoryExtractor(store)

    provider = os.environ.get("AURA_BRAIN_PROVIDER", "local")
    print(f"AURA_BRAIN_PROVIDER={provider}")

    use_brain = input("Use configured cloud/local brain? [y/N]: ").strip().lower() == "y"
    engine = CompanionReactionEngine(store, use_llm=use_brain)

    voice_enabled = input("Enable voice output? [y/N]: ").strip().lower() == "y"
    speaker = WindowsTTSSpeaker(enabled=voice_enabled)

    print("AURA_COMPANION_CONSOLE_READY")
    print("Type 'exit' to stop.")

    while True:
        message = input("\nUser message: ").strip()
        if message.lower() == "exit":
            break

        observation = input("Observation optional: ").strip()
        if observation:
            store.add_observation(
                user_id,
                event_type="manual_observation",
                event_summary=observation,
                confidence=0.7,
                source="console",
            )

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
        if speaker.enabled:
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
