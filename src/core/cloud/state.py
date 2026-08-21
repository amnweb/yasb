"""What the automatic backup remembers between runs."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from core.cloud.constants import AUTOBACKUP_STATE_FILE
from core.cloud.session import cloud_dir


@dataclass(frozen=True, slots=True)
class State:
    last_seen: str = ""
    last_backed_up: str = ""
    files: dict[str, str] = field(default_factory=dict)


def state_path() -> Path:
    return cloud_dir() / AUTOBACKUP_STATE_FILE


def read_state() -> State:
    """The stored signatures, or empty ones.

    Empty also covers an unreadable file. Worst case is one redundant backup, where guessing
    would mean silently never backing up again.
    """
    try:
        data = json.loads(state_path().read_bytes())
    except OSError, ValueError:
        return State()
    if not isinstance(data, dict):
        return State()
    seen, backed, files = data.get("last_seen"), data.get("last_backed_up"), data.get("files")
    return State(
        last_seen=seen if isinstance(seen, str) else "",
        last_backed_up=backed if isinstance(backed, str) else "",
        files=files if isinstance(files, dict) else {},
    )


def write_state(last_seen: str, last_backed_up: str, files: dict[str, str] | None = None) -> bool:
    try:
        state_path().write_text(
            json.dumps(
                {
                    "last_seen": last_seen,
                    "last_backed_up": last_backed_up,
                    "files": files if files is not None else {},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False
