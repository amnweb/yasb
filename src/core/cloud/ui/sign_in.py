from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.cloud.api import ApiClient, ApiError, approve_uri
from core.cloud.constants import BAD_SIGN_IN, DEVICE_CODE_TTL_S, DEVICE_POLL_INTERVAL_S, EXPIRED_CODE_APP
from core.cloud.workers import device_name
from core.utils.shell_utils import shell_open

POLL_INTERVAL_MS = DEVICE_POLL_INTERVAL_S * 1000
POLL_TIMEOUT_MS = DEVICE_CODE_TTL_S * 1000


class SignInFlow(QObject):
    """Emits exactly one of `signed_in` or `failed` per attempt."""

    code_ready = pyqtSignal(str)  # user_code, for the waiting screen
    signed_in = pyqtSignal(dict)  # the token payload
    failed = pyqtSignal(str, str)  # message, dialog title

    def __init__(self, api: ApiClient, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._device_code = ""
        self._verification_uri = ""
        self._elapsed_ms = 0

        self._poll = QTimer(self)
        self._poll.setInterval(POLL_INTERVAL_MS)
        self._poll.timeout.connect(self._tick)

    def start(self) -> None:
        call = self._api.request_device_code(device_name())
        call.succeeded.connect(self._on_code)
        call.failed.connect(self._on_code_failed)

    def _on_code_failed(self, error: ApiError) -> None:
        self.failed.emit(str(error), "Could Not Sign In")

    def cancel(self) -> None:
        self._poll.stop()
        self._device_code = ""

    def open_browser(self) -> None:
        if self._verification_uri:
            shell_open(self._verification_uri)

    def _on_code(self, payload: dict[str, Any]) -> None:
        self._device_code = str(payload.get("device_code") or "")
        if not self._device_code:
            # Without it there is nothing to poll for. Starting anyway put a blank code on
            # screen and waited forever, which is the one outcome this class promises not to
            # have: exactly one of signed_in or failed, per attempt.
            self.failed.emit(BAD_SIGN_IN, "Could Not Sign In")
            return

        # Refused rather than opened when it is not on our own site - see approve_uri. Treated
        # as a failed attempt rather than carrying on: there would be no browser to approve in
        # and no address to reach it at, so polling would only spin until the code expired -
        # the same dead wait the missing device_code above exists to prevent.
        self._verification_uri = approve_uri(payload)
        if not self._verification_uri:
            self.failed.emit(BAD_SIGN_IN, "Could Not Sign In")
            return

        self._elapsed_ms = 0
        self.code_ready.emit(payload.get("user_code", ""))
        self.open_browser()
        self._poll.start()

    def _tick(self) -> None:
        if not self._device_code:
            self._poll.stop()
            return

        self._elapsed_ms += POLL_INTERVAL_MS
        if self._elapsed_ms >= POLL_TIMEOUT_MS:
            self.cancel()
            self.failed.emit(EXPIRED_CODE_APP, "Request Expired")
            return

        call = self._api.poll_device_token(self._device_code)
        call.succeeded.connect(self._on_token)
        call.failed.connect(self._on_poll_failed)

    def _on_token(self, payload: dict[str, Any]) -> None:
        # A poll still in flight when cancel() ran lands here. The cleared code says the
        # attempt is over, so do not sign anyone in on the way out.
        if not self._device_code:
            return
        self.cancel()
        self.signed_in.emit(payload)

    def _on_poll_failed(self, error: ApiError) -> None:
        if not self._device_code:
            return
        # Still waiting, not a failure.
        if error.code in ("authorization_pending", "slow_down"):
            return
        self.cancel()
        message = {
            "access_denied": "The request was denied in the browser.",
            "expired_token": EXPIRED_CODE_APP,
        }.get(error.code, str(error))
        self.failed.emit(message, "Could Not Sign In")
