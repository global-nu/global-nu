"""The daily run. One entry point for the LaunchAgent and for the CLI.

    python3 -m tools.news.pipeline [--dry-run] [--no-ai] [--no-build]

The automatic run and the manual one go through `run()`; there is no second
code path that could drift from the first.

Order matters and is not arbitrary:

    fetch -> synthesise -> link-check -> render -> build

Link-checking sits before rendering, so a dead link is dropped rather than
published. There is deliberately no publish step yet: this site is developed
locally and goes to GitHub Pages at launch (Phase 4), at which point a commit
and push are appended here and nowhere else.

A step that fails is logged and skipped; the pages it would have written keep
yesterday's content, with yesterday's timestamp visible on them. A half-built
page is worse than a stale one.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from . import cache, conferences as conf_mod, fetch_arxiv, fetch_feeds
from . import fetch_indico, fetch_inspire, linkcheck, render, state, synthesize
from .common import ROOT, get_logger, load_config, now_iso
from .lock import LockBusy, run_lock

EXPERIMENTAL_CATS = ("hep-ex", "nucl-ex", "physics.ins-det", "astro-ph.HE")


def _safe(step: str, fn, log, default):
    """Run a fetch step; never let one source take the whole run down."""
    try:
        return fn()
    except Exception as exc:                                  # noqa: BLE001
        log.warning("%s: failed (%s: %s)", step, exc.__class__.__name__, exc)
        return default


def _experiment_pool(feeds: list[dict], arxiv: list[dict]) -> list[dict]:
    """What the Experiments section may be written from: laboratory and
    collaboration news first — that is what the section is about — then
    experimental preprints, which carry the results those items refer to."""
    # Deliberately "any category" here, unlike the digest's two streams: a
    # result worth writing about counts whichever list it was filed under.
    exp_arxiv = [r for r in arxiv
                 if any(c.startswith(EXPERIMENTAL_CATS)
                        for c in (r.get("extra") or {}).get("categories", []))]
    return feeds + exp_arxiv


def run(*, dry_run: bool = False, use_ai: bool = True, do_build: bool = True,
        verbose: bool = True) -> int:
    log = get_logger("news", verbose=verbose)
    cfg = load_config()
    log.info("=" * 62)
    log.info("run started (dry_run=%s, ai=%s, build=%s)", dry_run, use_ai, do_build)

    # ------------------------------------------------------------ 1. fetch --
    arxiv = _safe("arxiv", lambda: fetch_arxiv.fetch(cfg, log), log, [])
    feeds = _safe("feeds", lambda: fetch_feeds.fetch(cfg, log), log, [])
    papers = _safe("inspire", lambda: fetch_inspire.fetch_literature(cfg, log), log, [])
    events = _safe("indico", lambda: fetch_indico.fetch(cfg, log), log, [])

    if events:
        events = conf_mod.sort_for_page(conf_mod.merge([events], log))

    for name, records in (("arxiv", arxiv), ("feeds", feeds),
                          ("inspire", papers), ("indico", events)):
        if records:
            cache.store(name, records)
    log.info("fetched: %d arXiv, %d feed items, %d papers, %d events",
             len(arxiv), len(feeds), len(papers), len(events))

    # ------------------------------------------------------- 2. synthesise --
    narrative = None
    if use_ai:
        narrative = _safe(
            "synthesis",
            lambda: synthesize.synthesize(cfg, _experiment_pool(feeds, arxiv),
                                          papers, log),
            log, None)
        if narrative:
            state.save_narrative(narrative)
    if narrative is None:
        narrative = state.previous_narrative()
        if narrative:
            log.info("synthesis: reusing the last good narrative")

    # ------------------------------------------------------- 3. link-check --
    all_records = arxiv + feeds + papers + events
    # Only "broken" is acted on. "unverified" means the host refused the
    # check — publishers answer 403 to anything that is not a browser — and
    # dropping a live DOI because a CDN was unfriendly would be worse than
    # leaving it in.
    bad = _safe("linkcheck",
                lambda: {u: v for u, v in
                         linkcheck.check(linkcheck.urls_of(all_records), cfg, log).items()
                         if v == "broken"},
                log, {})
    alive = linkcheck.filter_records(all_records, bad, log) if bad else all_records
    alive_ids = {r["id"] for r in alive}
    arxiv = [r for r in arxiv if r["id"] in alive_ids]
    events = [r for r in events if r["id"] in alive_ids]
    known = cache.index(alive)

    # ----------------------------------------------------------- 4. render --
    if dry_run:
        log.info("dry run: fetched and checked, nothing written")
        state.mark_run("dry-run", f"{len(alive)} live records")
        return 0

    wrote = []
    if render.digest(fetch_arxiv.top(arxiv, int(cfg["arxiv"].get("max_items", 12))), log):
        wrote.append("digest")
    if render.conferences(events, log):
        wrote.append("conferences")
    if render.news(narrative, known, log):
        wrote.append("news")
    if not wrote:
        log.warning("nothing was written — the pages keep their last content")

    # ------------------------------------------------------------ 5. build --
    if do_build and wrote:
        python = ROOT / ".venv" / "bin" / "python3"
        exe = str(python) if python.exists() else sys.executable
        proc = subprocess.run([exe, str(ROOT / "build.py")],
                              capture_output=True, text=True, cwd=ROOT)
        if proc.returncode != 0:
            log.error("build failed:\n%s", proc.stdout[-2000:] + proc.stderr[-2000:])
            state.mark_run("error", "build failed")
            return 1
        log.info("build ok")

    state.mark_run("ok", f"wrote {', '.join(wrote) or 'nothing'}")
    log.info("run finished at %s", now_iso())
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="global-nu daily update")
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch and check, write nothing")
    ap.add_argument("--no-ai", action="store_true",
                    help="skip the synthesis call, keep the previous narrative")
    ap.add_argument("--no-build", action="store_true", help="skip build.py")
    ap.add_argument("--quiet", action="store_true", help="log to file only")
    args = ap.parse_args(argv)

    try:
        with run_lock():
            return run(dry_run=args.dry_run, use_ai=not args.no_ai,
                       do_build=not args.no_build, verbose=not args.quiet)
    except LockBusy as exc:
        print(f"another run is in progress ({exc}) — nothing done", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
