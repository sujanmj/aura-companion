from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from companion.private_session import generate_private_response


class PrivateSessionTests(unittest.TestCase):
    def test_private_response_uses_only_a_fresh_in_memory_store(self):
        inspected = []

        class InspectingEngine:
            def __init__(self, store, *, use_llm):
                self.store = store
                self.use_llm = use_llm

            def generate_reaction(self, user_id):
                conversations = self.store.get_recent_conversations(user_id)
                inspected.append({
                    "path": str(self.store.db_path),
                    "use_llm": self.use_llm,
                    "conversation": [(row["role"], row["message"]) for row in conversations],
                    "facts": self.store.get_memory_facts(user_id),
                    "observations": self.store.get_latest_observations(user_id),
                })
                return {"response": "A private reply.", "reasons": [], "tone": "friendly_warm"}

        with patch("companion.private_session.CompanionReactionEngine", InspectingEngine):
            result = generate_private_response("Please keep this between us.", use_llm=False)

        self.assertEqual(result["response"], "A private reply.")
        self.assertEqual(result["provider"], "local")
        self.assertEqual(inspected, [{
            "path": ":memory:",
            "use_llm": False,
            "conversation": [("user", "Please keep this between us.")],
            "facts": [],
            "observations": [],
        }])

    def test_private_response_rejects_blank_and_oversized_messages(self):
        with patch("companion.private_session.CompanionReactionEngine") as engine:
            for message in ("  ", "x" * 8001):
                with self.subTest(length=len(message)):
                    with self.assertRaises(ValueError):
                        generate_private_response(message)
            engine.assert_not_called()


if __name__ == "__main__":
    unittest.main()
