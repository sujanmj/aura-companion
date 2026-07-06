import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
DB_FILES = (
    "aura_memory.db",
    "aura_memory.db-wal",
    "aura_memory.db-shm",
    "aura_memory.db-journal",
)


def main() -> None:
    blocked = False

    for name in DB_FILES:
        path = DATA_DIR / name
        if not path.exists():
            continue
        try:
            path.unlink()
        except PermissionError:
            blocked = True

    if blocked:
        print("AURA_DEV_MEMORY_RESET_BLOCKED")
        print("SQLite DB is currently being used by another process.")
        print("Stop running AURA services such as:")
        print("python scripts/run_sensor_api.py")
        print("Then retry:")
        print("python scripts/reset_dev_memory.py")
        sys.exit(1)

    print("AURA_DEV_MEMORY_RESET_OK")


if __name__ == "__main__":
    main()
