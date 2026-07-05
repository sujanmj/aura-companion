import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_companion_console import main


if __name__ == "__main__":
    print("Starting AURA voice companion console...")
    main(enable_microphone=True)
