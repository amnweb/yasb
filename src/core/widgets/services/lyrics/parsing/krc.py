from __future__ import annotations

import base64
import logging
import zlib
from collections.abc import Sequence

from ..models import Line, Word
from ..normalize import normalize_lines

logger = logging.getLogger("core.widgets.services.lyrics.parsing.krc")

CIPHER = bytes(
    [
        0x40,
        0x47,
        0x61,
        0x77,
        0x5E,
        0x32,
        0x74,
        0x47,
        0x51,
        0x36,
        0x31,
        0x2D,
        0xCE,
        0xD2,
        0x6E,
        0x69,
    ]
)


def decode_krc(content_b64: str) -> str:
    """
    Decodes and decompresses a Kugou KRC base64 payload.
    Skips the 4-byte header (@Gaw), applies byte-wise XOR against CIPHER,
    and inflates using zlib.
    """
    packed = base64.b64decode(content_b64)
    if len(packed) <= 4:
        raise ValueError("KRC content too short")
    body = packed[4:]
    unmasked = bytes(b ^ CIPHER[i % 16] for i, b in enumerate(body))
    return zlib.decompress(unmasked).decode("utf-8", errors="replace")


def parse_krc(
    krc_text: str,
    title: str | None = None,
    artists: Sequence[str] | None = None,
) -> list[Line]:
    """
    Parses Kugou KRC lyrics text into normalized Line objects with Word timings.
    Line headers: [start_ms, duration_ms]
    Word stamps: <rel_start_ms, word_duration_ms, flag>spoken_text
    """
    lines: list[Line] = []

    for raw_line in krc_text.splitlines():
        line_str = raw_line.strip()
        if not line_str:
            continue

        parsed_line = read_krc_line(line_str)
        if parsed_line is not None:
            lines.append(parsed_line)

    if lines:
        lines = normalize_lines(lines, title=title or "", artists=artists or ())

    return lines


def read_krc_line(line_str: str) -> Line | None:
    """Parses a single KRC line."""
    if not line_str.startswith("["):
        return None

    close_idx = line_str.find("]")
    if close_idx == -1:
        return None

    header = line_str[1:close_idx]
    if "," not in header:
        # Metadata line like [ti:Title] or [ar:Artist]
        return None

    parts = header.split(",")
    try:
        start_ms = int(parts[0].strip())
        duration_ms = int(parts[1].strip())
    except ValueError:
        return None

    end_ms = start_ms + duration_ms
    rest = line_str[close_idx + 1 :]

    words: list[Word] = []
    text_parts: list[str] = []

    while "<" in rest:
        open_idx = rest.find("<")
        shut_idx = rest.find(">", open_idx)
        if shut_idx == -1:
            break

        if open_idx > 0:
            lead = rest[:open_idx]
            text_parts.append(lead)
            if words:
                words[-1].text += lead

        stamp_str = rest[open_idx + 1 : shut_idx]
        s_parts = stamp_str.split(",")
        at: int | None = None
        length: int | None = None
        if len(s_parts) >= 2:
            try:
                at = int(s_parts[0].strip())
                length = int(s_parts[1].strip())
            except ValueError:
                pass

        rest = rest[shut_idx + 1 :]
        next_open = rest.find("<")
        if next_open != -1:
            spoken = rest[:next_open]
            rest = rest[next_open:]
        else:
            spoken = rest
            rest = ""

        if at is not None and length is not None:
            words.append(
                Word(
                    start_ms=start_ms + at,
                    end_ms=start_ms + at + length,
                    text=spoken,
                )
            )
        text_parts.append(spoken)

    if rest:
        text_parts.append(rest)
        if words:
            words[-1].text += rest

    combined_text = "".join(text_parts).strip()
    if not combined_text:
        return None

    return Line(
        start_ms=start_ms,
        end_ms=end_ms,
        text=combined_text,
        words=words if words else None,
        voice="lead",
    )
