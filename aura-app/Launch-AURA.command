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
printf '\nAURA keeps memory in the existing repository data/aura_memory.db.\nSet AURA_DB_PATH to use a different existing database.\nOpen http://127.0.0.1:8790 and enter the session code below.\n\n'
npm start
