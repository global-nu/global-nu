"""The one AI call of the day, and the rules that keep it honest.

The single most dangerous thing an automatically generated physics page can do
is state a result, a number or a link that nobody published. CLAUDE.md exists
because that already happened once on this site, with oscillation parameters
attributed to the wrong paper.

So the model here is deliberately not trusted with facts that can be checked
mechanically:

  * it never emits a URL — it cites record ids, and render.py looks the links
    up in the fetch cache;
  * an item citing an id that was not in the input is dropped, not repaired;
  * any URL that appears in its prose anyway is stripped, and the item is
    logged as suspect;
  * it runs with tools disabled, so "verified" can only mean "was in the
    input", never "I went and looked".

What is left for the model is the part no fetcher can do: deciding what
matters this week and saying it in English.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys

from .common import truncate

# Tools are off: this call must be a pure function of its prompt. A model that
# can browse might "check" a claim and then write something no fetcher ever
# retrieved, which is exactly the failure this design prevents.
DISALLOWED = ["Bash", "Read", "Write", "Edit", "WebFetch", "WebSearch",
              "Glob", "Grep", "Task"]

URL_RE = re.compile(r"https?://\S+|\bwww\.\S+", re.I)
FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.S)

# A URL is not the only way to name a source falsely. A bare DOI or arXiv
# number in the prose reads exactly like a citation, and nothing downstream
# checks it — it is not a link, so the id-resolution guard never sees it. The
# prompt forbids these; this is what happens when the instruction slips.
IDENT_RE = re.compile(
    r"\b(?:arXiv:\s*\d{4}\.\d{4,5}(?:v\d+)?"      # arXiv:2608.01890v2
    r"|10\.\d{4,9}/[^\s,;)\]]+"                    # a bare DOI
    r"|\b\d{4}\.\d{4,5}v\d+)\b",                   # 2608.01890v1
    re.I)

SYSTEM = (
    "You are writing the daily news page of a neutrino physicist's academic "
    "website. Accuracy outranks fluency, completeness and interest. "
    "You answer with JSON only."
)

PROMPT = """You are given today's fetched records about neutrino physics. Write the \
narrative sections of a news page from THESE RECORDS ONLY.

## Absolute rules

1. Every statement you write must be supported by the records below. If the \
records do not say it, you do not write it.
2. Never write a URL, a DOI or an arXiv number in your prose. Cite records by \
their `id` in the `ids` field instead. The page builder resolves ids to the \
real links; a link you invent would be published as if it were real.
3. Never state a numerical result (a mass, a mixing angle, a significance, an \
exposure, a limit) unless that exact number appears in the record you are \
citing. When in doubt, describe the result qualitatively instead.
4. Do not speculate about what an experiment "is expected to" announce unless \
a record says so. "No news" is a correct answer for an experiment.
5. Attribute nothing to an author or collaboration that the record does not \
attribute to them.
6. If you cannot fill a section honestly from the records, return fewer items. \
An empty list is acceptable and is better than a padded one.

## Style

British-leaning scientific English, plain and specific, no marketing voice, no \
exclamation marks, no "exciting"/"groundbreaking"/"revolutionary". Present \
tense for status, past tense for results. A reader is a working physicist who \
is not in this subfield. Do not open items with the experiment's name repeated \
from the heading.

## Sections

**experiments** — up to {max_experiments} items on running and upcoming \
experiments (JUNO, DUNE, Hyper-Kamiokande, IceCube, KM3NeT, KATRIN, \
KamLAND-Zen, LEGEND, nEXO, SBN, NOvA, T2K, Super-Kamiokande, Borexino, SNO+, …): \
recent results, results expected soon, new projects, construction or \
commissioning milestones. Each item: a `heading` naming the experiment or \
project (2-4 words), `text` of 2-4 sentences, and `ids` of the records it rests \
on (1 to 3 ids).

**theory** — up to {max_theory} items, each on ONE recently PUBLISHED paper \
from the theory records. `text` is 2-3 sentences saying what the paper does and \
why a neutrino physicist would care. `ids` must contain exactly one id, the \
paper's.

**overview** — two sentences summarising the state of play this week, from the \
records. No ids needed.

## Records

### Experiment and news records
{experiment_records}

### Published theory records
{theory_records}

## Output

JSON only, no prose around it, no code fence:

{{"overview": "...",
  "experiments": [{{"heading": "...", "text": "...", "ids": ["..."]}}],
  "theory": [{{"text": "...", "ids": ["..."]}}]}}
"""


# --------------------------------------------------------------------------- #
# prompt building
# --------------------------------------------------------------------------- #
def compact(records: list[dict], abstract_chars: int) -> str:
    """One line per record: enough to judge it, small enough to stay cheap.

    The id comes first on the line so that the model, which must echo it back
    verbatim, sees it as the record's name rather than as metadata.
    """
    lines = []
    for r in records:
        bits = [f'[{r["id"]}]']
        if r.get("date"):
            bits.append(r["date"])
        src = r.get("extra", {}).get("feed") or r.get("extra", {}).get("journal")
        if src:
            bits.append(f"({src})")
        bits.append(r["title"])
        head = " ".join(bits)
        body = truncate(r.get("summary", ""), abstract_chars)
        authors = r.get("authors", "")
        if authors:
            head += f" — {authors}"
        lines.append(head + (f"\n    {body}" if body else ""))
    return "\n".join(lines) if lines else "(none available today)"


def build_prompt(cfg: dict, experiment_records: list[dict],
                 theory_records: list[dict]) -> str:
    conf = cfg.get("synthesis", {})
    chars = int(conf.get("abstract_chars", 700))
    cap = int(conf.get("max_records", 90))
    # Split the record budget between the two pools rather than letting a
    # bumper crop of preprints crowd the news out entirely.
    exp = experiment_records[:max(10, cap // 2)]
    thy = theory_records[:max(10, cap - len(exp))]
    return PROMPT.format(
        max_experiments=int(conf.get("max_experiments", 10)),
        max_theory=int(conf.get("max_theory", 6)),
        experiment_records=compact(exp, chars),
        theory_records=compact(thy, chars),
    )


# --------------------------------------------------------------------------- #
# the call
# --------------------------------------------------------------------------- #
def call_claude(prompt: str, cfg: dict, log: logging.Logger) -> str | None:
    """Run `claude -p --model sonnet`. Returns raw stdout, or None on failure.

    Never raises: a failed synthesis is a fallback, not a broken run.
    """
    conf = cfg.get("synthesis", {})
    cmd = [
        "claude", "-p",
        "--model", str(conf.get("model", "sonnet")),
        "--output-format", "text",
        "--append-system-prompt", SYSTEM,
        "--disallowed-tools", *DISALLOWED,
    ]
    log.info("synthesis: calling %s (%d chars of prompt)",
             " ".join(cmd[:5]), len(prompt))
    try:
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            timeout=int(conf.get("timeout", 300)),
        )
    except FileNotFoundError:
        log.warning("synthesis: the `claude` CLI is not on PATH — "
                    "a LaunchAgent needs ~/.local/bin added explicitly")
        return None
    except subprocess.TimeoutExpired:
        log.warning("synthesis: timed out after %ss", conf.get("timeout", 300))
        return None
    if proc.returncode != 0:
        log.warning("synthesis: claude exited %s: %s",
                    proc.returncode, (proc.stderr or "").strip()[:400])
        return None
    return proc.stdout


# --------------------------------------------------------------------------- #
# parsing and validation
# --------------------------------------------------------------------------- #
def extract_json(raw: str) -> dict | None:
    """Pull the JSON object out of the reply, tolerating a stray code fence."""
    if not raw:
        return None
    text = FENCE_RE.sub("", raw.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def scrub(text: str) -> tuple[str, list[str]]:
    """Make model prose safe to paste into the page. Returns (text, notes).

    Three separate hazards, all cheap to remove and none of them things the
    model was asked to produce:

      * URLs and bare identifiers (DOI, arXiv number) — invented citations
        that no downstream check can catch, because they are not links.
      * newlines — the prose is dropped into a raw HTML block, and build.py's
        `expand_fences` scans line by line for a leading ':::'. One such line
        in a generated paragraph would restructure the whole page. Collapsing
        whitespace makes a leading ':::' impossible by construction.
    """
    notes: list[str] = []
    if URL_RE.search(text):
        text = URL_RE.sub("", text)
        notes.append("URL")
    if IDENT_RE.search(text):
        text = IDENT_RE.sub("", text)
        notes.append("bare identifier")
    # Collapses newlines too — deliberately, see above.
    text = " ".join(text.split())
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text.strip(" ,;:"), notes


def _clean_item(item: object, known: dict[str, dict], *, want_heading: bool,
                exactly_one_id: bool, log: logging.Logger,
                dropped: list[str]) -> dict | None:
    if not isinstance(item, dict):
        return None
    text = str(item.get("text", "")).strip()
    if not text:
        return None

    raw_ids = item.get("ids") or []
    if isinstance(raw_ids, str):
        raw_ids = [raw_ids]
    ids = [str(i).strip() for i in raw_ids if str(i).strip()]

    unknown = [i for i in ids if i not in known]
    ids = [i for i in ids if i in known]
    if unknown:
        # The load-bearing check. A cited id that was never fetched means the
        # model reached outside its input; the safe reading is that the whole
        # item is unreliable, not just that one citation.
        dropped.append(f'unknown id(s) {unknown} in "{text[:60]}…"')
        return None
    if not ids:
        dropped.append(f'no citable record for "{text[:60]}…"')
        return None
    if exactly_one_id:
        ids = ids[:1]
    else:
        ids = ids[:3]

    # Belt and braces: the prompt forbids URLs and identifiers, so one showing
    # up means the instruction slipped. Strip rather than publish.
    text, notes = scrub(text)
    if notes:
        dropped.append(f'stripped {" and ".join(notes)} from '
                       f'"{text[:50]}…" (kept the item)')
    if not text:
        return None

    out = {"text": text, "ids": ids}
    if want_heading:
        heading, _ = scrub(str(item.get("heading", "")))
        if not heading:
            return None
        out["heading"] = heading
    return out


def validate(obj: dict, known: dict[str, dict], cfg: dict,
             log: logging.Logger, theory_known: dict[str, dict] | None = None
             ) -> dict | None:
    """Turn raw model output into a narrative whose every citation resolves.

    `theory_known` is the published-literature pool. Theory highlights are
    checked against it alone: the section is headed "recently published
    papers, each with its arXiv preprint, INSPIRE record and journal DOI", and
    a citation to a laboratory press release would put a news item under that
    promise with none of those three links. Validating both sections against
    one merged pool let exactly that through.
    """
    conf = cfg.get("synthesis", {})
    dropped: list[str] = []
    theory_pool = known if theory_known is None else theory_known

    experiments = []
    for item in (obj.get("experiments") or [])[:int(conf.get("max_experiments", 10))]:
        clean = _clean_item(item, known, want_heading=True, exactly_one_id=False,
                            log=log, dropped=dropped)
        if clean:
            experiments.append(clean)

    theory = []
    for item in (obj.get("theory") or [])[:int(conf.get("max_theory", 6))]:
        clean = _clean_item(item, theory_pool, want_heading=False,
                            exactly_one_id=True, log=log, dropped=dropped)
        if clean:
            theory.append(clean)

    overview, _ = scrub(str(obj.get("overview", "")))

    for msg in dropped:
        log.warning("synthesis: dropped — %s", msg)
    log.info("synthesis: kept %d experiment items, %d theory items, "
             "%d rejected", len(experiments), len(theory), len(dropped))

    if not experiments and not theory:
        log.warning("synthesis: nothing survived validation")
        return None
    return {"overview": overview, "experiments": experiments,
            "theory": theory, "rejected": len(dropped)}


# --------------------------------------------------------------------------- #
def synthesize(cfg: dict, experiment_records: list[dict],
               theory_records: list[dict], log: logging.Logger) -> dict | None:
    """Full step: prompt -> claude -> JSON -> validated narrative, or None."""
    if not cfg.get("synthesis", {}).get("enabled", True):
        log.info("synthesis: disabled in config")
        return None
    if not experiment_records and not theory_records:
        log.warning("synthesis: no records to work from — skipping the call")
        return None

    prompt = build_prompt(cfg, experiment_records, theory_records)
    raw = call_claude(prompt, cfg, log)
    if raw is None:
        return None
    obj = extract_json(raw)
    if obj is None:
        log.warning("synthesis: reply was not JSON (%d chars, starts %r)",
                    len(raw), raw[:120])
        return None

    from . import cache
    known = cache.index(experiment_records + theory_records)
    return validate(obj, known, cfg, log,
                    theory_known=cache.index(theory_records))


if __name__ == "__main__":  # pragma: no cover
    from . import cache
    from .common import get_logger, load_config
    cfg = load_config()
    log = get_logger("news.synth")
    exp = cache.load_records("feeds") + [
        r for r in cache.load_records("arxiv")
        if any(c.startswith(("hep-ex", "nucl-ex", "physics.ins-det"))
               for c in r["extra"].get("categories", []))]
    thy = cache.load_records("inspire")
    if "--prompt" in sys.argv:
        print(build_prompt(cfg, exp, thy))
        sys.exit(0)
    result = synthesize(cfg, exp, thy, log)
    print(json.dumps(result, indent=1, ensure_ascii=False) if result
          else "synthesis produced nothing")
