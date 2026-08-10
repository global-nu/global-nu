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
./.venv/bin/pip install --quiet markdown PyYAML Pillow
echo "virtualenv ready:  ./.venv/bin/python3 build.py"
