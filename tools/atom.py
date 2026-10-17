"""Atom 1.0 feeds for the site (RFC 4287).

One writer for the three feeds — releases (tools/make_release.py), the arXiv
digest and the news (tools/news/render.py) — so they share one format and one
set of escaping rules. Entries are given already ordered newest first. Links
are absolute: a feed is read away from the site, where a relative URL means
nothing.
"""

from __future__ import annotations

import datetime as _dt
from xml.sax.saxutils import escape

SITE = "https://global-nu.org"


def _when(d: str) -> str:
    """A date or datetime string as RFC 3339; a bare date is midnight UTC."""
    d = (d or "").strip()
    if len(d) == 10:
        return d + "T00:00:00Z"
    try:
        return _dt.datetime.fromisoformat(d.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def feed(feed_id: str, title: str, page: str, self_path: str, subtitle: str,
         entries: list[dict]) -> str:
    """entries: dicts with id, title, link, updated, summary, and optionally
    authors (list of names) and categories (list of labels)."""
    updated = max((_when(e["updated"]) for e in entries), default=_when(""))
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           '<feed xmlns="http://www.w3.org/2005/Atom">',
           f"<id>{SITE}/{escape(feed_id)}</id>",
           f"<title>{escape(title)}</title>",
           f"<subtitle>{escape(subtitle)}</subtitle>",
           f'<link rel="alternate" type="text/html" href="{SITE}/{escape(page)}"/>',
           f'<link rel="self" type="application/atom+xml" href="{SITE}/{escape(self_path)}"/>',
           f"<updated>{updated}</updated>",
           "<author><name>global-nu.org, Bari group</name></author>"]
    for e in entries:
        out.append("<entry>")
        out.append(f"<id>{escape(e['id'])}</id>")
        out.append(f"<title>{escape(e['title'])}</title>")
        out.append(f'<link rel="alternate" href="{escape(e["link"])}"/>')
        out.append(f"<updated>{_when(e['updated'])}</updated>")
        for a in e.get("authors") or []:
            out.append(f"<author><name>{escape(a)}</name></author>")
        for c in e.get("categories") or []:
            out.append(f'<category term="{escape(c, {chr(34): "&quot;"})}"/>')
        out.append(f'<summary type="text">{escape(e.get("summary", ""))}</summary>')
        out.append("</entry>")
    out.append("</feed>")
    return "\n".join(out) + "\n"
