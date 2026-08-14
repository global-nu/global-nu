#!/usr/bin/env python3
"""fetch_commons_images.licence_ok must actually refuse NC and ND licences.

    ./.venv/bin/python3 tools/tests/test_commons_licence.py

Found by the final-fix-round-2 review: ALLOWED contains the substring
"cc by", and Commons' LicenseShortName values are single hyphenated tokens
("cc by-nc 4.0"), so the old `bad in s.split()` check split only on
whitespace and never isolated "nc"/"nd" out of "by-nc"/"by-nd" — the
REFUSED-token check silently never fired, and the same string then matched
ALLOWED's "cc by" substring and came back accepted. `licence_ok("CC BY-NC
4.0")`, `licence_ok("CC BY-NC-SA 3.0")` and `licence_ok("CC BY-ND 2.0")` all
returned True under the bug. Photos._save_thumb resizes to 640px, which
makes publishing an ND file an actual derivative work, and the same function
gates the experiments map's already-live images — see the second half of
this file.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.fetch_commons_images import licence_ok      # noqa: E402

fail: list[str] = []
checks = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
    else:
        fail.append(label)
        print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


# --------------------------------------------------------------------- #
# 1. NC and ND must be refused, hyphenated exactly as Commons writes them.
# --------------------------------------------------------------------- #
for bad_licence in ("CC BY-NC 4.0", "CC BY-NC-SA 3.0", "CC BY-ND 2.0",
                    "CC BY-NC-ND 3.0", "cc by-nd 2.5"):
    ok, why = licence_ok(bad_licence, "File:Whatever.jpg")
    check(f"{bad_licence!r} is refused, not accepted off the 'cc by' substring",
          ok is False, (ok, why))

# --------------------------------------------------------------------- #
# 2. Genuinely-reusable licences must still pass — the fix must not widen
#    the refusal past what it was ever meant to catch.
# --------------------------------------------------------------------- #
for good_licence in ("CC BY-SA 4.0", "CC BY-SA 3.0", "CC BY-SA 2.5 ca",
                     "CC BY-SA 2.5", "CC BY 4.0", "CC BY 3.0", "CC0",
                     "CC0 1.0 Universal", "Public domain"):
    ok, why = licence_ok(good_licence, "File:Whatever.jpg")
    check(f"{good_licence!r} still passes after the fix", ok is True, (ok, why))

# --------------------------------------------------------------------- #
# 3. Already-refused shapes stay refused (no regression from the fix).
# --------------------------------------------------------------------- #
for still_bad in ("All rights reserved", "fair use", "non-free", ""):
    ok, why = licence_ok(still_bad, "File:Whatever.jpg")
    check(f"{still_bad!r} is still refused", ok is False, (ok, why))


# --------------------------------------------------------------------- #
# 4. The audit this finding actually asked for: every photograph the site
#    currently PUBLISHES must pass the corrected rule. Two sources:
#      - site-src/data/photos.yaml, `status: keep` entries — gates the
#        experiments map's already-live photographs (tools/make_map.py).
#      - var/news/photocache.json — the conference-city photographs
#        (tools/news/photos.py). Gitignored, machine-local, and refreshed
#        daily by the pipeline, so it is audited here defensively (skipped
#        outright if absent, e.g. a fresh checkout) rather than asserted on
#        as committed fact, but checked for real whenever it exists.
# --------------------------------------------------------------------- #
import yaml                                              # noqa: E402

PHOTOS_YAML = ROOT / "site-src" / "data" / "photos.yaml"
if PHOTOS_YAML.exists():
    doc = yaml.safe_load(PHOTOS_YAML.read_text(encoding="utf-8")) or {}
    kept = [p for p in doc.get("photos", []) if p.get("status") == "keep"]
    checks += 1
    bad = [(p.get("subject"), p.get("licence"))
           for p in kept if not licence_ok(p.get("licence", ""), p.get("title", ""))[0]]
    if not bad:
        print(f"  ok   every published experiments-map photo ({len(kept)} kept "
              f"entries in photos.yaml) passes the corrected licence_ok")
    else:
        fail.append("published experiments-map photo licence audit")
        print(f"  FAIL published experiments-map photo licence audit\n         {bad}")

PHOTOCACHE = ROOT / "var" / "news" / "photocache.json"
if PHOTOCACHE.exists():
    import json
    cache = json.loads(PHOTOCACHE.read_text(encoding="utf-8"))
    entries = [(k, v) for k, v in cache.items() if v]
    checks += 1
    bad2 = [(k, v.get("licence")) for k, v in entries
            if not licence_ok(v.get("licence", ""), v.get("file", ""))[0]]
    if not bad2:
        print(f"  ok   every published conference-city photo ({len(entries)} "
              f"entries in photocache.json) passes the corrected licence_ok")
    else:
        fail.append("published conference-city photo licence audit")
        print(f"  FAIL published conference-city photo licence audit\n         {bad2}")
else:
    print("  --   photocache.json absent (fresh checkout) — audit skipped")


print()
if fail:
    print(f"  ! {len(fail)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — licence_ok genuinely refuses NC/ND, and every "
     "published photo (experiments map + conference cities) clears the corrected rule")
