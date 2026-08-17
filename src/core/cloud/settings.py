"""User settings for the cloud app, stored beside the credentials."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.cloud.constants import (
    MAX_EXCLUDE_RULE_LENGTH,
    MAX_EXCLUDE_RULES,
    SETTINGS_FILE,
    SETTINGS_VERSION,
)
from core.cloud.session import cloud_dir


def clean_rules(values: Any) -> tuple[str, ...]:
    """Whatever came in, reduced to rules worth storing.

    Applied on the way in and out. The file is hand-editable, so a badly edited list has to be
    survivable rather than fatal.
    """
    if not isinstance(values, list):
        return ()

    seen: dict[str, None] = {}
    for value in values:
        if not isinstance(value, str):
            continue
        rule = value.strip()
        if rule and len(rule) <= MAX_EXCLUDE_RULE_LENGTH:
            seen[rule] = None
    return tuple(seen)[:MAX_EXCLUDE_RULES]


@dataclass(frozen=True, slots=True)
class Settings:
    exclude: tuple[str, ...] = ()
    auto_backup: bool = False
    debug_logging: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "version": SETTINGS_VERSION,
            "exclude": list(self.exclude),
            "auto_backup": {"enabled": self.auto_backup},
            "debug_logging": self.debug_logging,
        }

    @classmethod
    def from_json(cls, data: Any) -> Settings:
        if not isinstance(data, dict):
            return cls()
        auto = data.get("auto_backup")
        return cls(
            exclude=clean_rules(data.get("exclude")),
            auto_backup=bool(auto.get("enabled")) if isinstance(auto, dict) else False,
            debug_logging=bool(data.get("debug_logging")),
        )


def settings_path() -> Path:
    return cloud_dir() / SETTINGS_FILE


def load() -> Settings:
    """Read the file, or return defaults. Never raises."""
    try:
        return Settings.from_json(json.loads(settings_path().read_bytes()))
    except OSError, ValueError:
        return Settings()


def staging_path(target: Path) -> Path:
    """Per process: the window and the scheduled task both write settings, and a shared
    staging file can be written by one while the other renames it."""
    return target.with_name(f"{target.name}.{os.getpid()}.partial")


def save(settings: Settings) -> bool:
    """Write the file, reporting whether it worked.

    Failure is a return value, never an exception. The caller in the window runs inside a Qt
    slot, where an escaping exception aborts the process, so even the cleanup has to be
    allowed to fail.
    """
    target = settings_path()
    staging = staging_path(target)
    try:
        staging.write_text(json.dumps(settings.to_json(), indent=2), encoding="utf-8")
        staging.replace(target)
        return True
    except OSError:
        try:
            staging.unlink(missing_ok=True)
        except OSError:
            pass
        return False
