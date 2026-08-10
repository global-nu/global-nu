"""var/news/state.json — what the last run produced, and what to fall back to.

The narrative sections (Experiments, Theory) are the only part of the page
that costs an AI call. When that call fails, the page must not go blank and
must not silently pretend yesterday's prose is today's: the stored narrative
keeps its own `generated_at`, and the renderer prints that date next to it.
"""

from __future__ import annotations

from typing import Any

from .common import STATE, now_iso, read_json, write_json

EMPTY: dict[str, Any] = {
    "last_run": None,        # iso timestamp of the last run, successful or not
    "last_success": None,    # iso timestamp of the last run that published
    "last_status": "never",  # ok | partial | failed | never
    "last_message": "",
    "narrative": None,       # see save_narrative()
    "linkcheck": None,       # {"at":…, "checked":n, "failed":[{url,reason}]}
    "deploy": None,          # {"at":…, "ok":bool, "detail":str}
    "counts": {},            # per-source record counts of the last fetch
}


def load() -> dict:
    st = read_json(STATE, None)
    if not isinstance(st, dict):
        return dict(EMPTY)
    merged = dict(EMPTY)
    merged.update(st)
    return merged


def save(st: dict) -> None:
    write_json(STATE, st)


def update(**fields: Any) -> dict:
    st = load()
    st.update(fields)
    save(st)
    return st


# --------------------------------------------------------------------------- #
def save_narrative(narrative: dict) -> dict:
    """Store a fresh narrative, stamped with the moment it was generated.

    `narrative` is the validated model output: {"overview": str,
    "experiments": [...], "theory": [...]}, where every entry already had its
    ids checked against the cache.
    """
    st = load()
    payload = dict(narrative)
    payload["generated_at"] = now_iso()
    st["narrative"] = payload
    save(st)
    return payload


def previous_narrative() -> dict | None:
    """The last narrative that was generated, or None if there has never been
    one. The renderer labels it with its own date."""
    n = load().get("narrative")
    return n if isinstance(n, dict) and n.get("generated_at") else None


def mark_run(status: str, message: str = "") -> dict:
    st = load()
    st["last_run"] = now_iso()
    st["last_status"] = status
    st["last_message"] = message
    if status == "ok":
        st["last_success"] = st["last_run"]
    save(st)
    return st
