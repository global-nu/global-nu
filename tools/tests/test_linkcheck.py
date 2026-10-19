#!/usr/bin/env python3
"""The link checker removes dead links, not links Python cannot verify.

    ./.venv/bin/python3 tools/tests/test_linkcheck.py

No network: `requests.Session` is replaced with a stand-in that raises.

On 19 October 2026 three real conferences left the page (indico.ifca.es,
meetings.iac.es, soup2026.ca.infn.it) because their servers omit an
intermediate certificate: browsers and macOS curl open them, `requests`
raises SSLError — which is a ConnectionError subclass, and so was read as
"the host refuses connections".
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import linkcheck                                 # noqa: E402

problems: list[str] = []
checks = 0


def check(label: str, ok: bool) -> None:
    global checks
    checks += 1
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")
    if not ok:
        problems.append(label)


class _Raising:
    def __init__(self, exc):
        self.exc = exc

    def head(self, *a, **k):
        raise self.exc

    get = head

    def close(self):
        pass


def verdict(exc) -> str:
    real = linkcheck.requests.Session
    linkcheck.requests.Session = lambda: _Raising(exc)
    try:
        return linkcheck._check_one("https://x.example/", 5, ())[1]
    finally:
        linkcheck.requests.Session = real


check("SSLError really is a ConnectionError subclass (the trap)",
      issubclass(requests.exceptions.SSLError, requests.exceptions.ConnectionError))
check("a certificate Python cannot verify is unverified, not broken",
      verdict(requests.exceptions.SSLError("unable to get local issuer certificate"))
      == linkcheck.UNVERIFIED)
check("a timeout is unverified",
      verdict(requests.exceptions.ConnectTimeout("slow")) == linkcheck.UNVERIFIED)
check("a refused connection is still broken",
      verdict(requests.exceptions.ConnectionError("refused")) == linkcheck.BROKEN)

print()
if problems:
    print(f"{len(problems)} of {checks} checks FAIL")
    sys.exit(1)
print(f"all {checks} checks pass — only a certainly dead link is removed")
