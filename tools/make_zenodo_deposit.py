#!/usr/bin/env python3
"""Assemble the Zenodo deposit for the parameter register.

    ./.venv/bin/python3 tools/make_zenodo_deposit.py            # build only
    ./.venv/bin/python3 tools/make_zenodo_deposit.py --sandbox --token TOKEN

By default this touches no network at all: it writes the package into
var/zenodo/ and prints what to upload. --sandbox rehearses the whole round
trip against sandbox.zenodo.org, which mints throwaway DOIs and can be got
wrong as many times as needed.

The real deposit is made by hand, from Antonio's account, and this script has
no flag that makes one. A DOI cannot be withdrawn: minting one is a decision
a person takes, not a side effect of running a tool.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from tools import register_meta                          # noqa: E402
import make_history_data                                  # noqa: E402

OUT_DIR = ROOT / "var" / "zenodo"
CFG = ROOT / "site-src" / "site.yaml"

DESCRIPTION = """\
<p>A register of the three-flavour neutrino oscillation parameters as
published by three independent global analyses &mdash; Bari, NuFit and
Valencia &mdash; across {span}. It holds {n} published values and limits
covering {nvars} parameters.</p>

<p>Every value is transcribed by hand from the table of the paper that
printed it, and each row names that paper and that table. No value is
interpolated, averaged, read off a figure, or carried over from another
release. Each row carries the number twice: <code>value_as_published</code>,
exactly as the paper printed it in its own convention and normalisation, and
<code>value_our_convention</code>, the same quantity in the Bari convention
&delta;m&sup2; = m&#8322;&sup2; &minus; m&#8321;&sup2; and
&Delta;m&sup2; = m&#8323;&sup2; &minus; (m&#8321;&sup2; + m&#8322;&sup2;)/2.
Only &Delta;m&sup2; is ever converted, because it is the only quantity the
three groups report differently.</p>

<p>The register is the source of the parameter-history page at
<a href="{url}/history.html">{url}/history.html</a>, where every field is
documented. See README.md in this deposit for the same documentation.</p>
"""


def _cfg() -> dict:
    return yaml.safe_load(CFG.read_text(encoding="utf-8"))


def _plain(html_text: str) -> str:
    """FIELD_DOCS is written as HTML for the web page. Make it text.

    The README must describe exactly the columns the exports carry, so it is
    generated from the same FIELD_DOCS the page uses rather than written
    again here — a second copy would start out identical and end up wrong.

    Entities are decoded as well as tags stripped. FIELD_DOCS writes Greek
    letters and dashes as `&sigma;` and `&mdash;` because it is HTML; a
    deposit README is read as plain text, where those are not characters but
    noise — and the deposit is permanent.
    """
    text = re.sub(r"<code>(.*?)</code>", r"`\1`", html_text, flags=re.S)
    text = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"\2 (\1)", text,
                  flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    # Last, so an entity that spelled a tag character cannot become one.
    text = html.unescape(text)
    return " ".join(text.split())


def _zenodo_name(display_name: str) -> str:
    """"Antonio Marrone" -> "Marrone, Antonio", Zenodo's "Family, Given" form.

    Derived from the verified name in site.yaml rather than typed a second
    time in "Family, Given" order, so the two can never say different names.

    Only correct for a plain two-token "Given Family" name, which is what
    site.yaml holds today. A compound surname ("Antonio Marrone Garcia"), a
    particle ("van der Something"), or a mononym would come out wrong — this
    must be revisited before a second creator is added to the config, not
    after, because the result goes onto a record that cannot be withdrawn.
    """
    parts = display_name.split()
    if len(parts) < 2:
        return display_name
    return f"{parts[-1]}, {' '.join(parts[:-1])}"


def _readme(facts: dict, cfg: dict, meta: dict, licence_url: str) -> str:
    ds = cfg.get("dataset") or {}
    lines = [
        f"# {meta['title']}",
        "",
        # "values and limits", not "values": one row is a kind: limit, a bound
        # with no central value, and the count covers both.
        f"{facts['n_rows']} published values and limits, "
        f"{facts['years'][0]}–{facts['years'][1]}, "
        f"from the Bari, NuFit and Valencia global analyses.",
        "",
        "Published, with the page that documents it, at "
        f"{cfg['site_url']}/history.html",
        "",
        "## Files",
        "",
        "- `history.json` — the register, as an object with a `note` and a "
        "`rows` array.",
        "- `history.csv` — the same rows, one per line, same column names.",
        "",
        "## Columns",
        "",
    ]
    for name, doc in make_history_data.FIELD_DOCS:
        lines.append(f"- `{name}` — {_plain(doc)}")
    lines += [
        "",
        "## Parameters",
        "",
    ]
    for v in facts["variables"]:
        # No unit clause where register_meta could not establish a unit: the
        # README states what is known and stays silent on what is not.
        unit = f", in units of {v['unit']}" if v.get("unit") else ""
        lines.append(f"- `{v['name']}` — {v['label']}{unit}")
    lines += [
        "",
        "## Licence",
        "",
        f"CC BY 4.0 — {licence_url}",
        "",
        "Attribute the register to "
        f"{(ds.get('creator') or {}).get('name', '')} and the "
        "Bari group. If you state one of these numbers, state also the paper "
        "and the table it came from — every row carries both.",
        "",
    ]
    return "\n".join(lines)


def build_package(out_dir: Path) -> dict:
    """Write the deposit package into out_dir and return its metadata."""
    facts = register_meta.register_facts()
    cfg = _cfg()
    ds = cfg.get("dataset") or {}
    creator = ds.get("creator") or {}
    related = ds.get("related") or {}
    licence_url = ds.get("license", "")
    lo, hi = facts["years"]

    out_dir.mkdir(parents=True, exist_ok=True)

    # Every related identifier here would assert a permanent relation on a
    # record that can never be withdrawn. A blank or missing config key must
    # never become an entry that points at nothing — so only identifiers
    # that are actually present get emitted, rather than emitting all three
    # unconditionally and hoping the config is complete.
    #
    # The paper and its preprint are "references", not "isSupplementTo". The
    # register is a compilation drawing values from some twenty-five papers by
    # three independent groups across a quarter century; the 2025 Bari paper is
    # one source among them, and calling the register that article's
    # supplementary material would misstate what this dataset is. The site page
    # keeps isDocumentedBy, which is exactly what it is.
    related_identifiers = [
        {"identifier": f"{cfg['site_url']}/history.html",
         "relation": "isDocumentedBy", "resource_type": "publication-webpage",
         "scheme": "url"},
    ]
    paper_doi = related.get("paper_doi", "")
    if paper_doi:
        related_identifiers.append({
            "identifier": paper_doi, "relation": "references",
            "resource_type": "publication-article", "scheme": "doi"})
    arxiv_id = related.get("arxiv", "")
    if arxiv_id:
        related_identifiers.append({
            "identifier": f"arXiv:{arxiv_id}", "relation": "references",
            "resource_type": "publication-preprint", "scheme": "arxiv"})

    meta = {
        "upload_type": "dataset",
        # From register_meta, not from a constant here: history.html asserts
        # the DOI of this record, so the two must name it identically.
        "title": facts["title"],
        "version": "1.0.0",
        "language": "eng",
        "creators": [{
            "name": _zenodo_name(creator.get("name", "")),
            "orcid": creator.get("orcid", ""),
            "affiliation": creator.get("affiliation", ""),
        }],
        "description": DESCRIPTION.format(
            span=f"{lo}–{hi}", n=facts["n_rows"],
            nvars=len(facts["variables"]), url=cfg["site_url"]),
        "license": "cc-by-4.0",
        "access_right": "open",
        "keywords": [
            "neutrino oscillations", "global fit", "neutrino mass ordering",
            "mixing angles", "CP violation phase", "three-flavour oscillations",
        ],
        "related_identifiers": related_identifiers,
    }
    # publication_date is deliberately NOT set. Zenodo reads it as the date
    # the record was published, and the deposit may be made a long time after
    # the register last changed — setting it to the data's own date would
    # backdate the record and claim a priority the deposit does not have. Left
    # out, Zenodo fills in the real deposit date. When the data last changed is
    # a different fact, and it is carried by dateModified on the page and by
    # the README, where it means what it says.

    shutil.copyfile(register_meta.EXPORT, out_dir / "history.json")
    shutil.copyfile(register_meta.EXPORT.with_suffix(".csv"), out_dir / "history.csv")
    (out_dir / "README.md").write_text(
        _readme(facts, cfg, meta, licence_url), encoding="utf-8")
    # Same rule as the creators block and the README: an attribution naming
    # nobody is worse than one naming no individual at all, so an unset
    # config name drops the clause rather than leaving a blank in its place.
    creator_name = creator.get("name", "")
    attribution = f"{creator_name} and the Bari group" if creator_name else "the Bari group"
    (out_dir / "LICENSE.txt").write_text(
        "This dataset is licensed CC BY 4.0.\n"
        f"Full text: {licence_url}\n\n"
        f"Attribute the parameter register to {attribution}, and cite it "
        "by its DOI.\n", encoding="utf-8")
    (out_dir / "zenodo.json").write_text(
        json.dumps({"metadata": meta}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    return meta


def rehearse(pkg: Path, token: str) -> None:
    """Run the whole deposit against sandbox.zenodo.org. Never the real one."""
    import urllib.request

    base = "https://sandbox.zenodo.org/api/deposit/depositions"

    def call(url: str, data: bytes | None, method: str, ctype: str) -> dict:
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        if ctype:
            req.add_header("Content-Type", ctype)
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
        return json.loads(body) if body else {}

    dep = call(base, b"{}", "POST", "application/json")
    print(f"  sandbox deposition {dep['id']} created")
    bucket = dep["links"]["bucket"]
    for name in ("history.json", "history.csv", "README.md", "LICENSE.txt"):
        call(f"{bucket}/{name}", (pkg / name).read_bytes(), "PUT",
             "application/octet-stream")
        print(f"  uploaded {name}")
    payload = json.loads((pkg / "zenodo.json").read_text(encoding="utf-8"))
    call(f"{base}/{dep['id']}", json.dumps(payload).encode(), "PUT",
         "application/json")
    print(f"  metadata accepted — review it at {dep['links']['html']}")
    print("  NOT published: publishing is done by hand, on the real Zenodo.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--sandbox", action="store_true",
                    help="rehearse against sandbox.zenodo.org (needs --token)")
    ap.add_argument("--token", default="", help="a sandbox.zenodo.org API token")
    args = ap.parse_args()

    meta = build_package(args.out)
    print(f"package written to {args.out}")
    print(f"  title:   {meta['title']}")
    print(f"  version: {meta['version']}")
    print(f"  files:   history.json, history.csv, README.md, LICENSE.txt")
    print(f"  metadata: {args.out / 'zenodo.json'}")

    if args.sandbox:
        if not args.token:
            sys.exit("--sandbox needs --token (make one at sandbox.zenodo.org)")
        rehearse(args.out, args.token)
    else:
        print("\nNo network was touched. To rehearse:  --sandbox --token TOKEN")


if __name__ == "__main__":
    main()
