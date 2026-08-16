"""Notice when the site has stopped updating, and do something about it.

On 2026-08-16 the daily LaunchAgent exited before it could log anything: no
line in news.log, no line in launchd.log, and the site simply stopped being
refreshed. Nothing noticed. That is the failure this module exists for, and
it explains its shape — a check that lives inside the run cannot catch a run
that never began, so this one lives outside it and asks a different question:
when did this site last update?

The answer is `state.json`'s `last_success`, which the pipeline writes only
when a run got all the way through. Everything here is a decision made from
that one timestamp.
"""
from __future__ import annotations

import datetime as _dt
import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MAX_HOURS = 26.0


def hours_since_success(state: dict, now: _dt.datetime) -> float | None:
    """Hours since the last successful run, or None if there is no answer.

    None means "never succeeded, or the record is unreadable" — deliberately
    not 0.0 and not a huge number, because a caller that mistook either for a
    real age would draw exactly the wrong conclusion from it.

    `now` is a parameter rather than a call to the clock so the decision is
    reproducible: the same state gives the same answer on any day.
    """
    raw = state.get("last_success")
    if not raw:
        return None
    try:
        when = _dt.datetime.fromisoformat(str(raw))
    except (ValueError, TypeError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=now.tzinfo)
    return (now - when).total_seconds() / 3600.0


def should_act(state: dict, now: _dt.datetime, max_hours: float) -> bool:
    """True when the site is stale enough to be worth intervening.

    Never having succeeded counts as stale. That is the most alarming state a
    site can be in, not the calmest, and reading a missing record as "nothing
    to worry about" is how a broken job stays broken.

    The boundary belongs to the quiet side: a run that lands exactly on the
    threshold is punctual, not late, and must not raise an alarm.
    """
    age = hours_since_success(state, now)
    if age is None:
        return True
    return age > max_hours


def compose_report(hours: float | None, rerun_ok: bool,
                   detail: str) -> tuple[str, str]:
    """The subject and body of the one message a human will read.

    The two outcomes get different subjects on purpose. "It broke and I have
    already fixed it" and "it broke and it is still broken" ask for different
    things from the reader — the second on a Sunday morning, the first not at
    all — and a mail client that threaded them together would hide exactly
    the transition that matters.

    The age goes in the body, never the subject: a subject that changes every
    run turns one recurring fault into a inbox full of apparently separate
    ones.
    """
    age = "an unknown time" if hours is None else f"{hours:.0f} hours"
    if rerun_ok:
        subject = "global-nu: the daily run had stopped — recovered"
        body = (f"The site had not been refreshed for {age}.\n\n"
                "The pipeline was run again and succeeded, so the site is "
                "current. Nothing needs doing; this is a record that the "
                "scheduled run did not happen when it should have.\n")
    else:
        subject = "global-nu: the daily run has stopped — retry failed"
        body = (f"The site has not been refreshed for {age}, and running the "
                "pipeline again did not fix it.\n\nThe site is serving stale "
                "pages until this is looked at.\n")
    if detail:
        body += f"\n{detail}\n"
    return subject, body


def _rerun() -> tuple[bool, str]:
    """Run the pipeline exactly as the LaunchAgent does. Never raises.

    The same interpreter, module and working directory launchd uses, so a
    recovery run cannot succeed in a way the scheduled one would not. Output
    is captured rather than streamed: it becomes the body of the message, and
    the last lines are the part worth reading.
    """
    try:
        out = subprocess.run(
            [str(ROOT / ".venv" / "bin" / "python3"), "-m",
             "tools.news.pipeline", "--quiet"],
            cwd=ROOT, capture_output=True, text=True, timeout=3600, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    tail = "\n".join((out.stdout + out.stderr).strip().splitlines()[-20:])
    return out.returncode == 0, tail


def main(argv: list[str] | None = None) -> int:
    """Check, and if the site is stale, fix it and say so.

    Exits 0 whenever the watchdog itself did its job, including when the
    recovery run failed — the failure is reported by mail, and a non-zero
    exit here would only add a second, quieter alarm nobody reads.
    """
    import argparse
    from . import mailer, state
    from .common import load_config

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="report the verdict and change nothing")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    log = logging.getLogger("watchdog")

    cfg = (load_config().get("alerts") or {})
    max_hours = float(cfg.get("max_hours", DEFAULT_MAX_HOURS))
    now = _dt.datetime.now().astimezone()
    st = state.load()

    age = hours_since_success(st, now)
    if not should_act(st, now, max_hours):
        log.info("watchdog: last success %.1f h ago, under %.0f h — quiet",
                 age or 0.0, max_hours)
        return 0

    log.warning("watchdog: last success %s ago (limit %.0f h) — rerunning",
                "never" if age is None else f"{age:.1f} h", max_hours)
    if args.dry_run:
        log.info("watchdog: dry run, not rerunning and not sending mail")
        return 0

    ok, detail = _rerun()
    subject, body = compose_report(age, ok, detail)
    log.info("watchdog: rerun %s", "succeeded" if ok else "FAILED")

    account = cfg.get("account") or ""
    recipient = cfg.get("recipient") or account
    host, port = cfg.get("smtp_host") or "", int(cfg.get("smtp_port") or 587)
    password = mailer.keychain_password(account) if account else None

    if not (account and recipient and host and password):
        # Degrade, never die: the recovery run is the half that keeps the site
        # correct, and it has already happened. Say loudly why nobody was told.
        if not (account and host):
            why = "alerts are not configured in tools/news/config.yaml"
        else:
            why = f"no Keychain password for {account!r}"
        log.error("watchdog: NOT sending mail — %s. The message would have "
                  "been: %s", why, subject)
        return 0

    try:
        mailer.send(mailer.build_message(subject, body, account, recipient),
                    host, port, account, password)
        log.info("watchdog: told %s", recipient)
    except Exception as exc:                    # noqa: BLE001 — see below
        # Any failure to send is caught: an unreachable mail server must not
        # turn a site that has just been repaired into a job that looks broken.
        log.error("watchdog: could not send mail (%s: %s)",
                  type(exc).__name__, exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
