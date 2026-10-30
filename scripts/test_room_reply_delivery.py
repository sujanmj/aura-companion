"""Hardware-free checks for the invited-room playback gate."""

import unittest
from pathlib import Path
import sys
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from devices.room_reply_delivery import deliver_invited_reply


SESSION = "session-test"
GENERATION = 4
TURN = "turn-test"
REPLY = "Hello from the invited room."


class RoomReplyDeliveryTests(unittest.TestCase):
    def test_success_claims_validates_then_plays_exactly_once(self):
        calls = []

        def claim(session_id, generation, turn_id):
            calls.append(("claim", session_id, generation, turn_id))
            return 0

        def validate(session_id, generation, turn_id):
            calls.append(("validate", session_id, generation, turn_id))
            return 0

        def playback(reply):
            calls.append(("playback", reply))

        result = deliver_invited_reply(
            SESSION, GENERATION, TURN, REPLY,
            claim=claim, validate=validate, playback=playback,
        )

        self.assertTrue(result)
        self.assertEqual(calls, [
            ("claim", SESSION, GENERATION, TURN),
            ("validate", SESSION, GENERATION, TURN),
            ("playback", REPLY),
        ])

    def test_rejected_or_unknown_claim_never_validates_or_plays(self):
        calls = []

        def claim(session_id, generation, turn_id):
            calls.append(("claim", session_id, generation, turn_id))
            return 1

        def validate(*_):
            calls.append(("validate",))
            return 0

        result = deliver_invited_reply(
            SESSION, GENERATION, TURN, REPLY,
            claim=claim,
            validate=validate,
            playback=lambda reply: calls.append(("playback", reply)),
        )

        self.assertFalse(result)
        self.assertEqual(calls, [("claim", SESSION, GENERATION, TURN)])

    def test_boolean_claim_result_is_not_treated_as_success(self):
        validate = mock.Mock(return_value=0)
        playback = mock.Mock()

        result = deliver_invited_reply(
            SESSION, GENERATION, TURN, REPLY,
            claim=mock.Mock(return_value=False),
            validate=validate,
            playback=playback,
        )

        self.assertFalse(result)
        validate.assert_not_called()
        playback.assert_not_called()

    def test_stale_validation_never_plays(self):
        calls = []

        def claim(*args):
            calls.append(("claim", *args))
            return 0

        def validate(*args):
            calls.append(("validate", *args))
            return 1

        result = deliver_invited_reply(
            SESSION, GENERATION, TURN, REPLY,
            claim=claim,
            validate=validate,
            playback=lambda reply: calls.append(("playback", reply)),
        )

        self.assertFalse(result)
        self.assertEqual(calls, [
            ("claim", SESSION, GENERATION, TURN),
            ("validate", SESSION, GENERATION, TURN),
        ])

    def test_empty_reply_does_not_claim_or_play(self):
        for reply in ("", "  ", None):
            with self.subTest(reply=reply):
                claim = mock.Mock(return_value=0)
                validate = mock.Mock(return_value=0)
                playback = mock.Mock()

                result = deliver_invited_reply(
                    SESSION, GENERATION, TURN, reply,
                    claim=claim, validate=validate, playback=playback,
                )

                self.assertFalse(result)
                claim.assert_not_called()
                validate.assert_not_called()
                playback.assert_not_called()

    def test_playback_error_is_not_retried(self):
        playback = mock.Mock(side_effect=OSError("speaker unavailable"))
        with self.assertRaisesRegex(OSError, "speaker unavailable"):
            deliver_invited_reply(
                SESSION, GENERATION, TURN, REPLY,
                claim=mock.Mock(return_value=0),
                validate=mock.Mock(return_value=0),
                playback=playback,
            )
        playback.assert_called_once_with(REPLY)


if __name__ == "__main__":
    unittest.main()
