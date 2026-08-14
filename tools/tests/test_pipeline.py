#!/usr/bin/env python3
"""pipeline.run — the from_cache tense-refresh, and render steps through _safe.

    ./.venv/bin/python3 tools/tests/test_pipeline.py

Two things the final whole-branch review found:

  * pipeline.run(from_cache=True) replays conference records fetched — and
    tense-flagged (extra.upcoming/in_progress) — on an earlier day, exactly
    the shape of staleness fetch_nu_unbound's 304 path produces. It must run
    them through conferences.sort_for_page (which now re-derives the tense
    from extra.closing against today, see conferences._refresh_tense) rather
    than handing them to render.conferences as-is.

  * render.digest/conferences/news used to be called bare, unlike every fetch
    step, which all go through pipeline._safe. render.conferences now does
    network requests, PIL decoding and cache writes on top of what used to be
    plain string formatting, so it can fail the way a fetch step can — and
    the module docstring's promise ("a step that fails is logged and
    skipped") must hold for it too.

Everything that would touch the network, the real var/news state, or the
real content pages is monkeypatched or redirected to a temp file; this suite
makes no network call and writes nothing under the real var/ or site-src/.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import cache, conferences as conf_mod, pipeline, render, state  # noqa: E402

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


def _rec(title, opening, closing, upcoming_flag):
    """A minimal, valid conference record — same shape cache.load_records
    hands back — with a deliberately STALE tense flag: `upcoming_flag` is
    what a fetcher wrote on some earlier day, independent of what
    opening/closing actually say today."""
    return {
        "id": f"nu:{title}", "source": "inspire-conf", "title": title,
        "url": f"https://example.org/{title}", "links": {}, "authors": "",
        "date": opening, "summary": "",
        "extra": {"acronym": title, "place": "Bari, IT", "city": "Bari",
                  "country_code": "IT", "opening": opening, "closing": closing,
                  "provider": "nu-unbound", "scope": "neutrino",
                  "upcoming": upcoming_flag, "in_progress": upcoming_flag,
                  "flagship": True},
    }


# A record whose flags say "still upcoming" (as a stale cache entry would),
# but whose closing date is three weeks in the past.
_stale = _rec("Stale Cached Meeting", "2020-01-01", "2020-01-05", True)


def _fake_load_records(source, day=None):
    return {"indico": [_stale], "arxiv": [], "feeds": [], "inspire": []}.get(source, [])


_captured_render_conf_records: list[dict] = []


def _capturing_render_conferences(records, log, stamp=None):
    _captured_render_conf_records.extend(records)
    return True


def _noop_render_ok(*a, **k):
    return True


_orig_load_records = cache.load_records
_orig_latest_day_with = cache.latest_day_with
_orig_render_digest = render.digest
_orig_render_conferences = render.conferences
_orig_render_news = render.news
_orig_state_state = state.STATE
_orig_pipeline_state_ref = None  # pipeline imports the module, not the name

cache.load_records = _fake_load_records
cache.latest_day_with = lambda source, within_days=7: None
render.digest = _noop_render_ok
render.conferences = _capturing_render_conferences
render.news = _noop_render_ok
state.STATE = Path(tempfile.mkdtemp()) / "state.json"

try:
    rc = pipeline.run(dry_run=False, use_ai=False, do_build=False,
                      verbose=False, from_cache=True)
finally:
    cache.load_records = _orig_load_records
    cache.latest_day_with = _orig_latest_day_with
    render.digest = _orig_render_digest
    render.conferences = _orig_render_conferences
    render.news = _orig_render_news
    state.STATE = _orig_state_state

check("pipeline.run(from_cache=True) completes and reports ok", rc == 0, rc)
check("render.conferences was reached with at least the stale record",
      len(_captured_render_conf_records) == 1, _captured_render_conf_records)
_seen = _captured_render_conf_records[0] if _captured_render_conf_records else {}
check("the from_cache path recomputed the stale record's tense before render: "
      "extra.upcoming is now False, not the stale cached True",
      _seen.get("extra", {}).get("upcoming") is False, _seen.get("extra"))
check("in_progress was recomputed alongside it",
      _seen.get("extra", {}).get("in_progress") is False, _seen.get("extra"))


# --------------------------------------------------------------------------- #
# render.conferences failing must not take the whole run down, and must not
# stop render.news from still being attempted — the same "one bad step is
# logged and skipped, the rest of the run continues" contract every fetch
# step already has via pipeline._safe.
# --------------------------------------------------------------------------- #
_news_called = []


def _raising_render_conferences(records, log, stamp=None):
    raise RuntimeError("simulated render.conferences failure")


def _tracking_render_news(*a, **k):
    _news_called.append(True)
    return True


cache.load_records = _fake_load_records
cache.latest_day_with = lambda source, within_days=7: None
render.digest = _noop_render_ok
render.conferences = _raising_render_conferences
render.news = _tracking_render_news
state.STATE = Path(tempfile.mkdtemp()) / "state.json"

try:
    rc2 = pipeline.run(dry_run=False, use_ai=False, do_build=False,
                       verbose=False, from_cache=True)
except Exception as exc:                                      # noqa: BLE001
    rc2 = None
    _raised = exc
else:
    _raised = None
finally:
    cache.load_records = _orig_load_records
    cache.latest_day_with = _orig_latest_day_with
    render.digest = _orig_render_digest
    render.conferences = _orig_render_conferences
    render.news = _orig_render_news
    state.STATE = _orig_state_state

check("a raising render.conferences does not propagate out of pipeline.run",
      _raised is None, repr(_raised))
check("pipeline.run still returns its normal ok status despite the failed step",
      rc2 == 0, rc2)
check("render.news still ran after render.conferences failed",
      bool(_news_called), _news_called)


print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — from_cache tense refresh, render steps through _safe")
