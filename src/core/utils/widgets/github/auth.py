import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

from core.utils.system import app_data_path

_OAUTH_APPS = {
    "notifications": {"client_id": "Ov23li0KAXuxNzbEl9Jy", "scope": "notifications"},
    "copilot": {"client_id": "Iv23lixvCWMEuoUakkey", "scope": ""},
}

_TOKEN_FILES = {
    "notifications": app_data_path("github_token"),
    "copilot": app_data_path("github_copilot_token"),
}


def get_saved_token(name: str = "notifications") -> str:
    """Read a saved OAuth token from disk. Returns empty string if not found."""
    try:
        path = _TOKEN_FILES[name]
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    except Exception as e:
        logging.error("GitHubAuth: Failed to read saved token: %s", e)
    return ""


def save_token(token: str, name: str = "notifications") -> None:
    """Persist an OAuth token to disk."""
    try:
        _TOKEN_FILES[name].write_text(token, encoding="utf-8")
        logging.info("GitHubAuth token saved successfully.")
    except Exception as e:
        logging.error("GitHubAuth failed to save token: %s", e)


def request_device_code(name: str = "notifications") -> dict:
    """
    Request a device code from GitHub OAuth Device Flow.
    Returns dict with: device_code, user_code, verification_uri, expires_in, interval.
    Raises on network/API error.
    """
    app = _OAUTH_APPS[name]
    params = {"client_id": app["client_id"]}
    if app["scope"]:
        params["scope"] = app["scope"]
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        "https://github.com/login/device/code",
        data=data,
        headers={"Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logging.error("GitHubAuth HTTP %s: %s", e.code, body)
        raise RuntimeError(f"GitHub returned HTTP {e.code}.\nDetails: {body}") from e
    except urllib.error.URLError as e:
        logging.error("GitHubAuth network error: %s", e)
        raise RuntimeError("Network error.\nCheck your internet connection.") from e


def poll_for_token(
    device_code: str,
    interval: int,
    on_success: Callable[[str], None],
    on_error: Callable[[str], None],
    stop_flag: Callable[[], bool],
    save_fn: Callable[[str], None] | None = None,
    name: str = "notifications",
) -> None:
    """
    Poll GitHub for an access token after the user has authorized the device.
    Runs in a background thread.

    - on_success(token) is called when the user approves.
    - on_error(message) is called on any unrecoverable error.
    - stop_flag() should return True to cancel polling early.
    """
    poll_interval = max(interval, 5)
    cid = _OAUTH_APPS[name]["client_id"]
    post_data_base = {
        "client_id": cid,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }

    while not stop_flag():
        time.sleep(poll_interval)
        if stop_flag():
            return
        try:
            encoded = urllib.parse.urlencode(post_data_base).encode("utf-8")
            req = urllib.request.Request(
                "https://github.com/login/oauth/access_token",
                data=encoded,
                headers={"Accept": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            error = result.get("error")
            if error == "authorization_pending":
                continue
            elif error == "slow_down":
                poll_interval += 5
                continue
            elif error == "expired_token":
                on_error("Device code expired.\nPlease try again.")
                return
            elif error == "access_denied":
                on_error("Authorization was denied.")
                return
            elif error:
                on_error(f"Authorization failed: {error}")
                return

            token = result.get("access_token", "")
            if token:
                _save = save_fn if save_fn is not None else save_token
                _save(token)
                on_success(token)
                return

        except urllib.error.URLError:
            on_error("Network error.\nCheck your internet connection.")
            return
        except Exception as e:
            logging.error("GitHubAuth polling error: %s", e)
            on_error(f"Unexpected error: {e}")
            return
