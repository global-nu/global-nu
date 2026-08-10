"""var/news/run.lock — one pipeline run at a time, and never a permanent block.

    from tools.news.lock import run_lock, LockBusy

    try:
        with run_lock():
            ...                      # the whole pipeline
    except LockBusy as exc:
        log.info("another run is in progress: %s", exc)

WHY A LOCK AT ALL
    The daily LaunchAgent and the dashboard's "run now" button call the same
    pipeline. Two of them at once would interleave writes to var/news/cache/,
    state.json and site-src/content/Neutrino-News.md, and could rsync a
    half-rendered page to the server. One run at a time is the invariant.

HOW IT IS TAKEN
    os.open(..., O_CREAT | O_EXCL | O_WRONLY). The kernel makes creation and
    existence-test a single operation, so two runs starting in the same
    millisecond cannot both win. There is deliberately no "if the file exists"
    check before the create: that pattern reintroduces exactly the race the
    O_EXCL flag exists to close.

WHY STALENESS MATTERS MORE THAN THE LOCK
    A lock file is state that outlives the process holding it. A run killed
    with SIGKILL, a Mac put to sleep mid-run, a crash inside a fetcher: each
    leaves a lock nobody owns, and from then on every daily run refuses to
    start. The site would silently stop updating, and nothing would say why.
    So a lock is only believed while both of these hold:

      * the PID inside it belongs to a process that still exists
        (os.kill(pid, 0): ProcessLookupError = gone, PermissionError = alive
        but owned by somebody else — still alive, so still respected);
      * the timestamp inside it is younger than `max_age` (default 6 hours,
        overridable in config.yaml under `schedule: lock_max_age_hours:`).

    The age test is what saves a *wedged* run — a process still alive but
    hanging forever on a socket. Its PID looks perfectly healthy; only the
    clock reveals it. The daily job is 24 h apart, so a 6 h ceiling can never
    steal the lock from a run that is genuinely working.

RECLAIMING IS ITSELF A RACE
    Two runs can decide "this lock is stale" simultaneously. Unlinking it and
    creating a new one is two steps and both could pass. So the stale file is
    first os.rename()d out of the way: rename is atomic, exactly one process
    can move a given path, the loser gets ENOENT and simply retries the O_EXCL
    create — where the winner is already waiting for it.

RELEASING
    Always in a finally, and only if the file still contains our own PID and
    the token we wrote. If somebody else reclaimed our lock because we looked
    stale, that file belongs to them: deleting it on the way out would leave
    them running unprotected.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Iterator

from .common import LOCK, get_logger, load_config

# Six hours: far longer than any healthy run (the pipeline is minutes,
# dominated by one AI call with a 300 s timeout), far shorter than the 24 h
# between daily runs.
DEFAULT_MAX_AGE = 6 * 60 * 60.0

# A lock whose contents cannot be parsed was written by a run that died
# between the create and the write. It is trusted for this long only, so that
# the sub-millisecond window between those two syscalls is not a race.
GRACE_SECONDS = 30.0

# Never loop forever reclaiming: if three attempts in a row lose the rename
# race, something pathological is happening and busy is the honest answer.
MAX_ATTEMPTS = 3


class LockBusy(RuntimeError):
    """Another run holds the lock and it is not stale."""


# --------------------------------------------------------------------------- #
# reading the lock file
# --------------------------------------------------------------------------- #
def _payload(token: str) -> str:
    """What goes inside the lock: PID, when, who. JSON so it stays readable
    with `cat var/news/run.lock` while a run is in flight."""
    return json.dumps({
        "pid": os.getpid(),
        "at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "token": token,
        "host": os.uname().nodename,
    }, indent=1) + "\n"


def _parse(raw: str) -> dict:
    """Best effort. A corrupt lock is not an error, it is a stale lock."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _pid_alive(pid: int) -> bool:
    """Signal 0 checks for existence without delivering anything.

    ProcessLookupError -> no such process, the lock is an orphan.
    PermissionError    -> the process exists but belongs to another user; we
                          cannot signal it, which is not a reason to doubt it.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _age_seconds(data: dict, path: Path) -> float:
    """Age from the timestamp we wrote, falling back to the file's mtime."""
    stamp = data.get("at")
    if isinstance(stamp, str):
        try:
            when = _dt.datetime.fromisoformat(stamp)
        except ValueError:
            when = None
        if when is not None:
            now = _dt.datetime.now(when.tzinfo) if when.tzinfo else _dt.datetime.now()
            return max(0.0, (now - when).total_seconds())
    try:
        return max(0.0, _dt.datetime.now().timestamp() - path.stat().st_mtime)
    except OSError:
        return 0.0


def _stale_reason(path: Path, max_age: float) -> tuple[str | None, str, int]:
    """Inspect an existing lock.

    Returns (reason, raw_contents, inode). `reason` is None when the lock is
    healthy and must be respected; otherwise it is the sentence that goes in
    the WARNING, because a lock being broken open is always worth a log line.
    """
    try:
        raw = path.read_text(encoding="utf-8")
        inode = path.stat().st_ino
    except FileNotFoundError:
        return ("vanished while being read", "", 0)
    except OSError:
        return (None, "", 0)  # unreadable: assume alive, do not break it open

    data = _parse(raw)
    age = _age_seconds(data, path)
    pid = data.get("pid")

    if not isinstance(pid, int):
        if age > GRACE_SECONDS:
            return (f"unreadable lock, {age:.0f}s old", raw, inode)
        return (None, raw, inode)

    if not _pid_alive(pid):
        return (f"PID {pid} is not running", raw, inode)

    if age > max_age:
        return (f"PID {pid} still alive but the lock is {age / 3600:.1f} h old "
                f"(limit {max_age / 3600:.1f} h) — treating the run as wedged",
                raw, inode)

    return (None, raw, inode)


# --------------------------------------------------------------------------- #
# taking and releasing
# --------------------------------------------------------------------------- #
def _configured_max_age() -> float:
    """`schedule: lock_max_age_hours:` in config.yaml, if anyone set it.

    Absent or unusable, the built-in default stands. A lock must never fail to
    be taken because a configuration file has a typo in it.
    """
    try:
        cfg = load_config()
    except Exception:
        return DEFAULT_MAX_AGE
    raw = (cfg.get("schedule") or {}).get("lock_max_age_hours")
    try:
        hours = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_AGE
    return hours * 3600.0 if hours > 0 else DEFAULT_MAX_AGE


def _reclaim(path: Path, raw_seen: str, inode_seen: int,
             log: logging.Logger) -> bool:
    """Move a stale lock aside. True if the path is now free to try again.

    The rename is the arbitration: only one process can rename a given path,
    so only one process reclaims. Anyone who loses gets FileNotFoundError and
    retries the create, which the winner may already have satisfied.
    """
    aside = path.with_name(f"{path.name}.stale.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    try:
        os.rename(path, aside)
    except FileNotFoundError:
        return True                      # someone else got there first
    except OSError as exc:
        log.warning("could not clear the stale lock %s (%s)", path, exc)
        return False

    # Paranoia: confirm we moved the file we inspected and not a fresh lock
    # that appeared in between. Inode identity is the only reliable test.
    try:
        moved_ino = aside.stat().st_ino
        moved_raw = aside.read_text(encoding="utf-8")
    except OSError:
        return True
    if inode_seen and moved_ino != inode_seen and moved_raw != raw_seen:
        log.warning("the lock changed while it was being reclaimed — putting it back")
        with contextlib.suppress(OSError):
            os.rename(aside, path)
        return False

    with contextlib.suppress(OSError):
        aside.unlink()
    return True


def acquire(path: Path | None = None, *, max_age: float | None = None,
            log: logging.Logger | None = None) -> str:
    """Take the lock, or raise LockBusy. Returns the token to release with."""
    path = Path(path or LOCK)
    log = log or get_logger()
    limit = float(max_age) if max_age is not None else _configured_max_age()
    path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex

    for _ in range(MAX_ATTEMPTS):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            reason, raw, inode = _stale_reason(path, limit)
            if reason is None:
                data = _parse(raw)
                holder = data.get("pid", "?")
                since = data.get("at", "unknown time")
                raise LockBusy(
                    f"{path} held by PID {holder} since {since}") from None
            log.warning("stale lock at %s: %s — reclaiming", path, reason)
            if not _reclaim(path, raw, inode, log):
                raise LockBusy(f"{path} could not be reclaimed") from None
            continue
        except OSError as exc:
            raise LockBusy(f"{path}: {exc}") from None

        try:
            os.write(fd, _payload(token).encode("utf-8"))
        finally:
            os.close(fd)
        return token

    raise LockBusy(f"{path}: lost the reclaim race {MAX_ATTEMPTS} times")


def release(token: str, path: Path | None = None,
            log: logging.Logger | None = None) -> bool:
    """Remove the lock only if it is still ours. True if we removed it."""
    path = Path(path or LOCK)
    log = log or get_logger()
    data = _parse(_read_quietly(path))
    if not data:
        return False
    if data.get("pid") != os.getpid() or data.get("token") != token:
        log.warning("not releasing %s: it now belongs to PID %s",
                    path, data.get("pid"))
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        log.warning("could not remove %s (%s)", path, exc)
        return False
    return True


def _read_quietly(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def is_locked(path: Path | None = None, *, max_age: float | None = None) -> dict:
    """Non-destructive status, for the dashboard. Never touches the file.

    {"locked": bool, "pid": int|None, "at": str|None, "stale": str|None}
    """
    path = Path(path or LOCK)
    limit = float(max_age) if max_age is not None else _configured_max_age()
    if not path.exists():
        return {"locked": False, "pid": None, "at": None, "stale": None}
    reason, raw, _ = _stale_reason(path, limit)
    data = _parse(raw)
    return {"locked": reason is None, "pid": data.get("pid"),
            "at": data.get("at"), "stale": reason}


@contextlib.contextmanager
def run_lock(path: Path | None = None, *, max_age: float | None = None,
             log: logging.Logger | None = None) -> Iterator[Path]:
    """The supported entry point. Raises LockBusy if a live run holds it."""
    path = Path(path or LOCK)
    log = log or get_logger()
    token = acquire(path, max_age=max_age, log=log)
    try:
        yield path
    finally:
        release(token, path, log=log)


# --------------------------------------------------------------------------- #
# self-test:  python3 -m tools.news.lock
# --------------------------------------------------------------------------- #
if __name__ == "__main__":                      # pragma: no cover
    import sys
    import tempfile
    import time

    ok = True

    def check(label: str, condition: bool, detail: str = "") -> None:
        global ok
        mark = "ok  " if condition else "FAIL"
        ok = ok and condition
        print(f"  [{mark}] {label}" + (f"   {detail}" if detail else ""))

    tmpdir = Path(tempfile.mkdtemp(prefix="news-lock-selftest-"))
    lockfile = tmpdir / "run.lock"
    print(f"self-test on {lockfile}\n")
    quiet = logging.getLogger("news.lock.selftest")
    quiet.addHandler(logging.StreamHandler(sys.stdout))
    quiet.setLevel(logging.WARNING)

    # 1. take it, and a second attempt must be refused
    print("1. mutual exclusion")
    with run_lock(lockfile, log=quiet) as held:
        check("lock file created", held.exists(), str(held))
        body = _parse(held.read_text())
        check("contains our PID", body.get("pid") == os.getpid(),
              f"pid={body.get('pid')}")
        check("contains an ISO timestamp", bool(body.get("at")), body.get("at", ""))
        try:
            with run_lock(lockfile, log=quiet):
                check("second acquisition refused", False, "it succeeded!")
        except LockBusy as exc:
            check("second acquisition refused", True, f"LockBusy: {exc}")

    # 2. released on exit
    print("\n2. release")
    check("lock file removed on exit", not lockfile.exists())
    check("a new run can take it again",
          bool(acquire(lockfile, log=quiet)) and lockfile.exists())
    lockfile.unlink()

    # 3. a lock left by a process that no longer exists
    print("\n3. stale lock, dead PID")
    child = os.fork()
    if child == 0:
        os._exit(0)                      # a PID that is about to be certain-dead
    os.waitpid(child, 0)                 # reaped: not even a zombie remains
    check("the forked child is really gone", not _pid_alive(child), f"pid={child}")

    lockfile.write_text(json.dumps({
        "pid": child,
        "at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "token": "not-ours",
        "host": "selftest",
    }) + "\n", encoding="utf-8")
    status = is_locked(lockfile)
    check("is_locked() reports it stale", status["stale"] is not None,
          str(status["stale"]))
    with run_lock(lockfile, log=quiet) as held:
        body = _parse(held.read_text())
        check("stale lock reclaimed", body.get("pid") == os.getpid(),
              f"pid={body.get('pid')}")
    check("reclaimed lock released", not lockfile.exists())

    # 4. a lock held by a live process but far too old
    print("\n4. wedged run, live PID but past max_age")
    old = _dt.datetime.now().astimezone() - _dt.timedelta(hours=9)
    lockfile.write_text(json.dumps({
        "pid": os.getpid(),              # unquestionably alive: it is us
        "at": old.isoformat(timespec="seconds"),
        "token": "not-ours",
        "host": "selftest",
    }) + "\n", encoding="utf-8")
    check("PID in the lock is alive", _pid_alive(os.getpid()))
    try:
        with run_lock(lockfile, max_age=24 * 3600, log=quiet):
            check("respected while under max_age", False, "it broke a live lock")
    except LockBusy:
        check("respected while under max_age", True, "LockBusy as expected")
    with run_lock(lockfile, max_age=6 * 3600, log=quiet) as held:
        body = _parse(held.read_text())
        check("reclaimed once past max_age", body.get("token") != "not-ours")

    # 5. we must not delete a lock that is no longer ours
    print("\n5. release is owner-only")
    token = acquire(lockfile, log=quiet)
    lockfile.write_text(json.dumps({"pid": os.getpid(), "at": "x",
                                    "token": "someone-else"}) + "\n",
                        encoding="utf-8")
    check("foreign lock left alone", release(token, lockfile, log=quiet) is False)
    lockfile.unlink()

    # 6. exceptions inside the block still release
    print("\n6. release happens even on error")
    try:
        with run_lock(lockfile, log=quiet):
            raise ValueError("boom")
    except ValueError:
        pass
    check("lock released after an exception", not lockfile.exists())

    # 7. the race the O_EXCL flag exists for: many runs starting at once.
    #    The winner must stay alive while the others try: a lock whose creator
    #    has already exited is genuinely abandoned, and reclaiming it is the
    #    correct behaviour, not a lost race. (The first version of this test
    #    had the winner exit immediately and saw three "winners" for exactly
    #    that reason.)
    print("\n7. simultaneous starts — exactly one winner")
    n = 24
    kids = []
    sys.stdout.flush()                   # or every child inherits the buffer
    for _ in range(n):
        pid = os.fork()
        if pid == 0:
            try:
                acquire(lockfile, log=quiet)
                time.sleep(2)            # hold it, as a real run would
                os._exit(0)              # 0 = I took the lock
            except LockBusy:
                os._exit(1)              # 1 = correctly refused
            except BaseException:
                os._exit(2)              # 2 = something else broke
        kids.append(pid)
    winners = busy = broken = 0
    for pid in kids:
        code = os.waitpid(pid, 0)[1] >> 8
        winners += code == 0
        busy += code == 1
        broken += code not in (0, 1)
    check("exactly one of 24 concurrent starts won", winners == 1,
          f"{winners} winner, {busy} refused, {broken} errored")
    check("no child failed unexpectedly", broken == 0)
    lockfile.unlink(missing_ok=True)

    with contextlib.suppress(OSError):
        for leftover in tmpdir.iterdir():
            leftover.unlink()
        tmpdir.rmdir()

    print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    sys.exit(0 if ok else 1)
