#!/usr/bin/env python3
"""common.http_get asks again when the answer can change, and only then.

    ./.venv/bin/python3 tools/tests/test_http_retry.py

Written for a day the digest lost. On 14 September 2026 the 07:30 run asked
arXiv for the day's preprints, arXiv answered HTTP 429 "Rate exceeded", the
single attempt returned None, and render.digest left the page untouched — so
the site went on showing 12 September's papers with nothing but a timestamp
to say why. A rate limiter is temporary by definition; one attempt turned a
few seconds of throttling into a missing section for a day.

What is checked here is the judgement, not the plumbing: which answers are
worth asking again for (429 and the 5xx family), which are not (404, 403, and
anything that raised before a status existed — asking again cannot change
those), that the server's own Retry-After wins over our schedule, and that
the waits actually happen in order. The `sleep` argument exists for this
test: real waits would make the suite take half a minute to prove arithmetic.

No network. Every response is a stub.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import common                                   # noqa: E402

problems: list[str] = []
checks = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
    else:
        problems.append(label)
        print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


class _Response:
    def __init__(self, status: int, headers: dict | None = None):
        self.status_code = status
        self.headers = headers or {}
        self.url = "https://example.org/q"


class _Log:
    def __init__(self):
        self.lines: list[str] = []

    def _add(self, msg, *a):
        self.lines.append(msg % a if a else msg)

    info = warning = _add

    def debug(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


def run(statuses, *, headers=None, raises=None, retries=(5, 20)):
    """http_get against a scripted sequence of answers.

    Returns (result, attempts, waits, log).
    """
    calls = {"n": 0}
    waits: list[float] = []

    def fake_get(url, params=None, headers=None, timeout=None):
        i = calls["n"]
        calls["n"] += 1
        if raises and i in raises:
            raise common.requests.RequestException("boom")
        status = statuses[min(i, len(statuses) - 1)]
        return _Response(status, (headers_by_attempt or {}).get(i))

    headers_by_attempt = headers
    real_get = common.requests.get
    common.requests.get = fake_get
    log = _Log()
    try:
        r = common.http_get("https://example.org/q", log=log, retries=retries,
                            sleep=waits.append)
    finally:
        common.requests.get = real_get
    return r, calls["n"], waits, log


# --------------------------------------------------------------------- #
# what is retried
# --------------------------------------------------------------------- #
r, attempts, waits, log = run([429, 429, 200])
check("a 429 that clears on the third attempt returns the response",
      r is not None and r.status_code == 200, f"{r} after {attempts}")
check("...having asked exactly three times (two retries)", attempts == 3, attempts)
check("...waiting the configured 5s then 20s, in that order", waits == [5, 20], waits)

r, attempts, _, _ = run([503, 200])
check("a 503 is retried the same way — a source that was fine a minute ago",
      r is not None and attempts == 2, f"{r} after {attempts}")

r, attempts, waits, log = run([429])
check("a 429 that never clears gives up and returns None", r is None, r)
check("...after the full schedule of attempts, not more", attempts == 3, attempts)
check("...and says in the log how many attempts it took",
      any("3 attempts" in line for line in log.lines), log.lines)

# --------------------------------------------------------------------- #
# what is NOT retried: asking again cannot change these answers
# --------------------------------------------------------------------- #
for status in (404, 403, 400, 301):
    r, attempts, _, _ = run([status])
    check(f"HTTP {status} is not retried — the answer would be the same",
          r is None and attempts == 1, f"{attempts} attempts")

r, attempts, _, _ = run([200], raises={0})
check("a connection that raises is not retried either, and returns None",
      r is None and attempts == 1, f"{attempts} attempts")

# --------------------------------------------------------------------- #
# the server's own schedule wins over ours
# --------------------------------------------------------------------- #
r, attempts, waits, _ = run([429, 200], headers={0: {"Retry-After": "12"}})
check("Retry-After from the server is honoured instead of our own wait",
      waits == [12], waits)

r, attempts, waits, _ = run([429, 200], headers={0: {"Retry-After": "9999"}})
check("an absurd Retry-After is capped rather than parking the run for hours",
      waits == [common.MAX_RETRY_WAIT], waits)

r, attempts, waits, _ = run([429, 200], headers={0: {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}})
check("a Retry-After we cannot read falls back to our own wait, not to zero",
      waits == [5], waits)

# --------------------------------------------------------------------- #
# the caller's contract is unchanged: None means "omit this source"
# --------------------------------------------------------------------- #
r, attempts, _, _ = run([500, 500, 500], retries=())
check("with retries switched off the behaviour is exactly what it always was",
      r is None and attempts == 1, f"{attempts} attempts")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — http_get retries what can change, "
      f"and gives up on what cannot")
