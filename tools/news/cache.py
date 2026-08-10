"""The dated raw-data cache, and the record shape everything else agrees on.

Why a cache at all: it makes run-on-run comparison possible ("what is new
since yesterday"), it lets --no-ai and the fallback path work without hitting
the network again, and — the important one — it is the authority for links.
The renderer resolves every URL from here, so a link on the page can only be
one that a fetcher actually retrieved.

Record shape (a plain dict, deliberately not a class — it is serialised to
JSON on every run and read back by three separate modules):

    id       str   stable, source-prefixed: "arxiv:2608.01890"
    source   str   arxiv | inspire | inspire-conf | feed
    title    str
    url      str   the primary link, always present
    links    dict  named alternatives: arxiv / inspire / doi / journal
    authors  str   display form, already truncated with "et al."
    date     str   YYYY-MM-DD, the date that matters for this source
    summary  str   plain text, tags stripped
    extra    dict  source-specific (categories, journal, place, score, …)
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

from .common import CACHE, now_iso, read_json, write_json

RECORD_FIELDS = ("id", "source", "title", "url", "links", "authors", "date",
                 "summary", "extra")

_ID_SAFE = re.compile(r"[^A-Za-z0-9._:/-]+")


def make_record(*, id: str, source: str, title: str, url: str,
                links: dict | None = None, authors: str = "", date: str = "",
                summary: str = "", extra: dict | None = None) -> dict:
    """Build a record, normalising the id so it survives a JSON round-trip and
    can be quoted verbatim inside the synthesis prompt."""
    clean_id = _ID_SAFE.sub("-", id.strip())
    return {
        "id": clean_id,
        "source": source,
        "title": title.strip(),
        "url": url.strip(),
        "links": {k: v for k, v in (links or {}).items() if v},
        "authors": authors.strip(),
        "date": date,
        "summary": summary,
        "extra": extra or {},
    }


def valid_record(rec: object) -> bool:
    """A record without an id or a primary URL cannot be rendered: the whole
    anti-invention scheme rests on being able to resolve id -> real link."""
    return (isinstance(rec, dict)
            and all(k in rec for k in RECORD_FIELDS)
            and bool(rec["id"]) and bool(rec["url"]) and bool(rec["title"]))


# --------------------------------------------------------------------------- #
def day_dir(day: _dt.date | None = None) -> Path:
    return CACHE / (day or _dt.date.today()).isoformat()


def store(source: str, records: list[dict], errors: list[str] | None = None,
          day: _dt.date | None = None) -> Path:
    d = day_dir(day)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{source}.json"
    write_json(path, {
        "source": source,
        "fetched_at": now_iso(),
        "errors": errors or [],
        "records": [r for r in records if valid_record(r)],
    })
    return path


def load(source: str, day: _dt.date | None = None) -> dict:
    return read_json(day_dir(day) / f"{source}.json",
                     {"source": source, "fetched_at": None, "errors": [],
                      "records": []})


def load_records(source: str, day: _dt.date | None = None) -> list[dict]:
    return [r for r in load(source, day).get("records", []) if valid_record(r)]


def latest_day_with(source: str, within_days: int = 7) -> _dt.date | None:
    """Most recent day that has a non-empty cache for `source`.

    Used by the fallback path: if today's fetch of one source failed, showing
    yesterday's records (clearly dated) beats showing nothing, and beats
    inventing anything.
    """
    today = _dt.date.today()
    for back in range(within_days + 1):
        day = today - _dt.timedelta(days=back)
        if load_records(source, day):
            return day
    return None


def index(records: list[dict]) -> dict[str, dict]:
    """id -> record. The renderer's lookup table."""
    return {r["id"]: r for r in records if valid_record(r)}


def prune(keep_days: int = 30) -> int:
    """Drop cache directories older than `keep_days`. Cheap housekeeping so an
    unattended daily run does not grow without bound."""
    if not CACHE.exists():
        return 0
    cutoff = _dt.date.today() - _dt.timedelta(days=keep_days)
    removed = 0
    for d in CACHE.iterdir():
        if not d.is_dir():
            continue
        try:
            day = _dt.date.fromisoformat(d.name)
        except ValueError:
            continue
        if day < cutoff:
            for f in d.iterdir():
                f.unlink()
            d.rmdir()
            removed += 1
    return removed
