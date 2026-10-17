#!/usr/bin/env python3
"""Facets, grouping and calendar export of the conference page.

    ./.venv/bin/python3 tools/tests/test_conf_facets.py

The grouping is the risky part: a wrong fold hides a meeting under another
meeting's name. These cases pin the conservative rule in
tools/news/conferences.group_related.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.news import conferences as cm  # noqa: E402


def ev(i, title, opening, closing, cc="US", city="Irvine", acronym=""):
    return {"id": i, "title": title, "url": f"https://x/{i}",
            "extra": {"opening": opening, "closing": closing, "country_code": cc,
                      "city": city, "acronym": acronym, "place": f"{city}, {cc}"}}


bad = []


def check(label, ok):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")
    if not ok:
        bad.append(label)


check("kind: school wins over workshop", cm.kind_of({"title": "Summer School and Workshop on Neutrinos"}) == "school")
check("kind: conference", cm.kind_of({"title": "XXXII International Conference on Neutrino Physics"}) == "conference")
check("kind: unknown title is 'other'", cm.kind_of({"title": "NuFact 2026"}) == "other")
check("continent from country code", cm.continent_of({"extra": {"country_code": "it"}}) == "Europe")
check("no country, no continent", cm.continent_of({"extra": {}}) == "")

main = ev("m", "XXXII International Conference on Neutrino Physics and Astrophysics", "2026-06-22", "2026-06-26",
          city="University of California", acronym="Neutrino 2026")
sat = ev("s", "Satellite event of Neutrino 2026", "2026-06-20", "2026-06-21", city="Elsewhere")
school = ev("k", "17th International Neutrino Summer School", "2026-06-28", "2026-07-10", city="University of California")
far_school = ev("f", "Another Summer School", "2026-07-20", "2026-07-30", city="University of California")
other_country = ev("o", "Satellite event of Neutrino 2026", "2026-06-20", "2026-06-21", cc="JP", city="Tokyo")
unrelated_ws = ev("u", "Workshop on Lattice QCD", "2026-06-23", "2026-06-24", city="Boston")
top, kids = cm.group_related([main, sat, school, far_school, other_country, unrelated_ws])
got = sorted(k["id"] for k in kids.get("m", []))
check("satellite naming the conference and adjacent school in the same city are folded", got == ["k", "s"])
check("a school weeks later, a meeting abroad and an unrelated workshop elsewhere stay separate",
      {r["id"] for r in top} == {"m", "f", "o", "u"})

ics = cm.to_ics([main])
check("ICS: all-day, exclusive end", "DTSTART;VALUE=DATE:20260622" in ics and "DTEND;VALUE=DATE:20260627" in ics)
check("ICS: CRLF line ends and escaped commas", "\r\n" in ics and "LOCATION:University of California\\, US" in ics)
check("ICS: lines folded at 75 octets", all(len(l.encode()) <= 75 for l in ics.split("\r\n")))
if bad:
    sys.exit(1)
print("all conference facet checks pass")
