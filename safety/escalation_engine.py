from __future__ import annotations

from memory.sqlite_store import AuraMemoryStore

DEFAULT_PLANS: tuple[dict, ...] = (
    {
        "event_type": "fall_detected",
        "severity": "high",
        "first_action": "Ask user if they are okay.",
        "second_action": "If no response, notify top emergency contact.",
        "final_action": "If configured, escalate to emergency service after confirmation.",
        "wait_seconds_before_escalation": 30,
        "requires_user_confirmation": True,
    },
    {
        "event_type": "fire_detected",
        "severity": "critical",
        "first_action": "Warn user immediately and ask them to leave the area.",
        "second_action": "Notify emergency contacts.",
        "final_action": "Emergency service escalation requires configured confirmation.",
        "wait_seconds_before_escalation": 10,
        "requires_user_confirmation": True,
    },
    {
        "event_type": "smoke_detected",
        "severity": "critical",
        "first_action": "Warn user about possible smoke.",
        "second_action": "Notify emergency contacts if not resolved.",
        "final_action": "Emergency service escalation requires configured confirmation.",
        "wait_seconds_before_escalation": 15,
        "requires_user_confirmation": True,
    },
    {
        "event_type": "heart_rate_high",
        "severity": "medium",
        "first_action": "Ask user how they feel and suggest sitting down.",
        "second_action": "Notify emergency contact if symptoms or no response.",
        "final_action": "Escalate only with confirmation.",
        "wait_seconds_before_escalation": 60,
        "requires_user_confirmation": True,
    },
    {
        "event_type": "unknown_person_detected",
        "severity": "medium",
        "first_action": "Notify user and ask if they recognize the person.",
        "second_action": "Save evidence and notify trusted contact if suspicious.",
        "final_action": "Police escalation requires user confirmation.",
        "wait_seconds_before_escalation": 30,
        "requires_user_confirmation": True,
    },
    {
        "event_type": "unknown_person_with_possible_weapon",
        "severity": "high",
        "first_action": "Alert user immediately and save evidence.",
        "second_action": "Notify emergency contacts.",
        "final_action": "Police escalation requires configured confirmation.",
        "wait_seconds_before_escalation": 5,
        "requires_user_confirmation": True,
    },
    {
        "event_type": "pill_missed",
        "severity": "medium",
        "first_action": "Remind user gently.",
        "second_action": "Repeat reminder later.",
        "final_action": "Notify caretaker if repeated missed medicine.",
        "wait_seconds_before_escalation": 900,
        "requires_user_confirmation": False,
    },
    {
        "event_type": "plant_moisture_low",
        "severity": "low",
        "first_action": "Suggest watering plant or trigger watering if enabled.",
        "second_action": "Log plant care reminder.",
        "final_action": None,
        "wait_seconds_before_escalation": 0,
        "requires_user_confirmation": False,
    },
)

SPOKEN_RESPONSES: dict[str, str] = {
    "fall_detected": (
        "{name}, I noticed a possible fall. Are you okay? "
        "Please say 'I'm okay' or move if you can."
    ),
    "fire_detected": (
        "I may be seeing a fire or smoke risk. Please move away from the area now. "
        "I will prepare to alert your emergency contact."
    ),
    "smoke_detected": (
        "I may be seeing possible smoke. Please check the area and move to safety if needed. "
        "I will prepare to alert your emergency contact."
    ),
    "heart_rate_high": (
        "{name}, your heart rate may be higher than usual. How are you feeling? "
        "Please sit down if you can."
    ),
    "pill_missed": (
        "It looks like your medicine may have been missed. "
        "Please take it if you haven't already."
    ),
    "unknown_person_detected": (
        "I noticed someone unfamiliar near the front door. Do you recognize them?"
    ),
    "unknown_person_with_possible_weapon": (
        "I noticed an unfamiliar person with a possible weapon-like object. "
        "Please stay safe. I am preparing to alert your emergency contact."
    ),
    "plant_moisture_low": (
        "It looks like a plant may need watering. "
        "Would you like me to remind you or trigger watering if enabled?"
    ),
}


class EscalationEngine:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store

    def ensure_default_plans(self, user_id: int) -> None:
        for plan in DEFAULT_PLANS:
            if self.store.get_escalation_plan(user_id, plan["event_type"]) is None:
                self.store.add_escalation_plan(user_id, **plan)

    def _get_preferred_name(self, user_id: int) -> str:
        cur = self.store.conn.execute(
            "SELECT preferred_name, name FROM users WHERE id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        if row:
            return str(row["preferred_name"] or row["name"] or "there")
        return "there"

    def _build_spoken_response(self, user_id: int, event_type: str, plan: dict) -> str:
        template = SPOKEN_RESPONSES.get(event_type)
        if template:
            return template.format(name=self._get_preferred_name(user_id))
        return plan.get("first_action") or "A safety event may need your attention."

    def build_escalation_response(
        self,
        user_id: int,
        event: dict,
        safety_result: dict,
    ) -> dict:
        event_type = event.get("event_type", "")
        event_id = event.get("event_id")
        plan = self.store.get_escalation_plan(user_id, event_type)

        contacts = self.store.get_emergency_contacts(user_id)
        top_contact = contacts[0]["name"] if contacts else None

        if plan is None:
            severity = safety_result.get("severity", event.get("severity", "medium"))
            first_action = safety_result.get(
                "action_summary",
                "Review the safety event and respond as needed.",
            )
            self.store.add_escalation_log(
                user_id,
                event_type=event_type,
                escalation_stage="first_action",
                action_summary=first_action,
                severity=severity,
                source_event_id=event_id,
            )
            return {
                "event_type": event_type,
                "severity": severity,
                "first_action": first_action,
                "second_action": None,
                "final_action": None,
                "wait_seconds_before_escalation": 30,
                "requires_user_confirmation": True,
                "contacts_available": bool(contacts),
                "top_contact": top_contact,
                "spoken_response": first_action,
            }

        severity = plan.get("severity", safety_result.get("severity", "medium"))
        first_action = plan["first_action"]

        self.store.add_escalation_log(
            user_id,
            event_type=event_type,
            escalation_stage="first_action",
            action_summary=first_action,
            severity=severity,
            source_event_id=event_id,
        )

        return {
            "event_type": event_type,
            "severity": severity,
            "first_action": first_action,
            "second_action": plan.get("second_action"),
            "final_action": plan.get("final_action"),
            "wait_seconds_before_escalation": plan.get("wait_seconds_before_escalation", 30),
            "requires_user_confirmation": bool(plan.get("requires_user_confirmation")),
            "contacts_available": bool(contacts),
            "top_contact": top_contact,
            "spoken_response": self._build_spoken_response(user_id, event_type, plan),
        }
