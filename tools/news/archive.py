"""Keep every edition of the arXiv digest, filed by announcement date.

The digest page is overwritten every morning, so without this the previous
day simply ceases to exist. This module keeps the records that reached the
page and regenerates a page per day and per calendar month from them.

Why announcement date and not the day the page showed it: `window_hours` is
168, so each edition draws on the last seven days and consecutive editions
overlap almost entirely — 92 of 100 identifiers in the record cache appear on
more than one day. Keyed on the run, the archive would repeat itself seven
times over. Keyed on the record's own `date`, every paper is filed once, and a
late run is harmless: a paper announced on the 12th that first enters the
window on the 14th still lands under the 12th.

Nothing here ever deletes. Pages are regenerated from the store rather than
appended to, so any page can be rebuilt from scratch and cannot drift.
"""
from __future__ import annotations

import json
from pathlib import Path

from .common import VAR

STORE = VAR / "archive.json"


def load() -> dict[str, list[dict]]:
    """The store, or an empty one. A missing or unreadable file is empty.

    Never fatal: the archive is a record of the digest, and losing it must
    not stop the digest from being published today.
    """
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(store: dict[str, list[dict]]) -> None:
    """Write the store, sorted, so a run that changes nothing writes nothing."""
    STORE.parent.mkdir(parents=True, exist_ok=True)
    ordered = {day: store[day] for day in sorted(store)}
    STORE.write_text(json.dumps(ordered, indent=1, ensure_ascii=False,
                                sort_keys=False) + "\n", encoding="utf-8")


def merge(store: dict[str, list[dict]],
          records: list[dict]) -> dict[str, list[dict]]:
    """File records under their own dates, merging by arXiv identifier.

    Returns a new store; the argument is not modified, so a caller can
    compare before and after to see whether anything actually changed.

    A record without a usable `date` or `id` is dropped. Filing it under today
    would place a paper in a day it was not announced in, and this project
    leaves out what it cannot establish rather than guessing it.
    """
    out = {day: list(items) for day, items in store.items()}
    for record in records:
        day = str(record.get("date") or "")
        ident = record.get("id")
        if not day or not ident:
            continue
        bucket = out.setdefault(day, [])
        for i, existing in enumerate(bucket):
            if existing.get("id") == ident:
                bucket[i] = record        # improved fields replace the old copy
                break
        else:
            bucket.append(record)
    # Sorted by identifier so a day's page is byte-identical between runs that
    # saw the same papers in a different order — otherwise every run would
    # rewrite every page and the daily commit would be noise.
    for day in out:
        out[day] = sorted(out[day], key=lambda r: str(r.get("id")))
    return out
