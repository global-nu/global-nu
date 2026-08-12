#!/usr/bin/env python3
"""Fetch freely-licensed photographs from Wikimedia Commons.

    ./.venv/bin/python3 tools/fetch_commons_images.py [--search]

Two rules, both enforced here rather than remembered:

  * Only licences that permit reuse are accepted — CC0, public domain, CC BY
    and CC BY-SA. Anything else, including "fair use" and any file whose
    licence the API does not state, is refused and reported. A photograph
    being downloadable is not permission to republish it.

  * Every accepted file keeps its provenance: the Commons file page, the
    author as Commons records it, the licence and its URL. That manifest is
    what the page renders as a credit, so an image cannot appear without one.

`--search` looks for new candidates and writes them to the manifest as
`status: candidate`; they are downloaded but not published until a human has
looked at them and set `status: keep`. Without the flag, only entries already
marked `keep` are (re)downloaded.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "site-src" / "data" / "photos.yaml"
# Candidates land outside site-src: an image only reaches the published
# tree once a human has marked it keep, and make_gallery.py copies it.
IMAGES = ROOT / "var" / "photo-candidates"

API = "https://commons.wikimedia.org/w/api.php"
UA = "global-nu-site/1.0 (https://global-nu.org; antonio.marrone@ba.infn.it)"

# Substrings of the licence short name that permit reuse with attribution.
ALLOWED = ("cc0", "public domain", "cc by", "cc-by")
# ...and these are never acceptable, whatever else the field says.
REFUSED = ("fair use", "non-free", "nc", "noncommercial", "nd", "noderiv")

# What to look for, and what the picture is meant to show.
SUBJECTS = [
    ("JUNO", "Jiangmen Underground Neutrino Observatory"),
    ("DUNE", "Deep Underground Neutrino Experiment OR Sanford Underground Research Facility"),
    ("Super-Kamiokande", "Super-Kamiokande detector"),
    ("IceCube", "IceCube Neutrino Observatory South Pole"),
    ("KM3NeT", "KM3NeT detection unit"),
    ("KATRIN", "KATRIN spectrometer Karlsruhe"),
    ("Gran Sasso", "Laboratori Nazionali del Gran Sasso hall"),
    ("SNOLAB", "SNOLAB Sudbury underground laboratory"),
    ("Fermilab", "Fermilab Wilson Hall"),
    ("Borexino", "Borexino detector"),
]


def api(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def clean(value: str) -> str:
    """Commons puts HTML in the author field; keep the words."""
    import re
    text = re.sub(r"<[^>]+>", "", value or "")
    return " ".join(text.split())


def short_author(value: str) -> str:
    """Credit the source, not the roster.

    Commons' Artist field is free text. For a collaboration upload it is
    routinely the paper's entire author list — seven hundred names for JUNO,
    which is what shipped under the photograph. CC BY asks for attribution
    "in a reasonable manner for the medium"; naming the collaboration and
    linking the file's page on Commons is the reasonable manner for a caption,
    and photos.yaml keeps the field intact.
    """
    text = (value or "").strip()
    if not text:
        return ""
    head = text.split(":", 1)[0].strip()
    if head.lower().endswith(("collaboration", "collaborations")):
        return head
    names = [n.strip() for n in text.split(",") if n.strip()]
    if len(names) > 3:
        return f"{names[0]} et al."
    return text


def licence_ok(short: str, name: str) -> tuple[bool, str]:
    s = (short or "").lower()
    if not s:
        return False, "no licence stated"
    if any(bad in s.split() for bad in ("nc", "nd")) or \
       any(bad in s for bad in ("fair use", "non-free", "noncommercial", "noderiv")):
        return False, f"licence forbids reuse or derivatives: {short}"
    if any(good in s for good in ALLOWED):
        return True, short
    return False, f"licence not on the allowed list: {short}"


def search(term: str, query: str, limit: int = 3) -> list[dict]:
    data = api({
        "action": "query", "generator": "search", "gsrsearch": query,
        "gsrnamespace": "6", "gsrlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": "1400",
    })
    out = []
    for page in (data.get("query", {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        short = clean((meta.get("LicenseShortName") or {}).get("value", ""))
        ok, why = licence_ok(short, page.get("title", ""))
        out.append({
            "subject": term,
            "title": page.get("title", ""),
            "page": f"https://commons.wikimedia.org/wiki/"
                    f"{urllib.parse.quote(page.get('title','').replace(' ', '_'))}",
            "thumb": info.get("thumburl", ""),
            "author": clean((meta.get("Artist") or {}).get("value", "")),
            "author_short": short_author(clean((meta.get("Artist") or {}).get("value", ""))),
            "credit": clean((meta.get("Credit") or {}).get("value", "")),
            "licence": short,
            "licence_url": clean((meta.get("LicenseUrl") or {}).get("value", "")),
            "accepted": ok,
            "reason": why,
            "status": "candidate" if ok else "refused",
        })
    return out


def slug(title: str) -> str:
    import re
    base = title.split(":", 1)[-1].rsplit(".", 1)[0]
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:60]


def download(entry: dict) -> Path | None:
    if not entry.get("thumb"):
        return None
    dest = IMAGES / f"commons-{slug(entry['title'])}.jpg"
    req = urllib.request.Request(entry["thumb"], headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = r.read()
    except Exception as exc:                                  # noqa: BLE001
        print(f"    ! download failed: {exc}")
        return None
    IMAGES.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    entry["file"] = dest.name
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", action="store_true",
                    help="look for new candidates on Commons")
    args = ap.parse_args()

    manifest = {"photos": []}
    if MANIFEST.exists():
        manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or manifest

    if args.search:
        found = []
        for term, query in SUBJECTS:
            print(f"  {term} …")
            try:
                results = search(term, query)
            except Exception as exc:                          # noqa: BLE001
                print(f"    ! search failed: {exc}")
                continue
            for r in results:
                mark = "ok  " if r["accepted"] else "REFUSED"
                print(f"    {mark} {r['licence'] or '(none)':<28} {r['title'][:58]}")
                if not r["accepted"]:
                    print(f"          {r['reason']}")
                    continue
                if download(r):
                    found.append(r)
            time.sleep(1)
        seen = {p.get("title") for p in manifest["photos"]}
        manifest["photos"] += [f for f in found if f["title"] not in seen]

    else:
        for entry in manifest["photos"]:
            if entry.get("status") == "keep" and not (IMAGES / entry.get("file", "")).exists():
                download(entry)

    MANIFEST.write_text(
        "# Photographs from Wikimedia Commons, with the provenance the credit\n"
        "# line is built from. Only licences permitting reuse are accepted, and\n"
        "# the check lives in tools/fetch_commons_images.py, not here.\n"
        "#\n"
        "# status: candidate  downloaded, not yet looked at — never published\n"
        "#         keep       inspected, depicts what it claims, published\n"
        "#         drop       inspected and rejected\n"
        + yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8")

    kept = sum(1 for p in manifest["photos"] if p.get("status") == "keep")
    cand = sum(1 for p in manifest["photos"] if p.get("status") == "candidate")
    print(f"\nmanifest: {len(manifest['photos'])} entries — {kept} kept, {cand} awaiting review")


if __name__ == "__main__":
    main()
