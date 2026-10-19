#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v node >/dev/null || ! command -v python3 >/dev/null; then
  echo 'AURA needs Node.js 22.12+ and Python 3.11+. Install them, then reopen this launcher.'
  read -r -p 'Press Enter to close.'
  exit 1
fi
node -e 'const [a,b]=process.versions.node.split(".").map(Number);if(a<22||(a===22&&b<12)){console.error("Node.js 22.12+ required");process.exit(1)}'
python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
if [ ! -d node_modules ]; then npm ci --ignore-scripts; fi
if [ ! -f dist/index.html ]; then npm run build; fi
if [ "$(uname -s)" = "Darwin" ] && [ ! -d 'release/AURA Companion.app' ]; then npm run macos:app; fi
printf '
AURA uses the existing database at data/aura_memory.db.
The server stays on while this Terminal window is running.
Open http://127.0.0.1:8790 and enter the session code below.

'
node server/server.mjs &
AURA_SERVER_PID=$!
trap 'kill "$AURA_SERVER_PID" 2>/dev/null || true' EXIT
for attempt in {1..40}; do
  if curl -fsS http://127.0.0.1:8790/ >/dev/null 2>&1; then break; fi
  sleep 0.25
done
if [ "$(uname -s)" = "Darwin" ] && [ -d 'release/AURA Companion.app' ]; then
  open -a "$PWD/release/AURA Companion.app"
fi
wait "$AURA_SERVER_PID"
