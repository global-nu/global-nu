#!/usr/bin/env python3
"""Landmark news (a Nobel prize…) can never be missed, buried or late.

    ./.venv/bin/python3 tools/tests/test_news_landmark.py

On 6 October 2026 Francis Halzen won the Nobel Prize in Physics for IceCube
and on the morning of the 7th the news page did not say so: the daily run had
fired four hours before the announcement, and nothing in the pipeline would
have put the story first even once it arrived. See tools/news/landmark.py.

No network, no AI call: the feed fetch and the pipeline run are replaced.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import fetch_feeds, landmark, pipeline, synthesize  # noqa: E402

PASS, FAIL = "\033[32mok  \033[0m", "\033[31mFAIL\033[0m"
_results: list[tuple[bool, str]] = []
# Not get_logger("news.test"): that one writes into the real news.log, and
# this file's fake Nobel records would read there as real alarms.
log = logging.getLogger("landmark-test")
log.addHandler(logging.NullHandler())
log.propagate = False
TODAY = _dt.date.today()
CFG = {"landmarks": {"enabled": True, "pin_days": 7}}
SECTIONS = [{"key": "experiments", "max": 10, "kind": "news"},
            {"key": "theory", "max": 6, "kind": "paper"}]


def check(cond: bool, name: str, detail: str = "") -> None:
    _results.append((bool(cond), name))
    print(f"  [{PASS if cond else FAIL}] {name}" + (f"   {detail}" if detail else ""))


def rec(i, title, days=0, summary="Neutrinos from the cosmos. More text."):
    return {"id": f"feed:x:{i}", "source": "feed", "title": title,
            "url": f"https://example.org/{i}", "authors": "X",
            "date": (TODAY - _dt.timedelta(days=days)).isoformat(),
            "summary": summary, "extra": {"feed": "X", "weight": 1}}


NOBEL = "Francis Halzen, IceCube principal investigator, wins 2026 Physics Nobel Prize"


def test_tag_reads_the_title_not_the_summary():
    a = rec(1, NOBEL)
    b = rec(2, "Halzen, Nobel 2026")
    c = rec(3, "KM3NeT news", summary="Nobel laureate Takaaki Kajita commented.")
    landmark.tag([a, b, c], CFG)
    check(a["extra"].get("landmark") and b["extra"].get("landmark"),
          "a Nobel in the title is a landmark (both spellings)")
    check(not c["extra"].get("landmark"),
          "a Nobel laureate quoted in the summary is not")


def test_pin_survives_the_cap_and_ages_out():
    recs = [rec(i, f"Ordinary item {i}") for i in range(12)]
    recs.append(rec(99, NOBEL, days=1))
    old = rec(98, "Breakthrough Prize to someone", days=20)
    recs.append(old)
    landmark.tag(recs, CFG)
    out = landmark.pin(recs, CFG, 10)
    check(out[0]["id"] == "feed:x:99" and len(out) == 10,
          "a fresh landmark leads and the cap still holds")
    check(old not in out[:1], "a landmark older than pin_days is not pinned")


def test_feed_cap_cannot_drop_a_landmark():
    items = "".join(
        f"<item><title>Neutrino item {i}</title><link>https://e.org/{i}</link>"
        f"<pubDate>{(TODAY).strftime('%a, %d %b %Y')} 10:00:00 +0000</pubDate>"
        f"<description>neutrino</description></item>" for i in range(8))
    items += (f"<item><title>{NOBEL}</title><link>https://e.org/nobel</link>"
              f"<pubDate>{(TODAY - _dt.timedelta(days=1)).strftime('%a, %d %b %Y')}"
              " 10:00:00 +0000</pubDate><description>IceCube neutrino"
              "</description></item>")
    xml = f"<rss><channel>{items}</channel></rss>".encode()

    class R:
        content = xml
    orig = fetch_feeds.http_get
    fetch_feeds.http_get = lambda *a, **k: R()
    try:
        out = fetch_feeds._fetch_source(
            {"name": "IceCube", "url": "https://e.org/feed"},
            pats=fetch_feeds._keyword_patterns(["neutrino"]), window_days=45,
            per_feed_max=2, timeout=5, log=log, errors=[], cfg=CFG)
    finally:
        fetch_feeds.http_get = orig
    check(any(r["url"] == "https://e.org/nobel" for r in out),
          "the per-feed cap keeps the landmark", f"{len(out)} kept")


def test_enforce_writes_the_missing_item_from_the_record():
    lm = rec(1, NOBEL, summary="Halzen led IceCube. It found cosmic neutrinos. "
                               "A third sentence.")
    landmark.tag([lm], CFG)
    narrative = {"overview": "JUNO reported new results.",
                 "experiments": [{"heading": "JUNO", "text": "t",
                                  "ids": ["feed:x:5"]}], "theory": []}
    out = landmark.enforce(narrative, [lm], CFG, SECTIONS, log)
    first = out["experiments"][0]
    check(first["ids"] == ["feed:x:1"], "the landmark leads Experiments")
    check(first["text"] == "Halzen led IceCube. It found cosmic neutrinos.",
          "its text is the record's own first sentences", repr(first["text"]))
    check("Nobel" in out["overview"].split(".")[0],
          "the overview opens with it", out["overview"][:60])
    check(len(out["experiments"]) == 2, "nothing else was dropped")


def test_enforce_moves_the_models_item_and_does_not_duplicate():
    lms = [rec(1, NOBEL), rec(2, "Halzen, Nobel 2026"),
           rec(3, "Nobel Prize in physics awarded to Francis Halzen")]
    landmark.tag(lms, CFG)
    narrative = {"overview": "Francis Halzen won the Nobel prize.",
                 "experiments": [
                     {"heading": "JUNO", "text": "a", "ids": ["feed:x:7"]},
                     {"heading": "KM3NeT", "text": "b", "ids": ["feed:x:8"]},
                     {"heading": "Nobel", "text": "c", "ids": ["feed:x:2"]}]}
    out = landmark.enforce(narrative, lms, CFG, SECTIONS, log)
    exp = out["experiments"]
    check(exp[0]["heading"] == "Nobel" and len(exp) == 3,
          "the model's own item is moved first, three outlets stay one item")
    check(out["overview"] == "Francis Halzen won the Nobel prize.",
          "an overview that names it is left alone")


def test_enforce_without_any_narrative():
    lm = rec(1, NOBEL)
    landmark.tag([lm], CFG)
    out = landmark.enforce(None, [lm], CFG, SECTIONS, log)
    check(out and out["experiments"][0]["ids"] == ["feed:x:1"],
          "a failed AI call still publishes the landmark")


def test_prompt_announces_it():
    lm = rec(1, NOBEL)
    landmark.tag([lm], CFG)
    p = synthesize.build_prompt(CFG, [lm], [])
    i, j = p.find("Landmark news"), p.rfind("## Output")
    check(0 <= i < j and "feed:x:1" in p[i:j],
          "the prompt names the landmark before the Output section")


def test_hourly_check_is_silent_and_fires_once():
    lm = rec(1, NOBEL)
    calls = []
    orig = (fetch_feeds.fetch, pipeline.run, pipeline.state.load,
            pipeline.load_config, pipeline.get_logger)
    pipeline.load_config = lambda: CFG
    # Never the real logger: a test that writes "landmark: not yet on the
    # page" into var/news/…/news.log plants a false alarm in the log a person
    # reads on the day something goes wrong. It happened, once, on 7 Oct 2026.
    pipeline.get_logger = lambda *a, **k: log
    pipeline.run = lambda **k: calls.append(k) or 0

    class A:
        dry_run = no_ai = no_build = False
        quiet = True
    try:
        fetch_feeds.fetch = lambda cfg, log: [rec(2, "Ordinary")]
        pipeline.state.load = lambda: {"landmarks_published": []}
        pipeline.landmark_check(A())
        check(calls == [], "no landmark: no run")

        fetch_feeds.fetch = lambda cfg, log: [dict(lm, extra=dict(lm["extra"]))]
        pipeline.landmark_check(A())
        check(len(calls) == 1 and calls[0]["do_build"],
              "a new landmark starts a full run with build (and push)")

        pipeline.state.load = lambda: {"landmarks_published": ["feed:x:1"]}
        pipeline.landmark_check(A())
        check(len(calls) == 1, "an already published landmark does not")
    finally:
        (fetch_feeds.fetch, pipeline.run, pipeline.state.load,
         pipeline.load_config, pipeline.get_logger) = orig


def test_the_wiring_is_real():
    """A mock hides the wiring: the real config and the real plist must agree."""
    import yaml
    cfg = yaml.safe_load((ROOT / "tools/news/config.yaml")
                         .read_text(encoding="utf-8"))
    names = {s["name"] for s in cfg["feeds"]["sources"] if s.get("enabled")}
    check({"Physics World", "IceCube"} <= names,
          "Physics World and IceCube are enabled feeds")
    check(landmark.enabled(cfg), "landmarks are on in config.yaml")
    import plistlib
    pl = plistlib.loads((ROOT / "tools/news/launchd/"
                         "org.global-nu.landmark-watch.plist.template").read_bytes())
    check("--if-landmark" in pl["ProgramArguments"]
          and pl.get("StartInterval") == 3600
          and "StartCalendarInterval" not in pl and not pl.get("RunAtLoad")
          and "StandardOutPath" not in pl,
          "the watch agent: --if-landmark, hourly, no RunAtLoad, no sink")
    inst = (ROOT / "tools/news/install-launchagent.sh").read_text()
    check("org.global-nu.landmark-watch" in inst,
          "the installer installs the watch agent")


def main() -> int:
    for fn in (test_tag_reads_the_title_not_the_summary,
               test_pin_survives_the_cap_and_ages_out,
               test_feed_cap_cannot_drop_a_landmark,
               test_enforce_writes_the_missing_item_from_the_record,
               test_enforce_moves_the_models_item_and_does_not_duplicate,
               test_enforce_without_any_narrative,
               test_prompt_announces_it,
               test_hourly_check_is_silent_and_fires_once,
               test_the_wiring_is_real):
        fn()
    failed = [n for ok, n in _results if not ok]
    print(f"\n{len(_results) - len(failed)}/{len(_results)} checks passed")
    for n in failed:
        print("  - " + n)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
