from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from typing import Any, cast

from ..models import Line, Word
from ..normalize import normalize_lines

logger = logging.getLogger("core.widgets.services.lyrics.parsing.yrc")


def parse_yrc(
    yrc_text: str,
    title: str | None = None,
    artists: Sequence[str] | None = None,
) -> tuple[list[Line], list[str]]:
    """
    Parses NetEase YRC word-timed lyric text into normalized Line objects and extracted writers.
    Line headers: [start_ms, duration_ms]
    Word stamps: (start_ms, duration_ms, flag)text
    Credit lines: JSON lines starting with '{' containing '作词' or '作曲'.
    """
    lines: list[Line] = []
    writers: list[str] = []

    for raw_line in yrc_text.splitlines():
        line_str = raw_line.strip()
        if not line_str:
            continue

        # Extract credit/writer JSON lines
        if line_str.startswith("{"):
            w = _extract_writers_from_json(line_str)
            for name in w:
                if name not in writers:
                    writers.append(name)
            continue

        parsed_line = read_yrc_line(line_str)
        if parsed_line is not None:
            lines.append(parsed_line)

    if lines:
        lines = normalize_lines(lines, title=title or "", artists=artists or ())

    return lines, writers


def read_yrc_line(line_str: str) -> Line | None:
    """Parses a single YRC line."""
    if not line_str.startswith("["):
        return None

    close_idx = line_str.find("]")
    if close_idx == -1:
        return None

    header = line_str[1:close_idx]
    rest = line_str[close_idx + 1 :]

    header_parts = header.split(",")
    if len(header_parts) < 2:
        return None

    try:
        start_ms = int(header_parts[0].strip())
        duration_ms = int(header_parts[1].strip())
    except ValueError:
        return None

    end_ms = start_ms + duration_ms

    words: list[Word] = []
    full_text_parts: list[str] = []

    pos = 0
    while pos < len(rest):
        open_idx = rest.find("(", pos)
        if open_idx == -1:
            # Trailing text
            tail = rest[pos:]
            if tail:
                full_text_parts.append(tail)
                if words:
                    words[-1].text += tail
            break

        # Leading text before '('
        if open_idx > pos:
            lead = rest[pos:open_idx]
            full_text_parts.append(lead)
            if words:
                words[-1].text += lead

        close_p = rest.find(")", open_idx)
        if close_p == -1:
            # Malformed tag, treat rest as text
            tail = rest[pos:]
            full_text_parts.append(tail)
            break

        stamp_str = rest[open_idx + 1 : close_p]
        parts = stamp_str.split(",")
        if len(parts) >= 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
            w_start = int(parts[0].strip())
            w_dur = int(parts[1].strip())
            w_end = w_start + w_dur

            # The spoken word extends until the next '('
            next_open = rest.find("(", close_p + 1)
            if next_open != -1:
                spoken = rest[close_p + 1 : next_open]
                pos = next_open
            else:
                spoken = rest[close_p + 1 :]
                pos = len(rest)

            words.append(Word(start_ms=w_start, end_ms=w_end, text=spoken))
            full_text_parts.append(spoken)
        else:
            # Not a valid stamp, treat as literal text
            literal = rest[open_idx : close_p + 1]
            full_text_parts.append(literal)
            pos = close_p + 1

    combined_text = "".join(full_text_parts).strip()
    if not combined_text:
        return None

    return Line(
        start_ms=start_ms,
        end_ms=end_ms,
        text=combined_text,
        words=words if words else None,
        voice="lead",
    )


def _extract_writers_from_json(json_line: str) -> list[str]:
    """Extracts 作词 / 作曲 names from NetEase credit lines."""
    writers: list[str] = []
    try:
        data = cast("dict[str, Any]", json.loads(json_line))
        pieces: list[dict[str, Any]] = [p for p in cast("list[Any]", data.get("c", [])) if isinstance(p, dict)]
        credit_text = "".join(str(p.get("tx", "")) for p in pieces)
        if not credit_text:
            return writers

        delim = ":" if ":" in credit_text else ("：" if "：" in credit_text else None)
        if not delim:
            return writers

        label, names = credit_text.split(delim, 1)
        if "作词" in label or "作曲" in label or "Lyricist" in label or "Composer" in label:
            for name in re.split(r"[/、,]", names):
                clean_name = name.strip()
                if clean_name and clean_name not in writers:
                    writers.append(clean_name)
    except Exception:
        pass
    return writers
