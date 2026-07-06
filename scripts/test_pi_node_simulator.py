import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_HUB_URL = "http://127.0.0.1:8787"

TEST_CASES = (
    ("bedroom", "fall_detected"),
    ("kitchen", "smoke_detected"),
    ("balcony", "plant_moisture_low"),
    ("front_door", "unknown_person_detected"),
    ("medicine", "pill_missed"),
)


def health_check(hub_url: str) -> bool:
    try:
        request = urllib.request.Request(
            f"{hub_url}/health",
            headers={"Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status == 200
    except urllib.error.URLError:
        return False


def main() -> None:
    hub_url = DEFAULT_HUB_URL

    if not health_check(hub_url):
        print("AURA_PI_NODE_SIMULATOR_TEST_SKIPPED: server not running")
        return

    simulator = PROJECT_ROOT / "scripts" / "pi_node_simulator.py"

    for node, event_type in TEST_CASES:
        result = subprocess.run(
            [sys.executable, str(simulator), node, event_type],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        if result.returncode != 0:
            print(
                f"AURA_PI_NODE_SIMULATOR_TEST_ERROR: "
                f"{node} {event_type} failed with code {result.returncode}"
            )
            raise SystemExit(result.returncode)

    print("AURA_PI_NODE_SIMULATOR_TEST_OK")


if __name__ == "__main__":
    main()
