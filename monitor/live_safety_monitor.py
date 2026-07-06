from __future__ import annotations

import time
from typing import Any

from actions.action_dispatcher import ActionDispatcher
from devices.event_bus import DeviceEventBus
from memory.sqlite_store import AuraMemoryStore
from safety.escalation_engine import EscalationEngine
from safety.safety_engine import SafetyEngine


class LiveSafetyMonitor:
    def __init__(
        self,
        store: AuraMemoryStore,
        speaker=None,
        sleep_seconds: int = 3,
    ) -> None:
        self.store = store
        self.speaker = speaker
        self.sleep_seconds = sleep_seconds
        self.event_bus = DeviceEventBus(store)
        self.safety_engine = SafetyEngine(store)
        self.escalation_engine = EscalationEngine(store)

    def _event_for_processing(self, event: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_id": event["id"],
            "event_type": event["event_type"],
            "event_summary": event["event_summary"],
            "severity": event.get("severity", "low"),
            "requires_action": bool(event.get("requires_action")),
            "room": event.get("room"),
        }

    def process_event(self, user_id: int, event: dict[str, Any]) -> dict[str, Any]:
        event_id = int(event["id"])
        processing_event = self._event_for_processing(event)
        dispatcher = ActionDispatcher(self.store, self.speaker)

        safety_result = self.safety_engine.evaluate_event(user_id, processing_event)

        if not safety_result.get("requires_action"):
            self.event_bus.mark_event_status(event_id, "ignored")
            return {
                "event_id": event_id,
                "event_type": event["event_type"],
                "status": "ignored",
                "safety": safety_result,
                "escalation": None,
                "dispatch_results": [],
            }

        self.escalation_engine.ensure_default_plans(user_id)
        escalation = self.escalation_engine.build_escalation_response(
            user_id,
            processing_event,
            safety_result,
        )

        dispatch_results: list[dict[str, Any]] = []

        spoken_response = escalation.get("spoken_response")
        if spoken_response:
            dispatch_results.append(
                dispatcher.dispatch(
                    user_id,
                    action_type="speak_now",
                    action_summary=spoken_response,
                    target=processing_event.get("room"),
                    source_event_id=event_id,
                    speak_text=spoken_response,
                )
            )

        if escalation.get("requires_user_confirmation"):
            dispatch_results.append(
                dispatcher.dispatch(
                    user_id,
                    action_type="ask_confirmation",
                    action_summary=escalation["first_action"],
                    target=processing_event.get("room"),
                    source_event_id=event_id,
                )
            )

        second_action = escalation.get("second_action")
        if second_action:
            dispatch_results.append(
                dispatcher.dispatch(
                    user_id,
                    action_type="notify_contact_simulated",
                    action_summary=second_action,
                    target=escalation.get("top_contact"),
                    source_event_id=event_id,
                )
            )

        self.event_bus.mark_event_status(event_id, "dispatched")

        return {
            "event_id": event_id,
            "event_type": event["event_type"],
            "status": "dispatched",
            "safety": safety_result,
            "escalation": escalation,
            "dispatch_results": dispatch_results,
        }

    def process_once(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        pending_events = self.event_bus.get_pending_events(user_id, limit=limit)
        results: list[dict[str, Any]] = []

        for event in pending_events:
            results.append(self.process_event(user_id, event))

        return results

    def run_forever(self, user_id: int, interval_seconds: int = 3, limit: int = 10) -> None:
        print("AURA_LIVE_SAFETY_MONITOR_START")
        try:
            while True:
                results = self.process_once(user_id, limit=limit)
                for result in results:
                    print(
                        f"- event_id={result['event_id']} "
                        f"type={result['event_type']} status={result['status']}"
                    )
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\nAURA_LIVE_SAFETY_MONITOR_STOPPED")
