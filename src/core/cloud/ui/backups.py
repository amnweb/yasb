from typing import Any, override

from PyQt6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QObject, QPersistentModelIndex, Qt

from core.cloud.models import Snapshot, format_size, relative_time

ROLES = ["snapshotId", "note", "details", "shareUrl", "pending"]


class BackupModel(QAbstractListModel):
    """The snapshots shown in the backups list, newest first."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._snapshots: list[Snapshot] = []
        # Rows waiting for the server to confirm a delete, whose actions stay off until then
        self._pending: set[str] = set()

    @override
    def roleNames(self) -> dict[int, QByteArray]:
        return {Qt.ItemDataRole.UserRole + i: QByteArray(name.encode()) for i, name in enumerate(ROLES)}

    @override
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._snapshots)

    @override
    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not 0 <= index.row() < len(self._snapshots) or not 0 <= role - Qt.ItemDataRole.UserRole < len(ROLES):
            return None
        snapshot = self._snapshots[index.row()]
        match ROLES[role - Qt.ItemDataRole.UserRole]:
            case "snapshotId":
                return snapshot.id
            case "note":
                return snapshot.note.strip()
            case "details":
                device = snapshot.device_name or "Unknown PC"
                version = snapshot.app_version or "Unknown"
                when = relative_time(snapshot.created_at)
                return f"{when} - {format_size(snapshot.size_bytes)} - {device} (v{version})"
            case "shareUrl":
                return snapshot.share_url
            case _:
                return snapshot.id in self._pending

    def find(self, snapshot_id: str) -> Snapshot | None:
        return next((s for s in self._snapshots if s.id == snapshot_id), None)

    def _row(self, snapshot_id: str) -> int:
        return next((i for i, s in enumerate(self._snapshots) if s.id == snapshot_id), -1)

    def reset(self, snapshots: list[Snapshot]) -> None:
        self.beginResetModel()
        self._snapshots = list(snapshots)
        self._pending.clear()
        self.endResetModel()

    def append(self, snapshots: list[Snapshot]) -> None:
        if snapshots:
            start = len(self._snapshots)
            self.beginInsertRows(QModelIndex(), start, start + len(snapshots) - 1)
            self._snapshots.extend(snapshots)
            self.endInsertRows()

    def prepend(self, snapshot: Snapshot) -> None:
        self.beginInsertRows(QModelIndex(), 0, 0)
        self._snapshots.insert(0, snapshot)
        self.endInsertRows()

    def replace(self, snapshot: Snapshot) -> None:
        row = self._row(snapshot.id)
        if row >= 0:
            self._snapshots[row] = snapshot
            self.dataChanged.emit(self.index(row), self.index(row))

    def remove(self, snapshot_id: str) -> None:
        row = self._row(snapshot_id)
        self._pending.discard(snapshot_id)
        if row >= 0:
            self.beginRemoveRows(QModelIndex(), row, row)
            del self._snapshots[row]
            self.endRemoveRows()

    def set_pending(self, snapshot_id: str, pending: bool) -> None:
        if pending:
            self._pending.add(snapshot_id)
        else:
            self._pending.discard(snapshot_id)
        row = self._row(snapshot_id)
        if row >= 0:
            pending_role = Qt.ItemDataRole.UserRole + ROLES.index("pending")
            self.dataChanged.emit(self.index(row), self.index(row), [pending_role])
