"""Apply a snapshot archive back to the configuration directory.

Every archive entry is validated before anything is written, the current config is zipped
first so a failed restore can be put back, and the new content is staged beside the target
and swapped in with a single rename.
"""

import logging
import os
import re
import secrets
import shutil
import subprocess
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from core.cloud.constants import BAR_COMMAND_TIMEOUT_S, BAR_PROCESS_NAME, BAR_STOP_TIMEOUT_S, SAFETY_KEEP
from core.cloud.errors import Cancelled, RestoreError, UnsafePathError
from core.utils.process import is_process_running
from settings import SCRIPT_PATH

logger = logging.getLogger(__name__)

RESERVED_NAMES: frozenset[str] = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{n}" for n in range(1, 10)}
    | {f"LPT{n}" for n in range(1, 10)}
)
"""Windows device names. Reserved whatever the extension, so CON.txt counts."""

_DRIVE = re.compile(r"^[A-Za-z]:")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True, slots=True)
class RestoreResult:
    restored: tuple[str, ...]
    safety_archive: Path | None


@dataclass(frozen=True, slots=True)
class RestoreOutcome:
    restore: RestoreResult
    bar_was_running: bool
    bar_restarted: bool


def validate_member(name: str) -> PurePosixPath:
    """Validate one archive entry name and return the safe relative path."""
    if not name or name in (".", ".."):
        raise UnsafePathError(f"Archive contains an invalid entry name: {name!r}")

    if _CONTROL.search(name):
        raise UnsafePathError(f"Archive entry contains control characters: {name!r}")

    # A ZIP may use either separator, so normalise before checking.
    unified = name.replace("\\", "/")

    if unified.startswith("/"):
        raise UnsafePathError(f"Archive entry is an absolute path: {name!r}")
    if _DRIVE.match(unified):
        raise UnsafePathError(f"Archive entry has a drive letter: {name!r}")
    if unified.startswith("//"):
        raise UnsafePathError(f"Archive entry is a UNC path: {name!r}")
    if ":" in unified:
        # Also catches NTFS alternate data streams like "notes.txt:hidden".
        raise UnsafePathError(f"Archive entry contains a colon: {name!r}")

    parts = [part for part in unified.split("/") if part != ""]
    if not parts:
        raise UnsafePathError(f"Archive entry resolves to nothing: {name!r}")

    for part in parts:
        if part == "..":
            raise UnsafePathError(f"Archive entry traverses upward: {name!r}")
        if part == ".":
            raise UnsafePathError(f"Archive entry contains a '.' component: {name!r}")
        # Windows strips trailing dots and spaces, so "foo. " and "foo" collide.
        if part != part.rstrip(". "):
            raise UnsafePathError(f"Archive entry has a trailing dot or space: {name!r}")
        stem = part.split(".")[0].upper()
        if stem in RESERVED_NAMES:
            raise UnsafePathError(f"Archive entry uses the reserved device name {stem}: {name!r}")

    return PurePosixPath(*parts)


def _validated_members(archive: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, PurePosixPath]]:
    """Validate every entry up front. Nothing is written unless all of them pass."""
    members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
    for info in archive.infolist():
        if info.is_dir():
            validate_member(info.filename.rstrip("/") or ".")
            continue
        members.append((info, validate_member(info.filename)))
    return members


def create_safety_archive(
    root: Path, safety_dir: Path, *, keep: int = SAFETY_KEEP, should_stop: Callable[[], bool] | None = None
) -> Path | None:
    """Zip the current configuration. Returns None if there is nothing to save.

    Interruptible because no plan limit bounds it: this captures what a backup skips.
    """
    if not root.exists():
        return None

    safety_dir.mkdir(parents=True, exist_ok=True)
    target = safety_dir / f"config-{time.strftime('%Y%m%d-%H%M%S')}.zip"

    try:
        # Everything, including logs and oversized files a backup skips.
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(root.rglob("*")):
                if should_stop is not None and should_stop():
                    raise Cancelled("The restore was cancelled")
                if path.is_symlink() or not path.is_file():
                    continue
                try:
                    archive.write(path, arcname=path.relative_to(root).as_posix())
                except OSError:
                    continue  # a locked file must not cost us the rest of the copy
    except BaseException:
        target.unlink(missing_ok=True)  # a half-written copy looks like a way back
        raise

    prune_safety_archives(safety_dir, keep=keep)
    return target


def prune_safety_archives(safety_dir: Path, *, keep: int = SAFETY_KEEP) -> None:
    """Keep only the newest `keep` safety archives."""
    if not safety_dir.is_dir():
        return
    for stale in sorted(safety_dir.glob("config-*.zip"), reverse=True)[keep:]:
        stale.unlink(missing_ok=True)


def restore_archive(
    archive_path: Path,
    root: Path,
    *,
    safety_dir: Path | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> RestoreResult:
    """Replace `root` with the contents of `archive_path`.

    Files added since the backup are gone, so the result is one state rather than a mix. On
    failure the previous configuration is restored from the safety archive.

    `should_stop` is checked only while staging: the swap is an rmtree and a rename with
    nothing to unwind in between.
    """
    if not archive_path.is_file():
        raise RestoreError(f"Snapshot archive not found: {archive_path}")

    root.mkdir(parents=True, exist_ok=True)
    staging = root.parent / f".{root.name}.restore-{secrets.token_hex(4)}"
    safety: Path | None = None
    restored: list[str] = []

    try:
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise RestoreError("Snapshot archive is corrupt")
            members = _validated_members(archive)

            if safety_dir is not None:
                safety = create_safety_archive(root, safety_dir, should_stop=should_stop)

            staging.mkdir(parents=True, exist_ok=False)
            for info, relative in members:
                if should_stop is not None and should_stop():
                    raise Cancelled("The restore was cancelled")
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as sink:
                    shutil.copyfileobj(source, sink)
                restored.append(relative.as_posix())

        # Staging is a sibling, so this is a rename rather than a copy.
        logger.debug("restore: replacing %s (safety copy at %s)", root, safety)
        shutil.rmtree(root, ignore_errors=True)
        os.replace(staging, root)

    except Cancelled:
        # Nothing to undo: cancelling is only possible before the swap touches `root`.
        raise
    except BaseException as exc:
        logger.error("restore failed, rolling back: %s", exc)
        if not _rollback(root, safety):
            logger.error("rollback failed; previous configuration is at %s", safety)
            raise RestoreError(
                "The restore failed and your previous configuration could not be put back. "
                f"A copy of it is saved at {safety}."
            ) from exc
        if isinstance(exc, RestoreError | UnsafePathError):
            raise
        if isinstance(exc, zipfile.BadZipFile):
            raise RestoreError(f"Snapshot archive is not a valid ZIP: {exc}") from exc
        if isinstance(exc, OSError):
            raise RestoreError(f"Restore failed: {exc.strerror or exc}") from exc
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return RestoreResult(tuple(restored), safety)


def extract_archive(
    archive_path: Path, target: Path, *, should_stop: Callable[[], bool] | None = None
) -> tuple[str, ...]:
    """Unpack a snapshot into `target`, creating it if needed.

    Same validation as a restore, but nothing already in `target` is removed. Deliberately
    not restore_archive, which would wipe whatever folder the user picked.
    """
    if not archive_path.is_file():
        raise RestoreError(f"Snapshot archive not found: {archive_path}")

    written: list[str] = []
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RestoreError("Snapshot archive is corrupt")
        members = _validated_members(archive)
        target.mkdir(parents=True, exist_ok=True)
        for info, relative in members:
            if should_stop is not None and should_stop():
                raise Cancelled("The save was cancelled")
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, destination.open("wb") as sink:
                shutil.copyfileobj(source, sink)
            written.append(relative.as_posix())
    return tuple(written)


def _rollback(root: Path, safety: Path | None) -> bool:
    """Put the previous configuration back.

    False only when there was a copy and it could not be restored, which is the one outcome
    the caller has to tell the user about.
    """
    if safety is None or not safety.is_file():
        return True
    try:
        root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(safety) as archive:
            archive.extractall(root)
        return True
    except Exception:
        return False


class BarController:
    """Starts and stops YASB through yasbc. Never raises, so a missing CLI cannot cost the
    user their restore."""

    def __init__(self) -> None:
        self._executable = self._locate()

    @staticmethod
    def _locate() -> str | None:
        found = shutil.which("yasbc")
        if found:
            return found
        bundled = Path(SCRIPT_PATH) / "yasbc.exe"
        return str(bundled) if bundled.exists() else None

    def is_running(self) -> bool:
        # The process table, not the pipe: os.path.exists on \\.\pipe\ is unreliable.
        return is_process_running(BAR_PROCESS_NAME)

    def _run(self, *args: str) -> bool:
        if self._executable is None:
            return False
        try:
            done = subprocess.run(
                [self._executable, *args],
                creationflags=subprocess.CREATE_NO_WINDOW,
                capture_output=True,
                timeout=BAR_COMMAND_TIMEOUT_S,
            )
        except OSError, subprocess.SubprocessError:
            return False
        return done.returncode == 0

    def stop(self) -> bool:
        ok = self._run("stop", "--silent")
        # yasbc exits before the bar does, and the restore must not replace open files.
        deadline = time.monotonic() + BAR_STOP_TIMEOUT_S
        while is_process_running(BAR_PROCESS_NAME) and time.monotonic() < deadline:
            time.sleep(0.25)
        return ok

    def start(self) -> bool:
        return self._run("start", "--silent")


def restore_with_restart(
    archive_path: Path,
    root: Path,
    *,
    safety_dir: Path | None = None,
    controller: BarController | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> RestoreOutcome:
    """Stop the bar, restore, start it again. Only restarts if it was running before."""
    controller = controller or BarController()
    was_running = controller.is_running()

    if was_running:
        controller.stop()

    restarted = False
    try:
        result = restore_archive(archive_path, root, safety_dir=safety_dir, should_stop=should_stop)
    finally:
        # In finally: a failed restore must not leave the desktop bare.
        if was_running:
            restarted = controller.start()

    return RestoreOutcome(restore=result, bar_was_running=was_running, bar_restarted=restarted)
