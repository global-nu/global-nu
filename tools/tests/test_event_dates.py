#!/usr/bin/env python3
"""Conference dates checked against the organisers' own page.

    ./.venv/bin/python3 tools/tests/test_event_dates.py

No network: `http_get` is replaced with a stand-in serving JSON-LD extracted
from the real event pages on 19 October 2026 (tools/tests/data/eventdates/),
and the date cache lives in a temporary directory, never under var/.

It comes from DISCRETE 2026, published for days as 13–17 October — a month
early, and shown as already over — because Neutrino Unbound listed it so and
nothing ever read the date on the page the record linked to, which said
13–17 November. The other fixtures are the cases a naive check gets wrong:
NNN26 and Patras 2026, where the list gives the workshop days and the page
the whole event (correct, must not be touched), and LHCP 2027, whose dates
Indico's export API shifts by a day while the page's JSON-LD does not.
"""

from __future__ import annotations

import datetime as dt
import logging
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import eventdates                              # noqa: E402

DATA = ROOT / "tools" / "tests" / "data" / "eventdates"
TODAY = dt.date(2026, 10, 19)

problems: list[str] = []
checks = 0

log = logging.getLogger("news.test.eventdates")
log.addHandler(logging.NullHandler())
log.propagate = False


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
    else:
        problems.append(label)
        print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


def page(name: str) -> str:
    return (DATA / f"{name}.html").read_text(encoding="utf-8")


def jsonld(*nodes: str) -> str:
    return "".join(f'<script type="application/ld+json">{n}</script>' for n in nodes)


D = dt.date

# ------------------------------------------------------------------ parsing --
print("reading the page")
check("DISCRETE 2026: 13–17 November, from the real page",
      eventdates.dates_from_html(page("discrete-2026")) == (D(2026, 11, 13), D(2026, 11, 17)))
check("Patras 2026: 8–13 November in Perth's own time",
      eventdates.dates_from_html(page("patras-2026")) == (D(2026, 11, 8), D(2026, 11, 13)))
check("NNN26: 26–30 October",
      eventdates.dates_from_html(page("nnn26")) == (D(2026, 10, 26), D(2026, 10, 30)))
check("LHCP 2027: ends 4 June in Vancouver, not 5 June as the export API says",
      eventdates.dates_from_html(page("lhcp-2027")) == (D(2027, 5, 31), D(2027, 6, 4)))
check("an end at midnight closes the previous day",
      eventdates.dates_from_html(jsonld(
          '{"@type":"Event","startDate":"2027-07-12T08:00:00-04:00",'
          '"endDate":"2027-07-15T00:00:00-04:00"}')) == (D(2027, 7, 12), D(2027, 7, 14)))
check("a one-day meeting ending at midnight stays one day",
      eventdates.dates_from_html(jsonld(
          '{"@type":"Event","startDate":"2027-01-28T00:00:00+01:00",'
          '"endDate":"2027-01-28T00:00:00+01:00"}')) == (D(2027, 1, 28), D(2027, 1, 28)))
check("an Event subtype in a @type list counts",
      eventdates.dates_from_html(jsonld(
          '{"@type":["Thing","EducationEvent"],"startDate":"2027-01-11",'
          '"endDate":"2027-01-29"}')) == (D(2027, 1, 11), D(2027, 1, 29)))
check("two different Events on one page say nothing",
      eventdates.dates_from_html(jsonld(
          '{"@type":"Event","startDate":"2026-11-02","endDate":"2026-11-04"}',
          '{"@type":"Event","startDate":"2026-12-07","endDate":"2026-12-09"}')) is None)
check("sessions under subEvent do not compete with the event",
      eventdates.dates_from_html(jsonld(
          '{"@type":"Event","startDate":"2026-11-02","endDate":"2026-11-04",'
          '"subEvent":[{"@type":"Event","startDate":"2026-11-03"}]}'))
      == (D(2026, 11, 2), D(2026, 11, 4)))
check("an interval of months (a series page) says nothing",
      eventdates.dates_from_html(jsonld(
          '{"@type":"Event","startDate":"2026-01-01","endDate":"2026-12-31"}')) is None)
check("no JSON-LD, or broken JSON-LD, says nothing",
      eventdates.dates_from_html("<html><p>13-17 November 2026</p></html>") is None
      and eventdates.dates_from_html(jsonld("{not json")) is None)

check("months named in English, abbreviated, Italian and in figures",
      eventdates.months_named(
          "<p>Nov 13-17, 2026</p><p>13 novembre 2026</p><p>Deadline: 30.09.2026</p>"
          "<p>September 2026</p><script>var x='March 2026'</script>")
      == ["2026-09", "2026-11"])
check("'September 21 to 26, 2026' names September (school.lomcon.ru)",
      eventdates.months_named("<p>from September 21 to 26, 2026.</p>") == ["2026-09"])

# ------------------------------------------------------------------- check --
def rec(rid: str, url: str, start: str, end: str, provider: str = "nu-unbound") -> dict:
    return {"id": rid, "title": rid, "url": url, "date": start,
            "extra": {"opening": start, "closing": end, "provider": provider,
                      "span": "as listed"}}


PAGES = {"https://conference.uniba.sk/event/2/": page("discrete-2026"),
         "https://indico.global/event/16402/": page("patras-2026"),
         "https://indico.neutrino.or.kr/event/514/": page("nnn26"),
         "https://indico.cern.ch/event/1689315/": page("lhcp-2027"),
         # No JSON-LD: only prose, as on hand-made conference sites.
         "https://example.org/wrong-month": "<h1>School</h1><p>9-13 November 2026"
                                            "</p><p>Apply by 1 September 2026</p>",
         "https://example.org/right-month": "<p>26 - 30 October 2026</p>",
         "https://example.org/last-year": "<p>The 2025 edition: 6-10 October 2025</p>",
         "https://example.org/no-text": "<div id='app'></div>",
         # A past meeting's page, naming only its deadlines (Clusters26).
         "https://example.org/deadlines": "<p>Abstract Submission Deadline: 6 March 2026</p>"
                                          "<p>Registration Deadline: 28 May 2026</p>",
         # A link that lands on the previous edition's Indico page.
         "https://example.org/old-edition": jsonld(
             '{"@type":"Event","startDate":"2025-10-06T09:00:00+02:00",'
             '"endDate":"2025-10-10T13:00:00+02:00"}'),
         # The start of what agenda.infn.it sent once its bot check woke up.
         "https://agenda.infn.it/event/50802/":
             "<!doctype html><html lang=\"en\"><head><title>Making sure you&#39;re "
             "not a bot!</title><link rel=\"stylesheet\" "
             "href=\"/.within.website/x/xess/xess.min.css\">"}
fetched: list[str] = []


class _Resp:
    status_code = 200

    def __init__(self, text):
        self.text = text


def fake_get(url, **_):
    fetched.append(url)
    return _Resp(PAGES[url]) if url in PAGES else None


def records() -> list[dict]:
    return [rec("discrete", "https://conference.uniba.sk/event/2/", "2026-10-13", "2026-10-17"),
            rec("patras", "https://indico.global/event/16402/", "2026-11-09", "2026-11-13"),
            rec("nnn", "https://indico.neutrino.or.kr/event/514/", "2026-10-28", "2026-10-30"),
            rec("lhcp", "https://indico.cern.ch/event/1689315/", "2027-05-31", "2027-06-05",
                provider="indico"),
            rec("down", "https://soup2026.ca.infn.it/", "2026-10-26", "2026-10-30"),
            rec("inspire", "https://inspirehep.net/conferences/3198870",
                "2027-02-15", "2027-02-19", provider=""),
            rec("wrong", "https://example.org/wrong-month", "2026-10-12", "2026-10-16"),
            rec("right", "https://example.org/right-month", "2026-10-26", "2026-10-30"),
            rec("lastyear", "https://example.org/last-year", "2026-10-05", "2026-10-09"),
            rec("notext", "https://example.org/no-text", "2026-10-05", "2026-10-09"),
            rec("anubis", "https://agenda.infn.it/event/50802/", "2026-10-11", "2026-10-22"),
            rec("edition", "https://example.org/old-edition", "2026-10-05", "2026-10-09"),
            rec("deadlines", "https://example.org/deadlines", "2026-06-08", "2026-06-12")]


tmp = Path(tempfile.mkdtemp())
eventdates.DATE_CACHE = tmp / "datecache.json"
eventdates.http_get = fake_get

print("\nchecking records against their pages")
recs = records()
found = eventdates.check(recs, log, today=TODAY)
by = {r["id"]: r for r in recs}
check("DISCRETE is corrected to the page's 13–17 November",
      by["discrete"]["extra"]["opening"] == "2026-11-13"
      and by["discrete"]["extra"]["closing"] == "2026-11-17"
      and by["discrete"]["date"] == "2026-11-13"
      and by["discrete"]["extra"]["span"] == "13–17 November 2026",
      str(by["discrete"]))
check("… and remembers what the list said",
      by["discrete"]["extra"]["dates_from_page"] == {"listed": ["2026-10-13", "2026-10-17"]})
check("Patras keeps the list's 9–13 November (inside the page's 8–13)",
      by["patras"]["extra"]["opening"] == "2026-11-09"
      and "dates_from_page" not in by["patras"]["extra"])
check("NNN26 keeps the list's 28–30 October (inside the page's 26–30)",
      by["nnn"]["extra"]["opening"] == "2026-10-28")
check("LHCP's day-late export date is pulled back to 4 June",
      by["lhcp"]["extra"]["closing"] == "2027-06-04")
check("exactly DISCRETE and LHCP are corrected",
      sorted(f["id"] for f in found if f["kind"] == "corrected")
      == ["discrete", "lhcp"], str(found))
check("a page a year off is another edition: SUSPECT, left as listed",
      by["edition"]["extra"]["opening"] == "2026-10-05"
      and [f["why"] for f in found if f["id"] == "edition"] == ["the page is about"])
check("a prose page naming only other months of the year is SUSPECT",
      [f["id"] for f in found if f["kind"] == "suspect" and f["id"] != "edition"]
      == ["wrong"]
      and [f for f in found if f["id"] == "wrong"][0]["page"] == ["2026-09", "2026-11"],
      str(found))
check("… and its dates are left exactly as listed",
      by["wrong"]["extra"]["opening"] == "2026-10-12"
      and "dates_from_page" not in by["wrong"]["extra"])
check("a meeting months over is not doubted for naming only its deadlines",
      not any(f["id"] == "deadlines" for f in found))
check("prose naming the listed month, only last year, or nothing raises nothing",
      not {"right", "lastyear", "notext"} & {f["id"] for f in found})
check("an unreachable page leaves the record alone",
      by["down"]["extra"]["opening"] == "2026-10-26")
check("INSPIRE's fallback pages are never fetched",
      not any("inspirehep.net" in u for u in fetched))
cache = eventdates.read_json(eventdates.DATE_CACHE, {})
check("a failed fetch is not cached, so tomorrow tries again",
      "https://soup2026.ca.infn.it/" not in cache)
check("nor is a bot-check page, which would pass for a page without dates",
      "https://agenda.infn.it/event/50802/" not in cache
      and not any(f["id"] == "anubis" for f in found))

check("corrected DISCRETE is upcoming again, not 'recent'",
      by["discrete"]["extra"].get("upcoming") is True
      and by["discrete"]["extra"].get("in_progress") is False,
      str(by["discrete"]["extra"]))

print("\nthe cache")
fetched.clear()
eventdates.check(records(), log, today=TODAY + dt.timedelta(days=3))
check("within RECHECK_DAYS nothing reachable is fetched again",
      sorted(fetched) == ["https://agenda.infn.it/event/50802/",
                          "https://soup2026.ca.infn.it/"], str(fetched))
fetched.clear()
eventdates.check(records(), log, today=TODAY + dt.timedelta(days=8))
check("after RECHECK_DAYS every page is read again", len(fetched) == 12, str(fetched))
fetched.clear()
offline = records()
eventdates.check(offline, log, offline=True, today=TODAY + dt.timedelta(days=60))
check("offline: no request, cached dates still applied",
      fetched == [] and offline[0]["extra"]["opening"] == "2026-11-13")

print("\nthe mail")
sent: list[tuple[str, str]] = []
first = eventdates.notify(found, {}, log, send=lambda s, b: sent.append((s, b)))
check("the first sighting is mailed", len(first) == 4 and len(sent) == 1)
check("the mail names the conference, both intervals and the page",
      "listed (nu-unbound): 2026-10-13 – 2026-10-17" in sent[0][1]
      and "event page:  2026-11-13 – 2026-11-17" in sent[0][1]
      and "https://conference.uniba.sk/event/2/" in sent[0][1])
check("the suspect is in the same mail, under TO CHECK, with the months seen",
      "TO CHECK" in sent[0][1]
      and "months the page names: 2026-09, 2026-11" in sent[0][1]
      and "the page is about: 2025-10-06 – 2025-10-10" in sent[0][1]
      and "2 to check" in sent[0][0] and "2 corrected" in sent[0][0], sent[0][0])
again = eventdates.notify(found, {}, log, send=lambda s, b: sent.append((s, b)))
check("the same correction the next day is not mailed again",
      again == [] and len(sent) == 1)
moved = [dict(found[0], page=["2026-11-20", "2026-11-24"])]
check("a page that changes its dates again is mailed again",
      len(eventdates.notify(moved, {}, log, send=lambda s, b: sent.append((s, b)))) == 1)


def broken(*_):
    raise OSError("smtp down")


fresh = [dict(found[0], id="other")]
check("a mail that fails is not marked as sent",
      eventdates.notify(fresh, {}, log, send=broken) == []
      and len(eventdates.notify(fresh, {}, log,
                                send=lambda s, b: sent.append((s, b)))) == 1)

print()
if problems:
    print(f"{len(problems)} of {checks} checks FAIL")
    sys.exit(1)
print(f"all {checks} checks pass — dates read from the organisers' page")
