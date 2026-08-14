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
from . import fetch_indico, fetch_inspire, fetch_nu_unbound, linkcheck, render
from . import state, synthesize
from .common import ROOT, get_logger, load_config, now_iso
from .lock import LockBusy, run_lock

# What the Experiments narrative may be written from. Deliberately WIDER than
# render.EXPERIMENTAL_CATS, which splits the digest's two streams: a result
# worth writing about counts whichever list it was filed under, and
# astro-ph.HE is where neutrino-telescope results appear. The two constants
# used to be one, which is how every astro-ph.HE preprint — theory included —
# ended up filed as "Experimental" on the digest page.
EXPERIMENT_POOL_CATS = ("hep-ex", "nucl-ex", "physics.ins-det", "astro-ph.HE")


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
                 if any(c.startswith(EXPERIMENT_POOL_CATS)
                        for c in (r.get("extra") or {}).get("categories", []))]
    return feeds + exp_arxiv


def run(*, dry_run: bool = False, use_ai: bool = True, do_build: bool = True,
        verbose: bool = True, from_cache: bool = False) -> int:
    log = get_logger("news", verbose=verbose)
    cfg = load_config()
    log.info("=" * 62)
    log.info("run started (dry_run=%s, ai=%s, build=%s, from_cache=%s)",
             dry_run, use_ai, do_build, from_cache)

    # ------------------------------------------------------------ 1. fetch --
    if from_cache:
        # Re-render the three pages from the records already on disk, calling
        # no API and no model. This exists because the pages are generated
        # files: correcting how one of them is *written* means editing the
        # renderer and regenerating, and a regeneration that had to re-fetch
        # would change what the page says at the same time as how it says it,
        # which makes the correction impossible to review.
        day = cache.latest_day_with("arxiv")          # None means today
        arxiv = cache.load_records("arxiv", day)
        feeds = cache.load_records("feeds", day)
        papers = cache.load_records("inspire", day)
        events = cache.load_records("indico", day)
        log.info("from cache (%s): %d arXiv, %d feed items, %d papers, %d events",
                 day or "today", len(arxiv), len(feeds), len(papers), len(events))
    else:
        arxiv = _safe("arxiv", lambda: fetch_arxiv.fetch(cfg, log), log, [])
        feeds = _safe("feeds", lambda: fetch_feeds.fetch(cfg, log), log, [])
        papers = _safe("inspire",
                       lambda: fetch_inspire.fetch_literature(cfg, log), log, [])
        events = _safe("indico", lambda: fetch_indico.fetch(cfg, log), log, [])
        nu_conf = _safe("nu-unbound",
                        lambda: fetch_nu_unbound.fetch(cfg, log), log, [])
        in_conf = _safe("inspire conferences",
                        lambda: fetch_inspire.fetch_conferences(cfg, log,
                                                                scope="neutrino"), log, [])
        gen_conf = _safe("inspire conferences (general)",
                         lambda: fetch_inspire.fetch_conferences(cfg, log,
                                                                 scope="general"), log, [])
        groups = [g for g in (events, nu_conf, in_conf, gen_conf) if g]
        if groups:
            events = conf_mod.sort_for_page(conf_mod.merge(groups, log))

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
    # Records read back from the cache were link-checked by the run that
    # fetched them; re-checking them would put the network back in the path of
    # a re-render that is supposed to touch nothing but the wording.
    bad = {} if from_cache else _safe(
        "linkcheck",
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

        # ------------------------------------------------------- 6. publish --
        # Until the site is live, the daily run stops at the build and the
        # pages sit on this machine. Once GitHub Pages serves global-nu.org,
        # a run that does not push means the published site freezes at
        # whatever was there on launch day while the digest keeps updating
        # locally — the failure would be silent and slow.
        #
        # Off by default. Turn it on by setting publish.push: true in
        # tools/news/config.yaml, at launch and not before.
        if (cfg.get("publish") or {}).get("push"):
            _push_generated(log)

    state.mark_run("ok", f"wrote {', '.join(wrote) or 'nothing'}")
    log.info("run finished at %s", now_iso())
    return 0


# Only these reach a commit. The daily job regenerates three pages and their
# built output; anything else in the tree is someone's work in progress and is
# not this job's to commit.
PUBLISHED_BY_JOB = [
    "site-src/content/digest.md", "site-src/content/news.md",
    "site-src/content/conferences.md",
    "site/digest.html", "site/news.html", "site/conferences.html",
    "site/sitemap.xml",
]

# tools.news.photos writes one photograph per city on the conference map,
# named from a slug of the city ("images/conf-shanghai.jpg") that this list
# cannot predict — which cities appear is only known after today's sources
# merge — so these are matched by glob rather than listed by name, in both
# trees: site-src/images-src (what build.py reads next time) and site/images
# (what the subtree push below actually deploys). Leaving these out of the
# commit would mean the map's photographs are drawn locally today and then
# never reach the live site, since `git subtree push` only ever pushes what
# was committed, not what merely exists in the working tree.
PHOTO_GLOBS = ["site-src/images-src/conf-*.jpg", "site/images/conf-*.jpg"]


def _push_generated(log) -> None:
    """Commit the regenerated pages and push. Never fatal to the run."""
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT)

    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch != "main":
        log.warning("publish: on branch %r, not main — not pushing", branch)
        return
    if not git("remote", "get-url", "origin").stdout.strip():
        log.warning("publish: no origin remote — not pushing")
        return

    existing = [p for p in PUBLISHED_BY_JOB if (ROOT / p).exists()]
    for pattern in PHOTO_GLOBS:
        existing += [str(p.relative_to(ROOT)) for p in sorted(ROOT.glob(pattern))]
    if git("add", "--", *existing).returncode != 0:
        log.error("publish: git add failed")
        return
    # `git diff --cached --quiet` exits 0 when the index matches HEAD.
    if git("diff", "--cached", "--quiet").returncode == 0:
        log.info("publish: the regenerated pages are unchanged — nothing to push")
        return

    msg = f"Daily refresh — {now_iso()[:10]}\n\nGenerated by tools/news/pipeline.py."
    if git("commit", "-m", msg).returncode:
        log.error("publish: commit failed")
        return

    # The remote moves without us: GitHub's own settings UI commits a CNAME to
    # the source branch when a custom domain is set, and that alone was enough
    # to make the first real run fail with "fetch first". An unattended job
    # that stops publishing because the remote is one commit ahead would go
    # unnoticed for as long as nobody happened to look, so it rebases first.
    # Generated pages rebase cleanly; anything that does not is a real conflict
    # and is left alone for a person to resolve.
    git("fetch", "origin", "main")
    rebase = git("pull", "--rebase", "origin", "main")
    if rebase.returncode:
        git("rebase", "--abort")
        log.error("publish: the remote has diverged and the rebase failed — "
                  "nothing pushed, resolve by hand:\n%s",
                  (rebase.stdout + rebase.stderr)[-800:])
        return

    push = git("push", "origin", "main")
    if push.returncode:
        log.error("publish: push failed:\n%s", (push.stdout + push.stderr)[-800:])
        return
    log.info("publish: pushed the regenerated pages to origin/main")

    # main is the repository; gh-pages is the site. GitHub Pages serves the
    # root of a branch, and site/ is a subdirectory, so the built tree is
    # published as a subtree. Pushing main alone would update the repo and
    # leave the live site exactly as it was — the failure this whole step
    # exists to prevent, wearing a different hat.
    deploy = git("subtree", "push", "--prefix", "site", "origin", "gh-pages")
    if deploy.returncode:
        log.error("publish: the site was NOT deployed — main has the new pages "
                  "but gh-pages does not:\n%s",
                  (deploy.stdout + deploy.stderr)[-800:])
        return
    log.info("publish: deployed site/ to gh-pages — the live site is current")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="global-nu daily update")
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch and check, write nothing")
    ap.add_argument("--no-ai", action="store_true",
                    help="skip the synthesis call, keep the previous narrative")
    ap.add_argument("--no-build", action="store_true", help="skip build.py")
    ap.add_argument("--from-cache", action="store_true",
                    help="re-render from the last cached fetch: no API call, "
                         "no model call, no link check")
    ap.add_argument("--quiet", action="store_true", help="log to file only")
    args = ap.parse_args(argv)

    try:
        with run_lock():
            return run(dry_run=args.dry_run,
                       use_ai=not args.no_ai and not args.from_cache,
                       do_build=not args.no_build, verbose=not args.quiet,
                       from_cache=args.from_cache)
    except LockBusy as exc:
        print(f"another run is in progress ({exc}) — nothing done", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
