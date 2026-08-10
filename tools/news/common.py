"""Paths, configuration, logging and the HTTP helper shared by the pipeline.

Ported from the pipeline of home.ba.infn.it/~marrone: the fetching, caching,
locking and synthesis layers are the same proven code, pointed at this site's
pages. Only the presentation is written fresh, because the two sites present
the same material differently.

Everything mutable the pipeline produces lives under var/, which is outside
site/ and outside the git index, so a cache file cannot end up published.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import logging.handlers
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("Missing dependency: PyYAML  ->  ./setup-venv.sh")
try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("Missing dependency: requests  ->  ./setup-venv.sh")

ROOT = Path(__file__).resolve().parents[2]
NEWS = ROOT / "tools" / "news"
CONFIG = NEWS / "config.yaml"
VAR = ROOT / "var" / "news"
CACHE = VAR / "cache"
LOGS = VAR / "logs"
STATE = VAR / "state.json"
LOCK = VAR / "run.lock"

SITE_SRC = ROOT / "site-src"
CONTENT = SITE_SRC / "content"
DATA = SITE_SRC / "data"
NEWS_PAGE = CONTENT / "news.md"
DIGEST_PAGE = CONTENT / "digest.md"
CONFERENCES_PAGE = CONTENT / "conferences.md"
RESOURCES = DATA / "news_resources.yaml"

# This site keeps its interests in its own config.yaml rather than borrowing
# the personal site's file: the two are free to diverge.
INTERESTS = NEWS / "interests.md"

USER_AGENT = ("global-nu/1.0 (https://global-nu.org; "
              "antonio.marrone@ba.infn.it)")

LOG_MAX_BYTES = 1_000_000
LOG_BACKUPS = 5


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #
def load_config(path: Path | None = None) -> dict:
    """Read the config for *use*. Plain dicts, plain PyYAML — callers that only
    read must not have to care that the file is comment-annotated."""
    with open(path or CONFIG, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    if not isinstance(cfg, dict):
        raise ValueError(f"{path or CONFIG}: expected a mapping at the top level")
    return cfg


def _round_tripper():
    """ruamel's round-trip YAML, configured to match the file's own layout."""
    from ruamel.yaml import YAML
    rt = YAML()
    rt.preserve_quotes = True
    rt.width = 88
    rt.indent(mapping=2, sequence=4, offset=2)
    return rt


def load_config_rt(path: Path | None = None):
    """Read the config for *editing*, keeping comments and order.

    Returns a ruamel CommentedMap, which behaves like a dict.
    """
    with open(path or CONFIG, encoding="utf-8") as fh:
        return _round_tripper().load(fh)


def save_config(cfg, path: Path | None = None) -> None:
    """Write the config back without destroying it.

    This file is documentation as much as configuration — why the arXiv window
    is 168 hours, which .htaccess directives the server refuses, why a feed is
    disabled. `yaml.safe_dump` silently drops every one of those comments, and
    a dashboard save would quietly strip the reasoning out of the project. So
    edits go through ruamel's round-trip loader, which keeps comments, key
    order and quoting.

    Pass the object returned by `load_config_rt`, mutated. A plain dict also
    works, but then there are no comments to preserve — the caller has already
    thrown them away by reading with `load_config`.
    """
    target = path or CONFIG
    tmp = target.with_suffix(target.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        _round_tripper().dump(cfg, fh)
    tmp.replace(target)


# --------------------------------------------------------------------------- #
# logging
# --------------------------------------------------------------------------- #
def get_logger(name: str = "news", verbose: bool = True) -> logging.Logger:
    """One rotating file plus stderr. Idempotent: repeated calls do not stack
    handlers, which matters because the dashboard imports the pipeline."""
    log = logging.getLogger(name)
    if getattr(log, "_news_configured", False):
        # Already set up — but possibly by an earlier caller that did not know
        # the verbosity yet. run_lock() takes the lock (and logs) before the
        # pipeline gets to choose, so a later --quiet must still be honoured,
        # or the dashboard's crash sink fills up with ordinary INFO lines.
        _set_stderr(log, verbose)
        return log
    log.setLevel(logging.DEBUG)
    LOGS.mkdir(parents=True, exist_ok=True)

    fh = logging.handlers.RotatingFileHandler(
        LOGS / "news.log", maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS,
        encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s",
                                      "%Y-%m-%d %H:%M:%S"))
    log.addHandler(fh)

    _set_stderr(log, verbose)
    log._news_configured = True          # type: ignore[attr-defined]
    return log


_STDERR_TAG = "news-stderr"


def _set_stderr(log: logging.Logger, verbose: bool) -> None:
    """Attach or detach the stderr handler.

    verbose=False means the file only, not "a quieter stderr". The dashboard
    runs the pipeline with --quiet and captures its stderr separately; if
    ordinary lines still went there, every one would appear both in news.log
    and again in the crash sink shown underneath it on the status page.
    """
    existing = [h for h in log.handlers if getattr(h, "name", "") == _STDERR_TAG]
    if verbose and not existing:
        sh = logging.StreamHandler(sys.stderr)
        sh.name = _STDERR_TAG
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
        log.addHandler(sh)
    elif not verbose:
        for h in existing:
            log.removeHandler(h)


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def http_get(url: str, *, timeout: int = 30, params: dict | None = None,
             headers: dict | None = None, log: logging.Logger | None = None
             ) -> requests.Response | None:
    """GET that returns None instead of raising.

    Every caller treats an unreachable source as "omit this source", never as
    "make something up" — the rule from CLAUDE.md, enforced by giving callers
    nothing to work with when the fetch fails.
    """
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    try:
        r = requests.get(url, params=params, headers=hdrs, timeout=timeout)
    except requests.RequestException as exc:
        if log:
            log.warning("fetch failed: %s (%s)", url, exc.__class__.__name__)
        return None
    if r.status_code != 200:
        if log:
            log.warning("fetch failed: %s (HTTP %s)", r.url, r.status_code)
        return None
    return r


# --------------------------------------------------------------------------- #
# text
# --------------------------------------------------------------------------- #
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(raw: str | None) -> str:
    """Strip tags and collapse whitespace. Feed summaries arrive as HTML."""
    if not raw:
        return ""
    import html as _html
    text = _TAG_RE.sub(" ", raw)
    text = _html.unescape(text)
    text = unicodedata.normalize("NFC", text)
    return _WS_RE.sub(" ", text).strip()


def truncate(text: str, limit: int) -> str:
    """Cut on a word boundary; the ellipsis marks that it was cut."""
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:.")
    return cut + " …"


def today() -> _dt.date:
    return _dt.date.today()


def now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def pretty_stamp(iso: str | None) -> str:
    """'2026-08-09T07:31:04+02:00' -> '9 August 2026, 07:31 CEST'."""
    if not iso:
        return "never"
    try:
        dt = _dt.datetime.fromisoformat(iso)
    except ValueError:
        return iso
    # fromisoformat gives a fixed-offset zone whose name is "UTC+02:00".
    # Converting to the local zone attaches real tzinfo, so the page says
    # "CEST" like a person would.
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    tz = dt.tzname() or ""
    return f"{dt.day} {dt:%B %Y}, {dt:%H:%M}" + (f" {tz}" if tz else "")


# --------------------------------------------------------------------------- #
# small JSON helpers, used for the cache and the state file
# --------------------------------------------------------------------------- #
def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, payload: Any) -> None:
    """Atomic: a run interrupted mid-write must not leave a truncated state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(path)
