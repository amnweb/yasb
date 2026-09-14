"""One automatic-backup check: has the configuration changed and gone quiet?

Run by Task Scheduler through `yasb_cloud.exe --auto-backup`. Nothing is resident: the process
starts, decides, and usually exits without touching the network.

A change is noted and nothing happens until the folder looks the same on two checks in a row,
so an editing session produces one backup of the finished state rather than one per interval.
Both signatures are persisted because this process has no memory between runs.
"""

import hashlib
from pathlib import Path

from core.cloud.errors import SnapshotError
from core.cloud.snapshot import collect_files
from core.cloud.state import read_state, write_state
from settings import DEFAULT_CONFIG_DIRECTORY


def entries(exclude: tuple[str, ...] = ()) -> dict[str, str]:
    """Every file a snapshot would contain, mapped to its size and modification time."""
    root = Path(DEFAULT_CONFIG_DIRECTORY)
    found: dict[str, str] = {}
    for candidate in collect_files(root, exclude):
        try:
            mtime = candidate.absolute.stat().st_mtime_ns
        except OSError:
            continue
        found[candidate.relative] = f"{candidate.size}:{mtime}"
    return found


def signature(files: dict[str, str]) -> str:
    """Hash of a file map from `entries`. Takes the map so one check costs one walk."""
    digest = hashlib.sha256()
    for relative, stamp in files.items():
        digest.update(f"{relative}\0{stamp}\0".encode())
    return digest.hexdigest()


def differences(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """What changed between two file maps, as lines fit for a log."""
    lines = [f"added {name}" for name in sorted(after.keys() - before.keys())]
    lines += [f"removed {name}" for name in sorted(before.keys() - after.keys())]
    lines += [
        f"modified {name} ({before[name]} -> {after[name]})"
        for name in sorted(before.keys() & after.keys())
        if before[name] != after[name]
    ]
    return lines


def decide(now: dict[str, str]) -> tuple[bool, str]:
    """Whether this run should back up, and the signature it would be recording."""
    current = signature(now)
    state = read_state()

    if current != state.last_seen:
        write_state(last_seen=current, last_backed_up=state.last_backed_up, files=now)
        return False, ""

    if state.files != now:
        # A state file written before the map existed; refresh it or every run reports the
        # whole folder as newly added.
        write_state(last_seen=state.last_seen, last_backed_up=state.last_backed_up, files=now)

    if current == state.last_backed_up:
        return False, ""

    return True, current


def mark_backed_up(value: str) -> None:
    """Record a signature as safely in the cloud. Only call this after an upload succeeded.

    A failure leaves the stored value alone, so the next quiet run tries again. That is the
    whole retry mechanism. The file map is carried over, not dropped.
    """
    state = read_state()
    write_state(last_seen=state.last_seen, last_backed_up=value, files=state.files)


def mark_in_sync(exclude: tuple[str, ...] = ()) -> None:
    """Record the configuration as backed up, without backing it up.

    Called after a manual backup and after a restore, or the next quiet run uploads the state
    it just downloaded.
    """
    try:
        files = entries(exclude)
    except SnapshotError, OSError:
        return
    current = signature(files)
    write_state(last_seen=current, last_backed_up=current, files=files)
