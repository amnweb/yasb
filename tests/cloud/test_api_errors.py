"""Turning a failed response into an ApiError.

    python -m pytest tests/cloud/test_api_errors.py -q

The four shapes a caller can be handed, and the one rule that matters across all of them:
whatever the server said about the failure is what the user is shown.
"""

import json
import tempfile
from pathlib import Path
from typing import cast

from PyQt6.QtNetwork import QNetworkReply, QNetworkRequest

from core.cloud.api import error_from, reply_error, save_reply


def _body(code: str, message: str) -> bytes:
    return json.dumps({"error": {"code": code, "message": message, "detail": {}}}).encode()


def test_the_servers_own_message_and_code_survive():
    error = error_from(503, _body("maintenance", "The service is temporarily down for maintenance."))

    assert str(error) == "The service is temporarily down for maintenance."
    assert error.code == "maintenance"
    assert error.status == 503


def test_a_reply_that_never_arrived_reads_as_a_connection_problem():
    error = error_from(0, b"")

    assert error.code == "network_error"
    assert "connection" in str(error)


def test_a_status_with_no_usable_body_still_names_itself():
    for body in (b"", b"<html>502 Bad Gateway</html>", b"[]", b'{"error": "not an object"}'):
        error = error_from(502, body)

        assert error.code == "server_error", f"{body!r} decoded as {error.code}"
        assert "502" in str(error)


def test_a_401_keeps_its_status_so_the_refresh_path_recognises_it():
    """is_auth_failure falls back to the status when the code is one it does not know."""
    assert error_from(401, _body("something_new", "No.")).is_auth_failure


class _Reply:
    """Only what reply_error touches. A real QNetworkReply needs a network stack."""

    def __init__(
        self, status: int, body: bytes, error: QNetworkReply.NetworkError = QNetworkReply.NetworkError.NoError
    ) -> None:
        self._status = status
        self._body = body
        self._error = error

    def error(self) -> QNetworkReply.NetworkError:
        return self._error

    def attribute(self, _which: QNetworkRequest.Attribute) -> int | None:
        # Qt returns None for a request that never got a response, which is why the caller
        # cannot simply trust this to be an int.
        return self._status or None

    def readAll(self) -> bytes:
        return self._body

    def deleteLater(self) -> None:
        pass


def test_a_raw_reply_is_read_the_same_way_as_a_tracked_call():
    """The download path streams its own reply, so it decodes through here instead of Call.
    Reporting a fixed sentence there made maintenance, a lapsed plan and a deleted backup
    indistinguishable."""
    error = reply_error(cast(QNetworkReply, _Reply(503, _body("maintenance", "Back shortly."))))

    assert str(error) == "Back shortly."
    assert error.code == "maintenance"


def test_a_raw_reply_that_never_reached_the_server_reads_as_a_connection_problem():
    assert reply_error(cast(QNetworkReply, _Reply(0, b""))).code == "network_error"


def test_a_download_that_cannot_be_written_comes_back_as_an_error():
    """save_reply runs inside a `finished` slot, where an exception aborts the process with
    nothing printed rather than propagating. A snapshot that will not write to disk, a full
    disk being the way that happens, has to arrive as an ApiError like any other failure."""
    with tempfile.TemporaryDirectory() as raw:
        target = Path(raw) / "snapshot.ysb"
        target.mkdir()

        try:
            error = save_reply(cast(QNetworkReply, _Reply(200, b"payload")), target)
        except Exception as exc:
            raise AssertionError(f"save_reply raised {type(exc).__name__} instead of returning it") from exc

        assert error is not None, "an unwritable target was reported as a successful download"
        assert error.code == "write_failed", f"reported as {error.code}"


def test_a_download_we_aborted_ourselves_is_not_reported_as_a_failure():
    """Closing the window aborts the download. Read as an error it becomes a dialog about a
    dead connection, on a window that is already going away."""
    aborted = cast(QNetworkReply, _Reply(0, b"", QNetworkReply.NetworkError.OperationCanceledError))

    assert reply_error(aborted).code == "cancelled"
