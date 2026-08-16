#!/usr/bin/env python3
"""pipeline.run — the from_cache tense-refresh, and render steps through _safe.

    ./.venv/bin/python3 tools/tests/test_pipeline.py

Two things the final whole-branch review found:

  * pipeline.run(from_cache=True) replays conference records fetched — and
    tense-flagged (extra.upcoming/in_progress) — on an earlier day, exactly
    the shape of staleness fetch_nu_unbound's 304 path produces. It must run
    them through conferences.sort_for_page (which now re-derives the tense
    from extra.closing against today, see conferences._refresh_tense) rather
    than handing them to render.conferences as-is.

  * render.digest/conferences/news used to be called bare, unlike every fetch
    step, which all go through pipeline._safe. render.conferences now does
    network requests, PIL decoding and cache writes on top of what used to be
    plain string formatting, so it can fail the way a fetch step can — and
    the module docstring's promise ("a step that fails is logged and
    skipped") must hold for it too.

Everything that would touch the network, the real var/news state, or the
real content pages is monkeypatched or redirected to a temp file; this suite
makes no network call and writes nothing under the real var/ or site-src/.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import (archive, cache, common, conferences as conf_mod,
                         pipeline, render, state)  # noqa: E402

# Send this run's logging to a throwaway directory before anything configures
# a logger. The pipeline writes to var/news/logs/news.log, and that file is
# how a human diagnoses a real outage — so a test must not write into it. This
# suite provokes a failure on purpose, and the line it produces reads
# "WARNING render conferences: failed (RuntimeError: simulated ...)". Left in
# the operational log it is indistinguishable, at a glance on a bad morning,
# from a failure that actually happened; it was mistaken for one on
# 2026-08-16. `common.LOGS` is read inside get_logger, not captured at import,
# so rebinding it here is enough.
common.LOGS = Path(tempfile.mkdtemp(prefix="gnu-test-logs-"))

# pipeline.run's archive step (see pipeline._archive) calls archive.save,
# archive.write_pages and archive.update_index unconditionally — they are not
# behind the render.* seams this file patches below. Left pointed at the
# module's real paths, two full pipeline.run() calls below silently rewrote
# this checkout's actual site-src/content/digest/*.md with a fresh stamp on
# every run of this test file, exactly the "writes nothing under the real
# var/ or site-src/" this docstring promises and, on 2026-08-16, did not
# keep. Redirected to a throwaway directory for the lifetime of this file.
_archive_tmp = Path(tempfile.mkdtemp(prefix="gnu-test-archive-"))
archive.STORE = _archive_tmp / "archive.json"
archive.CONTENT_DIR = _archive_tmp / "content" / "digest"
archive.DIGEST_MD = _archive_tmp / "digest.md"
archive.DIGEST_MD.write_text(
    f"intro\n\n{archive.BEGIN}\n{archive.END}\n", encoding="utf-8")

problems: list[str] = []
checks = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
    else:
        problems.append(label)
        print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


def _rec(title, opening, closing, upcoming_flag):
    """A minimal, valid conference record — same shape cache.load_records
    hands back — with a deliberately STALE tense flag: `upcoming_flag` is
    what a fetcher wrote on some earlier day, independent of what
    opening/closing actually say today."""
    return {
        "id": f"nu:{title}", "source": "inspire-conf", "title": title,
        "url": f"https://example.org/{title}", "links": {}, "authors": "",
        "date": opening, "summary": "",
        "extra": {"acronym": title, "place": "Bari, IT", "city": "Bari",
                  "country_code": "IT", "opening": opening, "closing": closing,
                  "provider": "nu-unbound", "scope": "neutrino",
                  "upcoming": upcoming_flag, "in_progress": upcoming_flag,
                  "flagship": True},
    }


# A record whose flags say "still upcoming" (as a stale cache entry would),
# but whose closing date is three weeks in the past.
_stale = _rec("Stale Cached Meeting", "2020-01-01", "2020-01-05", True)


def _fake_load_records(source, day=None):
    return {"indico": [_stale], "arxiv": [], "feeds": [], "inspire": []}.get(source, [])


_captured_render_conf_records: list[dict] = []


def _capturing_render_conferences(records, log, stamp=None):
    _captured_render_conf_records.extend(records)
    return True


def _noop_render_ok(*a, **k):
    return True


_orig_load_records = cache.load_records
_orig_latest_day_with = cache.latest_day_with
_orig_render_digest = render.digest
_orig_render_conferences = render.conferences
_orig_render_news = render.news
_orig_state_state = state.STATE
_orig_pipeline_state_ref = None  # pipeline imports the module, not the name

cache.load_records = _fake_load_records
cache.latest_day_with = lambda source, within_days=7: None
render.digest = _noop_render_ok
render.conferences = _capturing_render_conferences
render.news = _noop_render_ok
state.STATE = Path(tempfile.mkdtemp()) / "state.json"

try:
    rc = pipeline.run(dry_run=False, use_ai=False, do_build=False,
                      verbose=False, from_cache=True)
finally:
    cache.load_records = _orig_load_records
    cache.latest_day_with = _orig_latest_day_with
    render.digest = _orig_render_digest
    render.conferences = _orig_render_conferences
    render.news = _orig_render_news
    state.STATE = _orig_state_state

check("pipeline.run(from_cache=True) completes and reports ok", rc == 0, rc)
check("render.conferences was reached with at least the stale record",
      len(_captured_render_conf_records) == 1, _captured_render_conf_records)
_seen = _captured_render_conf_records[0] if _captured_render_conf_records else {}
check("the from_cache path recomputed the stale record's tense before render: "
      "extra.upcoming is now False, not the stale cached True",
      _seen.get("extra", {}).get("upcoming") is False, _seen.get("extra"))
check("in_progress was recomputed alongside it",
      _seen.get("extra", {}).get("in_progress") is False, _seen.get("extra"))


# --------------------------------------------------------------------------- #
# render.conferences failing must not take the whole run down, and must not
# stop render.news from still being attempted — the same "one bad step is
# logged and skipped, the rest of the run continues" contract every fetch
# step already has via pipeline._safe.
# --------------------------------------------------------------------------- #
_news_called = []


def _raising_render_conferences(records, log, stamp=None):
    raise RuntimeError("simulated render.conferences failure")


def _tracking_render_news(*a, **k):
    _news_called.append(True)
    return True


cache.load_records = _fake_load_records
cache.latest_day_with = lambda source, within_days=7: None
render.digest = _noop_render_ok
render.conferences = _raising_render_conferences
render.news = _tracking_render_news
state.STATE = Path(tempfile.mkdtemp()) / "state.json"

try:
    rc2 = pipeline.run(dry_run=False, use_ai=False, do_build=False,
                       verbose=False, from_cache=True)
except Exception as exc:                                      # noqa: BLE001
    rc2 = None
    _raised = exc
else:
    _raised = None
finally:
    cache.load_records = _orig_load_records
    cache.latest_day_with = _orig_latest_day_with
    render.digest = _orig_render_digest
    render.conferences = _orig_render_conferences
    render.news = _orig_render_news
    state.STATE = _orig_state_state

check("a raising render.conferences does not propagate out of pipeline.run",
      _raised is None, repr(_raised))
check("pipeline.run still returns its normal ok status despite the failed step",
      rc2 == 0, rc2)
check("render.news still ran after render.conferences failed",
      bool(_news_called), _news_called)


# --------------------------------------------------------------------------- #
# pipeline._push_generated / PHOTO_GLOBS seam (final-fix-round-2 HIGH, and the
# finding this branch has now failed to close twice): a takedown's deletion
# must be STAGED, COMMITTED and PUSHED — not silently dropped because the
# add-list was built by globbing the working tree in Python, which only ever
# sees files that still exist. tools/tests/test_photos.py's own section 11
# cannot see this: it proves the bytes are gone from disk, not that the
# deletion ever reaches a commit — that only happens at this seam, between
# photos.py and pipeline.py. This exercises the REAL _push_generated against
# a throwaway git repository (a local bare "origin", so fetch/rebase/push all
# run for real), not a reimplementation of its logic.
# --------------------------------------------------------------------------- #
import shutil                                          # noqa: E402
import subprocess                                       # noqa: E402


class _CollectingLog:
    """Same shape as the real logger, but keeps every message instead of
    printing it, so a test can assert on exactly what _push_generated
    reported — in particular, that no "the remote has diverged" misdiagnosis
    ever fires once the staging bug is fixed."""

    def __init__(self):
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def _fmt(self, msg, args):
        return msg % args if args else msg

    def info(self, msg, *a, **k):
        self.infos.append(self._fmt(msg, a))

    def warning(self, msg, *a, **k):
        self.warnings.append(self._fmt(msg, a))

    def error(self, msg, *a, **k):
        self.errors.append(self._fmt(msg, a))

    def debug(self, *a, **k):
        pass


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _build_repo_with_a_tracked_photo() -> tuple[Path, Path]:
    """A throwaway git repository shaped just enough like the real one to
    exercise _push_generated for real: both photo trees, one conf-*.jpg
    already TRACKED in each (the exact shape PHOTO_GLOBS matches, and the
    exact shape a takedown finds — see photos.py's module docstring: the 31
    conf-*.jpg files are git-tracked in both trees), and a local bare
    "origin" the repo has already pushed to, so fetch/pull --rebase/push all
    run against a real remote rather than being stubbed out."""
    root = Path(tempfile.mkdtemp())
    remote = Path(tempfile.mkdtemp()) / "origin.git"
    _git(root, "init", "-q", "-b", "main", ".")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    (root / "site-src" / "images-src").mkdir(parents=True)
    (root / "site" / "images").mkdir(parents=True)
    (root / "site-src" / "images-src" / "conf-testcity.jpg").write_bytes(b"old-src-bytes")
    (root / "site" / "images" / "conf-testcity.jpg").write_bytes(b"old-site-bytes")
    (root / "site-src" / "content").mkdir(parents=True)
    (root / "site-src" / "content" / "conferences.md").write_text("old content\n")
    (root / "site").mkdir(exist_ok=True)
    (root / "site" / "conferences.html").write_text("<html>old</html>\n")
    add = _git(root, "add", "-A")
    assert add.returncode == 0, add.stderr
    commit = _git(root, "commit", "-q", "-m", "seed")
    assert commit.returncode == 0, commit.stderr
    _git(remote.parent, "init", "-q", "--bare", str(remote))
    _git(root, "remote", "add", "origin", str(remote))
    push = _git(root, "push", "-q", "-u", "origin", "main")
    assert push.returncode == 0, push.stderr
    return root, remote


def _run_takedown_through_pipeline() -> dict:
    """Simulate a takedown (delete the tracked photo from both trees, the
    way photos._delete_local_copies does) and a same-day content
    regeneration, then call the REAL pipeline._push_generated against the
    throwaway repo, and report everything a RED/GREEN check needs."""
    root, remote = _build_repo_with_a_tracked_photo()
    try:
        (root / "site-src" / "images-src" / "conf-testcity.jpg").unlink()
        (root / "site" / "images" / "conf-testcity.jpg").unlink()
        (root / "site-src" / "content" / "conferences.md").write_text("new content\n")
        (root / "site" / "conferences.html").write_text("<html>new</html>\n")

        log = _CollectingLog()
        _orig_root = pipeline.ROOT
        pipeline.ROOT = root
        try:
            pipeline._push_generated(log)
        finally:
            pipeline.ROOT = _orig_root

        status_after = _git(root, "status", "--porcelain").stdout
        tracked_after = _git(root, "ls-tree", "-r", "HEAD", "--name-only").stdout
        head_subject = _git(root, "log", "-1", "--format=%s").stdout.strip()
        local_head = _git(root, "rev-parse", "HEAD").stdout.strip()
        remote_head = _git(remote, "rev-parse", "main").stdout.strip()
        gh_pages = _git(remote, "branch", "--list", "gh-pages").stdout
        rebase_probe = _git(root, "pull", "--rebase", "origin", "main")
        return {
            "status_after": status_after,
            "tracked_after": tracked_after,
            "head_subject": head_subject,
            "local_head": local_head,
            "remote_head": remote_head,
            "gh_pages": gh_pages,
            "rebase_probe_rc": rebase_probe.returncode,
            "rebase_probe_out": rebase_probe.stdout + rebase_probe.stderr,
            "log": log,
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(remote, ignore_errors=True)
        shutil.rmtree(remote.parent, ignore_errors=True)


_r = _run_takedown_through_pipeline()

check("git status --porcelain is clean after _push_generated — the "
      "deletion (and the regenerated content) reached a commit, nothing "
      "left sitting unstaged",
      _r["status_after"] == "", _r["status_after"])
check("the taken-down file is gone from the committed tree in "
      "site-src/images-src, not just off disk",
      "site-src/images-src/conf-testcity.jpg" not in _r["tracked_after"],
      _r["tracked_after"])
check("the taken-down file is gone from the committed tree in site/images "
      "too — the tree the subtree push actually deploys from",
      "site/images/conf-testcity.jpg" not in _r["tracked_after"],
      _r["tracked_after"])
check("a new commit was actually made (HEAD moved past the seed commit)",
      _r["head_subject"] != "seed", _r["head_subject"])
check("the commit was pushed to origin/main — local and remote HEAD match",
      _r["local_head"] == _r["remote_head"] and bool(_r["local_head"]),
      (_r["local_head"], _r["remote_head"]))
check("site/ was deployed to gh-pages by the subtree push",
      "gh-pages" in _r["gh_pages"], _r["gh_pages"])
check("no error was logged — in particular, no misdiagnosed \"the remote "
      "has diverged\" (that message is what a dirty tree from an unstaged "
      "deletion used to produce, even though the remote never diverged)",
      _r["log"].errors == [], _r["log"].errors)
check("a genuine git pull --rebase against this same remote, run right "
      "after _push_generated, is not blocked by a dirty tree",
      _r["rebase_probe_rc"] == 0, _r["rebase_probe_out"])


print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — from_cache tense refresh, render steps "
     "through _safe, and a takedown's deletion staged/committed/pushed by "
     "the real _push_generated in a throwaway git repository")
