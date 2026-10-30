"""Fail-closed software gate for an explicitly invited room reply.

This module has no audio, network, provider, or memory implementation. Callers
inject those boundaries so authorization can be tested without Pi hardware.
"""

from collections.abc import Callable

TurnOperation = Callable[[str, int, str], int]
Playback = Callable[[str], None]


def deliver_invited_reply(
    session_id: str,
    generation: int,
    turn_id: str,
    reply: str,
    *,
    claim: TurnOperation,
    validate: TurnOperation,
    playback: Playback,
) -> bool:
    """Run one claim and one fresh validation before invoking playback.

    Nonzero authorization results fail closed. Exceptions propagate, and no
    step is automatically retried. Validation is a point-in-time fence only;
    callers still need cancellation and fencing at a real playback boundary.
    """
    if not isinstance(reply, str) or not reply.strip():
        return False
    claim_result = claim(session_id, generation, turn_id)
    if type(claim_result) is not int or claim_result != 0:
        return False
    validation_result = validate(session_id, generation, turn_id)
    if type(validation_result) is not int or validation_result != 0:
        return False
    playback(reply)
    return True
