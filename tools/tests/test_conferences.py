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

from tools.news import conferences as conf          # noqa: E402
from tools.news import fetch_inspire, fetch_nu_unbound   # noqa: E402

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

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — three sources, merged into one listing")
