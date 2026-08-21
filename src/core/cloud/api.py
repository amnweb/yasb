"""HTTP client built on QNetworkAccessManager.

Calls return a Call with `succeeded` and `failed` signals and an `abort()`. `download` is the
exception: it hands back the raw reply so the caller can write it straight to disk. The window
aborts everything outstanding in closeEvent.
"""

import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import quote

from PyQt6.QtCore import QByteArray, QFile, QIODevice, QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkProxyFactory,
    QNetworkReply,
    QNetworkRequest,
)

from core.cloud.constants import API_BASE_URL, API_PREFIX, BASE_URL, CONTROL_TIMEOUT_MS
from core.cloud.session import Session
from settings import BUILD_VERSION

logger = logging.getLogger(__name__)

QNetworkProxyFactory.setUseSystemConfiguration(True)


class ApiError(Exception):
    """A failed call. `code` is the server's stable identifier, or a local one."""

    def __init__(self, message: str, *, code: str = "network_error", status: int = 0):
        super().__init__(message)
        self.code = code
        self.status = status

    @property
    def is_auth_failure(self) -> bool:
        return self.code in ("unauthenticated", "invalid_credentials", "session_expired") or self.status == 401


def _decode(body: bytes) -> Any:
    if not body:
        return None
    try:
        return json.loads(body)
    except ValueError:
        return None


def approve_uri(payload: dict) -> str:
    """The device-flow approval page from a /device/code reply, or "" if it is not ours.

    Checked because this is opened with ShellExecuteW, which runs a local path, a UNC path or
    any protocol handler as readily as an https URL. The prefix only, so the server can still
    move the path or change the query without a client release.
    """
    value = str(payload.get("verification_uri_complete") or payload.get("verification_uri") or "")
    return value if value.startswith(f"{BASE_URL}/") else ""


def error_from(status: int, body: bytes) -> ApiError:
    """Read a failed response, preferring whatever the server said about it."""
    payload = _decode(body)
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        problem = payload["error"]
        return ApiError(
            str(problem.get("message", "Something went wrong")),
            code=str(problem.get("code", "server_error")),
            status=status,
        )
    if status == 0:
        return ApiError("Could not reach YASB Cloud. Check your connection.", code="network_error")
    return ApiError(f"Unexpected server response ({status})", code="server_error", status=status)


def reply_error(reply: QNetworkReply) -> ApiError:
    """The same, for the download path, which streams a raw reply rather than using Call."""
    if reply.error() == QNetworkReply.NetworkError.OperationCanceledError:
        # We aborted it, so there is nothing to report.
        return ApiError("", code="cancelled")
    status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) or 0
    return error_from(status, bytes(reply.readAll()))


def save_reply(reply: QNetworkReply, path: Path) -> ApiError | None:
    """Write a finished download to `path`, returning the failure or None. Consumes the reply.

    A failed write is a return value, never an exception: this runs in a `finished` slot,
    where an exception aborts the process with nothing printed.
    """
    try:
        if reply.error() != QNetworkReply.NetworkError.NoError:
            return reply_error(reply)
        try:
            path.write_bytes(bytes(reply.readAll()))
        except OSError as exc:
            return ApiError(f"Could not save the download: {exc.strerror or exc}", code="write_failed")
        return None
    finally:
        reply.deleteLater()


class Call(QObject):
    """One in-flight request."""

    succeeded = pyqtSignal(object)
    failed = pyqtSignal(object)
    finished = pyqtSignal()

    def __init__(self, reply: QNetworkReply, parent: QObject | None = None, device: QIODevice | None = None) -> None:
        super().__init__(parent)
        self._reply = reply
        self._device = device
        self._done = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._timer.start(CONTROL_TIMEOUT_MS)
        # Restarted whenever bytes move: the limit is silence, not duration.
        reply.uploadProgress.connect(self._on_activity)
        reply.downloadProgress.connect(self._on_activity)
        reply.finished.connect(self._on_finished)

    def _on_activity(self, _done: int, _total: int) -> None:
        if not self._done:
            self._timer.start(CONTROL_TIMEOUT_MS)

    def abort(self) -> None:
        if not self._done and self._reply is not None:
            self._done = True
            self._timer.stop()
            self._reply.abort()

    def _on_timeout(self) -> None:
        if self._done:
            return
        self._done = True
        # Before the abort, which re-enters _on_finished and emits finished from there.
        logger.warning("api timeout: %s", self._reply.request().url().path())
        self.failed.emit(ApiError("The server did not respond in time", code="timeout"))
        self._reply.abort()

    def _on_finished(self) -> None:
        if self._done:
            self._cleanup()
            return
        self._done = True
        self._timer.stop()

        reply, self._reply = self._reply, None
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) or 0
        body = bytes(reply.readAll())
        error = reply.error()
        # Not on the abort path: Qt reads the device again while the event loop unwinds it.
        if self._device is not None:
            self._device.close()
            self._device = None
        reply.deleteLater()

        if error == QNetworkReply.NetworkError.OperationCanceledError:
            self.finished.emit()
            return

        if 200 <= status < 300:
            payload = _decode(body)
            # Not a JSON object becomes an empty one: consumers use .get(), and an
            # AttributeError inside a Qt slot takes the process down instead of surfacing.
            self.succeeded.emit(payload if isinstance(payload, dict) else {})
        else:
            failure = error_from(status, body)
            logger.warning("api %s -> %s %s", reply.request().url().path(), status, failure.code)
            self.failed.emit(failure)
        self.finished.emit()

    def _cleanup(self) -> None:
        if self._reply is not None:
            self._reply.deleteLater()
            self._reply = None
        self.finished.emit()


class ApiClient(QObject):
    """Typed-ish wrapper around the REST API."""

    signed_out = pyqtSignal()

    def __init__(self, session: Session, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self._net = QNetworkAccessManager(self)
        self._calls: list[Call] = []
        self._downloads: list[QNetworkReply] = []

    def _request(self, path: str, *, authenticated: bool = True) -> QNetworkRequest:
        request = QNetworkRequest(QUrl(f"{API_BASE_URL}{API_PREFIX}{path}"))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setRawHeader(b"User-Agent", f"YASB-Cloud/{BUILD_VERSION}".encode())
        # The bearer token is on this request, so never follow a redirect down to http.
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute, QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy
        )
        if authenticated and self._session.tokens.access_token:
            request.setRawHeader(b"Authorization", f"Bearer {self._session.tokens.access_token}".encode())
        return request

    def _track(self, call: Call) -> Call:
        self._calls.append(call)
        call.finished.connect(lambda: self._calls.remove(call) if call in self._calls else None)
        return call

    def _send(self, verb: str, path: str, body: dict | None = None, *, authenticated: bool = True) -> Call:
        logger.debug("api %s %s", verb, path)
        request = self._request(path, authenticated=authenticated)
        payload = QByteArray(json.dumps(body or {}).encode("utf-8"))

        if verb == "GET":
            reply = self._net.get(request)
        elif verb == "POST":
            reply = self._net.post(request, payload)
        elif verb == "PATCH":
            reply = self._net.sendCustomRequest(request, b"PATCH", payload)
        elif verb == "DELETE":
            reply = self._net.sendCustomRequest(request, b"DELETE")
        else:
            raise ValueError(f"Unsupported verb {verb}")
        return self._track(Call(reply, self))

    def _authenticated(self, verb: str, path: str, body: dict | None = None) -> Call:
        """`_send`, plus: a 401 from this route ends the session.

        The device-flow calls and logout use `_send` instead, on purpose.
        """
        call = self._send(verb, path, body)
        call.failed.connect(self._on_auth_failure)
        return call

    def _on_auth_failure(self, error: ApiError) -> None:
        if error.is_auth_failure:
            logger.warning("signed out by the server: %s", error.code)
            self._session.sign_out()
            self.signed_out.emit()

    def abort_all(self) -> None:
        for call in list(self._calls):
            call.abort()
        self._calls.clear()
        for reply in list(self._downloads):
            reply.abort()
        self._downloads.clear()

    def request_device_code(self, device_label: str) -> Call:
        return self._send("POST", "/device/code", {"device_label": device_label}, authenticated=False)

    def poll_device_token(self, device_code: str) -> Call:
        return self._send("POST", "/device/token", {"device_code": device_code}, authenticated=False)

    def logout(self) -> Call:
        """Not `_authenticated`: an already-dead token answers 401 here, and the caller is
        signing out regardless."""
        return self._send("POST", "/auth/logout", {})

    def me(self) -> Call:
        return self._authenticated("GET", "/me")

    def list_backups(self, offset: int = 0, search: str = "") -> Call:
        """One page. The server fixes the page size and reports the total."""
        query = f"?offset={max(0, int(offset))}"
        if search:
            query += f"&search={quote(search)}"
        return self._authenticated("GET", f"/backups{query}")

    def begin_backup(
        self,
        *,
        size_bytes: int,
        sha256: str,
        file_count: int,
        note: str,
        device_name: str,
        app_version: str,
    ) -> Call:
        return self._authenticated(
            "POST",
            "/backups",
            {
                "size_bytes": size_bytes,
                "sha256": sha256,
                "file_count": file_count,
                "note": note,
                "device_name": device_name,
                "app_version": app_version,
            },
        )

    def get_backup(self, backup_id: str) -> Call:
        """One snapshot, in the same shape the list returns it."""
        return self._authenticated("GET", f"/backups/{backup_id}")

    def update_note(self, backup_id: str, note: str) -> Call:
        return self._authenticated("PATCH", f"/backups/{backup_id}", {"note": note})

    def delete_backup(self, backup_id: str) -> Call:
        return self._authenticated("DELETE", f"/backups/{backup_id}")

    def share_backup(self, backup_id: str) -> Call:
        """Publish a backup. The reply carries the page URL, which the server builds."""
        return self._authenticated("POST", f"/backups/{backup_id}/share", {})

    def unshare_backup(self, backup_id: str) -> Call:
        return self._authenticated("DELETE", f"/backups/{backup_id}/share")

    def upload(self, backup_id: str, blob: Path) -> Call:
        """Send the whole snapshot. Qt reads from the file, so it is never held in memory."""
        request = self._request(f"/backups/{backup_id}/content")
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/octet-stream")
        request.setHeader(QNetworkRequest.KnownHeaders.ContentLengthHeader, blob.stat().st_size)

        handle = QFile(str(blob))
        if not handle.open(QIODevice.OpenModeFlag.ReadOnly):
            raise OSError(handle.errorString())
        reply = self._net.sendCustomRequest(request, b"PUT", handle)
        handle.setParent(reply)
        return self._track(Call(reply, self, device=handle))

    def download(self, backup_id: str) -> QNetworkReply:
        """The raw reply, so the caller can write it straight to disk.

        Given the same silence limit Call uses, and registered so abort_all reaches it.
        """
        request = self._request(f"/backups/{backup_id}/content")
        reply = self._net.get(request)

        timer = QTimer(reply)
        timer.setSingleShot(True)
        timer.timeout.connect(reply.abort)
        timer.start(CONTROL_TIMEOUT_MS)
        reply.downloadProgress.connect(lambda *_: timer.start(CONTROL_TIMEOUT_MS))
        reply.finished.connect(timer.stop)

        self._downloads.append(reply)
        reply.finished.connect(lambda: self._downloads.remove(reply) if reply in self._downloads else None)
        return reply
