#!/usr/bin/env python3
"""The conferences page's sources, and the rules that bind them.

    ./.venv/bin/python3 tools/tests/test_conferences.py

The page was fed by Indico alone, so it showed whatever Indico's generic
categories held — a Czech-Slovak HEP workshop and an HL-LHC meeting led the
published page while NuFact and the Erice school were absent. These checks are
about the sources being there and the merge holding, not about any one day's
listing, so every record here is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import tempfile

from tools.news import conferences as conf          # noqa: E402
from tools.news import fetch_inspire, fetch_nu_unbound, render   # noqa: E402

problems: list[str] = []
checks = 0


class _Log:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def debug(self, *a, **k): pass


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
    else:
        problems.append(label)
        print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


check("the Neutrino Unbound fetcher exists and is callable",
      callable(getattr(fetch_nu_unbound, "fetch", None)))
check("INSPIRE can be asked for conferences, not only literature",
      callable(getattr(fetch_inspire, "fetch_conferences", None)))
check("INSPIRE conferences split into upcoming and concluded",
      callable(getattr(fetch_inspire, "split", None)))


def rec(name, url, city, country, opening, closing, provider, scope="neutrino"):
    return {"id": f"{provider}:{name}", "title": name, "url": url,
            "extra": {"acronym": name.split()[0], "place": f"{city}, {country}",
                      "city": city, "country_code": country,
                      "opening": opening, "closing": closing,
                      "provider": provider, "scope": scope, "upcoming": True}}


# One conference, listed by two sources, must merge into one entry that
# remembers both — this is what conferences.py is for and what three sources
# will exercise every morning.
nufact_nu = rec("NuFact 2026", "https://nufact2026.example.org/",
                "Shanghai", "CN", "2026-08-31", "2026-09-05", "nu-unbound")
nufact_in = rec("NuFact 2026", "https://inspirehep.net/conferences/2812345",
                "Shanghai", "CN", "2026-08-31", "2026-09-05", "inspire")
other = rec("Erice School 2026", "https://erice.example.org/",
            "Erice", "IT", "2026-09-14", "2026-09-22", "nu-unbound")

merged = conf.merge([[nufact_nu], [nufact_in], [other]], _Log())
check("a conference listed by two sources merges into one entry",
      len(merged) == 2, f"got {len(merged)}: {[m['title'] for m in merged]}")
lead = next((m for m in merged if m["title"] == "NuFact 2026"), None)
check("the merged entry records both providers",
      bool(lead) and len(set((lead.get("extra") or {}).get("providers") or [])) >= 2,
      f"providers: {(lead or {}).get('extra', {}).get('providers')}")

# render.conferences() must split on whether a conference is still ahead
# (extra.upcoming), not on which part of the field it covers (extra.scope,
# "neutrino" vs "general" — the axis conferences.split_scope() uses for the
# two sections a later task builds). Redirected to a scratch file so this
# does not overwrite the real site-src/content/conferences.md.
render.CONFERENCES_PAGE = Path(tempfile.mkdtemp()) / "conferences.md"


def _render_split(records):
    render.conferences(records, _Log(), stamp="test")
    text = render.CONFERENCES_PAGE.read_text(encoding="utf-8")
    upcoming_block, _, recent_block = text.partition('<h2>Recent</h2>')
    return upcoming_block, recent_block


still_ahead = rec("Still Ahead 2099", "https://ahead.example.org/", "Bari", "IT",
                  "2099-01-01", "2099-01-05", "nu-unbound")
still_ahead["extra"]["upcoming"] = True

already_over = rec("Already Over 2020", "https://over.example.org/", "Bari", "IT",
                   "2020-01-01", "2020-01-05", "nu-unbound")
already_over["extra"]["upcoming"] = False

# Upcoming AND scope="general" — the exact combination the bug got wrong: the
# old predicate read `scope != "past"` as "upcoming", so a general-scope
# record was never the cause, but the fix must not swap one field-confusion
# for another in the other direction.
general_upcoming = rec("General Physics Meeting 2099", "https://general.example.org/",
                       "Bari", "IT", "2099-02-01", "2099-02-05", "nu-unbound",
                       scope="general")
general_upcoming["extra"]["upcoming"] = True

up_block, recent_block = _render_split([still_ahead, already_over, general_upcoming])
check("a record with extra.upcoming=True renders under Upcoming, not Recent",
      "Still Ahead 2099" in up_block and "Still Ahead 2099" not in recent_block)
check("a record with extra.upcoming=False renders under Recent, not Upcoming",
      "Already Over 2020" in recent_block and "Already Over 2020" not in up_block)
check("a record whose extra.scope is 'general' is not thereby treated as concluded",
      "General Physics Meeting 2099" in up_block
      and "General Physics Meeting 2099" not in recent_block)

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — three sources, merged into one listing")
