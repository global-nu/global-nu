#!/usr/bin/env python3
"""Build a self-contained copy of the site under preview/.

Each page carries its stylesheet, its fonts and its script inline, so a single
file opens correctly anywhere — a phone, a cloud drive, an email attachment —
with no server and no assets folder beside it. The links between pages keep
their names, so the copy stays navigable.

    ./.venv/bin/python3 tools/make_preview.py

This is a convenience for review only. It is not the site: `site/` is what
gets published, and preview/ is git-ignored so the two can never be confused.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
OUT = ROOT / "preview"


def inline_fonts(css: str, fonts_dir: Path) -> str:
    """Replace url("../fonts/x.woff2") with a data: URI."""
    def sub(m: re.Match) -> str:
        f = fonts_dir / m.group(1)
        if not f.exists():
            return m.group(0)
        return f'url("data:font/woff2;base64,{base64.b64encode(f.read_bytes()).decode()}")'
    return re.sub(r'url\("\.\./fonts/([^"]+)"\)', sub, css)


def main() -> None:
    if not SITE.exists():
        raise SystemExit("site/ not found — run build.py first")

    css = inline_fonts((SITE / "assets/css/site.css").read_text(encoding="utf-8"),
                       SITE / "assets" / "fonts")
    js = (SITE / "assets/js/site.js").read_text(encoding="utf-8")
    search_js = SITE / "assets/js/search.js"

    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.html"):
        old.unlink()

    written = 0
    for page in sorted(SITE.glob("*.html")):
        html = page.read_text(encoding="utf-8")
        # Preloads point at files that will not be there; drop them rather
        # than leave a console full of 404s.
        html = re.sub(r'<link rel="preload"[^>]*>', "", html)
        html = re.sub(r'<link rel="icon"[^>]*>', "", html)
        # Every replacement below goes through a lambda: re.sub processes
        # backslash escapes in a replacement *string*, and search.js is full
        # of regexes — "\s" would raise "bad escape" and take the run down.
        html = re.sub(r'<link rel="stylesheet" href="assets/css/site\.css[^"]*">',
                      lambda _m: f"<style>{css}</style>", html)
        # The site defers its script; here it is inlined, so wait for the DOM
        # ourselves or the toggle would bind before the button exists.
        html = re.sub(r'<script src="assets/js/site\.js[^"]*" defer></script>',
                      lambda _m: "<script>document.addEventListener("
                      f"'DOMContentLoaded',function(){{{js}}});</script>", html)
        if search_js.exists():
            code = search_js.read_text(encoding="utf-8")
            html = re.sub(r'<script src="assets/js/search\.js[^"]*" defer></script>',
                          lambda _m: "<script>document.addEventListener("
                          f"'DOMContentLoaded',function(){{{code}}});</script>", html)
        # No analytics in a local copy: a preview must not count as a visit.
        html = re.sub(r'<script data-goatcounter[^>]*></script>', "", html)
        (OUT / page.name).write_text(html, encoding="utf-8")
        written += 1

    total = sum(f.stat().st_size for f in OUT.glob("*.html"))
    print(f"preview/: {written} self-contained pages, {total // 1024} KB total")
    print(f"open {OUT / 'index.html'}")


if __name__ == "__main__":
    main()
