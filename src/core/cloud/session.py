"""Authentication state and its on-disk cache.

Tokens and the master key are DPAPI-protected, so only the signed-in Windows user on this
machine can read them. That stops another local account or a stolen drive, not malware already
running as the user.
"""

import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.cloud.constants import (
    CLOUD_DIR_NAME,
    DPAPI_SESSION_ENTROPY,
    DPAPI_VAULT_ENTROPY,
    SESSION_FILE,
    VAULT_FILE,
)
from core.cloud.encryption.cng import KEY_LEN
from core.cloud.encryption.dpapi import protect, unprotect
from core.cloud.errors import CloudError


@dataclass(slots=True)
class Tokens:
    access_token: str = ""
    device_token: str = ""
    email: str = ""
    user_id: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "device_token": self.device_token,
            "email": self.email,
            "user_id": self.user_id,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Tokens:
        return cls(
            access_token=str(data.get("access_token", "")),
            device_token=str(data.get("device_token", "")),
            email=str(data.get("email", "")),
            user_id=str(data.get("user_id", "")),
        )


def cloud_dir() -> Path:
    """`%LOCALAPPDATA%\\YASB\\cloud`, created on demand."""
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "YASB" / CLOUD_DIR_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


@dataclass(slots=True)
class Session:
    """In-memory auth state, optionally persisted.

    `master_key` is held only here and in vault.bin. It is never written to session.bin,
    which holds the tokens.
    """

    tokens: Tokens = field(default_factory=Tokens)
    master_key: bytes | None = None
    _directory: Path | None = None

    @property
    def directory(self) -> Path:
        if self._directory is None:
            self._directory = cloud_dir()
        return self._directory

    def apply_login(self, payload: dict[str, Any]) -> bool:
        """Take a login reply, or return False and leave the session as it was.

        The device token and master key fall back to what is held, since not every reply
        carries them.
        """
        try:
            user = payload.get("user") or {}
            tokens = Tokens(
                access_token=str(payload.get("access_token", "")),
                device_token=str(payload.get("device_token") or self.tokens.device_token),
                email=str(user.get("email", self.tokens.email)),
                user_id=str(user.get("id", self.tokens.user_id)),
            )
            master_key = self.master_key
            if raw := payload.get("master_key"):
                master_key = base64.b64decode(raw)
        except AttributeError, TypeError, ValueError:
            return False

        if not tokens.access_token:
            return False
        if master_key is None or len(master_key) != KEY_LEN:
            return False

        self.tokens = tokens
        self.master_key = master_key
        self.save()
        return True

    def sign_out(self) -> None:
        """Forget the session, in memory and on disk. Never raises.

        One caller is `_on_auth_failure`, a Qt slot, where an exception aborts the process.
        Deleting can fail because the scheduled task reads session.bin every interval and
        Windows will not delete a file another process holds open. Emptying succeeds where
        deleting does not, and `load` already signs out on a cache it cannot decrypt.
        """
        self.tokens = Tokens()
        self.master_key = None
        for name in (SESSION_FILE, VAULT_FILE):
            path = self.directory / name
            try:
                path.unlink(missing_ok=True)
            except OSError:
                try:
                    path.write_bytes(b"")
                except OSError:
                    pass

    def save(self) -> None:
        """Persist the session so the app opens signed in."""
        try:
            blob = json.dumps(self.tokens.to_json()).encode("utf-8")
            (self.directory / SESSION_FILE).write_bytes(protect(blob, DPAPI_SESSION_ENTROPY))
            if self.master_key is not None:
                (self.directory / VAULT_FILE).write_bytes(protect(self.master_key, DPAPI_VAULT_ENTROPY))
        except CloudError, OSError:
            # A cache that will not write is not a failed sign-in. It costs one next launch.
            pass

    def load(self) -> bool:
        """Restore a cached session, clearing it if any part will not come back.

        Both files or neither. Tokens without the vault would sign the user in with no way
        to decrypt anything, and that only shows up later, at a restore.
        """
        session_path = self.directory / SESSION_FILE
        vault_path = self.directory / VAULT_FILE
        if not session_path.is_file():
            return False

        try:
            self.tokens = Tokens.from_json(json.loads(unprotect(session_path.read_bytes(), DPAPI_SESSION_ENTROPY)))
            if vault_path.is_file():
                self.master_key = unprotect(vault_path.read_bytes(), DPAPI_VAULT_ENTROPY)
        except CloudError, OSError, ValueError:
            self.sign_out()
            return False

        if not self.tokens.access_token or self.master_key is None:
            self.sign_out()
            return False

        return True
