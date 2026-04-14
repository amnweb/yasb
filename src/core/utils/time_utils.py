import os
from datetime import UTC, datetime


def get_relative_time(iso_timestamp: str, short: bool = False) -> str:
    """
    Convert an ISO 8601 timestamp to a human-readable relative time string.

    Args:
        iso_timestamp: ISO 8601 formatted timestamp (e.g., "2024-11-01T12:00:00Z")
        short: If True, return a compact format (e.g., "3m", "5h", "1d", "20 Apr").

    Returns:
        A relative time string (e.g., "3 days ago", "2 weeks ago", "just now")
        or a compact form when *short=True* (e.g., "3d", "5h", "33m").
        Returns empty string if timestamp is invalid or empty.

    Examples:
        >>> get_relative_time("2024-11-07T12:00:00Z")
        "just now"
        >>> get_relative_time("2024-11-04T12:00:00Z")
        "3 days ago"
        >>> get_relative_time("2024-11-04T12:00:00Z", short=True)
        "3d"
    """
    if not iso_timestamp:
        return ""

    try:
        # Parse ISO 8601 timestamp
        updated = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        diff = now - updated

        seconds = diff.total_seconds()
        minutes = seconds / 60
        hours = minutes / 60
        days = hours / 24
        weeks = days / 7
        months = days / 30
        years = days / 365

        if seconds < 60:
            return "now" if short else "just now"
        elif minutes < 60:
            m = int(minutes)
            return f"{m}m" if short else f"{m} minute{'s' if m != 1 else ''} ago"
        elif hours < 24:
            h = int(hours)
            return f"{h}h" if short else f"{h} hour{'s' if h != 1 else ''} ago"
        elif days < 7:
            d = int(days)
            return f"{d}d" if short else f"{d} day{'s' if d != 1 else ''} ago"
        elif short:
            if days < 365:
                return updated.strftime("%-d %b") if os.name != "nt" else updated.strftime("%#d %b")
            return updated.strftime("%b %Y")
        elif weeks < 4:
            w = int(weeks)
            return f"{w} week{'s' if w != 1 else ''} ago"
        elif months < 12:
            mo = int(months)
            return f"{mo} month{'s' if mo != 1 else ''} ago"
        else:
            y = int(years)
            return f"{y} year{'s' if y != 1 else ''} ago"
    except Exception:
        return ""
