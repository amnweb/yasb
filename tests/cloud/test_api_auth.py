# pyright: reportPrivateUsage=false

"""What the client does when the server refuses a request.

    python -m pytest tests/cloud/test_api_auth.py -q

The desktop holds one token until it is revoked, so there is nothing to refresh and nothing
to replay. A refusal means the session was ended somewhere else - signed out on this machine,
this device revoked from the site, or every device revoked - and the only correct answer is
to drop the credentials and ask for a new sign-in.

ApiClient is built with __new__ and given only a QObject base, so no network stack is needed
and _send is replaced with a stub.
"""

import os
import tempfile
from collections.abc import Callable

import pytest
from PyQt6.QtCore import QObject

from core.cloud.api import ApiClient, ApiError
from core.cloud.constants import SESSION_FILE
from core.cloud.session import Session


class _Signal:
    def __init__(self) -> None:
        self.handler: Callable[[ApiError], None] | None = None

    def connect(self, handler: Callable[[ApiError], None]) -> None:
        self.handler = handler

    def emit(self, error: ApiError) -> None:
        assert self.handler is not None
        self.handler(error)


class _Call:
    def __init__(self) -> None:
        self.succeeded = _Signal()
        self.failed = _Signal()
        self.finished = _Signal()

    def abort(self) -> None:
        pass


def _recording_send(sent: list[_Call]) -> Callable[..., _Call]:
    def send(*_args: object, **_kwargs: object) -> _Call:
        sent.append(_Call())
        return sent[-1]

    return send


class _Session:
    def __init__(self) -> None:
        self.signed_out = 0

    def sign_out(self) -> None:
        self.signed_out += 1


def _client(monkeypatch: pytest.MonkeyPatch) -> tuple[ApiClient, _Session, list[bool]]:
    client = ApiClient.__new__(ApiClient)
    QObject.__init__(client)
    session = _Session()
    monkeypatch.setattr(client, "_session", session, raising=False)

    emitted: list[bool] = []
    client.signed_out.connect(lambda: emitted.append(True))

    monkeypatch.setattr(client, "_send", _recording_send([]))
    return client, session, emitted


def test_a_refused_request_ends_the_session(monkeypatch: pytest.MonkeyPatch):
    client, session, emitted = _client(monkeypatch)

    call = client._authenticated("GET", "/me")
    call.failed.emit(ApiError("Session has expired", code="session_expired", status=401))

    assert session.signed_out == 1
    assert emitted == [True], "the window has to be told, or it keeps showing the backup list"


def test_a_dropped_connection_does_not_end_the_session(monkeypatch: pytest.MonkeyPatch):
    """A timeout or a 500 means we could not ask, which is not the same as being told no.
    Deleting the credentials over a flaky network costs the user a browser sign-in."""
    client, session, emitted = _client(monkeypatch)

    for error in (
        ApiError("The server did not respond in time", code="timeout"),
        ApiError("Could not reach YASB Cloud", code="network_error"),
        ApiError("Unexpected server response (500)", code="server_error", status=500),
    ):
        client._authenticated("GET", "/me").failed.emit(error)

    assert session.signed_out == 0
    assert emitted == []


def test_nothing_is_retried_or_replayed(monkeypatch: pytest.MonkeyPatch):
    """There is no refresh to wait for, so one request is one attempt."""
    client, _session, _emitted = _client(monkeypatch)
    sent: list[_Call] = []
    monkeypatch.setattr(client, "_send", _recording_send(sent))

    client._authenticated("GET", "/me").failed.emit(ApiError("no", code="session_expired", status=401))

    assert len(sent) == 1


def test_signing_out_survives_the_cache_being_held_open():
    """`_on_auth_failure` calls sign_out from a Qt slot, where an exception aborts the process
    instead of surfacing. The scheduled task reads session.bin every interval and Windows will
    not delete a file another process holds open, so this has to survive it and still leave
    nothing behind that can sign the user back in."""
    previous = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as raw:
        os.environ["LOCALAPPDATA"] = raw
        try:
            session = Session()
            cached = session.directory / SESSION_FILE
            cached.write_bytes(b"cached session blob")

            holding = cached.open("rb")
            try:
                session.sign_out()
            except Exception as exc:
                raise AssertionError(f"sign_out raised {type(exc).__name__} instead of clearing what it could") from exc
            finally:
                holding.close()

            assert Session().load() is False, "a signed-out session came back on the next launch"
        finally:
            if previous is None:
                del os.environ["LOCALAPPDATA"]
            else:
                os.environ["LOCALAPPDATA"] = previous
