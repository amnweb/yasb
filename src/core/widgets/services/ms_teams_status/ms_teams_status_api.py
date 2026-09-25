import logging
import os
import re
import shutil
import subprocess
from enum import Enum
from pathlib import Path
from typing import Self

from pydantic import BaseModel
from PyQt6.QtCore import QObject, QUrl

AVAIL_RE = re.compile(r"availability:\s*([A-Za-z]+)", re.IGNORECASE)
UNREAD_RE = re.compile(r"unread notification count:\s*(\d+)", re.IGNORECASE)


class AvailabilityStatusText(Enum):
    Available = "Available"
    AvailableIdle = "Available Idle"
    Away = "Away"
    BeRightBack = "Be Right Back"
    Busy = "Busy"
    InAMeeting = "In A Meeting"
    InACall = "In A Call"
    Presenting = "Presenting"
    OnThePhone = "On The Phone"
    DoNotDisturb = "Do Not Disturb"
    Focusing = "Focusing"
    Offline = "Offline"

    @classmethod
    def to_status(cls, token: str) -> Self | None:
        return cls.__members__.get(token)  # the member, or None if unknown


class AvailabilitySettable(Enum):
    Available = "available"
    Away = "away"
    BeRightBack = "be-right-back"
    Busy = "busy"
    DoNotDisturb = "dnd"
    Offline = "offline"
    Reset = None


class AvailabilityStatusClass(Enum):
    Available = "available"
    AvailableIdle = "available-idle"
    Away = "away"
    BeRightBack = "be-right-back"
    Busy = "busy"
    InAMeeting = "in-a-meeting"
    InACall = "in-a-call"
    Presenting = "presenting"
    OnThePhone = "on-the-phone"
    DoNotDisturb = "do-not-disturb"
    Focusing = "focusing"
    Offline = "offline"
    Reset = "reset"

    @classmethod
    def to_class(cls, token: str) -> Self | None:
        return cls.__members__.get(token)  # the member, or None if unknown


class AvailabilityStatus(BaseModel):
    status: AvailabilityStatusText
    status_class: AvailabilityStatusClass
    unread: int


class MSTeamsStatusAPI(QObject):
    _instance: MSTeamsStatusAPI | None = None
    # Resolved on first use — the probe spawns PowerShell, so it can't run at import time.
    _teams_installed: bool | None = None

    @classmethod
    def get_instance(cls, parent: QObject, url: QUrl = None):
        if cls._instance is not None:
            return cls._instance
        cls._instance = MSTeamsStatusAPI(parent, url)
        return cls._instance

    def __init__(self, parent: QObject, url: QUrl = None):
        super().__init__(parent)

        self._teams_log_dir = MSTeamsStatusAPI._find_teams_log_dir()
        self._last_status: AvailabilityStatus | None = None

        self._tail = 8000
        self._max_logs = 3

    def get_status(self) -> AvailabilityStatus | None:
        if self._teams_log_dir is None:
            self._teams_log_dir = MSTeamsStatusAPI._find_teams_log_dir()

        # log rotates every few hours, fresh file carries no
        # availability line until the next presence change or 5-minute heartbeat.
        # re-resolve on every call and fall back through the previous logs.
        logs = MSTeamsStatusAPI._find_teams_logs(self._teams_log_dir, self._max_logs)
        status, unread = self._find_status(logs)
        status_member = AvailabilityStatusText.to_status(status)

        if status_member is None:
            return self._last_status

        self._last_status = AvailabilityStatus(
            status=status_member,
            status_class=AvailabilityStatusClass.to_class(status),
            unread=unread if unread is not None else 0,
        )
        return self._last_status

    def _find_status(self, logs: list[Path]) -> tuple[str | None, int | None]:
        """Most recent availability/unread pair across `logs`, which are newest-first."""
        avail_match = None
        notif_match = None

        for log in logs:
            try:
                lines = MSTeamsStatusAPI._tail_lines(log, self._tail)
            except OSError:
                continue  # rotated or locked out from under us

            for line in reversed(lines):
                if avail_match is None:
                    avail_match = AVAIL_RE.search(line)
                if notif_match is None:
                    notif_match = UNREAD_RE.search(line)
                if avail_match is not None and notif_match is not None:
                    break

            if avail_match is not None and notif_match is not None:
                break

        return (
            avail_match.group(1) if avail_match else None,
            int(notif_match.group(1)) if notif_match else None,
        )

    @classmethod
    def _is_teams_installed(cls) -> bool:
        if cls._teams_installed is None:
            cls._teams_installed = cls._check_teams_installed()
        return cls._teams_installed

    @staticmethod
    def _check_teams_installed() -> bool:
        """True if the new Teams MSIX package is registered for this user."""
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-AppxPackage -Name MSTeams | Select-Object -First 1 -ExpandProperty PackageFullName",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except FileNotFoundError, subprocess.TimeoutExpired:
            return False
        return result.returncode == 0 and result.stdout.strip() != ""

    @classmethod
    def ms_teams_timer_start(cls):
        return

    @staticmethod
    def _find_teams_log_dir() -> Path | None:
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            return None

        packages = Path(local) / "Packages"
        if not packages.is_dir():
            return None

        # Don't trust the exact family name — match any MSTeams_* package.
        for pkg in packages.glob("MSTeams_*"):
            log_dir = pkg / "LocalCache" / "Microsoft" / "MSTeams" / "Logs"
            if log_dir.is_dir():
                return log_dir

        return None

    @staticmethod
    def _find_teams_logs(teams_log_dir: Path | None, limit: int = 3) -> list[Path]:
        if teams_log_dir and teams_log_dir.is_dir():
            log_dir = teams_log_dir
        else:
            log_dir = MSTeamsStatusAPI._find_teams_log_dir()
        if not log_dir:
            return []

        logs = [p for p in log_dir.glob("MSTeams_*.log") if p.is_file()]
        logs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return logs[:limit]

    @staticmethod
    def _tail_lines(path: Path, max_lines: int, block_size: int = 65536) -> list[str]:
        blocks: list[bytes] = []
        newlines = 0
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            pos = f.tell()
            while pos > 0 and newlines <= max_lines:
                read_size = min(block_size, pos)
                pos -= read_size
                f.seek(pos)
                block = f.read(read_size)
                newlines += block.count(b"\n")
                blocks.append(block)
        # Join before decoding so a multi-byte char split across a block boundary survives.
        lines = b"".join(reversed(blocks)).decode("utf-8", errors="replace").splitlines()
        return lines[-max_lines:]

    def set_status(self, status: AvailabilitySettable) -> bool:
        if not self._is_teams_installed():
            logging.warning("MS Teams not installed or not findable")
            return False

        exe = shutil.which("ms-teams") or shutil.which("ms-teams.exe")
        if not exe:
            return False

        arg = "--reset-presence" if status is AvailabilitySettable.Reset else f"--set-presence-to-{status.value}"
        try:
            subprocess.run([exe, arg], timeout=10)
            return True
        except OSError, subprocess.TimeoutExpired:
            return False
