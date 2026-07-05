import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config.env_loader import load_env_file
from brain.llm_provider import ClaudeProvider


def main() -> None:
    load_env_file()

    print("AURA_CLAUDE_PROVIDER_TEST_START")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY_MISSING")
        raise SystemExit(0)

    if not os.environ.get("ANTHROPIC_MODEL"):
        print("ANTHROPIC_MODEL_MISSING")
        print("Add ANTHROPIC_MODEL=<model name from Claude console> to config/keys.env")
        raise SystemExit(0)

    provider = ClaudeProvider()
    response = provider.generate(
        "Reply as AURA in one short warm sentence: Sujan is nervous about a presentation."
    )

    if response:
        print("AURA_CLAUDE_PROVIDER_TEST_OK")
        print("RESPONSE:")
        print(response)
    else:
        print("AURA_CLAUDE_PROVIDER_TEST_FALLBACK_NEEDED")


if __name__ == "__main__":
    main()
