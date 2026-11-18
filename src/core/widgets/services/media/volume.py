"""Per-application audio volume for native media cards (never the system master)."""

import os
from typing import Any

from pycaw.pycaw import AudioUtilities

from core.utils.win32.aumid import get_aumid_for_process
from core.utils.win32.aumid_process import get_process_name_for_aumid


class AppVolumeController:
    def __init__(self) -> None:
        self._interfaces: dict[str, list[Any]] = {}
        self._executables: dict[str, str] = {}

    def refresh(self, app_ids: set[str]) -> None:
        self._interfaces = {app_id: [] for app_id in app_ids}
        for app_id in app_ids:
            if app_id not in self._executables:
                name = app_id if app_id.lower().endswith(".exe") else get_process_name_for_aumid(app_id)
                self._executables[app_id] = os.path.basename(name or "").lower()
        try:
            sessions: list[Any] = list(AudioUtilities.GetAllSessions())
        except Exception:
            return
        for session in sessions:
            try:
                process = session.Process
                if process is None:
                    continue
                aumid = get_aumid_for_process(int(process.pid)) or ""
                matches = [app_id for app_id in app_ids if app_id.lower() == aumid.lower()]
                if not matches:
                    exe = process.name().lower()
                    candidates = [app_id for app_id in app_ids if self._executables.get(app_id) == exe]
                    # An executable can host several PWAs. Do not guess which player owns the audio.
                    if len(candidates) == 1:
                        matches = candidates
                for app_id in matches:
                    self._interfaces[app_id].append(session.SimpleAudioVolume)
            except Exception:
                continue

    def snapshot(self, app_id: str) -> tuple[int, bool] | None:
        interfaces = self._interfaces.get(app_id, [])
        if not interfaces:
            return None
        try:
            level = round(float(interfaces[0].GetMasterVolume()) * 100)
            return min(100, max(0, level)), all(bool(interface.GetMute()) for interface in interfaces)
        except Exception:
            self._interfaces.pop(app_id, None)
            return None

    def set_volume(self, app_id: str, level: int) -> None:
        for interface in self._interfaces.get(app_id, []):
            try:
                interface.SetMasterVolume(min(100, max(0, level)) / 100, None)
                if level > 0:
                    interface.SetMute(False, None)
            except Exception:
                pass

    def toggle_mute(self, app_id: str) -> None:
        snapshot = self.snapshot(app_id)
        if snapshot is None:
            return
        for interface in self._interfaces.get(app_id, []):
            try:
                interface.SetMute(not snapshot[1], None)
            except Exception:
                pass
