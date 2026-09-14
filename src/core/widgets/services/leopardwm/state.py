"""Strict, bounded assembly of LeopardWM's complete workspace transactions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Window:
    hwnd: int
    is_floating: bool
    is_sticky: bool


@dataclass(frozen=True)
class Workspace:
    index: int
    name: str | None
    windows: tuple[Window, ...]


@dataclass(frozen=True)
class Monitor:
    device_name: str
    monitor_id: int
    active_workspace_index: int
    workspaces: tuple[Workspace, ...]


@dataclass(frozen=True)
class WorkspaceSnapshot:
    session_id: str
    revision: int
    focused_monitor_device_name: str | None
    monitors: tuple[Monitor, ...]


def _integer(value, minimum=0, maximum=2**64 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid integer in workspace state")
    return value


def _string(value, nullable=False):
    if nullable and value is None:
        return value
    if not isinstance(value, str) or (not nullable and not value) or "\0" in value:
        raise ValueError("Invalid string in workspace state")
    return value


class SnapshotAssembler:
    # Generous desktop limits, independent of the transport's byte and time limits.
    MAX_RECORDS = 100_000
    MAX_MONITORS = 128

    def __init__(self):
        self.reset()

    @property
    def in_progress(self):
        return self._begin is not None

    def _discard(self):
        self._begin = None
        self._monitors = {}
        self._workspaces = {}
        self._windows = {}
        self._record_count = 0

    def reset(self):
        self._discard()
        self._last = None

    def feed(self, event: dict) -> WorkspaceSnapshot | None:
        try:
            return self._feed(event)
        except (ValueError, KeyError, TypeError) as error:
            self._discard()
            raise ValueError(f"Invalid LeopardWM workspace state: {error}") from error

    def _feed(self, event):
        if not isinstance(event, dict):
            raise ValueError("Event must be an object")
        kind = event["type"]
        if kind == "heartbeat" and not self.in_progress:
            _integer(event["uptime_seconds"])
            return None
        if kind == "workspace_snapshot_begin":
            if self.in_progress:
                raise ValueError("Interrupted snapshot")
            if _integer(event["protocol_version"]) not in (3, 4):
                raise ValueError("Unsupported workspace snapshot protocol")
            session = _string(event["session_id"])
            revision = _integer(event["revision"])
            focused = _string(event["focused_monitor_device_name"], nullable=True)
            if self._last and session == self._last[0] and revision <= self._last[1]:
                raise ValueError("Workspace revision did not advance")
            self._begin = session, revision, focused
            return None
        if kind not in ("workspace_snapshot_chunk", "workspace_snapshot_end") or not self.in_progress:
            raise ValueError(f"Unexpected event: {kind}")
        if _integer(event["revision"]) != self._begin[1]:
            raise ValueError("Mismatched workspace revision")
        if kind == "workspace_snapshot_chunk":
            records = event["records"]
            if not isinstance(records, list):
                raise ValueError("Records must be an array")
            self._record_count += len(records)
            if self._record_count > self.MAX_RECORDS:
                raise ValueError("Snapshot record limit exceeded")
            for record in records:
                self._record(record)
            return None
        snapshot = self._finish()
        self._last = snapshot.session_id, snapshot.revision
        self._discard()
        return snapshot

    def _record(self, record):
        if not isinstance(record, dict):
            raise ValueError("Record must be an object")
        kind = record["kind"]
        device = _string(record["monitor_device_name"])
        if kind == "monitor":
            if device in self._monitors or len(self._monitors) >= self.MAX_MONITORS:
                raise ValueError("Duplicate monitor or monitor limit exceeded")
            monitor_id = _integer(record["monitor_id"], -(2**63), 2**63 - 1)
            if monitor_id == 0 or any(item[0] == monitor_id for item in self._monitors.values()):
                raise ValueError("Invalid or duplicate monitor handle")
            self._monitors[device] = monitor_id, _integer(record["active_workspace_index"], 0, 8)
            return
        index = _integer(record["workspace_index"], 0, 8)
        key = device, index
        if kind == "workspace":
            if key in self._workspaces:
                raise ValueError("Duplicate workspace")
            self._workspaces[key] = _string(record["name"], nullable=True)
        elif kind == "window":
            hwnd = _integer(record["hwnd"], 1)
            if hwnd in self._windows:
                raise ValueError("Duplicate window ownership")
            if type(record["is_floating"]) is not bool or type(record["is_sticky"]) is not bool:
                raise ValueError("Invalid window flags")
            self._windows[hwnd] = key, Window(hwnd, record["is_floating"], record["is_sticky"])
        else:
            raise ValueError("Unknown workspace record kind")

    def _finish(self):
        session, revision, focused = self._begin
        if focused is not None and focused not in self._monitors:
            raise ValueError("Focused monitor is missing")
        expected = {(device, index) for device in self._monitors for index in range(9)}
        if self._workspaces.keys() != expected:
            raise ValueError("Snapshot must include all nine workspaces for each monitor")
        members = {key: [] for key in expected}
        for key, window in self._windows.values():
            if key not in members:
                raise ValueError("Window references an unknown workspace")
            members[key].append(window)
        monitors = []
        for device, (monitor_id, active) in sorted(self._monitors.items()):
            workspaces = tuple(
                Workspace(
                    index,
                    self._workspaces[device, index],
                    tuple(sorted(members[device, index], key=lambda window: window.hwnd)),
                )
                for index in range(9)
            )
            monitors.append(Monitor(device, monitor_id, active, workspaces))
        return WorkspaceSnapshot(session, revision, focused, tuple(monitors))
