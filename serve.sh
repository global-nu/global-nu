#!/usr/bin/env bash
# Local preview of the built site.
#   ./serve.sh          -> http://localhost:8000
#   ./serve.sh 8080     -> http://localhost:8080
set -euo pipefail

PORT="${1:-8000}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE="$ROOT/site"

if [ ! -d "$SITE" ]; then
  echo "site/ not found — run:  python3 build.py"
  exit 1
fi

echo "Serving $SITE on http://localhost:$PORT  (Ctrl-C to stop)"
command -v open >/dev/null 2>&1 && (sleep 1 && open "http://localhost:$PORT") &
exec python3 -m http.server "$PORT" --directory "$SITE"
