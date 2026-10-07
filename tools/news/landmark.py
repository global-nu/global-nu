"""Landmark news: the items a news page may never miss, bury or wait a day for.

On 6 October 2026 Francis Halzen won the Nobel Prize in Physics for IceCube,
and the next morning Neutrino News still did not say so. Nothing failed. The
daily run had fired at 07:30 on the 6th, four hours before the announcement in
Stockholm; Physics World had the story at 11:52, the IceCube feed at 21:20,
and the page would have learned about it only at 07:30 on the 7th — and then
only as one record among ten, in whatever position the model chose to give it.

Three holes, so three rules, all deterministic — none of them depends on the
model noticing that a Nobel prize matters:

  * `tag()` — a record whose TITLE names a landmark (a Nobel prize, a
    Breakthrough prize, …) is marked as such. The title, not the summary: a
    summary that says "Nobel laureate Takaaki Kajita commented…" is ordinary
    news, and pinning it would teach the reader to ignore the pin.
  * `pin()` — a fresh landmark (at most `pin_days` old) is exempt from the
    per-feed and overall caps and sorted first, so a chatty week cannot push
    it off the page.
  * `enforce()` — after synthesis, a fresh landmark must be cited by the FIRST
    item of the first news section, and named in the overview. If the model
    left it out, the item is written here from the record itself (its title
    and its own summary) and the overview is prefixed with the title. A
    reused narrative, on a day when the AI call failed, gets the same
    treatment: the guarantee does not depend on the call working.

And the fourth hole, the clock, is closed by `pending()` together with
`pipeline --if-landmark`: an hourly check that fetches the feeds only, and
runs the full pipeline only when a fresh landmark is not yet on the page. On
every other hour it exits 0 without writing a line — a check that runs
twenty-four times a day is harmless only if the normal case is silent.
"""

from __future__ import annotations

import datetime as _dt
import re

# Used when an edition's config has no `landmarks.keywords`. Prizes only, on
# purpose: "discovery" or "first observation" appear in press-release titles
# every week, and a pin that fires every week is not a pin.
DEFAULT_KEYWORDS = [
    "nobel prize", "nobel laureate", "nobel physics", "physics nobel",
    "nobel 20",                        # "Halzen, Nobel 2026"
    "breakthrough prize", "wolf prize", "dirac medal", "shaw prize",
    "kavli prize", "pontecorvo prize", "sakurai prize", "panofsky prize",
    "gruber prize", "crafoord prize",
]
DEFAULT_PIN_DAYS = 7


def _conf(cfg: dict) -> dict:
    return dict(cfg.get("landmarks") or {})


def enabled(cfg: dict) -> bool:
    return bool(_conf(cfg).get("enabled", True))


def _patterns(cfg: dict) -> list[re.Pattern]:
    words = _conf(cfg).get("keywords") or DEFAULT_KEYWORDS
    pats = []
    for kw in words:
        parts = [re.escape(p) for p in re.split(r"[\s\-]+", str(kw)) if p]
        if parts:
            pats.append(re.compile(r"(?<!\w)" + r"[\s\-]+".join(parts),
                                   re.IGNORECASE))
    return pats


def is_landmark(rec: dict, cfg: dict) -> bool:
    title = str(rec.get("title", ""))
    return any(p.search(title) for p in _patterns(cfg))


def tag(records: list[dict], cfg: dict) -> list[dict]:
    """Mark landmark records in place (extra.landmark = True). Idempotent."""
    if not enabled(cfg):
        return records
    for rec in records:
        if is_landmark(rec, cfg):
            rec.setdefault("extra", {})["landmark"] = True
    return records


def is_fresh(rec: dict, cfg: dict, today: _dt.date | None = None) -> bool:
    """A landmark that is still news: tagged and at most `pin_days` old."""
    if not (rec.get("extra") or {}).get("landmark"):
        return False
    try:
        day = _dt.date.fromisoformat(str(rec.get("date", ""))[:10])
    except ValueError:
        return False
    today = today or _dt.date.today()
    pin_days = int(_conf(cfg).get("pin_days", DEFAULT_PIN_DAYS))
    return 0 <= (today - day).days <= pin_days


def fresh(records: list[dict], cfg: dict,
          today: _dt.date | None = None) -> list[dict]:
    if not enabled(cfg):
        return []
    return [r for r in records if is_fresh(r, cfg, today)]


def pin(records: list[dict], cfg: dict, cap: int,
        today: _dt.date | None = None) -> list[dict]:
    """Fresh landmarks first and never cut; the rest fill what is left of `cap`.

    `cap` still bounds the total unless the landmarks alone exceed it — then
    they all stay: a cap exists to keep ordinary news short, not to drop the
    news of the year.
    """
    top = [r for r in records if is_fresh(r, cfg, today)]
    rest = [r for r in records if not is_fresh(r, cfg, today)]
    return top + rest[:max(cap - len(top), 0)]


# --------------------------------------------------------------------------- #
# after synthesis
# --------------------------------------------------------------------------- #
def _first_sentences(text: str, n: int = 2, limit: int = 420) -> str:
    text = " ".join(str(text).split())
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = " ".join(parts[:n]).strip()
    if len(out) > limit:
        out = out[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return out


# Words that say "a prize" without saying which. What is left of a keyword
# after removing them names the prize: "physics nobel" and "nobel 20" are both
# the Nobel, so three outlets reporting it are one event, not three items.
_GENERIC = {"prize", "prizes", "medal", "laureate", "laureates", "physics",
            "20", "award", "awarded"}


def family(rec: dict, cfg: dict) -> str | None:
    """Which prize a landmark title names ("nobel", "breakthrough", …)."""
    title = str(rec.get("title", ""))
    words = _conf(cfg).get("keywords") or DEFAULT_KEYWORDS
    for kw, pat in zip(words, _patterns(cfg)):
        if pat.search(title):
            name = [w for w in re.split(r"[\s\-]+", str(kw).lower())
                    if w and w not in _GENERIC]
            return name[0] if name else str(kw).lower()
    return None


def enforce(narrative: dict | None, landmarks: list[dict], cfg: dict,
            sections_cfg: list[dict], log) -> dict | None:
    """Make every fresh landmark lead the page. Returns the narrative.

    One event per prize family: the item that cites ANY record of the family
    goes to the top of the first news section; if no item cites one, an item
    is written from the newest record of the family. Never invents prose: an
    item written here is the record's own title and the first sentences of
    its own summary, cited by its own id — the rule the model is held to,
    applied by code.
    """
    if not landmarks:
        return narrative
    news_keys = [s["key"] for s in sections_cfg
                 if s.get("kind", "news") == "news"]
    if not news_keys:
        return narrative
    from .synthesize import scrub

    out = {k: (list(v) if isinstance(v, list) else v)
           for k, v in dict(narrative or {}).items()}
    lead = news_keys[0]
    cap = next((int(s.get("max", 10)) for s in sections_cfg
                if s["key"] == lead), 10)

    families: dict[str, list[dict]] = {}
    for rec in landmarks:
        families.setdefault(family(rec, cfg) or rec["id"], []).append(rec)
    # Oldest family first, so the newest event ends up on top.
    order = sorted(families, key=lambda f: max(r.get("date", "")
                                               for r in families[f]))
    for fam in order:
        ids = {r["id"] for r in families[fam]}
        item = None
        for key in news_keys:
            items = out.get(key) or []
            hit = next((i for i, it in enumerate(items)
                        if ids & set(it.get("ids") or [])), None)
            if hit is not None:
                item = items.pop(hit)
                out[key] = items
                break
        if item is None:
            rec = max(families[fam], key=lambda r: r.get("date", ""))
            heading, _ = scrub(rec.get("title", ""))
            text, _ = scrub(_first_sentences(rec.get("summary", "")) or heading)
            item = {"heading": heading, "text": text, "ids": [rec["id"]]}
            log.warning("landmark: the narrative did not cite %s (%s) — "
                        "written from the record itself", rec["id"],
                        rec.get("title", "")[:80])
        out[lead] = [item] + list(out.get(lead) or [])
    out[lead] = out[lead][:max(cap, len(families))]

    overview = str(out.get("overview", ""))
    missing = [f for f in order
               if not re.search(rf"(?<!\w){re.escape(f)}", overview, re.I)]
    if missing:
        newest = max(families[order[-1]], key=lambda r: r.get("date", ""))
        title, _ = scrub(newest.get("title", ""))
        out["overview"] = (title.rstrip(".") + ". " + overview).strip()
        log.warning("landmark: the overview did not mention %s — prefixed "
                    "with the record's title", ", ".join(missing))
    return out


def prompt_block(landmarks: list[dict]) -> str:
    """Told to the model too: the code guarantees the outcome, the prompt
    makes it likely that the guarantee is written in good English."""
    if not landmarks:
        return ""
    ids = ", ".join(r["id"] for r in landmarks)
    return (
        "## Landmark news — must lead the page\n\n"
        f"These records report a landmark event (a major prize): {ids}. "
        "The FIRST item of the first news section must be about it, citing "
        "those ids, and the overview's first sentence must name it. Write it "
        "from the records only, like everything else.\n\n")


# --------------------------------------------------------------------------- #
# the hourly check
# --------------------------------------------------------------------------- #
def pending(feeds: list[dict], cfg: dict, published: list[str],
            today: _dt.date | None = None) -> list[dict]:
    """Fresh landmarks whose id is not among those already published.

    Keyed on the record id, which is a hash of the URL: the same story from a
    second outlet is a second id and triggers a second run. That is the safe
    side of the trade — one extra rebuild — and the run is idempotent.
    """
    seen = set(published or [])
    return [r for r in fresh(tag(feeds, cfg), cfg, today) if r["id"] not in seen]
