"""Publish a release before its paper, as PRELIMINARY and without its files.

site.yaml `preliminary: "2026.a"` makes build.py read drafts/ into the PUBLIC
tree (site/). This module is what keeps that from being a draft build under
another name:

  * every page that shows the release carries a large blinking PRELIMINARY
    banner, and the release's own headings a PRELIMINARY badge;
  * nothing of the release can be downloaded: the Δχ² tables, the PDFs, the
    6D χ², the notebook and the release package are not copied, the links to
    them are removed, and the sections that exist only to hand them out are
    replaced by one notice. Figures stay, as pictures on the page.

The files of earlier releases are not touched: they were public before.
tools/tests/test_preliminary.py checks the built tree, not this code.
"""

from __future__ import annotations

import re

NOTICE_FILES = ("The Δχ² tables (1D, 2D and the full 6D χ²), the tables as PDF, "
                "the notebook and the release package will be published with the paper. "
                "Until then the values on this site are preliminary and may change.")

BANNER = ('<div class="prelim-banner" role="note"><div class="wrap">'
          '<strong class="prelim">Preliminary</strong>'
          '<span>Bari Release {rid}: preliminary results, the paper is in preparation. '
          'Values may still change; no data files are distributed yet.</span></div></div>')

# Set by build.py: the fingerprint of the published relpage.js, so a browser
# (or the app's service worker) never keeps yesterday's copy.
RELPAGE_V = ""

BADGE = '<span class="prelim prelim--badge">Preliminary</span>'

# Paths of the release that are never published. Figures (release-2026a/figures/)
# are published only as the images a page shows; links to them are removed too.
_RELEASE_HREF = re.compile(
    r'<a\b[^>]*\bhref="(?:\.\./)*(?:release-2026a/|data/releases/(?:2026\.a|latest))[^"]*"[^>]*>(.*?)</a>',
    re.S)


def shows_release(page: str, rid: str) -> bool:
    return rid in page or "release-2026a/" in page


def _section_span(page: str, at: int) -> tuple[int, int] | None:
    """Start and end of the <section> element enclosing index `at`."""
    start = page.rfind("<section", 0, at + len("<section"))
    if start < 0:
        return None
    depth = 0
    for m in re.finditer(r"<(/?)section\b[^>]*>", page[start:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return start, start + m.end()
    return None


def _drop_section(page: str, marker: str, replacement: str = "") -> str:
    at = page.find(marker)
    if at < 0:
        return page
    span = _section_span(page, at)
    if not span:
        return page
    return page[:span[0]] + replacement + page[span[1]:]


def _results_page(page: str, rid: str) -> str:
    notice = ('<section id="data"><div class="wrap"><h2>Data files</h2>'
              '<span id="data-6d"></span><span id="chi2-6d-sezione"></span>'
              f'<p class="prelim-files"><strong class="prelim">Preliminary</strong> {NOTICE_FILES}</p>'
              '</div></section>')
    page = _drop_section(page, 'id="chi2-6d-sezione"')
    page = _drop_section(page, '<section id="data">', notice)
    page = _drop_section(page, "<h2>Run it in the browser</h2>")
    page = _drop_section(page, "<h2>Quick start</h2>")
    page = re.sub(r"<h3>The same tables as PDF</h3>\s*<ul class=\"rs-elenco\">.*?</ul>", "",
                  page, flags=re.S)
    page = re.sub(r'<a class="cta" href="#data(?:-6d)?">.*?</a>', "", page)
    page = page.replace(" Click a figure for the PDF.", "")
    page = page.replace("read from the 1D profiles in the downloads", "read from the 1D profiles")
    page = page.replace(
        "Everything on this page is downloadable,\n      and the notebook below regenerates every figure from the published tables\n      alone.",
        "These results are <strong>preliminary</strong>: the paper is in preparation, and the\n"
        "      tables, the notebook and the data files will be published with it.")
    page = re.sub(r"(Bari Group 2026\.a)</h1>", r"\1 " + BADGE + "</h1>", page)
    page = page.replace("Version of 2026-10-15", "Preliminary version of 2026-10-15")
    page = page.replace(r"{\url{https://home.ba.infn.it/~marrone/juno2026/}}",
                        r"{\url{https://global-nu.org/results.html}}")
    page = page.replace("{Version of 2026-10-15}", "{Preliminary, version of 2026-10-15}")
    page = page.replace("PDF and PNG.", "")
    page = re.sub(r'\s*<script src="data/relpage/(?:engine|panel)\.js"[^>]*></script>', "", page)
    if RELPAGE_V:
        page = page.replace('src="data/relpage/relpage.js"', f'src="data/relpage/relpage.js?v={RELPAGE_V}"')
    return page


def apply(page: str, url: str, rid: str) -> str:
    """The page as published while release `rid` is preliminary."""
    if not shows_release(page, rid):
        return page

    if url == "results.html":
        page = _results_page(page, rid)
    if url == "index.html":
        page = re.sub(r'\s*<a class="btn btn--ghost" href="results.html#(?:chi2-6d-sezione|data)">.*?</a>',
                      "", page)
    if url == "data.html":
        page = re.sub(
            r'(<section[^>]*id="current">.*?</div>\s*)<div class="dsets">.*?(</div></section>)',
            lambda m: m.group(1)
            + f'<p class="prelim-files"><strong class="prelim">Preliminary</strong> '
              f'Bari Release {rid} is shown on this site as preliminary results. {NOTICE_FILES}</p>'
              '<p class="small muted">The values of the previous release (the 2026 (1,&nbsp;2)-sector update '
              'on top of the March 2025 full release) remain available: '
              '<a href="data/current/parameters.csv" download>CSV</a> · '
              '<a href="data/current/parameters.json" download>JSON</a>.</p>\n'
            + m.group(2),
            page, count=1, flags=re.S)

    # Links to the release's files: a caption link ("· PDF") goes with its
    # separator, any other link keeps its content (the image, the label).
    page = re.sub(r'\s*(?:·|&middot;)\s*<a\b[^>]*\bhref="(?:\.\./)*release-2026a/[^"]*"[^>]*>\s*(?:PDF|PNG)\s*</a>',
                  "", page)
    page = _RELEASE_HREF.sub(lambda m: m.group(1), page)

    # The draft wording becomes the preliminary one.
    page = re.sub(
        r'<p class="relpanel__draft" role="note">.*?</p>',
        f'<p class="relpanel__draft" role="note"><strong class="prelim">Preliminary</strong> '
        f'Bari Release {rid}: the paper is in preparation and these values may still change. '
        'Data files will be published with the paper.</p>', page, flags=re.S)
    page = re.sub(
        r"<b>Draft — release (\S+) is shown in the Bari series and in the release list, from its draft numbers\.</b>",
        r'<b><strong class="prelim">Preliminary</strong> Release \1 is shown in the Bari series and in the release list with its preliminary numbers.</b>',
        page)
    page = re.sub(r"(<h2[^>]*>Bari Release " + re.escape(rid) + r")</h2>", r"\1 " + BADGE + "</h2>", page)
    for old, new in (("(draft, not published)", "(preliminary)"),
                     ("draft · newest release", "preliminary · newest release"),
                     (f"release {rid}, bestfit_ranges_FIT.json (draft)", f"release {rid}, preliminary values"),
                     ("(draft, values of", "(preliminary, values of"),
                     ("results (draft) —", "results (preliminary) —"),
                     ("Draft, not published; values as of", "Preliminary; values as of"),
                     ("Draft: Bari release", "Preliminary: Bari release"),
                     (f"https://global-nu.org/data/releases/{rid}/", "https://global-nu.org/results.html")):
        page = page.replace(old, new)

    page = re.sub(r"(<main\b[^>]*>)", lambda m: m.group(1) + BANNER.format(rid=rid), page, count=1)
    return page.replace("<body", '<body data-preliminary="' + rid + '"', 1) \
        if "data-preliminary=" not in page else page


def relpage_js(js: str) -> str:
    """The Results page's script without the routes to the release's files."""
    js = js.replace('<a href="${pdf}">PDF</a>', "")
    js = js.replace("const el = document.getElementById('online');",
                    "const el = document.getElementById('online');\n  if (!el) return;")
    return js
