"""OAuth helpers for the Google Calendar widget.

Uses Google's installed-app flow — `InstalledAppFlow.run_local_server` opens the
user's browser, runs a localhost HTTP listener for the redirect, and returns
credentials. Calendar scope has no device-flow equivalent for installed apps.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from core.utils.system import app_data_path

if TYPE_CHECKING:
    from collections.abc import Callable

    from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def credentials_path() -> Path:
    """Path where the user drops the OAuth client secrets JSON from Google Cloud Console."""
    return app_data_path("google_calendar_credentials.json")


def token_path() -> Path:
    """Path where the authorised user token is persisted."""
    return app_data_path("google_calendar_token.json")


def get_creds() -> Credentials | None:
    """Load saved credentials, refreshing them if expired. Returns None when missing/invalid.

    Caller is expected to invoke `run_install_flow` if this returns None and a
    credentials JSON exists at `credentials_path()`.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token = token_path()
    if not token.exists():
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    except Exception as e:
        logging.warning("GoogleCalendarAuth: ignoring unreadable token at %s: %s", token, e)
        return None

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_creds(creds)
            return creds
        except Exception as e:
            logging.warning("GoogleCalendarAuth: token refresh failed: %s", e)
            return None

    return None


def save_creds(creds: Credentials) -> None:
    """Persist credentials JSON to `token_path()`."""
    path = token_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(creds.to_json(), encoding="utf-8")
    except Exception as e:
        logging.error("GoogleCalendarAuth: failed to save token: %s", e)


def run_install_flow(on_url: Callable[[str], None] | None = None) -> Credentials:
    """Run Google's installed-app OAuth flow.

    Listens on a random localhost port for the redirect and blocks until the
    user completes (or cancels) sign-in. When ``on_url`` is provided, the auth
    URL is forwarded to it and the default browser is NOT opened automatically
    — the caller is responsible for surfacing the URL to the user. Otherwise
    the default browser is opened to Google's consent page as before.
    """
    import webbrowser

    from google_auth_oauthlib.flow import InstalledAppFlow

    creds_file = credentials_path()
    if not creds_file.exists():
        raise FileNotFoundError(f"OAuth client secrets missing at {creds_file}")

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)

    if on_url is None:
        creds = flow.run_local_server(port=0, open_browser=True)
    else:
        # google_auth_oauthlib computes the auth URL inside run_local_server
        # (it depends on the random port) and reaches a browser via
        # webbrowser.get(name).open(url). Intercept webbrowser.get so we can
        # capture the URL and skip the auto-open.
        class _CaptureBrowser:
            def open(self, url: str, *_args, **_kwargs) -> bool:
                on_url(url)
                return True

        original_get = webbrowser.get
        webbrowser.get = lambda *_a, **_kw: _CaptureBrowser()
        try:
            creds = flow.run_local_server(port=0, open_browser=True, authorization_prompt_message="")
        finally:
            webbrowser.get = original_get

    save_creds(creds)
    return creds
