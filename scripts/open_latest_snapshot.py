import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

SNAPSHOT_DIR = PROJECT_ROOT / "data" / "media" / "snapshots"


def main() -> None:
    if not SNAPSHOT_DIR.exists():
        print("AURA_OPEN_LATEST_SNAPSHOT_NONE")
        return

    snapshots = sorted(SNAPSHOT_DIR.glob("*.jpg"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not snapshots:
        print("AURA_OPEN_LATEST_SNAPSHOT_NONE")
        return

    latest = snapshots[0]
    os.startfile(latest)
    print("AURA_OPEN_LATEST_SNAPSHOT_OK")
    print(latest)


if __name__ == "__main__":
    main()
