#!/usr/bin/env bash
#
# Install (or refresh) the two LaunchAgents for global-nu.
#
#   tools/news/install-launchagent.sh            install / refresh both
#   tools/news/install-launchagent.sh --remove   uninstall both
#
# There are two, and the second exists because of the first's failure mode.
# The daily agent runs the pipeline. On 2026-08-16 it exited before it could
# log anything — nothing in news.log, nothing in launchd.log — and the site
# simply stopped being refreshed with nobody the wiser. A check inside the run
# cannot catch a run that never began, so the watchdog agent runs hours later,
# asks state.json when the site last updated, and if it has gone stale reruns
# the pipeline and sends one email.
#
# Both schedules come from tools/news/config.yaml, so the hours are configured
# in one place. Re-run this after changing them.
#
# Neither agent has RunAtLoad: installing something must never trigger a run.
# To test now, use `./update-daily --dry-run`, or `launchctl kickstart` as
# printed at the end.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DAILY="org.global-nu.daily"
WATCHDOG="org.global-nu.watchdog"

if [ "${1:-}" = "--remove" ]; then
  for LABEL in "$DAILY" "$WATCHDOG"; do
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
    echo "removed $LABEL"
  done
  exit 0
fi

PYTHON="$ROOT/.venv/bin/python3"
[ -x "$PYTHON" ] || { echo "run ./setup-venv.sh first" >&2; exit 1; }

# Both schedules in one read, so the two agents cannot drift apart in time.
read -r HOUR MINUTE WD_HOUR WD_MINUTE <<<"$("$PYTHON" - "$ROOT" <<'PY'
import sys, yaml, pathlib
cfg = yaml.safe_load((pathlib.Path(sys.argv[1]) / "tools/news/config.yaml").read_text()) or {}
s = cfg.get("schedule") or {}
a = cfg.get("alerts") or {}
print(int(s.get("hour", 7)), int(s.get("minute", 30)),
      int(a.get("hour", 12)), int(a.get("minute", 30)))
PY
)"

mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/var/news/logs"

install_agent() {
  local label="$1" hour="$2" minute="$3"
  local plist="$HOME/Library/LaunchAgents/$label.plist"
  local template="$ROOT/tools/news/launchd/$label.plist.template"
  sed -e "s|__ROOT__|$ROOT|g" -e "s|__PYTHON__|$PYTHON|g" \
      -e "s|__HOUR__|$hour|g" -e "s|__MINUTE__|$minute|g" \
      -e "s|__HOME__|$HOME|g" "$template" > "$plist"
  # Hand launchd a log file it created itself.
  #
  # This is not tidiness. launchd opens the job's stdout/stderr file BEFORE it
  # forks, and macOS records access to a file under a protected directory —
  # this repo lives on the Desktop — as a grant attached to that individual
  # file. A log file left over from an earlier install carries a grant that no
  # longer matches, launchd cannot open it, and it abandons the spawn with
  # EX_CONFIG (78). The program never runs, so nothing is written anywhere:
  # not the program's log, not the file that just refused to open. That is
  # exactly how the daily agent died silently on 2026-08-16 and stayed dead
  # for six days while the watchdog quietly covered for it.
  #
  # Rotated rather than deleted: watchdog.log holds the watchdog's own history,
  # which is worth keeping, and one .prev is enough to keep it.
  local log
  log="$(/usr/libexec/PlistBuddy -c 'Print :StandardOutPath' "$plist" 2>/dev/null || true)"
  if [ -n "$log" ] && [ -e "$log" ]; then
    mv -f "$log" "$log.prev"
  fi

  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$plist"
  printf 'installed %s — runs daily at %02d:%02d\n' "$label" "$hour" "$minute"
}

install_agent "$DAILY" "$HOUR" "$MINUTE"
install_agent "$WATCHDOG" "$WD_HOUR" "$WD_MINUTE"

echo
echo "logs:      $ROOT/var/news/logs/news.log  (and watchdog.log)"
echo "run now:   launchctl kickstart -k gui/$(id -u)/$DAILY"
echo "check now: $PYTHON -m tools.news.watchdog --dry-run"
echo "remove:    tools/news/install-launchagent.sh --remove"
echo
echo "The watchdog cannot send mail until its password is in the Keychain."
echo "Run this once, and type the password at the prompt so it never reaches"
echo "a shell history or a process listing:"
echo
echo "  security add-generic-password -a antonio.marrone@icloud.com \\"
echo "      -s global-nu-smtp -w"
