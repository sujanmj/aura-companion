import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from api.sensor_api_server import run_server


def main() -> None:
    host = "127.0.0.1"
    port = 8787

    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        port = int(sys.argv[2])

    run_server(host=host, port=port)


if __name__ == "__main__":
    main()
