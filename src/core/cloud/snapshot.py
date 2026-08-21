"""Collect the YASB configuration directory into a deterministic archive.

An ordinary ZIP, which encryption later wraps rather than replaces. Entries are sorted and
use POSIX separators, so the archive is byte-stable for unchanged input. Quota is checked
before any compression.
"""

import fnmatch
import os
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.cloud.constants import UNLIMITED
from core.cloud.errors import Cancelled, QuotaExceededError, SnapshotError
from core.cloud.models import format_size
from settings import DEFAULT_CONFIG_FILENAME, DEFAULT_STYLES_FILENAME

EXCLUDE_GLOBS: tuple[str, ...] = (
    "*.log",
    "*.log.*",
    "*.tmp",
    "*.temp",
    "*.bak",
    "~$*",
)
"""`*.log.*` YASB protected."""

EXCLUDE_DIRS: frozenset[str] = frozenset(
    {"__pycache__", ".git", ".venv", "venv", "node_modules", ".mypy_cache", "dumps"}
)
"""`dumps` is where the CLI writes crash dumps. YASB protected."""

ALWAYS_INCLUDE: frozenset[str] = frozenset({DEFAULT_CONFIG_FILENAME, DEFAULT_STYLES_FILENAME})
"""Paths no rule can exclude. Matched on the whole relative path, so a theme's own
config.yaml further down the tree is still the user's to exclude."""


@dataclass(frozen=True, slots=True)
class SnapshotResult:
    file_count: int
    total_bytes: int
    """Uncompressed size of everything included."""


@dataclass(frozen=True, slots=True)
class _Candidate:
    absolute: Path
    relative: str
    size: int


def _is_excluded_file(name: str, relative: str, extra: tuple[str, ...] = ()) -> bool:
    """The built-in globs, plus whatever the user added in settings.

    A user rule containing `/` matches the path relative to the configuration directory,
    anything else the file name at any depth. `ALWAYS_INCLUDE` wins over everything.
    """
    if relative in ALWAYS_INCLUDE:
        return False

    lowered = name.lower()
    if any(fnmatch.fnmatch(lowered, pattern) for pattern in EXCLUDE_GLOBS):
        return True

    lowered_relative = relative.lower()
    for pattern in extra:
        lowered_pattern = pattern.lower()
        target = lowered_relative if "/" in lowered_pattern else lowered
        if fnmatch.fnmatch(target, lowered_pattern):
            return True
    return False


def _relative_posix(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def collect_files(root: Path, exclude: tuple[str, ...] = ()) -> list[_Candidate]:
    """Walk `root` and decide what belongs in a snapshot.

    Reparse points are skipped rather than followed: one could pull in arbitrary files or
    escape the directory entirely.
    """
    if not root.exists():
        raise SnapshotError(f"Configuration directory does not exist: {root}")
    if not root.is_dir():
        raise SnapshotError(f"Configuration path is not a directory: {root}")

    resolved_root = root.resolve()
    included: list[_Candidate] = []

    def walk(directory: Path) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda e: e.name.lower())
        except OSError:
            return

        for entry in entries:
            path = Path(entry.path)
            try:
                if entry.is_symlink() or entry.is_junction():
                    continue

                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in EXCLUDE_DIRS:
                        walk(path)
                    continue

                if not entry.is_file(follow_symlinks=False):
                    continue

                if _is_excluded_file(entry.name, _relative_posix(root, path), exclude):
                    continue

                # Symlinks are skipped above; this catches anything else pointing outside.
                if not path.resolve().is_relative_to(resolved_root):
                    continue

                included.append(_Candidate(path, _relative_posix(root, path), entry.stat().st_size))
            except OSError:
                continue

    walk(root)
    included.sort(key=lambda candidate: candidate.relative)
    return included


def create_archive(
    root: Path,
    destination: Path,
    *,
    max_total_bytes: int = UNLIMITED,
    exclude: tuple[str, ...] = (),
    should_stop: Callable[[], bool] | None = None,
) -> SnapshotResult:
    """Build a ZIP of `root` at `destination`.

    `max_total_bytes` is the uncompressed total, deliberately: the server measures the
    ciphertext, which is smaller, so this never refuses something the server would have taken.
    """
    included = collect_files(root, exclude)

    # Before the ZipFile is opened, so an over-quota snapshot costs a walk, not a compress.
    declared = sum(candidate.size for candidate in included)
    if max_total_bytes != UNLIMITED and declared > max_total_bytes:
        raise QuotaExceededError(
            f"This snapshot is {format_size(declared)}, your plan allows {format_size(max_total_bytes)}."
        )

    staging = destination.with_name(destination.name + ".partial")
    total_bytes = 0

    try:
        with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for candidate in included:
                if should_stop is not None and should_stop():
                    raise Cancelled("Archiving was cancelled")
                try:
                    archive.write(candidate.absolute, arcname=candidate.relative)
                except OSError as exc:
                    raise SnapshotError(f"Could not read {candidate.relative}: {exc.strerror or exc}") from exc
                total_bytes += candidate.size

        staging.replace(destination)
    except BaseException:
        staging.unlink(missing_ok=True)
        raise

    return SnapshotResult(file_count=len(included), total_bytes=total_bytes)
