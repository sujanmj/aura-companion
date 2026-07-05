import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

CONFIG_KEYS_PATH = PROJECT_ROOT / "config" / "keys.env"
SQLITE_DB_PATH = PROJECT_ROOT / "data" / "aura_memory.db"
RECOMMENDED_PYTHON = "3.11"


def main() -> None:
    version = sys.version.split()[0]
    executable = sys.executable

    print("AURA_RUNTIME_CHECK")
    print(f"Python version: {version}")
    print(f"Executable: {executable}")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Config keys file exists: {CONFIG_KEYS_PATH.exists()}")
    print(f"SQLite DB exists: {SQLITE_DB_PATH.exists()}")
    print(f"Recommended Python: {RECOMMENDED_PYTHON}")

    parts = version.split(".")
    if len(parts) >= 2:
        major_minor = f"{parts[0]}.{parts[1]}"
        if major_minor != RECOMMENDED_PYTHON:
            print(
                "AURA_RUNTIME_WARNING: Python 3.11 is recommended before adding camera/audio AI packages."
            )


if __name__ == "__main__":
    main()
