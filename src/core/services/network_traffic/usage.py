"""Windows history and in-memory session counters."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from winrt.windows.foundation import AsyncStatus
from winrt.windows.networking.connectivity import ConnectionProfile, DataUsageGranularity, NetworkUsageStates

from core.services.network.adapters import Adapter
from core.services.network.connections import connection_profile

DAY = timedelta(days=1)
HOUR = timedelta(hours=1)

# The adapter id and network name of a connection
type ProfileKey = tuple[str, str]


class Session:
    def __init__(self) -> None:
        self.key: ProfileKey | None = None
        self.started = 0.0
        self.uploaded = self.downloaded = 0
        self.previous: tuple[float, Adapter] | None = None

    def sample(self, key: ProfileKey, adapter: Adapter | None, now: float, reset: bool) -> dict[str, Any]:
        if key != self.key or reset:
            self.key = key
            self.started = now
            self.uploaded = self.downloaded = 0
            self.previous = None

        upload_rate = download_rate = 0.0
        if adapter is not None and adapter.connected and self.previous is not None:
            sampled_at, previous = self.previous
            sent = max(0, adapter.uploaded - previous.uploaded)
            received = max(0, adapter.downloaded - previous.downloaded)
            self.uploaded += sent
            self.downloaded += received
            elapsed = now - sampled_at
            if elapsed > 0:
                upload_rate, download_rate = sent / elapsed, received / elapsed
        self.previous = (now, adapter) if adapter is not None and adapter.connected else None
        return {
            "uploadRate": upload_rate,
            "downloadRate": download_rate,
            "sessionUploaded": self.uploaded,
            "sessionDownloaded": self.downloaded,
            "sessionSeconds": int(now - self.started),
        }


def _usage(
    profile: ConnectionProfile, start: datetime, end: datetime, granularity: DataUsageGranularity, step: timedelta
) -> list[dict[str, int]]:
    if start >= end:
        return []
    operation = profile.get_network_usage_async(start, end, granularity, NetworkUsageStates())
    if operation.wait(5) == AsyncStatus.STARTED:
        operation.cancel()
        raise TimeoutError("Windows usage history timed out")
    return [
        {
            "stamp": int((start + index * step).timestamp() * 1000),
            "downloaded": item.bytes_received,
            "uploaded": item.bytes_sent,
        }
        for index, item in enumerate(operation.get_results())
    ]


def _midnight(day: date) -> datetime:
    return datetime.combine(day, time.min).astimezone(UTC)


def read_history(key: ProfileKey, today: date) -> dict[str, Any]:
    profile = connection_profile(key[0])
    if profile is None or profile.profile_name != key[1]:
        return {}
    now = datetime.now(UTC)
    midnights = [_midnight(today - timedelta(days=days)) for days in range(29, -1, -1)]
    daily: list[dict[str, int]] = []
    start = midnights[0]
    for day, following in zip(midnights, midnights[1:]):
        if following - day != DAY:
            # WinRT day buckets are 24 hours. Query short or long local days separately.
            daily.extend(_usage(profile, start, day, DataUsageGranularity.PER_DAY, DAY))
            daily.extend(_usage(profile, day, following, DataUsageGranularity.TOTAL, DAY))
            start = following

    midnight = midnights[-1]
    daily.extend(_usage(profile, start, midnight, DataUsageGranularity.PER_DAY, DAY))
    hourly = _usage(profile, midnight, now, DataUsageGranularity.PER_HOUR, HOUR)
    if hourly:
        daily.append(
            {
                "stamp": int(midnight.timestamp() * 1000),
                "downloaded": sum(point["downloaded"] for point in hourly),
                "uploaded": sum(point["uploaded"] for point in hourly),
            }
        )
    return {"daily": daily, "hourly": hourly, "updatedAt": int(now.timestamp() * 1000)}
