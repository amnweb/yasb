"""Reads and writes the .ysb snapshot container.

The payload is AES-256-GCM in fixed-size frames (STREAM construction), so memory use stays
bounded by one frame whatever the file size. The header is cleartext and holds framing only.

File layout:

    offset  size         field
    0       8            magic  b"YASBSNAP"
    8       2            format_version (u16 LE)
    10      2            reserved (u16 LE, zero)
    12      4            header_len (u32 LE)
    16      header_len   header JSON (UTF-8, cleartext)
    ...     60           wrapped file key: nonce(12) || ciphertext(32) || tag(16)
    ...     ...          frames, repeated:
                             4  frame_ct_len (u32 LE)
                             N  frame ciphertext || tag(16)

Frame nonce is prefix(7) || frame_index(u32 BE) || last_flag(1), where last_flag is 0x01 on
the final frame only. Frame AAD is sha256(header) || frame_index(u32 BE).
"""

import hashlib
import json
import secrets
import struct
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from core.cloud.encryption.cng import KEY_LEN, NONCE_LEN, TAG_LEN, GcmKey
from core.cloud.errors import Cancelled, FormatError, IntegrityError

MAGIC = b"YASBSNAP"
FORMAT_VERSION = 1
ALGORITHM = "AES-256-GCM/STREAM"

FRAME_SIZE = 1024 * 1024
"""Plaintext bytes per frame."""

NONCE_PREFIX_LEN = 7
"""`prefix(7) || index(4) || last_flag(1)` == 12-byte GCM nonce."""

_PREAMBLE = struct.Struct("<8sHHI")
_FRAME_LEN = struct.Struct("<I")
_INDEX = struct.Struct(">I")

WRAPPED_KEY_LEN = NONCE_LEN + KEY_LEN + TAG_LEN

MAX_HEADER_BYTES = 64 * 1024
"""A sane header is a few hundred bytes. Cap it so a malformed file cannot force a huge read."""

MAX_FRAMES = 1 << 24
"""16M frames at 1 MiB each is 16 TiB - far beyond any plan, but bounded."""


@dataclass(frozen=True, slots=True)
class SnapshotInfo:
    """Result of encrypting a snapshot."""

    ciphertext_size: int
    plaintext_size: int
    frames: int
    sha256: str
    """Hex digest over the whole `.ysb` file. The server recomputes it and rejects a mismatch."""


def _frame_nonce(prefix: bytes, index: int, is_last: bool) -> bytes:
    return prefix + _INDEX.pack(index) + (b"\x01" if is_last else b"\x00")


def _frame_count(plaintext_size: int, frame_size: int) -> int:
    # An empty payload still gets one (empty) final frame, so the last-flag always exists.
    if plaintext_size == 0:
        return 1
    return (plaintext_size + frame_size - 1) // frame_size


def _build_header(nonce_prefix: bytes, plaintext_size: int, frames: int, frame_size: int) -> bytes:
    header = {
        "v": FORMAT_VERSION,
        "alg": ALGORITHM,
        "frame_size": frame_size,
        "nonce_prefix": nonce_prefix.hex(),
        "plaintext_size": plaintext_size,
        "frames": frames,
    }
    return json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")


def encrypt_snapshot(
    source: Path,
    destination: Path,
    master_key: bytes,
    *,
    frame_size: int = FRAME_SIZE,
    should_stop: Callable[[], bool] | None = None,
) -> SnapshotInfo:
    """Encrypt `source` into a `.ysb` file at `destination`.

    A fresh file key per snapshot, wrapped with `master_key`. Two files that happen to draw
    the same nonce prefix are still under different keys, so no (key, nonce) pair repeats.

    Memory use is bounded by `frame_size` regardless of input size.
    """
    if frame_size <= 0:
        raise FormatError(f"frame_size must be positive, got {frame_size}")

    plaintext_size = source.stat().st_size
    frames = _frame_count(plaintext_size, frame_size)
    if frames > MAX_FRAMES:
        raise FormatError(f"Snapshot needs {frames} frames, over the {MAX_FRAMES} limit")

    nonce_prefix = secrets.token_bytes(NONCE_PREFIX_LEN)
    header = _build_header(nonce_prefix, plaintext_size, frames, frame_size)
    header_hash = hashlib.sha256(header).digest()

    file_key = secrets.token_bytes(KEY_LEN)
    key_nonce = secrets.token_bytes(NONCE_LEN)

    # Header hash as AAD here and on every frame, so the key will not unwrap against
    # framing that has been edited.
    with GcmKey(master_key) as wrapper:
        wrapped, wrap_tag = wrapper.encrypt(key_nonce, file_key, header_hash)

    digest = hashlib.sha256()
    written = 0

    def emit(handle: BinaryIO, chunk: bytes) -> None:
        nonlocal written
        handle.write(chunk)
        digest.update(chunk)
        written += len(chunk)

    with GcmKey(file_key) as key, source.open("rb") as src, destination.open("wb") as dst:
        emit(dst, _PREAMBLE.pack(MAGIC, FORMAT_VERSION, 0, len(header)))
        emit(dst, header)
        emit(dst, key_nonce + wrapped + wrap_tag)

        for index in range(frames):
            if should_stop is not None and should_stop():
                raise Cancelled("Encryption was cancelled")
            block = src.read(frame_size)
            is_last = index == frames - 1
            nonce = _frame_nonce(nonce_prefix, index, is_last)
            aad = header_hash + _INDEX.pack(index)
            ciphertext, tag = key.encrypt(nonce, block, aad)

            emit(dst, _FRAME_LEN.pack(len(ciphertext) + TAG_LEN))
            emit(dst, ciphertext)
            emit(dst, tag)

        if src.read(1):
            raise FormatError("Source file grew while it was being encrypted")

    return SnapshotInfo(
        ciphertext_size=written,
        plaintext_size=plaintext_size,
        frames=frames,
        sha256=digest.hexdigest(),
    )


def _read_exactly(handle: BinaryIO, count: int, what: str) -> bytes:
    data = handle.read(count)
    if len(data) != count:
        raise IntegrityError(f"Snapshot is truncated: expected {count} bytes of {what}, got {len(data)}")
    return data


def _parse_header(handle: BinaryIO) -> tuple[dict[str, object], bytes]:
    """Read and validate the preamble and header, returning it and its SHA-256 (the AAD)."""
    preamble = handle.read(_PREAMBLE.size)
    if len(preamble) != _PREAMBLE.size:
        raise FormatError("Not a YASB snapshot: file is too short")

    magic, version, _reserved, header_len = _PREAMBLE.unpack(preamble)
    if magic != MAGIC:
        raise FormatError("Not a YASB snapshot: bad magic")
    if version != FORMAT_VERSION:
        raise FormatError(f"Unsupported snapshot format version {version}; this build understands {FORMAT_VERSION}")
    if not 0 < header_len <= MAX_HEADER_BYTES:
        raise FormatError(f"Snapshot header length {header_len} is out of range")

    raw = _read_exactly(handle, header_len, "header")
    try:
        header = json.loads(raw)
    except ValueError as exc:
        raise FormatError(f"Snapshot header is not valid JSON: {exc}") from exc
    if not isinstance(header, dict):
        raise FormatError("Snapshot header must be a JSON object")

    return header, hashlib.sha256(raw).digest()


def _require_int(header: dict[str, object], field: str, low: int, high: int) -> int:
    value = header.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise FormatError(f"Snapshot header field {field!r} must be an integer")
    if not low <= value <= high:
        raise FormatError(f"Snapshot header field {field!r} is {value}, outside {low}..{high}")
    return value


def read_snapshot_header(path: Path) -> dict[str, object]:
    """Read the cleartext header without decrypting.

    Only the test suite calls this, deliberately: it is how the container format is
    asserted to expose nothing but framing.
    """
    with path.open("rb") as handle:
        header, _ = _parse_header(handle)
    return header


def decrypt_snapshot(
    source: Path,
    destination: Path,
    master_key: bytes,
    *,
    should_stop: Callable[[], bool] | None = None,
) -> int:
    """Decrypt a .ysb file to `destination`.

    Output is staged and moved into place only once every frame verifies, so a failed
    restore leaves no partial file behind.
    """
    staging = destination.with_name(destination.name + ".partial")

    try:
        with source.open("rb") as src:
            header, header_hash = _parse_header(src)

            if header.get("alg") != ALGORITHM:
                raise FormatError(f"Unsupported snapshot algorithm {header.get('alg')!r}")

            frame_size = _require_int(header, "frame_size", 1, 64 * 1024 * 1024)
            frames = _require_int(header, "frames", 1, MAX_FRAMES)
            plaintext_size = _require_int(header, "plaintext_size", 0, frames * frame_size)

            prefix_hex = header.get("nonce_prefix")
            if not isinstance(prefix_hex, str):
                raise FormatError("Snapshot header field 'nonce_prefix' must be a string")
            try:
                nonce_prefix = bytes.fromhex(prefix_hex)
            except ValueError as exc:
                raise FormatError(f"Snapshot header field 'nonce_prefix' is not valid hex: {exc}") from exc
            if len(nonce_prefix) != NONCE_PREFIX_LEN:
                raise FormatError(f"Nonce prefix must be {NONCE_PREFIX_LEN} bytes, got {len(nonce_prefix)}")

            # A header that disagrees with itself is rejected before any frame is read.
            if frames != _frame_count(plaintext_size, frame_size):
                raise FormatError("Snapshot header frame count does not match its declared plaintext size")

            blob = _read_exactly(src, WRAPPED_KEY_LEN, "wrapped file key")
            with GcmKey(master_key) as wrapper:
                file_key = wrapper.decrypt(
                    blob[:NONCE_LEN],
                    blob[NONCE_LEN:-TAG_LEN],
                    blob[-TAG_LEN:],
                    header_hash,
                )

            recovered = 0
            with GcmKey(file_key) as key, staging.open("wb") as dst:
                for index in range(frames):
                    if should_stop is not None and should_stop():
                        raise Cancelled("Decryption was cancelled")
                    raw_len = _read_exactly(src, _FRAME_LEN.size, "frame length")
                    (frame_len,) = _FRAME_LEN.unpack(raw_len)

                    if not TAG_LEN <= frame_len <= frame_size + TAG_LEN:
                        raise FormatError(f"Frame {index} declares an implausible length of {frame_len} bytes")

                    body = _read_exactly(src, frame_len, f"frame {index}")
                    is_last = index == frames - 1
                    nonce = _frame_nonce(nonce_prefix, index, is_last)
                    aad = header_hash + _INDEX.pack(index)

                    block = key.decrypt(nonce, body[:-TAG_LEN], body[-TAG_LEN:], aad)
                    dst.write(block)
                    recovered += len(block)

            if src.read(1):
                raise IntegrityError("Snapshot has trailing data after the final frame")
            if recovered != plaintext_size:
                raise IntegrityError(f"Snapshot decrypted to {recovered} bytes, header declared {plaintext_size}")

        staging.replace(destination)
        return recovered
    except BaseException:
        # Not just Exception: a Ctrl-C must take the half-written file with it too.
        staging.unlink(missing_ok=True)
        raise
