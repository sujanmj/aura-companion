"""Generate one AURA response with a new in-memory store and no saved context."""
import os

from memory.sqlite_store import AuraMemoryStore
from companion.reaction_engine import CompanionReactionEngine


def generate_private_response(message: str) -> dict:
    if not isinstance(message, str) or not message.strip() or len(message) > 8000:
        raise ValueError("Invalid private message")

    private_store = AuraMemoryStore(":memory:")
    try:
        private_store.apply_schema()
        user = private_store.get_or_create_user("Private turn")
        private_store.add_conversation(user, "user", message.strip())
        result = CompanionReactionEngine(private_store, use_llm=True).generate_reaction(user)
        provider_used = "LLM provider generated response" in result["reasons"]
        return {
            "response": result["response"],
            "provider": os.environ.get("AURA_BRAIN_PROVIDER", "local") if provider_used else "local",
            "tone": result["tone"],
        }
    finally:
        private_store.close()
