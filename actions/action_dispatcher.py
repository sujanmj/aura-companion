from __future__ import annotations

from memory.sqlite_store import AuraMemoryStore


class ActionDispatcher:
    def __init__(self, store: AuraMemoryStore, speaker=None) -> None:
        self.store = store
        self.speaker = speaker

    def dispatch(
        self,
        user_id: int,
        action_type: str,
        action_summary: str,
        target: str | None = None,
        source_event_id: int | None = None,
        speak_text: str | None = None,
    ) -> dict:
        status = "logged"

        if action_type == "speak_now":
            text_to_speak = speak_text or action_summary
            if self.speaker is not None and text_to_speak:
                try:
                    spoke = self.speaker.speak(text_to_speak)
                    status = "spoken" if spoke else "voice_error_logged"
                except Exception:
                    status = "voice_error_logged"
            else:
                status = "logged"
        elif action_type == "ask_confirmation":
            status = "confirmation_needed"
        elif action_type == "notify_contact_simulated":
            status = "simulated_notification_logged"
        elif action_type == "app_alert_simulated":
            status = "simulated_app_alert_logged"
        elif action_type == "siren_simulated":
            status = "simulated_siren_logged"
        elif action_type == "plant_water_simulated":
            status = "simulated_plant_watering_logged"

        action_log_id = self.store.add_action_log(
            user_id,
            action_type=action_type,
            action_summary=action_summary,
            target=target,
            status=status,
            source_event_id=source_event_id,
        )

        return {
            "action_log_id": action_log_id,
            "action_type": action_type,
            "status": status,
            "summary": action_summary,
        }
