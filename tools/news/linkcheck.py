"""Check the links before they reach the page, not after.

Running the checker on the finished HTML would only tell us the page is
already wrong. It runs on the candidate records instead, and the pipeline
drops whatever fails, so a dead link is never published in the first place.

## Why a link is only removed when it is *certainly* dead

The first live run of this checker flagged 25 links and deleted eight of the
eleven conferences. Not one of them was actually broken:

  * Indico servers (indico.global, indico.kit.edu, indico.cern.ch …) answer
    400 to a HEAD and 200 to a GET. Half the conference world runs Indico.
  * doi.org resolves, then the publisher — APS, World Scientific, IOP —
    answers 403 to anything that is not a browser it likes. Verified with a
    real Chrome User-Agent: still 403. The link works perfectly for a reader.

So a 403 says "this host dislikes robots", not "this page does not exist",
and treating the two alike silently strips real content off a physics page.
Only a definite verdict removes a link:

    404, 410, DNS failure, connection refused   -> broken, drop it
    403, 429, 5xx, timeouts, anything else      -> unverified, keep it

The unverified ones are counted and logged so the dashboard can show them; a
link that a reader can follow is never deleted on a robot's say-so.

Results are cached for a few days. Re-testing every arXiv and DOI link every
morning would be slow, rude to the hosts, and pointless: these do not rot
overnight.
"""

from __future__ import annotations

import datetime as _dt
import logging
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests

from .common import USER_AGENT, VAR, now_iso, read_json, write_json

LINKCACHE = VAR / "linkcache.json"
FRESH_DAYS = 5

OK = "ok"
BROKEN = "broken"
UNVERIFIED = "unverified"

# The only codes that mean the resource is not there.
DEAD_CODES = {404, 410}

# Timeouts mean slow or throttled, never gone. They are listed FIRST because
# requests.exceptions.ConnectTimeout is a *subclass* of ConnectionError, so
# catching ConnectionError first would silently classify every timeout as a
# dead link — which is how a slow morning could empty the page.
SLOW_EXCEPTIONS = (requests.exceptions.Timeout,)

# The host does not resolve or refuses the connection.
DEAD_EXCEPTIONS = (requests.exceptions.ConnectionError,)

# Hosts known to refuse HEAD. The checker retries with GET on any 4xx anyway,
# so this list is only an optimisation — one request instead of two.
GET_FIRST_HOSTS = ("doi.org", "www.nature.com", "link.springer.com",
                   "journals.aps.org", "www.sciencedirect.com",
                   "iopscience.iop.org", "indico.global", "indico.cern.ch")


def _load_cache() -> dict:
    data = read_json(LINKCACHE, {})
    return data if isinstance(data, dict) else {}


def _fresh(entry: dict) -> bool:
    """Is this cached verdict still usable?

    A BROKEN verdict is never reused. It is the only verdict that removes
    content, so caching it lets one bad moment keep deleting the page long
    after the cause is gone: a laptop whose Wi-Fi is not up at 07:30 marks
    every link dead, and the five-day TTL then republishes an empty page every
    morning for five days. Re-testing the handful of dead links each run costs
    almost nothing; getting it wrong costs the whole page.
    """
    if entry.get("verdict") == BROKEN:
        return False
    try:
        when = _dt.datetime.fromisoformat(entry["at"])
    except (KeyError, ValueError, TypeError):
        return False
    return _dt.datetime.now().astimezone() - when < _dt.timedelta(days=FRESH_DAYS)


def _verdict(code: int) -> str:
    if 200 <= code < 400:
        return OK
    if code in DEAD_CODES:
        return BROKEN
    return UNVERIFIED


def _check_one(url: str, timeout: int, get_first: tuple[str, ...]
               ) -> tuple[str, str, str]:
    """-> (url, verdict, reason)."""
    host = urlparse(url).netloc.lower()
    session = requests.Session()
    headers = {"User-Agent": USER_AGENT}
    try:
        if host in get_first:
            r = session.get(url, headers=headers, timeout=timeout,
                            allow_redirects=True, stream=True)
            r.close()
        else:
            r = session.head(url, headers=headers, timeout=timeout,
                             allow_redirects=True)
            # Plenty of servers simply do not implement HEAD, and answer 400,
            # 403, 405 or 501 to it while serving the page perfectly on GET.
            if 400 <= r.status_code < 500:
                r = session.get(url, headers=headers, timeout=timeout,
                                allow_redirects=True, stream=True)
                r.close()
        return url, _verdict(r.status_code), str(r.status_code)
    except SLOW_EXCEPTIONS as exc:
        return url, UNVERIFIED, exc.__class__.__name__
    except DEAD_EXCEPTIONS as exc:
        return url, BROKEN, exc.__class__.__name__
    except requests.RequestException as exc:
        return url, UNVERIFIED, exc.__class__.__name__
    finally:
        session.close()


def check(urls, cfg: dict, log: logging.Logger) -> dict[str, str]:
    """Return {url: reason} for links that are *certainly* dead.

    Anything not in the returned mapping stays on the page — including links
    that could not be verified. See the module docstring for why.
    """
    conf = cfg.get("linkcheck", {})
    urls = sorted({u for u in urls if u and u.startswith(("http://", "https://"))})
    if not conf.get("enabled", True):
        log.info("linkcheck: disabled in config (%d links unchecked)", len(urls))
        return {}
    if not urls:
        return {}

    get_first = tuple(set(GET_FIRST_HOSTS) | set(conf.get("get_only_hosts") or []))
    timeout = int(conf.get("timeout", 15))
    cache = _load_cache()

    todo = [u for u in urls if not (u in cache and _fresh(cache[u]))]
    results: dict[str, str] = {}
    for u in urls:
        if u not in todo:
            results[u] = cache[u].get("verdict", UNVERIFIED)

    if todo:
        fresh: dict[str, tuple[str, str]] = {}
        with ThreadPoolExecutor(max_workers=int(conf.get("workers", 8))) as pool:
            for url, verdict, reason in pool.map(
                    lambda u: _check_one(u, timeout, get_first), todo):
                fresh[url] = (verdict, reason)

        # Circuit breaker. If most of what we tried looks dead, the thing that
        # is down is us, not the entire web. Believing the result would strip
        # the page and publish the wreckage; the safe reading of "nothing
        # answered" is "we learned nothing this morning".
        dead = sum(1 for v, _ in fresh.values() if v == BROKEN)
        if len(fresh) >= 5 and dead > len(fresh) // 2:
            log.error("linkcheck: %d of %d links looked dead — treating this "
                      "as OUR network being down, not theirs; nothing will be "
                      "removed from the page this run", dead, len(fresh))
            return {}

        for url, (verdict, reason) in fresh.items():
            cache[url] = {"verdict": verdict, "reason": reason, "at": now_iso()}
            results[url] = verdict

    write_json(LINKCACHE, cache)

    broken = {u: cache.get(u, {}).get("reason", "?")
              for u, v in results.items() if v == BROKEN}
    unverified = [u for u, v in results.items() if v == UNVERIFIED]

    log.info("linkcheck: %d links (%d checked now, %d cached) — "
             "%d ok, %d unverified, %d broken",
             len(urls), len(todo), len(urls) - len(todo),
             sum(1 for v in results.values() if v == OK),
             len(unverified), len(broken))
    for url in sorted(unverified):
        log.debug("linkcheck: unverified (%s) %s",
                  cache.get(url, {}).get("reason", "?"), url)
    for url, reason in sorted(broken.items()):
        log.warning("linkcheck: BROKEN (%s) %s", reason, url)
    return broken


def urls_of(records: list[dict]) -> list[str]:
    """Every URL a record could put on the page: primary plus named links."""
    out = []
    for r in records:
        out.append(r.get("url", ""))
        out.extend(v for v in (r.get("links") or {}).values() if v)
    return out


def filter_records(records: list[dict], bad: dict[str, str],
                   log: logging.Logger) -> list[dict]:
    """Drop records whose primary URL is dead; blank out dead side links.

    A record survives a dead DOI (it still has arXiv and INSPIRE) but not a
    dead primary link, which is the one the title points at.
    """
    kept = []
    for r in records:
        if r.get("url") in bad:
            log.warning("dropped record %s — primary link is dead (%s)",
                        r["id"], bad[r["url"]])
            continue
        links = r.get("links") or {}
        r["links"] = {k: v for k, v in links.items() if v not in bad}
        kept.append(r)
    return kept
