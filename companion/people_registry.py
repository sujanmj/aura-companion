from __future__ import annotations

from memory.sqlite_store import AuraMemoryStore


class PeopleRegistry:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store

    def introduce_person(
        self,
        user_id: int,
        display_name: str,
        relation: str | None = None,
        notes: str | None = None,
        trust_level: str = "guest",
        consent_to_remember: bool = False,
        room: str | None = None,
    ) -> dict:
        existing = self.store.find_known_person(user_id, display_name)

        if existing:
            person_id = int(existing["id"])
            self.store.add_person_event(
                user_id,
                person_id=person_id,
                event_type="person_reintroduced",
                event_summary=f"{display_name} was reintroduced to AURA.",
                source="manual",
                room=room,
            )
            self.store.update_person_last_seen(user_id, person_id)
            return {
                "person_id": person_id,
                "display_name": existing["display_name"],
                "relation": existing.get("relation"),
                "trust_level": existing.get("trust_level"),
                "consent_to_remember": bool(existing.get("consent_to_remember")),
            }

        person_id = self.store.add_known_person(
            user_id,
            display_name=display_name,
            relation=relation,
            notes=notes,
            trust_level=trust_level,
            consent_to_remember=consent_to_remember,
        )
        self.store.add_person_event(
            user_id,
            person_id=person_id,
            event_type="person_introduced",
            event_summary=f"{display_name} was introduced to AURA.",
            source="manual",
            room=room,
        )
        self.store.update_person_last_seen(user_id, person_id)

        return {
            "person_id": person_id,
            "display_name": display_name,
            "relation": relation,
            "trust_level": trust_level,
            "consent_to_remember": consent_to_remember,
        }

    def mark_person_seen(
        self,
        user_id: int,
        display_name: str,
        room: str | None = None,
        source: str = "manual",
    ) -> dict:
        person = self.store.find_known_person(user_id, display_name)

        if person:
            person_id = int(person["id"])
            self.store.update_person_last_seen(user_id, person_id)
            self.store.add_person_event(
                user_id,
                person_id=person_id,
                event_type="known_person_seen",
                event_summary=f"{display_name} was seen near AURA.",
                source=source,
                room=room,
            )
            return {
                "known": True,
                "person_id": person_id,
                "display_name": person["display_name"],
                "trust_level": person.get("trust_level"),
            }

        self.store.add_person_event(
            user_id,
            person_id=None,
            event_type="unknown_person_seen",
            event_summary=f"Unknown person '{display_name}' was seen near AURA.",
            source=source,
            room=room,
        )
        return {
            "known": False,
            "display_name": display_name,
        }

    def build_guest_prompt(self, user_id: int, room: str | None = None) -> str:
        return "Looks like we may have a guest here. Would you like to introduce them to me?"

    def format_known_people(self, user_id: int) -> list[str]:
        lines: list[str] = []
        for person in self.store.get_known_people(user_id):
            consent = "yes" if person.get("consent_to_remember") else "no"
            last_seen = person.get("last_seen_at") or "never"
            lines.append(
                f"{person['display_name']} | {person.get('relation') or '-'} | "
                f"{person.get('trust_level')} | consent={consent} | last_seen={last_seen}"
            )
        return lines
