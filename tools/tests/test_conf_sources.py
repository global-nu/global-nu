#!/usr/bin/env python3
"""The conference calendar's sources: the INSPIRE sweep, and ageing.

    ./.venv/bin/python3 tools/tests/test_conf_sources.py

No network: `http_get` and `cache.store` are replaced with stand-ins, so this
touches neither INSPIRE nor the project's real cache under var/.

Three things are tested, and all three come from a real failure.

1. THE SWEEP IS BOUNDED. INSPIRE's conference collection holds tens of
   thousands of records. An unbounded loop over a collection that size is how
   a morning job becomes a morning outage — and INSPIRE would be the one
   paying for it. The page cap must hold even when the dates never stop the
   loop, and the loop must stop on its own as soon as it has passed the
   window.

2. THE SWEEP DOES NOT REPLACE THE QUERY. The two are UNIONED and deduplicated
   on `control_number`. If the sweep breaks — a changed payload, a bad page —
   the page must be exactly what it was before. And the query's own records do
   NOT pass through the topic filter: that filter exists for the thousand
   swept records, not for a source that was already asked a question encoding
   relevance.

3. A SOURCE THAT GOES DOWN MUST AGE, NOT VANISH. nu.to.infn.it has answered
   ConnectTimeout since 9 September 2026. Nothing recovered the conference
   sources from cache, so its 63 records did not get older — they disappeared,
   and the merged listing fell from 84 events (var/news/cache/2026-09-08/
   indico.json) to 29 (2026-09-12) with nothing saying so.
"""

from __future__ import annotations

import datetime as dt
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import cache, fetch_inspire, pipeline            # noqa: E402

problems: list[str] = []
checks = 0

log = logging.getLogger("news.test.sources")
log.addHandler(logging.NullHandler())
log.propagate = False
log.setLevel(logging.DEBUG)


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
    else:
        problems.append(label)
        print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


class _Recording(logging.Handler):
    """Captures the log lines: here the message IS the behaviour."""

    def __init__(self):
        super().__init__()
        self.lines: list[tuple[int, str]] = []

    def emit(self, record):
        self.lines.append((record.levelno, record.getMessage()))

    def says(self, *bits: str) -> bool:
        return any(all(b in msg for b in bits) for _, msg in self.lines)


def _recorder(name: str) -> tuple[logging.Logger, _Recording]:
    rec = logging.getLogger(name)
    rec.propagate = False
    rec.setLevel(logging.DEBUG)
    h = _Recording()
    rec.handlers = [h]
    return rec, h


# --------------------------------------------------------------------------- #
# stand-ins
# --------------------------------------------------------------------------- #
class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _hit(recid: int, opening: str, title: str, acronym: str = "",
         closing: str = "") -> dict:
    return {"metadata": {
        "control_number": recid,
        "opening_date": opening,
        "closing_date": closing or opening,
        "titles": [{"title": title}],
        "acronyms": [acronym] if acronym else [],
        "addresses": [{}],
        "urls": [],
    }}


_real_http_get = fetch_inspire.http_get
_real_store = cache.store


def _install(http_get, store) -> None:
    fetch_inspire.http_get = http_get                            # type: ignore
    cache.store = store                                          # type: ignore


def _restore() -> None:
    fetch_inspire.http_get = _real_http_get                      # type: ignore
    cache.store = _real_store                                    # type: ignore


# --------------------------------------------------------------------------- #
# 1. the sweep is bounded
# --------------------------------------------------------------------------- #
print("1. the sweep is bounded")

calls: list = []


def _endless(url, **kw):
    calls.append(kw.get("params", {}).get("page"))
    # Every page pretends its dates are inside the window: without the cap
    # this loop would never end.
    return _Resp({"hits": {"hits": [_hit(1000 + len(calls), "2027-01-01",
                                         "Something")]}})


fetch_inspire.http_get = _endless                                # type: ignore
fetch_inspire._SWEEP_CACHE.clear()
rec, h = _recorder("news.test.bound")
try:
    hits = fetch_inspire._sweep_hits({"sweep": {"max_pages": 3, "size": 5}},
                                     rec, dt.date(2026, 4, 15))
finally:
    _restore()
check("the loop stops at the page cap", len(calls) == 3,
      f"{len(calls)} pages requested, cap 3")
check("and returns what it collected", len(hits) == 3, str(len(hits)))
check("and WARNS that the window was not reached: a silent truncation would "
      "stay silent forever", h.says("page cap"))

pages = {
    1: [_hit(1, "2027-06-01", "Future"), _hit(2, "2026-06-01", "Recent")],
    2: [_hit(3, "2026-05-01", "Older"), _hit(4, "2025-01-01", "Ancient")],
    3: [_hit(5, "2024-01-01", "Prehistoric")],
}
seen: list = []


def _paged(url, **kw):
    p = kw.get("params", {}).get("page")
    seen.append(p)
    return _Resp({"hits": {"hits": pages.get(p, [])}})


fetch_inspire.http_get = _paged                                  # type: ignore
fetch_inspire._SWEEP_CACHE.clear()
try:
    hits = fetch_inspire._sweep_hits({"sweep": {"max_pages": 6, "size": 2}},
                                     log, dt.date(2026, 4, 15))
finally:
    _restore()
check("it stops at the page that passes the start of the window, without "
      "asking for a third", seen == [1, 2], str(seen))
check("and keeps every page it did ask for", len(hits) == 4, str(len(hits)))

fetch_inspire._SWEEP_CACHE.clear()
check("`sweep.enabled: false` makes no request at all",
      fetch_inspire._sweep_hits({"sweep": {"enabled": False}}, log,
                                dt.date(2026, 4, 15)) == [])


def _broken(url, **kw):
    if kw.get("params", {}).get("page") == 1:
        return _Resp({"hits": {"hits": [_hit(1, "2027-01-01", "Good")]}})
    return _Resp({"changed": "shape"})            # no hits.hits


fetch_inspire.http_get = _broken                                 # type: ignore
fetch_inspire._SWEEP_CACHE.clear()
rec, h = _recorder("news.test.broken")
try:
    hits = fetch_inspire._sweep_hits({"sweep": {"max_pages": 4, "size": 1}},
                                     rec, dt.date(2026, 4, 15))
finally:
    _restore()
check("what was collected before a bad payload is kept", len(hits) == 1,
      str(len(hits)))
check("and the log says the keyword query still answers",
      h.says("keyword query still answers"))

fetch_inspire.http_get = lambda url, **kw: None                  # type: ignore
fetch_inspire._SWEEP_CACHE.clear()
try:
    check("an unreachable API makes the sweep return [], not raise",
          fetch_inspire._sweep_hits({"sweep": {}}, log,
                                    dt.date(2026, 4, 15)) == [])
finally:
    _restore()

# --------------------------------------------------------------------------- #
# 2. the union, and the filter that applies to swept records only
# --------------------------------------------------------------------------- #
print("\n2. the union of query and sweep")

TODAY = dt.date.today()
SOON = (TODAY + dt.timedelta(days=40)).isoformat()


def _run_fetch(keyword_hits, sweep_pages, cfg_extra=None):
    """fetch_conferences with the network faked. -> (records, log, stored)."""
    stored: dict = {}

    def fake_store(source, records, errors=None, day=None):
        stored[source] = (list(records), list(errors or []))
        return Path("/dev/null")

    def fake(url, **kw):
        params = kw.get("params", {})
        if "page" in params:
            return _Resp({"hits": {"hits": sweep_pages.get(params["page"], [])}})
        return _Resp({"hits": {"hits": keyword_hits}})

    cfg = {"inspire": {"enabled": True, "conferences": {
        "query": "neutrino", "upcoming_months": 18, "recent_months": 5,
        "max_fetch": 250, "sweep": {"max_pages": 2, "size": 50},
        **(cfg_extra or {})}}}
    rec, h = _recorder("news.test.union")
    _install(fake, fake_store)
    fetch_inspire._SWEEP_CACHE.clear()
    try:
        out = fetch_inspire.fetch_conferences(cfg, rec, scope="neutrino")
    finally:
        _restore()
        fetch_inspire._SWEEP_CACHE.clear()
    return out, h, stored


# This record is `unknown` to the classifier: an unreadable title, no acronym.
# Found by the query it stays; found by the sweep it is dropped. That is the
# distinction the comment in fetch_inspire.py describes, and the only thing
# stopping the filter from quietly narrowing a source that already works.
unreadable = _hit(4242, SOON, "5th Workshop")

out, h, _ = _run_fetch([unreadable], {})
check("a record from the QUERY survives even when the classifier cannot "
      "read it", any(r["id"] == "conf:4242" for r in out), f"{len(out)} records")

out, h, _ = _run_fetch([], {1: [unreadable]})
check("the same record, arriving from the SWEEP, is dropped",
      not any(r["id"] == "conf:4242" for r in out), f"{len(out)} records")
check("and the count of dropped records reaches the log",
      h.says("dropped as off-topic"))

out, _, _ = _run_fetch([], {1: [
    _hit(1, SOON, "XXII International Workshop on Neutrino Telescopes",
         "Neutel 27"),
    _hit(2, SOON, "Dark Matter 2027: From the Smallest to the Largest"),
    _hit(3, SOON, "33rd Workshop on Deep Inelastic Scattering", "DIS2027"),
]})
ids = {r["id"] for r in out}
check("the sweep brings in a `core` record (Neutel 27)", "conf:1" in ids)
check("and a `related` one (Dark Matter 2027)", "conf:2" in ids)
check("but not an `adjacent` one (DIS2027)", "conf:3" not in ids,
      str(sorted(ids)))

same = _hit(77, SOON, "25th Workshop on Neutrino Detectors", "NNN27")
out, h, _ = _run_fetch([same], {1: [same]})
check("the same control_number never appears twice", len(out) == 1,
      f"{len(out)} records")
check("and the log says how many came from the keyword query",
      h.says("1 from the keyword query"))


def _dead_sweep(url, **kw):
    if "page" in kw.get("params", {}):
        return None
    return _Resp({"hits": {"hits": [
        _hit(9, SOON, "Neutrino Oscillation Workshop", "NOW 2027")]}})


stored: dict = {}
cfg = {"inspire": {"enabled": True, "conferences": {
    "query": "neutrino", "upcoming_months": 18, "recent_months": 5,
    "sweep": {"max_pages": 2, "size": 50}}}}
_install(_dead_sweep,
         lambda s, r, errors=None, day=None: stored.setdefault(
             s, (list(r), list(errors or []))))
fetch_inspire._SWEEP_CACHE.clear()
try:
    out = fetch_inspire.fetch_conferences(cfg, log, scope="neutrino")
finally:
    _restore()
    fetch_inspire._SWEEP_CACHE.clear()
check("sweep dead, query alive: the page is what it was before the sweep "
      "existed", len(out) == 1 and out[0]["id"] == "conf:9", f"{len(out)} records")

# The two calls per run (the neutrino block and `general`) must share one
# sweep: without the memo the run pages INSPIRE twice for identical bytes.
paged: list = []


def _counting(url, **kw):
    p = kw.get("params", {}).get("page")
    if p is not None:
        paged.append(p)
        return _Resp({"hits": {"hits": [_hit(1, "2025-01-01", "Ancient")]}})
    return _Resp({"hits": {"hits": []}})


cfg = {"inspire": {"enabled": True, "conferences": {
    "query": "x", "upcoming_months": 18, "recent_months": 5,
    "sweep": {"max_pages": 3, "size": 10},
    "general": {"query": "y", "upcoming_months": 18, "recent_months": 5,
                "series_hints": ["ICHEP"]}}}}
_install(_counting, lambda s, r, errors=None, day=None: None)
fetch_inspire._SWEEP_CACHE.clear()
try:
    fetch_inspire.fetch_conferences(cfg, log, scope="neutrino")
    first = len(paged)
    fetch_inspire.fetch_conferences(cfg, log, scope="general")
    total = len(paged)
finally:
    _restore()
    fetch_inspire._SWEEP_CACHE.clear()
check("the second call reuses the sweep instead of paging INSPIRE again",
      first == 1 and total == 1,
      f"{first} page the first time, {total} in all")

# --------------------------------------------------------------------------- #
# 3. a source that goes down ages instead of vanishing
# --------------------------------------------------------------------------- #
print("\n3. cache recovery for every conference source")

old = [{"id": "nu:1", "source": "inspire-conf", "title": "T",
        "url": "https://x.example/1", "links": {}, "authors": "",
        "date": "2026-10-01", "summary": "", "extra": {}}]
day = dt.date(2026, 9, 8)

_real_latest, _real_load = cache.latest_day_with, cache.load_records
cache.latest_day_with = lambda s, within_days=7: day              # type: ignore
cache.load_records = lambda s, d=None: list(old)                  # type: ignore
rec, h = _recorder("news.test.recover")
try:
    out = pipeline._recover_conferences(
        "nu-unbound", [], {"conferences_nu_unbound": {"enabled": True}},
        "conferences_nu_unbound", rec)
    check("a source that is empty today comes back from its last useful day",
          len(out) == 1, f"{len(out)} records")
    check("and the record keeps its OWN date: nothing is presented as fresher "
          "than it is", out[0]["date"] == "2026-10-01", out[0]["date"])
    check("the log NAMES the source and the day it is fishing from",
          h.says("nu-unbound", "cached on 2026-09-08"))
    check("and says it at WARNING, not buried among the INFO lines",
          any(lvl >= logging.WARNING for lvl, _ in h.lines))

    # All four conference sources, not just the one that went down.
    for source, key in (("indico-conf", "conferences_indico"),
                        ("inspire-conf", "inspire"),
                        ("inspire-conf-general", "inspire")):
        h.lines.clear()
        out = pipeline._recover_conferences(source, [],
                                            {key: {"enabled": True}}, key, rec)
        check(f"it covers {source} too", len(out) == 1, f"{len(out)} records")

    # A source switched off by hand must not come back from the dead.
    h.lines.clear()
    out = pipeline._recover_conferences(
        "nu-unbound", [], {"conferences_nu_unbound": {"enabled": False}},
        "conferences_nu_unbound", rec)
    check("a DISABLED source is not fished back: switching it off has to mean "
          "something", out == [])

    # And a successful fetch is passed through untouched, cache unread.
    alive = [{"id": "today"}]
    check("a successful fetch passes through intact, without reading the cache",
          pipeline._recover_conferences("nu-unbound", alive, {},
                                        "conferences_nu_unbound", rec) is alive)
finally:
    cache.latest_day_with, cache.load_records = _real_latest, _real_load

cache.latest_day_with = lambda s, within_days=7: None             # type: ignore
rec, h = _recorder("news.test.nocache")
try:
    out = pipeline._recover_conferences("nu-unbound", [], {},
                                        "conferences_nu_unbound", rec)
finally:
    cache.latest_day_with = _real_latest
check("nothing in the cache: no record is invented", out == [])
check("«empty with nothing cached» and «empty but recovered» are two different "
      "pieces of news and read differently", h.says("nothing cached"))

# --------------------------------------------------------------------------- #
# 4. the configuration all of this assumes
# --------------------------------------------------------------------------- #
print("\n4. the configuration")

import yaml                                                      # noqa: E402

cfg = yaml.safe_load((ROOT / "tools/news/config.yaml").read_text(encoding="utf-8"))
conf = cfg["inspire"]["conferences"]
sweep = conf.get("sweep") or {}
check("config.yaml switches the sweep on", sweep.get("enabled") is True)
check(f"and asks for a page inside INSPIRE's maximum "
      f"({fetch_inspire.INSPIRE_MAX_SIZE})",
      0 < int(sweep.get("size", 0)) <= fetch_inspire.INSPIRE_MAX_SIZE,
      str(sweep.get("size")))
check("and puts a real cap on the pages",
      0 < int(sweep.get("max_pages", 0)) <= 20, str(sweep.get("max_pages")))

# The window the sweep exists to fill, and the cap that keeps the tail it
# drags in from taking the page over.
check("the forward window is 18 months, the same horizon every other "
      "conference source uses",
      int(conf.get("upcoming_months", 0)) == 18
      and int((cfg.get("conferences_indico") or {}).get("upcoming_months", 0)) == 18
      and int((cfg.get("conferences_nu_unbound") or {}).get("upcoming_months", 0)) == 18
      and int((conf.get("general") or {}).get("upcoming_months", 0)) == 18,
      str(conf.get("upcoming_months")))
check("and the concluded tail has a ceiling",
      0 < int(conf.get("max_recent", 0)) <= 12, str(conf.get("max_recent")))

hosts = {s["host"]: s.get("enabled", True)
         for s in cfg["conferences_indico"]["sources"]}
# Hosts that do not answer must not creep in by inattention.
for dead in ("indico.fnal.gov", "indico.kek.jp", "indico.ictp.it",
             "agenda.infn.it"):
    check(f"config.yaml does not query {dead}", not hosts.get(dead, False),
          str(hosts.get(dead)))
# agenda.infn.it in particular: it answers 200 with an anti-bot interstitial,
# and that is a "no" this project honours rather than works around.
for expected in ("indico.in2p3.fr", "indico.ihep.ac.cn", "indico.nikhef.nl",
                 "indico.ph.tum.de"):
    check(f"config.yaml queries {expected} (probed: it brings records)",
          hosts.get(expected) is True)
for off in ("indico.desy.de", "indico.ego-gw.it"):
    check(f"config.yaml leaves {off} switched off (probed: no records)",
          hosts.get(off) is False)

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    for p in problems:
        print("    - " + p)
    sys.exit(1)
print(f"all {checks} checks pass — a bounded sweep, a union, and sources that age")
