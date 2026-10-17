#!/usr/bin/env bash
# Full verification battery for the redesign branch.
#   tools/check_all.sh            public build (site/) + drafts build (site-draft/) + every test
# Exit 0 only if both builds succeed and every test passes. A summary line per
# test goes to stdout; full output to var/check_all.log.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python3"
mkdir -p var
LOG="$ROOT/var/check_all.log"
: > "$LOG"
fail=0
run() {  # label, command...
  local label="$1"; shift
  if "$@" >>"$LOG" 2>&1; then echo "ok   $label"; else echo "FAIL $label"; fail=$((fail+1)); fi
}
run "build site/"        "$PY" build.py
run "build site-draft/"  "$PY" build.py --drafts
# A test must never write into what gets published: snapshot data-exports/
# after the builds and compare once the tests are done (a renderer test once
# replaced the real conferences.ics with its one-event fixture).
snap() { find data-exports -type f -print0 | sort -z | xargs -0 shasum | shasum; }
before="$(snap)"
for t in tools/tests/test_*.py; do
  echo "=== $t" >>"$LOG"
  run "$(basename "$t")" "$PY" "$t"
done
for t in tools/tests/test_*.js; do
  echo "=== $t" >>"$LOG"
  run "$(basename "$t")" node "$t"
done
if [ "$(snap)" = "$before" ]; then echo "ok   tests left data-exports/ untouched"
else echo "FAIL a test wrote into data-exports/"; fail=$((fail+1)); fi
echo "failures: $fail"
exit $(( fail > 0 ))
