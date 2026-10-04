"""Command behaviour for `yasbc cloud`.

    python -m pytest tests/cloud/test_cli.py -q

Signing out is the one command here with a consequence the user cannot see. It has to end the
session on the server, not just locally: desktop sessions run 180 days with no refresh, so a
local-only sign-out leaves the token live and the machine still listed on the account for the
rest of that. It also has to clear the local files whatever the server says, or a sign-out
attempted with no connection leaves the credentials on disk.
"""

import os
import tempfile

from core.cloud import cli
from core.cloud.api import ApiError
from core.cloud.constants import SESSION_FILE, VAULT_FILE
from core.cloud.session import Session


class _Client:
    """Records the one call cmd_logout is allowed to make."""

    def __init__(self, sent: list) -> None:
        self._sent = sent

    def logout(self) -> object:
        self._sent.append("POST /auth/logout")
        return object()


def _run_logout(*, signed_in: bool, error: ApiError | None) -> tuple[int, list, list[str]]:
    previous_env = os.environ.get("LOCALAPPDATA")
    previous_client, previous_run = cli.ApiClient, cli._run_call
    sent: list = []

    with tempfile.TemporaryDirectory() as raw:
        os.environ["LOCALAPPDATA"] = raw
        try:
            session = Session()
            if signed_in:
                session.tokens.access_token = "tok"
                session.tokens.email = "someone@example.com"
                session.master_key = b"k" * 32
                session.save()

            cli.ApiClient = lambda _session: _Client(sent)
            cli._run_call = lambda _call, *_a, **_k: (None, error)

            code = cli.cmd_logout()
            left = sorted(p.name for p in session.directory.iterdir() if p.name in (SESSION_FILE, VAULT_FILE))
            return code, sent, left
        finally:
            cli.ApiClient, cli._run_call = previous_client, previous_run
            if previous_env is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous_env


def test_signing_out_revokes_the_session_on_the_server():
    code, sent, left = _run_logout(signed_in=True, error=None)

    assert sent == ["POST /auth/logout"], "the session was only cleared locally and stays live on the server"
    assert left == [], f"credentials were left on disk: {left}"
    assert code == 0


def test_credentials_are_cleared_even_when_the_server_cannot_be_reached():
    """The report is what changes, not the outcome. Leaving the files behind because the
    network was down would be the one failure a user cannot see and cannot undo."""
    code, sent, left = _run_logout(signed_in=True, error=ApiError("no route", code="network_error"))

    assert sent == ["POST /auth/logout"], "revocation was not attempted"
    assert left == [], f"a failed revocation left credentials on disk: {left}"
    assert code == 0


def test_signing_out_when_not_signed_in_asks_the_server_nothing():
    code, sent, left = _run_logout(signed_in=False, error=None)

    assert sent == [], "a bearer-less logout was sent"
    assert left == []
    assert code == 0
