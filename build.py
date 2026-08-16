#!/usr/bin/env python3
"""
build.py — static-site generator for global-nu.org

    site-src/content/*.md  +  site-src/templates/*.html  ->  site/

Adapted from the generator of home.ba.infn.it/~marrone: the Markdown
pipeline, the ::: fences, the math shield and the link checker are the same
proven code. Removed here: the INFN protected trees, the INSPIRE publications
refresh and the analytics hook.

Design constraints:
  * output is pure static HTML/CSS/JS — GitHub Pages serves files, nothing else
  * zero external requests at runtime: fonts, KaTeX and JS are self-hosted
  * no trackers

Usage
    python3 build.py                 # full build
    python3 build.py --clean         # wipe site/ first
    python3 build.py --no-images     # skip the (slow) image pipeline

Dependencies: markdown, PyYAML, Pillow
    pip3 install markdown PyYAML Pillow
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("Missing dependency: PyYAML  ->  pip3 install PyYAML")
try:
    import markdown as md
except ImportError:  # pragma: no cover
    sys.exit("Missing dependency: markdown  ->  pip3 install markdown")

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "site-src"
CONTENT = SRC / "content"
TEMPLATES = SRC / "templates"
ASSETS = SRC / "assets"
IMAGES_SRC = SRC / "images-src"
DATA_EXPORTS = ROOT / "data-exports"
OUT = ROOT / "site"

# Unpublished work. drafts/ holds content and data for a release that is not
# out yet; it is git-ignored, and a normal build cannot reach it — --drafts
# builds to a DIFFERENT directory, so there is no flag that could quietly put
# an embargoed result into the tree that gets published.
DRAFTS = ROOT / "drafts"
OUT_DRAFT = ROOT / "site-draft"

MD_EXTENSIONS = ["extra", "attr_list", "md_in_html", "tables", "sane_lists", "footnotes"]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def load_config() -> dict:
    with open(SRC / "site.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body). Frontmatter is a leading --- ... --- block."""
    if not text.startswith("---"):
        return {}, text
    raw = text[3:]
    try:
        end = raw.index("\n---")
    except ValueError:
        return {}, text
    fm = yaml.safe_load(raw[:end]) or {}
    body = raw[end + 4:].lstrip("\n")
    return fm, body


# --------------------------------------------------------------------------- #
# ::: container fences
#
#   ::: section white          ->  <section class="section section--white">
#                                    <div class="wrap"> ... </div></section>
#   ::: section ink narrow     ->  same, inner <div class="wrap prose">
#   ::: cards                  ->  <div class="cards"> ... </div>
#   :::                        ->  closes the innermost open fence
# --------------------------------------------------------------------------- #
FENCE_RE = re.compile(r"^:::[ \t]*(.*?)[ \t]*$")

SECTION_TONES = {"paper", "white", "ink"}

TOKEN = "zqfencemarkerqz{}qz"   # plain alphanumeric: markdown strips \x02/\x03

MATH_TOKEN = "zqmathmarkerqz{}qz"
DISPLAY_MATH_RE = re.compile(r"^\$\$$.*?^\$\$$", re.S | re.M)


def shield_math(body: str) -> tuple[str, dict[str, str]]:
    """Replace $$ display-math blocks with inert tokens before Markdown runs.

    Not cosmetic. A `<` inside a formula — \\sum_{i<j} — reads to Markdown's
    inline HTML parser as the start of a tag `<j…`, and the parser it leaves
    behind is broken in a way that surfaces one block LATER: the next raw HTML
    block gets wrapped in <p> and its first child swallowed, unbalancing the
    page. On a neutrino site `<` in math is a matter of time, not chance, so
    every $$ block is shielded. KaTeX reads the restored text in the browser
    and never notices.

    Only $$-fenced display math is shielded. Inline math uses \\( … \\), which
    Markdown does not touch; a naive regex for single $…$ would false-match
    ordinary dollar signs in prose.
    """
    subs: dict[str, str] = {}

    def grab(m: re.Match) -> str:
        tok = MATH_TOKEN.format(len(subs))
        subs[tok] = m.group(0)
        return "\n" + tok + "\n"

    return DISPLAY_MATH_RE.sub(grab, body), subs


def expand_fences(body: str) -> tuple[str, dict[str, str]]:
    """Replace ::: fences with placeholder tokens.

    The wrappers are NOT emitted as `markdown="1"` HTML: python-markdown's
    md_in_html closes a raw block at the first top-level `</div>`, so a second
    sibling block inside the wrapper gets handed back to the block parser and,
    being indented, is swallowed as an indented code block. Inert tokens
    substituted after conversion sidestep that entirely.
    """
    out: list[str] = []
    stack: list[str] = []
    subs: dict[str, str] = {}
    n = 0

    def emit(html_fragment: str) -> None:
        nonlocal n
        tok = TOKEN.format(n)
        n += 1
        subs[tok] = html_fragment
        out.append("")
        out.append(tok)
        out.append("")

    for line in body.split("\n"):
        m = FENCE_RE.match(line)
        if not m:
            out.append(line)
            continue
        spec = m.group(1).strip()
        if not spec:                                   # closing fence
            emit(stack.pop() if stack else "")
            continue

        words = spec.split()
        head = words[0]
        rest = words[1:]

        if head == "section":
            tone = next((w for w in rest if w in SECTION_TONES), "paper")
            extra = [w for w in rest if w not in SECTION_TONES]
            inner = "wrap prose" if "narrow" in extra else "wrap"
            extra = [w for w in extra if w != "narrow"]
            sid = next((w[1:] for w in extra if w.startswith("#")), None)
            # Every remaining word is a section modifier and gets the block
            # prefix. Emitting it bare — which is what this did — produced
            # class="section section--paper alt" while the stylesheet was
            # waiting for .section--alt, so the alternating backgrounds were
            # silently absent from the whole site.
            mods = " ".join(f"section--{w}" for w in extra if not w.startswith("#"))
            attrs = f' id="{sid}"' if sid else ""
            cls = f"section section--{tone}" + (f" {mods}" if mods else "")
            emit(f'<section class="{cls}"{attrs}><div class="{inner}">')
            stack.append("</div></section>")
        else:
            klass = " ".join(w.lstrip(".") for w in words)
            emit(f'<div class="{klass}">')
            stack.append("</div>")

    while stack:
        emit(stack.pop())
    return "\n".join(out), subs


def restore_fences(html_text: str, subs: dict[str, str]) -> str:
    # Longest token first, so zqfencemarkerqz1qz never eats …10qz.
    for tok in sorted(subs, key=len, reverse=True):
        frag = subs[tok]
        html_text = html_text.replace(f"<p>{tok}</p>", frag).replace(tok, frag)
    return html_text


# --------------------------------------------------------------------------- #
# templating (deliberately tiny: {{key}} substitution only)
# --------------------------------------------------------------------------- #
def render_template(tpl: str, ctx: dict) -> str:
    def sub(m):
        key = m.group(1).strip()
        return str(ctx.get(key, ""))
    return re.sub(r"\{\{([a-z_0-9]+)\}\}", sub, tpl)


def _json_ld(obj: dict) -> str:
    """One JSON-LD object, as a script element that cannot break the page.

    A literal "</script>" inside any string would end the element early and
    spill JSON into the document as text. Escaping "<" as \\u003c is valid
    JSON, changes no value, and removes the whole class of problem. The same
    reasoning as the html.escape() on title and description below.
    """
    body = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    body = body.replace("<", "\\u003c")
    return f'<script type="application/ld+json">{body}</script>'


def head_extra(fm: dict, cfg: dict, url: str) -> str:
    """Structured metadata for the pages that ask for it in their front matter.

    Opt-in per page (`jsonld: dataset` / `jsonld: site`), because these blocks
    describe a specific object and a block that describes the wrong thing is
    worse than none. An unrecognised value is a build error rather than a
    silent empty string: a typo that removes the site's structured metadata
    would otherwise be found by an audit months later, if at all.
    """
    kind = fm.get("jsonld")
    if not kind:
        return ""
    if kind not in ("dataset", "site"):
        sys.exit(f"{url}: unknown 'jsonld: {kind}' — expected 'dataset' or 'site'")
    if kind == "dataset":
        return _dataset_head(fm, cfg, url)
    return _site_head(cfg)


def _dataset_head(fm: dict, cfg: dict, url: str) -> str:
    from tools import register_meta

    facts = register_meta.register_facts()
    ds_cfg = cfg.get("dataset") or {}
    creator = ds_cfg.get("creator") or {}
    base = cfg["site_url"]
    doi = (ds_cfg.get("doi") or "").strip()

    person = {"@type": "Person", "name": creator.get("name", "")}
    if creator.get("orcid"):
        person["identifier"] = f"https://orcid.org/{creator['orcid']}"
        person["sameAs"] = f"https://orcid.org/{creator['orcid']}"
    if creator.get("affiliation"):
        person["affiliation"] = {"@type": "Organization",
                                 "name": creator["affiliation"]}

    obj = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": fm.get("title", ""),
        "description": " ".join((fm.get("description") or "").split()),
        "url": f"{base}/{url}",
        "license": ds_cfg.get("license", ""),
        "isAccessibleForFree": True,
        "creator": person,
        "temporalCoverage": facts["temporal_coverage"],
        "variableMeasured": [
            {"@type": "PropertyValue", "name": v["name"],
             "alternateName": v["label"], "unitText": v["unit"]}
            for v in facts["variables"]
        ],
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "contentUrl": f"{base}/data/history.json"},
            {"@type": "DataDownload", "encodingFormat": "text/csv",
             "contentUrl": f"{base}/data/history.csv"},
        ],
    }
    # Absent, not empty: with no deposit there is no identifier to state.
    if facts["date_modified"]:
        obj["dateModified"] = facts["date_modified"]
    if doi:
        obj["identifier"] = f"https://doi.org/{doi}"

    tags = [
        ("citation_title", fm.get("title", "")),
        ("citation_author", creator.get("name", "")),
        ("citation_public_url", f"{base}/{url}"),
    ]
    if facts["date_modified"]:
        tags.append(("citation_publication_date",
                     facts["date_modified"].replace("-", "/")))
    if doi:
        tags.append(("citation_doi", doi))

    meta = "\n".join(
        f'<meta name="{n}" content="{html.escape(str(v), quote=True)}">'
        for n, v in tags if v)
    return _json_ld(obj) + "\n" + meta


def _site_head(cfg: dict) -> str:
    base = cfg["site_url"]
    org = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Bari neutrino global analysis group",
        "url": base,
        "parentOrganization": [
            {"@type": "Organization", "name": "Università degli Studi di Bari Aldo Moro"},
            {"@type": "Organization", "name": "INFN, Sezione di Bari"},
        ],
    }
    site = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": cfg["site_name"],
        "url": base,
        "description": cfg.get("tagline", ""),
        "publisher": {"@type": "Organization",
                      "name": "Bari neutrino global analysis group"},
    }
    return _json_ld(org) + "\n" + _json_ld(site)


KATEX_HEAD = (
    '<link rel="stylesheet" href="{{base}}assets/vendor/katex/katex.min.css">'
)
KATEX_BODY = """<script defer src="{{base}}assets/vendor/katex/katex.min.js"></script>
<script defer src="{{base}}assets/vendor/katex/auto-render.min.js"></script>
<script defer src="{{base}}assets/js/math.js"></script>"""


# --------------------------------------------------------------------------- #
# Outbound links open in a new tab
#
# The whole site is reference material: following an arXiv or DOI link should
# not throw the reader off the page they were reading. Applied once, to the
# finished page, so no hand-written anchor can be forgotten.
# --------------------------------------------------------------------------- #
A_TAG_RE = re.compile(r"<a\b([^>]*)>", re.I)
HREF_RE = re.compile(r'href="([^"]*)"', re.I)
REL_RE = re.compile(r'rel="([^"]*)"', re.I)

NEW_TAB_SUFFIXES = (".pdf", ".zip", ".ipynb", ".npz", ".csv", ".json", ".tar.gz")


def externalize_links(page: str, cfg: dict) -> str:
    from urllib.parse import urlparse

    site_host = urlparse(cfg["site_url"]).netloc

    def fix(m: re.Match) -> str:
        attrs = m.group(1)
        if "target=" in attrs.lower():
            return m.group(0)
        hm = HREF_RE.search(attrs)
        if not hm:
            return m.group(0)
        href = hm.group(1)
        if href.startswith(("mailto:", "#", "javascript:", "tel:")):
            return m.group(0)

        if href.startswith(("http://", "https://", "//")):
            probe = href if href.startswith(("http://", "https://")) else "https:" + href
            host = urlparse(probe).netloc
            external = bool(host) and host != site_host
        elif href.lower().endswith(NEW_TAB_SUFFIXES):
            external = True                       # downloads and standalone docs
        else:
            external = False

        if not external:
            return m.group(0)

        if REL_RE.search(attrs):
            attrs = REL_RE.sub(
                lambda r: 'rel="{}"'.format(
                    " ".join(sorted(set(r.group(1).split()) | {"noopener", "noreferrer"}))),
                attrs, count=1)
        else:
            attrs += ' rel="noopener noreferrer"'
        return "<a" + attrs + ' target="_blank">'

    return A_TAG_RE.sub(fix, page)


def build_nav(cfg: dict, current: str, base: str = "") -> tuple[str, str]:
    """Nav markup. `base` is the relative prefix ("" or "../") for sub-pages."""
    nav_items, foot_items = [], []
    for item in cfg["nav"]:
        cur = ' aria-current="page"' if item["url"] == current else ""
        nav_items.append(
            f'      <a href="{base}{item["url"]}"{cur}>{html.escape(item["label"])}</a>')
        foot_items.append(
            f'          <li><a href="{base}{item["url"]}">'
            f'{html.escape(item["label"])}</a></li>')
    return "\n".join(nav_items), "\n".join(foot_items)


# --------------------------------------------------------------------------- #
# images
# --------------------------------------------------------------------------- #
def build_images(cfg: dict, verbose: bool = True) -> None:
    if not IMAGES_SRC.exists():
        return
    try:
        from PIL import Image, ImageOps
    except ImportError:
        print("  ! Pillow not installed — copying images verbatim")
        dest = OUT / "images"
        dest.mkdir(parents=True, exist_ok=True)
        for p in sorted(IMAGES_SRC.iterdir()):
            if p.is_file():
                shutil.copy2(p, dest / p.name)
        return

    max_side = cfg["images"]["max_side"]
    quality = cfg["images"]["quality"]
    dest = OUT / "images"
    dest.mkdir(parents=True, exist_ok=True)
    n_done = n_skip = 0

    for p in sorted(IMAGES_SRC.iterdir()):
        if not p.is_file() or p.name.startswith("."):
            continue
        suffix = p.suffix.lower()
        if suffix in {".svg", ".gif"}:
            target = dest / p.name
            if not target.exists() or target.stat().st_mtime < p.stat().st_mtime:
                shutil.copy2(p, target)
                n_done += 1
            else:
                n_skip += 1
            continue
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}:
            continue

        out_name = p.stem + (".png" if suffix == ".png" else ".jpg")
        target = dest / out_name
        if target.exists() and target.stat().st_mtime >= p.stat().st_mtime:
            n_skip += 1
            continue

        with Image.open(p) as im:
            im = ImageOps.exif_transpose(im)
            if max(im.size) > max_side:
                im.thumbnail((max_side, max_side), Image.LANCZOS)
            if suffix == ".png":
                im.save(target, "PNG", optimize=True)
            else:
                if im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
                im.save(target, "JPEG", quality=quality, optimize=True,
                        progressive=True)
        n_done += 1
        if verbose:
            print(f"    img  {p.name} -> {out_name}")
    print(f"  images: {n_done} processed, {n_skip} up to date")


def copy_tree(src: Path, dst: Path) -> int:
    if not src.exists():
        return 0
    n = 0
    for p in src.rglob("*"):
        if p.is_dir() or p.name.startswith("."):
            continue
        target = dst / p.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_mtime < p.stat().st_mtime:
            shutil.copy2(p, target)
            n += 1
    return n


# --------------------------------------------------------------------------- #
# main build
# --------------------------------------------------------------------------- #
# Matches href/src attributes pointing at our own css/js, with any ../ prefix.
_ASSET_REF = re.compile(
    r'((?:href|src)="(?:\.\./)*)(assets/[^"?]+\.(?:css|js))"')


def asset_versions() -> dict[str, str]:
    """assets/…/file.{css,js} -> short content hash, so a returning reader
    never holds a stale stylesheet after a redeploy."""
    out: dict[str, str] = {}
    for p in ASSETS.rglob("*"):
        if p.is_file() and p.suffix in (".css", ".js"):
            rel = "assets/" + p.relative_to(ASSETS).as_posix()
            out[rel] = hashlib.sha1(p.read_bytes()).hexdigest()[:8]
    return out


def version_assets(page: str, versions: dict[str, str]) -> str:
    def sub(m: re.Match) -> str:
        v = versions.get(m.group(2))
        return m.group(0) if v is None else f'{m.group(1)}{m.group(2)}?v={v}"'
    return _ASSET_REF.sub(sub, page)


def content_dirs(with_drafts: bool) -> list[Path]:
    dirs = [CONTENT]
    if with_drafts and (DRAFTS / "content").is_dir():
        dirs.append(DRAFTS / "content")
    return dirs


def build_pages(cfg: dict, with_drafts: bool = False) -> tuple[list[str], list[str]]:
    tpl_cache: dict[str, str] = {}
    written, in_sitemap = [], []
    year = _dt.date.today().year
    versions = asset_versions()

    # GoatCounter counts pageviews without cookies, so no consent banner is
    # needed. An empty code in site.yaml must produce NO script tag: the
    # placeholder collapses and the built site carries no trace of analytics.
    #
    # count.js is served from this site, not from gc.zgo.at. The project's
    # founding rule is that no page loads anything from a third-party host,
    # and a <script src> pointing at somebody's CDN broke it on every page —
    # while the README claimed the opposite. The vendored copy is byte-for-byte
    # what gc.zgo.at serves (site-src/assets/vendor/goatcounter/count.js, ISC
    # licence, updated by re-fetching it). GoatCounter documents self-hosting:
    # the script reads its endpoint from the data-goatcounter attribute and
    # from nothing else.
    #
    # What remains, and cannot be removed without removing the analytics, is
    # the counting request itself: one image request per pageview to
    # <code>.goatcounter.com. Say that plainly wherever the site describes
    # itself; do not write "no runtime request to anything".
    gc_code = (cfg.get("goatcounter") or "").strip()
    analytics_tpl = (
        f'<script data-goatcounter="https://{gc_code}.goatcounter.com/count" '
        'async src="{{base}}assets/vendor/goatcounter/count.js"></script>'
    ) if gc_code else ""

    pages = [(d, p) for d in content_dirs(with_drafts) for p in sorted(d.rglob("*.md"))]
    for base_dir, path in pages:
        raw = path.read_text(encoding="utf-8")
        fm, body = split_frontmatter(raw)
        rel = path.relative_to(base_dir).with_suffix(".html")
        url = fm.get("url") or rel.as_posix()

        # Relative prefix so pages in sub-directories still resolve assets and
        # navigation correctly.
        base = "../" * url.count("/")

        converter = md.Markdown(extensions=MD_EXTENSIONS, output_format="html5")
        # Content is mostly hand-written, naturally indented HTML. An indented
        # block after a blank line would otherwise be swallowed and printed
        # verbatim as <pre><code>. Fenced ``` blocks still work and are the
        # only way we ever want code.
        converter.parser.blockprocessors.deregister("indent")
        shielded, math_subs = shield_math(body)
        fenced, subs = expand_fences(shielded)
        content_html = restore_fences(converter.convert(fenced), subs)
        for tok, formula in math_subs.items():
            # Escape on the way back in: a raw < inside the formula would open
            # a tag for the BROWSER too, splitting the text node so KaTeX's
            # auto-render never sees the full expression.
            safe = html.escape(formula, quote=False)
            content_html = content_html.replace(f"<p>{tok}</p>", safe)
            content_html = content_html.replace(tok, safe)

        # Generated figures are pulled in here rather than pasted into the
        # Markdown: the SVG is built from the data files by
        # tools/make_figures.py, so a page can never drift from the numbers.
        def _include(m: re.Match) -> str:
            roots = [SRC / "data" / "figures"]
            if with_drafts:
                roots.insert(0, DRAFTS / "figures")
            base = next((r / m.group(1) for r in roots
                         if (r / m.group(1)).with_suffix(".svg").exists()
                         or (r / m.group(1)).with_suffix(".html").exists()),
                        roots[-1] / m.group(1))
            src = next((p for p in (base.with_suffix(".svg"),
                                    base.with_suffix(".html")) if p.exists()),
                       base.with_suffix(".svg"))
            if not src.exists():
                print(f"    ! missing figure: {src.name} (run tools/make_figures.py)")
                return ""
            return src.read_text(encoding="utf-8")

        # Case-sensitive names: the first regex was lowercase-only, so
        # <!--include:spark-Dm2--> silently failed to resolve and the home
        # page shipped a stat card with no sparkline and a comment in its
        # place. Uppercase is legal in a figure name.
        content_html = re.sub(r"<!--\s*include:([A-Za-z0-9_-]+)\s*-->", _include,
                              content_html)

        # What remains as an HTML comment is working-notes — generator
        # provenance, editor hints — and none of it belongs on a public page:
        # a comment naming site-src/ paths shipped on history.html. An
        # include that failed to resolve is left VISIBLE by this (the regex
        # above consumed the well-formed ones), which is the point: a missing
        # figure should be seen, not hidden.
        content_html = re.sub(r"<!--(?!\s*include:).*?-->", "", content_html,
                              flags=re.S)

        tpl_name = fm.get("template", "base") + ".html"
        if tpl_name not in tpl_cache:
            tpl_cache[tpl_name] = (TEMPLATES / tpl_name).read_text(encoding="utf-8")

        nav, foot = build_nav(cfg, url, base)
        use_katex = bool(fm.get("katex"))
        scripts = "\n".join(
            f'<script src="{base}{s}" defer></script>'
            for s in (fm.get("scripts") or []))

        # title and description land inside attribute values in the template
        # (content="{{description}}"), so a double quote in the frontmatter
        # would end the attribute early and spill the rest out as bogus
        # attributes. Escape both; entities are equally valid in element text,
        # so <title> is fine too.
        page = render_template(tpl_cache[tpl_name], {
            "title": html.escape(fm.get("title", cfg["site_name"]), quote=True),
            "description": html.escape(fm.get("description", ""), quote=True),
            "url": url,
            "base": base,
            "site_url": cfg["site_url"],
            "site_name": html.escape(cfg["site_name"], quote=True),
            "content": content_html,
            "nav": nav,
            "footer_nav": foot,
            "year": year,
            "head_extra": head_extra(fm, cfg, url),
            "katex_head": KATEX_HEAD.replace("{{base}}", base) if use_katex else "",
            "katex_body": KATEX_BODY.replace("{{base}}", base) if use_katex else "",
            "scripts": scripts,
            "analytics": analytics_tpl.replace("{{base}}", base),
        })
        page = externalize_links(page, cfg)
        page = version_assets(page, versions)
        (OUT / url).parent.mkdir(parents=True, exist_ok=True)
        (OUT / url).write_text(page, encoding="utf-8")
        written.append(url)
        # A page can ask to stay out of the sitemap. 404.html is the case
        # this exists for: it must be built and its links must be checked,
        # but announcing an error page to search engines is nonsense.
        if fm.get("sitemap", True) is not False:
            in_sitemap.append(url)
        print(f"    page {path.name} -> {url}")
    return written, in_sitemap


def check_links(written: list[str]) -> None:
    """Report internal links / assets that do not exist in site/."""
    problems = []
    href_re = re.compile(r'(?:href|src)="([^"#][^"]*)"')
    comment_re = re.compile(r"<!--.*?-->", re.S)
    for url in written:
        text = comment_re.sub("", (OUT / url).read_text(encoding="utf-8"))
        for target in href_re.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "data:", "//")):
                continue
            clean = target.split("#")[0].split("?")[0]
            if not clean:
                continue
            resolved = ((OUT / url).parent / clean).resolve()
            if not resolved.exists():
                problems.append(f"{url}  ->  {target}")
    if problems:
        print("\n  ! broken internal references:")
        for p in sorted(set(problems)):
            print("      " + p)
    else:
        print("  links: all internal references resolve")

    # Hand-written HTML accidentally treated as an indented code block shows up
    # as <pre><code>&lt;div … — always a content bug, never intentional.
    leaked = []
    for url in written:
        text = (OUT / url).read_text(encoding="utf-8")
        n = len(re.findall(r"<pre><code>\s*&lt;", text))
        if n:
            leaked.append(f"{url}: {n}")
    if leaked:
        print("  ! HTML leaked into <pre><code> (check indentation):")
        for p in leaked:
            print("      " + p)
    else:
        print("  markup: no HTML leaked into code blocks")

    ext = set()
    for url in written:
        text = comment_re.sub("", (OUT / url).read_text(encoding="utf-8"))
        for target in href_re.findall(text):
            if target.startswith(("http://", "https://", "//")):
                ext.add(target.split("/")[2])
    if ext:
        print("  external hosts referenced (links only, no runtime deps):")
        for h in sorted(ext):
            print("      " + h)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build global-nu.org")
    ap.add_argument("--clean", action="store_true", help="remove site/ first")
    ap.add_argument("--no-images", action="store_true", help="skip image pipeline")
    ap.add_argument("--drafts", action="store_true",
                    help="include drafts/ and build to site-draft/ (never published)")
    args = ap.parse_args()

    cfg = load_config()

    global OUT
    if args.drafts:
        OUT = OUT_DRAFT
        print("DRAFT BUILD — includes unpublished material, never deploy this tree")

    if args.clean and OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)

    print("building ->", OUT)
    n = copy_tree(ASSETS, OUT / "assets")
    print(f"  assets: {n} files copied")

    # Release products exported from the analysis (tables, figures, data
    # files). The analysis code itself never lives here — see PROMPT_GLOBAL_NU.
    n = copy_tree(DATA_EXPORTS, OUT / "data")
    print(f"  data:   {n} files copied")

    if not args.no_images:
        build_images(cfg)

    if args.drafts:
        n = copy_tree(DRAFTS / "data", OUT / "data")
        print(f"  drafts: {n} data files copied")

    written, in_sitemap = build_pages(cfg, with_drafts=args.drafts)
    # The crawler policy is data, not a string in the middle of code: the list
    # of named agents is a public position of this site and has to be
    # reviewable in a diff. Only the Sitemap line is derived, so the domain
    # stays defined in exactly one place (site_url).
    robots = (SRC / "robots.txt").read_text(encoding="utf-8").rstrip("\n")
    (OUT / "robots.txt").write_text(
        f"{robots}\n\nSitemap: {cfg['site_url']}/sitemap.xml\n", encoding="utf-8")
    # llms.txt: not a standard, and no vendor has committed to honouring it.
    # It costs one small file, and it is the only place where the attribution
    # the CC BY licence requires is stated in a form a model reads. The DOI
    # line is absent, not empty, until there is a deposit to point at.
    ds_cfg = cfg.get("dataset") or {}
    doi = (ds_cfg.get("doi") or "").strip()
    (OUT / "llms.txt").write_text(render_template(
        (SRC / "llms.txt").read_text(encoding="utf-8"), {
            "site_url": cfg["site_url"],
            "tagline": cfg.get("tagline", ""),
            "creator_name": (ds_cfg.get("creator") or {}).get("name", ""),
            # The template puts this placeholder on its own line with no
            # blank line around it; the trailing \n here supplies that blank
            # line when there is a DOI to state, and an empty string leaves
            # a single blank line (not two) when there is not.
            "dataset_doi_line":
                f"Permanent identifier: https://doi.org/{doi}\n" if doi else "",
        }), encoding="utf-8")
    # GitHub Pages runs Jekyll on the published tree unless told not to; an
    # empty .nojekyll stops it touching files whose names start with _.
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    # CNAME must live INSIDE the published tree, because that tree is what is
    # pushed to gh-pages and Pages reads the file from the root it serves. Put
    # there by GitHub's settings UI instead, it would sit on main and never
    # reach gh-pages — the custom domain would silently unset itself on the
    # next deploy. Derived from site_url so there is one place to change it.
    domain = cfg["site_url"].split("//", 1)[-1].rstrip("/")
    (OUT / "CNAME").write_text(domain + "\n", encoding="utf-8")

    now = _dt.date.today().isoformat()
    urls = "\n".join(
        f"  <url><loc>{cfg['site_url']}/{u}</loc><lastmod>{now}</lastmod></url>"
        for u in in_sitemap)
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n</urlset>\n", encoding="utf-8")

    print(f"  {len(written)} pages written")
    check_links(written)
    print("done.")


if __name__ == "__main__":
    main()
