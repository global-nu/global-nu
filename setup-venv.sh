#!/usr/bin/env bash
# Project virtualenv. Homebrew's python3 is PEP 668 "externally managed":
# pip refuses to install into it, and forcing it would break the system
# interpreter. Everything this project needs lives in .venv/ instead.
#
#   ./setup-venv.sh          create (or refresh) .venv and install deps
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet markdown PyYAML Pillow playwright
# tools/tests/test_timeline_proportion.py drives a real Chromium layout
# (jsdom, used by the JS suite, never lays out CSS, so it cannot see an SVG
# rendering at the wrong size) — this fetches the browser build Playwright
# needs, on top of the Python package installed above.
./.venv/bin/python3 -m playwright install chromium
echo "virtualenv ready:  ./.venv/bin/python3 build.py"
