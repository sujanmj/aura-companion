import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
DB_FILES = (
    "aura_memory.db",
    "aura_memory.db-wal",
    "aura_memory.db-shm",
)


def main() -> None:
    for name in DB_FILES:
        path = DATA_DIR / name
        if path.exists():
            path.unlink()

    print("AURA_DEV_MEMORY_RESET_OK")


if __name__ == "__main__":
    main()
