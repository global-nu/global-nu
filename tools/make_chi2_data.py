#!/usr/bin/env python3
"""Convert a Bari_Group_Results Δχ² release into the JSON the explorer reads.

    ./.venv/bin/python3 tools/make_chi2_data.py <release-dir> [--draft]

<release-dir> is the folder holding data/bari*_1D_{a,b,c}.txt. With --draft the
output goes to drafts/data/, which is git-ignored and only ever reaches
site-draft/ — an embargoed release cannot be published by accident, because it
is never written into the tree that gets deployed.

Nothing is recomputed here and nothing is smoothed: the profiles are the
numbers in the release file, and the ordering offset is read from the header
of that same file rather than typed in. A file whose header does not state an
offset is refused, because a curve whose baseline is unknown cannot be drawn
honestly.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The label each parameter gets in the explorer, and how to write its unit.
LABELS = {
    "dm2_21":    ("δm²", "10⁻⁵ eV²"),
    "dm2_ee":    ("Δm²_ee", "10⁻³ eV²"),
    "dm2_31":    ("Δm²₃₁", "10⁻³ eV²"),
    "dm2":       ("Δm²", "10⁻³ eV²"),
    "absDm2":    ("|Δm²|", "10⁻³ eV²"),
    "dm2_ee_abs": ("|Δm²_ee|", "10⁻³ eV²"),
    "sin2_th12": ("sin²θ₁₂", ""),
    "sin2_th13": ("sin²θ₁₃", ""),
    "sin2_th23": ("sin²θ₂₃", ""),
    "delta_pi":  ("δ/π", ""),
    "delta_over_pi": ("δ/π", ""),
    "delta":     ("δ/π", ""),
}

OFFSET_RE = re.compile(r"offset\s*\(IO\s*-\s*NO\)\s*=\s*([-+0-9.eE]+)")
CASE_RE = re.compile(r"Data set\s*([abc])\)\s*(.+?)\s*$", re.M)


def parse(path: Path) -> dict:
    header, rows = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            header.append(line)
            continue
        parts = line.split()
        if len(parts) == 5 and parts[0] != "parameter":
            rows.append(parts)

    text = "\n".join(header)
    m = OFFSET_RE.search(text)
    if not m:
        sys.exit(f"{path.name}: the header states no (IO - NO) offset — refusing "
                 "to publish profiles whose common baseline is unknown")
    offset = float(m.group(1))

    cm = CASE_RE.search(text)
    label = cm.group(2).strip() if cm else path.stem

    params: dict[str, dict] = {}
    for name, value, unit, no, io in rows:
        p = params.setdefault(name, {"unit": unit, "v": [], "no": [], "io": []})
        p["v"].append(float(value))
        p["no"].append(float(no))
        p["io"].append(float(io))

    for name, p in params.items():
        nice, unit = LABELS.get(name, (name, p["unit"]))
        p["label"] = nice
        p["unit_label"] = unit

    return {"label": label, "offset_io_minus_no": offset, "params": params}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("release", help="folder containing data/*_1D_*.txt")
    ap.add_argument("--draft", action="store_true",
                    help="write to drafts/data/ instead of the published tree")
    args = ap.parse_args()

    src = Path(args.release).expanduser()
    files = sorted((src / "data").glob("*_1D_[abc].txt"))
    if not files:
        sys.exit(f"no *_1D_[abc].txt under {src / 'data'}")

    datasets = {}
    for f in files:
        key = f.stem[-1]
        datasets[key] = parse(f)
        n = sum(len(p["v"]) for p in datasets[key]["params"].values())
        print(f"  {f.name:26} case {key}  {len(datasets[key]['params'])} parameters, "
              f"{n} nodes, offset {datasets[key]['offset_io_minus_no']:+.4f}")

    out_dir = (ROOT / "drafts" / "data") if args.draft else (ROOT / "data-exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "chi2.json"
    doc = {
        "source": src.name,
        "note": ("Δχ² profiles as published in the release files; each ordering "
                 "is referred to its own free minimum, and the offset puts them "
                 "on a common scale."),
        "datasets": datasets,
    }
    dest.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    kb = dest.stat().st_size // 1024
    print(f"\nwrote {dest.relative_to(ROOT)} ({kb} KB)"
          + ("  [draft — never published]" if args.draft else ""))


if __name__ == "__main__":
    main()
