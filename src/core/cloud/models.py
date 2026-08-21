"""Typed views over the API's JSON, so parsing lives in one place."""

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


def _int(source: dict[str, Any], key: str, default: int = 0) -> int:
    value = source.get(key, default)
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _b64(value: Any) -> bytes:
    try:
        return base64.b64decode(value or "")
    except ValueError, TypeError:
        return b""


@dataclass(frozen=True, slots=True)
class Limits:
    max_storage_bytes: int = 0
    max_snapshot_bytes: int = 0

    @classmethod
    def from_json(cls, data: dict[str, Any] | None) -> Limits:
        data = data or {}
        return cls(
            max_storage_bytes=_int(data, "max_storage_bytes"),
            max_snapshot_bytes=_int(data, "max_snapshot_bytes"),
        )


@dataclass(frozen=True, slots=True)
class Usage:
    bytes: int = 0
    snapshots: int = 0

    @classmethod
    def from_json(cls, data: dict[str, Any] | None) -> Usage:
        data = data or {}
        return cls(bytes=_int(data, "bytes"), snapshots=_int(data, "snapshots"))


@dataclass(frozen=True, slots=True)
class Subscription:
    plan_id: str
    status: str

    @classmethod
    def from_json(cls, data: dict[str, Any] | None) -> Subscription | None:
        if not data:
            return None
        return cls(
            plan_id=str(data.get("plan_id", "")),
            status=str(data.get("status", "")),
        )

    @property
    def is_active(self) -> bool:
        return self.status in ("active", "trialing")


@dataclass(frozen=True, slots=True)
class Access:
    can_read: bool = False
    can_write: bool = False
    reason: str | None = None
    read_until: str = ""

    @classmethod
    def from_json(cls, data: dict[str, Any] | None) -> Access:
        data = data or {}
        return cls(
            can_read=bool(data.get("can_read")),
            can_write=bool(data.get("can_write")),
            reason=data.get("reason"),
            read_until=str(data.get("read_until") or ""),
        )


@dataclass(frozen=True, slots=True)
class Account:
    user_id: str
    email: str
    subscription: Subscription | None
    limits: Limits
    usage: Usage
    access: Access

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Account:
        user = data.get("user", {})
        return cls(
            user_id=str(user.get("id", "")),
            email=str(user.get("email", "")),
            subscription=Subscription.from_json(data.get("subscription")),
            limits=Limits.from_json(data.get("limits")),
            usage=Usage.from_json(data.get("usage")),
            access=Access.from_json(data.get("access")),
        )


@dataclass(frozen=True, slots=True)
class Snapshot:
    id: str
    size_bytes: int
    file_count: int
    created_at: str
    app_version: str
    note: str = ""
    device_name: str = ""
    share_url: str = ""
    """Empty unless this backup is published. The server builds the URL, so a domain change
    needs no client release."""

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Snapshot:
        return cls(
            id=str(data.get("id", "")),
            size_bytes=_int(data, "size_bytes"),
            file_count=_int(data, "file_count"),
            created_at=str(data.get("created_at", "")),
            app_version=str(data.get("app_version", "")),
            note=str(data.get("note", "")),
            device_name=str(data.get("device_name", "")),
            share_url=str((data.get("share") or {}).get("url", "")),
        )


def parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError, TypeError:
        return None


def format_timestamp(value: str) -> str:
    moment = parse_timestamp(value)
    return moment.astimezone().strftime("%d %b %Y, %H:%M") if moment else value


def relative_time(value: str) -> str:
    moment = parse_timestamp(value)
    if moment is None:
        return value

    seconds = (datetime.now(UTC) - moment).total_seconds()
    if seconds < 90:
        return "Just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(seconds // 86400)
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    return format_timestamp(value)


def format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
