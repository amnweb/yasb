import json
import logging
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from PyQt6.QtCore import QUrl
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from settings import BUILD_VERSION

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
# The beta header Claude Code sends to the usage endpoint
OAUTH_BETA = "oauth-2025-04-20"
STATUS_URL = "https://status.claude.com/api/v2/status.json"
TIMEOUT_MS = 20000
# What the status page reports, from all well to worst; anything else is unknown
STATUS_LEVELS = ("none", "minor", "major", "critical")


def config_dir() -> Path:
    """Claude Code's folder: CLAUDE_CONFIG_DIR, or .claude in the user's home."""
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def read_credentials() -> tuple[str, int]:
    """Claude Code's OAuth access token and when it expires, in ms since the epoch; ("", 0) when signed out.

    The token is only ever sent to Anthropic's usage endpoint; it is never logged, saved or given to QML.
    """
    try:
        data = json.loads((config_dir() / ".credentials.json").read_text(encoding="utf-8"))
    except OSError, ValueError:
        return "", 0
    oauth = cast(dict[str, Any], data).get("claudeAiOauth") if isinstance(data, dict) else None
    if not isinstance(oauth, dict):
        return "", 0
    oauth = cast(dict[str, Any], oauth)
    token = oauth.get("accessToken")
    expires = oauth.get("expiresAt")
    return (
        token if isinstance(token, str) else "",
        int(expires) if isinstance(expires, int | float) and not isinstance(expires, bool) else 0,
    )


def time_ms(iso: Any) -> int:
    """An ISO 8601 time as ms since the epoch, or 0."""
    if not isinstance(iso, str) or not iso:
        return 0
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return 0


def _limit(entry: Any, name: str) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    entry = cast(dict[str, Any], entry)
    used = entry.get("utilization", entry.get("percent"))
    if not isinstance(used, int | float) or isinstance(used, bool):
        return None
    return {"name": name, "percent": float(used), "resetsAt": time_ms(entry.get("resets_at"))}


def parse_usage(payload: Any) -> dict[str, Any]:
    """The usage endpoint's answer as {fiveHour, sevenDay, models}: each limit {name, percent, resetsAt}.

    fiveHour and sevenDay are None when missing. models are the per-model weekly caps, such as Fable's, from the
    answer's limits; the older seven_day_opus and seven_day_sonnet fields are always empty now.
    """
    data = cast(dict[str, Any], payload) if isinstance(payload, dict) else {}
    models: list[dict[str, Any]] = []
    raw_limits = data.get("limits")
    for raw in cast(list[Any], raw_limits) if isinstance(raw_limits, list) else []:
        entry = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
        if entry.get("kind") != "weekly_scoped":
            continue
        scope = entry.get("scope")
        model = cast(dict[str, Any], scope).get("model") if isinstance(scope, dict) else None
        name = cast(dict[str, Any], model).get("display_name") if isinstance(model, dict) else None
        limit = _limit(entry, name) if isinstance(name, str) and name else None
        if limit is not None:
            models.append(limit)
    return {
        "fiveHour": _limit(data.get("five_hour"), "5-hour"),
        "sevenDay": _limit(data.get("seven_day"), "7-day"),
        "models": models,
    }


def parse_status(payload: Any) -> dict[str, str] | None:
    """The status page's answer as {indicator, description}, indicator one of STATUS_LEVELS; None when unreadable."""
    status = cast(dict[str, Any], payload).get("status") if isinstance(payload, dict) else None
    if not isinstance(status, dict):
        return None
    status = cast(dict[str, Any], status)
    indicator = status.get("indicator")
    description = status.get("description")
    return {
        "indicator": indicator if indicator in STATUS_LEVELS else "unknown",
        "description": description if isinstance(description, str) else "",
    }


def read_reply(reply: QNetworkReply, site: str) -> tuple[Any, str]:
    """The reply's JSON and "", or None and what went wrong."""
    body = reply.readAll().data()
    try:
        data = json.loads(body) if body else None
    except ValueError:
        data = None
    error = reply.error()
    if error == QNetworkReply.NetworkError.NoError:
        return (data, "") if data is not None else (None, f"{site} sent an answer YASB could not read.")
    status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
    logging.warning("%s request failed: %s %s", site, error.name, status or "")
    if status == 401:
        return None, "Claude Code's sign-in has expired. Run any Claude Code command to renew it."
    if status == 429:
        return None, f"{site} is limiting requests; the last usage stays until it answers again."
    if status:
        return None, f"{site} returned HTTP {status}."
    return None, f"Could not connect to {site}."


def get_json(network: QNetworkAccessManager, url: str, done: Callable[[Any, str], None], token: str = "") -> None:
    """Calls done(data, "") with what the URL returns, or done(None, error); a token signs the request."""
    site = "Anthropic" if token else "the Claude status page"
    request = QNetworkRequest(QUrl(url))
    request.setRawHeader(b"User-Agent", f"YASB/{BUILD_VERSION}".encode())
    request.setTransferTimeout(TIMEOUT_MS)
    if token:
        request.setRawHeader(b"Authorization", f"Bearer {token}".encode())
        request.setRawHeader(b"anthropic-beta", OAUTH_BETA.encode())
    reply = network.get(request)
    if reply is None:
        done(None, f"Could not connect to {site}.")
        return

    def finished() -> None:
        reply.deleteLater()
        try:
            done(*read_reply(reply, site))
        except RuntimeError:
            # Whoever asked was destroyed while the answer came
            pass

    reply.finished.connect(finished)
