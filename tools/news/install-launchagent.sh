#!/usr/bin/env bash
#
# Install (or refresh) the daily LaunchAgent for global-nu.
#
#   tools/news/install-launchagent.sh            install / refresh
#   tools/news/install-launchagent.sh --remove   uninstall
#
# The schedule comes from tools/news/config.yaml, so the hour is configured in
# one place. Re-run this after changing it.
#
# The agent has no RunAtLoad: installing it must never trigger a run. To test
# it now, use `./update-daily --dry-run`, or `launchctl kickstart` as printed
# at the end.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LABEL="org.global-nu.daily"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
TEMPLATE="$ROOT/tools/news/launchd/$LABEL.plist.template"

if [ "${1:-}" = "--remove" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "removed $LABEL"
  exit 0
fi

PYTHON="$ROOT/.venv/bin/python3"
[ -x "$PYTHON" ] || { echo "run ./setup-venv.sh first" >&2; exit 1; }

read -r HOUR MINUTE <<<"$("$PYTHON" - "$ROOT" <<'PY'
import sys, yaml, pathlib
cfg = yaml.safe_load((pathlib.Path(sys.argv[1]) / "tools/news/config.yaml").read_text())
s = (cfg or {}).get("schedule") or {}
print(int(s.get("hour", 7)), int(s.get("minute", 30)))
PY
)"

mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/var/news/logs"
sed -e "s|__ROOT__|$ROOT|g" -e "s|__PYTHON__|$PYTHON|g" \
    -e "s|__HOUR__|$HOUR|g" -e "s|__MINUTE__|$MINUTE|g" \
    -e "s|__HOME__|$HOME|g" "$TEMPLATE" > "$PLIST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

printf 'installed %s — runs daily at %02d:%02d\n' "$LABEL" "$HOUR" "$MINUTE"
echo "logs:      $ROOT/var/news/logs/news.log"
echo "run now:   launchctl kickstart -k gui/$(id -u)/$LABEL"
echo "remove:    tools/news/install-launchagent.sh --remove"
