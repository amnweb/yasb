"""Tests for core.cloud.encryption.

Written as plain asserts so they run with no test-runner dependency:

    python -m pytest tests/cloud/test_encryption.py -q


Two independent kinds of check:

* **Known-answer tests** validate the AES-GCM implementation against published vectors,
  so a bug in the ctypes layer cannot hide behind a self-consistent round trip.
* **Round-trip and tamper tests** validate the container format.
"""

import os
import secrets
import tempfile
from pathlib import Path

from core.cloud.encryption.cng import GcmKey
from core.cloud.encryption.dpapi import protect, unprotect
from core.cloud.encryption.stream import (
    TAG_LEN,
    SnapshotInfo,
    decrypt_snapshot,
    encrypt_snapshot,
    read_snapshot_header,
)
from core.cloud.errors import CryptoError, FormatError, IntegrityError


def new_key() -> bytes:
    """A fresh AES-256 key, the same way production code makes one."""
    return secrets.token_bytes(32)


# --- Known-answer tests ------------------------------------------------------------------
# From "The Galois/Counter Mode of Operation (GCM)", McGrew & Viega - the AES-256 cases,
# which are also the NIST CAVP gcmEncryptExtIV256 vectors.

GCM_VECTORS = [
    {
        "name": "TC13 empty plaintext",
        "key": "00" * 32,
        "nonce": "00" * 12,
        "aad": "",
        "plaintext": "",
        "ciphertext": "",
        "tag": "530f8afbc74536b9a963b4f1c4cb738b",
    },
    {
        "name": "TC14 single zero block",
        "key": "00" * 32,
        "nonce": "00" * 12,
        "aad": "",
        "plaintext": "00" * 16,
        "ciphertext": "cea7403d4d606b6e074ec5d3baf39d18",
        "tag": "d0d1c8a799996bf0265b98b5d48ab919",
    },
    {
        "name": "TC15 four blocks, no aad",
        "key": "feffe9928665731c6d6a8f9467308308feffe9928665731c6d6a8f9467308308",
        "nonce": "cafebabefacedbaddecaf888",
        "aad": "",
        "plaintext": (
            "d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a72"
            "1c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b391aafd255"
        ),
        "ciphertext": (
            "522dc1f099567d07f47f37a32a84427d643a8cdcbfe5c0c97598a2bd2555d1aa"
            "8cb08e48590dbb3da7b08b1056828838c5f61e6393ba7a0abcc9f662898015ad"
        ),
        "tag": "b094dac5d93471bdec1a502270e3cc6c",
    },
    {
        "name": "TC16 with aad",
        "key": "feffe9928665731c6d6a8f9467308308feffe9928665731c6d6a8f9467308308",
        "nonce": "cafebabefacedbaddecaf888",
        "aad": "feedfacedeadbeeffeedfacedeadbeefabaddad2",
        "plaintext": (
            "d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a72"
            "1c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b39"
        ),
        "ciphertext": (
            "522dc1f099567d07f47f37a32a84427d643a8cdcbfe5c0c97598a2bd2555d1aa"
            "8cb08e48590dbb3da7b08b1056828838c5f61e6393ba7a0abcc9f662"
        ),
        "tag": "76fc6ece0f4e1768cddf8853bb2d551b",
    },
]


def test_gcm_known_answers():
    for vector in GCM_VECTORS:
        key = bytes.fromhex(vector["key"])
        nonce = bytes.fromhex(vector["nonce"])
        aad = bytes.fromhex(vector["aad"])
        plaintext = bytes.fromhex(vector["plaintext"])

        with GcmKey(key) as handle:
            ciphertext, tag = handle.encrypt(nonce, plaintext, aad)
            assert ciphertext.hex() == vector["ciphertext"], f"{vector['name']}: ciphertext mismatch"
            assert tag.hex() == vector["tag"], f"{vector['name']}: tag mismatch"

            recovered = handle.decrypt(nonce, ciphertext, tag, aad)
            assert recovered == plaintext, f"{vector['name']}: decrypt mismatch"


def test_gcm_rejects_wrong_key_nonce_aad_and_tag():
    key, nonce, aad = new_key(), secrets.token_bytes(12), b"context"
    with GcmKey(key) as handle:
        ciphertext, tag = handle.encrypt(nonce, b"payload", aad)

    for name, key_used, args in [
        ("wrong key", new_key(), (nonce, ciphertext, tag, aad)),
        ("wrong nonce", key, (secrets.token_bytes(12), ciphertext, tag, aad)),
        ("wrong aad", key, (nonce, ciphertext, tag, b"other")),
        ("flipped tag", key, (nonce, ciphertext, bytes([tag[0] ^ 1]) + tag[1:], aad)),
        ("flipped ciphertext", key, (nonce, bytes([ciphertext[0] ^ 1]) + ciphertext[1:], tag, aad)),
    ]:
        try:
            with GcmKey(key_used) as handle:
                handle.decrypt(*args)
        except IntegrityError:
            continue
        raise AssertionError(f"{name} was accepted")


def test_gcm_rejects_bad_sizes():
    for name, call in {
        "short key": lambda: GcmKey(secrets.token_bytes(16)),
        "short nonce": lambda: GcmKey(new_key()).encrypt(secrets.token_bytes(8), b"x"),
    }.items():
        try:
            call()
        except CryptoError:
            continue
        raise AssertionError(f"{name} was accepted")


def test_gcm_key_is_reusable():
    key = new_key()
    with GcmKey(key) as handle:
        for index in range(64):
            nonce = index.to_bytes(12, "big")
            payload = f"frame {index}".encode()
            ciphertext, tag = handle.encrypt(nonce, payload)
            assert handle.decrypt(nonce, ciphertext, tag) == payload


# --- Snapshot container ------------------------------------------------------------------


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def _round_trip(tmp: Path, payload: bytes, *, frame_size: int = 4096) -> SnapshotInfo:
    key = new_key()
    source = _write(tmp / "plain.bin", payload)
    blob = tmp / "snap.ysb"
    restored = tmp / "restored.bin"

    info = encrypt_snapshot(source, blob, key, frame_size=frame_size)
    assert info.plaintext_size == len(payload)
    assert info.ciphertext_size == blob.stat().st_size

    written = decrypt_snapshot(blob, restored, key)
    assert written == len(payload)
    assert restored.read_bytes() == payload
    return info


def test_snapshot_round_trip_across_boundary_sizes():
    frame = 4096
    sizes = [0, 1, frame - 1, frame, frame + 1, frame * 3, frame * 3 + 17]
    with tempfile.TemporaryDirectory() as raw:
        for size in sizes:
            tmp = Path(raw) / f"case{size}"
            tmp.mkdir()
            _round_trip(tmp, os.urandom(size), frame_size=frame)


def test_snapshot_is_larger_than_plaintext_but_not_absurdly():
    with tempfile.TemporaryDirectory() as raw:
        info = _round_trip(Path(raw), os.urandom(4096 * 4), frame_size=4096)
        assert info.frames == 4
        assert info.ciphertext_size > info.plaintext_size
        assert info.ciphertext_size < info.plaintext_size + 4096


def test_snapshot_header_is_readable_and_leaks_nothing():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        key = new_key()
        source = _write(tmp / "plain.bin", b"secret configuration contents")
        blob = tmp / "snap.ysb"
        encrypt_snapshot(source, blob, key, frame_size=4096)

        header = read_snapshot_header(blob)
        assert header["v"] == 1
        assert header["alg"] == "AES-256-GCM/STREAM"
        assert set(header) == {"v", "alg", "frame_size", "nonce_prefix", "plaintext_size", "frames"}

        # No plaintext should survive anywhere in the container.
        assert b"secret configuration" not in blob.read_bytes()


def test_snapshot_rejects_wrong_master_key():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        source = _write(tmp / "plain.bin", os.urandom(9000))
        blob = tmp / "snap.ysb"
        encrypt_snapshot(source, blob, new_key(), frame_size=4096)
        try:
            decrypt_snapshot(blob, tmp / "out.bin", new_key())
            raise AssertionError("wrong master key was accepted")
        except IntegrityError:
            pass


def test_snapshot_detects_a_flip_at_every_region():
    """A single flipped bit anywhere must be caught, wherever it lands."""
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        key = new_key()
        source = _write(tmp / "plain.bin", os.urandom(4096 * 3))
        blob = tmp / "snap.ysb"
        encrypt_snapshot(source, blob, key, frame_size=4096)
        original = blob.read_bytes()

        # Sample across the whole file: header, wrapped key, and every frame.
        offsets = [16, 40, 90, 130, 200, len(original) // 2, len(original) - 1]
        for offset in offsets:
            corrupted = bytearray(original)
            corrupted[offset] ^= 0x01
            target = tmp / "bad.ysb"
            target.write_bytes(bytes(corrupted))
            try:
                decrypt_snapshot(target, tmp / "out.bin", key)
            except IntegrityError, FormatError:
                continue
            raise AssertionError(f"a flipped bit at offset {offset} was accepted")


def test_snapshot_detects_truncation():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        key = new_key()
        source = _write(tmp / "plain.bin", os.urandom(4096 * 4))
        blob = tmp / "snap.ysb"
        encrypt_snapshot(source, blob, key, frame_size=4096)
        original = blob.read_bytes()

        for keep in (len(original) - 1, len(original) - TAG_LEN, len(original) // 2, 200):
            target = tmp / "cut.ysb"
            target.write_bytes(original[:keep])
            try:
                decrypt_snapshot(target, tmp / "out.bin", key)
            except IntegrityError, FormatError:
                continue
            raise AssertionError(f"truncation to {keep} bytes was accepted")


def test_snapshot_detects_appended_data():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        key = new_key()
        source = _write(tmp / "plain.bin", os.urandom(5000))
        blob = tmp / "snap.ysb"
        encrypt_snapshot(source, blob, key, frame_size=4096)

        target = tmp / "extra.ysb"
        target.write_bytes(blob.read_bytes() + b"trailing")
        try:
            decrypt_snapshot(target, tmp / "out.bin", key)
            raise AssertionError("trailing data was accepted")
        except IntegrityError, FormatError:
            pass


def test_snapshot_rejects_foreign_and_malformed_files():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        key = new_key()
        for name, content in {
            "empty": b"",
            "short": b"YASB",
            "bad magic": b"NOTASNAP" + bytes(64),
            "zip": b"PK\x03\x04" + bytes(64),
        }.items():
            target = _write(tmp / "foreign.ysb", content)
            try:
                decrypt_snapshot(target, tmp / "out.bin", key)
            except FormatError, IntegrityError:
                continue
            raise AssertionError(f"{name} was accepted as a snapshot")


def test_failed_decrypt_leaves_no_output_file():
    """A failed restore must not leave a partial file that could overwrite a good config."""
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        key = new_key()
        source = _write(tmp / "plain.bin", os.urandom(4096 * 4))
        blob = tmp / "snap.ysb"
        encrypt_snapshot(source, blob, key, frame_size=4096)

        corrupted = bytearray(blob.read_bytes())
        corrupted[-40] ^= 0x01  # inside the final frame
        target = _write(tmp / "bad.ysb", bytes(corrupted))

        destination = tmp / "out.bin"
        try:
            decrypt_snapshot(target, destination, key)
            raise AssertionError("corrupted snapshot was accepted")
        except IntegrityError:
            pass

        assert not destination.exists(), "a partial output file was left behind"
        assert not destination.with_name(destination.name + ".partial").exists()


def test_large_snapshot_streams_without_loading_it_all():
    """Exercise the real 1 MiB frame size on a payload several frames long."""
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        key = new_key()
        payload = os.urandom(5 * 1024 * 1024 + 12345)
        source = _write(tmp / "big.bin", payload)
        blob = tmp / "big.ysb"

        info = encrypt_snapshot(source, blob, key)
        assert info.frames == 6

        restored = tmp / "big.out"
        assert decrypt_snapshot(blob, restored, key) == len(payload)
        assert restored.read_bytes() == payload


# --- Randomness --------------------------------------------------------------------------


def test_keys_are_unique_and_correctly_sized():
    """Mirrors the server-side requirement that no two accounts share a master key."""
    keys = {new_key() for _ in range(2000)}
    assert len(keys) == 2000, "secrets.token_bytes(32) produced a duplicate"
    assert all(len(key) == 32 for key in keys)


# --- DPAPI -------------------------------------------------------------------------------


def test_dpapi_round_trip_and_domain_separation():
    entropy = b"yasb.cloud.vault.v1"
    secret = new_key()

    sealed = protect(secret, entropy)
    assert sealed != secret
    assert secret not in sealed
    assert unprotect(sealed, entropy) == secret

    try:
        unprotect(sealed, b"yasb.cloud.session.v1")
        raise AssertionError("a blob was unsealed with the wrong entropy")
    except CryptoError:
        pass
