#!/usr/bin/env python3
"""The watchdog decides whether the site has gone stale, and says so.

    ./.venv/bin/python3 tools/tests/test_watchdog.py

On 2026-08-16 the daily LaunchAgent exited before it could log anything: no
line in news.log, no line in launchd.log, and the site simply stopped being
refreshed. Nothing noticed. A check that lives inside the run cannot catch
that failure — it died before the run began — so the check has to live
outside it and ask a different question: when did this site last update?

`state.json`'s `last_success` is that answer, written by the pipeline itself
only when a run got all the way through. These tests pin the decision made
from it. They deliberately pass an explicit `now` rather than reading the
clock, so the same inputs give the same verdict on any day, at any hour.
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import watchdog                          # noqa: E402
from tools.news import mailer                            # noqa: E402

checks = 0
problems = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
        return
    problems.append(label)
    print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


NOW = _dt.datetime.fromisoformat("2026-08-16T12:30:00+02:00")


def state(last_success: str | None) -> dict:
    """A state.json as the pipeline writes one, trimmed to what matters."""
    return {"last_success": last_success, "last_run": "irrelevant"}


# --- how long has it been? -----------------------------------------------
check("a success two hours ago reads as two hours",
      watchdog.hours_since_success(
          state("2026-08-16T10:30:00+02:00"), NOW) == 2.0)

check("a success is measured across a day boundary",
      watchdog.hours_since_success(
          state("2026-08-15T07:32:29+02:00"), NOW) > 28.0)

check("a different timezone offset is honoured, not ignored",
      watchdog.hours_since_success(
          state("2026-08-16T08:30:00+00:00"), NOW) == 2.0,
      "08:30 UTC is 10:30 in +02:00, so two hours before NOW")

check("never having succeeded is not an age",
      watchdog.hours_since_success(state(None), NOW) is None)

check("an unparseable timestamp is not an age either",
      watchdog.hours_since_success(state("last tuesday"), NOW) is None)

# --- so, act or stay quiet? ----------------------------------------------
# The threshold is deliberately longer than a day: a run at 07:30 and a check
# at 12:30 are 29 hours apart when yesterday's run is the last good one, but
# only 5 hours apart when today's worked.
check("a site refreshed this morning is left alone",
      watchdog.should_act(state("2026-08-16T07:32:00+02:00"), NOW, 26.0)
      is False)

check("a site last refreshed yesterday morning is acted on",
      watchdog.should_act(state("2026-08-15T07:32:29+02:00"), NOW, 26.0)
      is True)

check("a site that has never succeeded is acted on",
      watchdog.should_act(state(None), NOW, 26.0) is True,
      "no success ever recorded is the most alarming state, not the calmest")

check("exactly at the threshold is not yet stale",
      watchdog.should_act(
          state((NOW - _dt.timedelta(hours=26)).isoformat()), NOW, 26.0)
      is False,
      "the boundary belongs to the quiet side, so a punctual run never alarms")

# --- the message a human will actually receive ---------------------------
msg = mailer.build_message(
    subject="global-nu: the site has not updated for 29 hours",
    body="Ran the pipeline again; it succeeded.",
    sender="antonio.marrone@icloud.com",
    recipient="antonio.marrone@icloud.com")

check("the message names its subject", msg["Subject"].startswith("global-nu:"))
check("the message has a sender and a recipient",
      msg["From"] == "antonio.marrone@icloud.com"
      and msg["To"] == "antonio.marrone@icloud.com")
check("the body survives into the message",
      "succeeded" in msg.get_content())
check("the message is plain text — no HTML mail from a cron job",
      msg.get_content_type() == "text/plain")

# A subject that changes on every run defeats mail threading and makes a
# recurring failure look like many different problems.
check("the subject carries no timestamp",
      not any(ch.isdigit() for ch in msg["Subject"].split("for")[0]),
      msg["Subject"])

# --- what the message says depends on whether the retry worked -----------
# This is the distinction that matters most to a reader: "it broke and I
# fixed it" and "it broke and it is still broken" call for different actions
# on a Sunday morning, and confusing them is worse than sending nothing.
recovered = watchdog.compose_report(hours=29.1, rerun_ok=True, detail="")
check("a recovered run says so in the subject",
      "recovered" in recovered[0].lower(), recovered[0])
check("a recovered run does not read as an emergency",
      "failed" not in recovered[0].lower(), recovered[0])

broken = watchdog.compose_report(
    hours=29.1, rerun_ok=False, detail="RuntimeError: no network")
check("a failed retry says so in the subject",
      "failed" in broken[0].lower(), broken[0])
check("a failed retry carries the detail into the body",
      "RuntimeError: no network" in broken[1], broken[1][:120])
check("both reports state how long the site had been stale",
      "29" in recovered[1] and "29" in broken[1])
check("the two subjects differ, so a mail client will not thread them as one",
      recovered[0] != broken[0])

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the watchdog knows stale from fresh")
