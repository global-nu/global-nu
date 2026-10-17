#!/usr/bin/env python3
"""Render the installable-app icons from site-src/images-src/app-icon/icon.svg.

    ./.venv/bin/python3 tools/make_app_icons.py

Needs rsvg-convert (Homebrew librsvg). The PNGs are kept in
site-src/assets/icons/, so the daily build does not need the tool.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "site-src/images-src/app-icon/icon.svg"
OUT = ROOT / "site-src/assets/icons"
SIZES = {"icon-192.png": 192, "icon-512.png": 512, "apple-touch-icon.png": 180}

exe = shutil.which("rsvg-convert") or sys.exit("rsvg-convert not found (brew install librsvg)")
OUT.mkdir(parents=True, exist_ok=True)
for name, px in SIZES.items():
    subprocess.run([exe, "-w", str(px), "-h", str(px), "-o", str(OUT / name), str(SVG)], check=True)
    print(f"  {name}: {px}px")
