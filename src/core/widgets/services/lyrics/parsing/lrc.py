from __future__ import annotations

import re

from ..models import Line, Word

TIMESTAMP_REGEX = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]")
OFFSET_REGEX = re.compile(r"\[offset:\s*([+-]?\d+)\s*\]", re.IGNORECASE)
TAG_REGEX = re.compile(r"\[[a-zA-Z]{1,10}:[^\]]*\]")
WORD_TIME_REGEX = re.compile(r"<(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?>([^<]+)")
AGENT_REGEX = re.compile(r"^[\{\[]agent:(v\d+|lead|counter|group|left|right)[\}\]]\s*", re.IGNORECASE)


def _parse_time(m: str, s: str, ms_part: str | None) -> int:
    minutes = int(m)
    seconds = int(s)
    total_ms = (minutes * 60 + seconds) * 1000
    if ms_part:
        if len(ms_part) == 1:
            total_ms += int(ms_part) * 100
        elif len(ms_part) == 2:
            total_ms += int(ms_part) * 10
        else:
            total_ms += int(ms_part[:3])
    return total_ms


def parse_lrc(content: str) -> list[Line]:
    """Parse LRC text into lyric lines."""
    if not content:
        return []

    lines = content.splitlines()
    offset_ms = 0

    for raw in lines:
        off_m = OFFSET_REGEX.search(raw)
        if off_m:
            try:
                offset_ms += int(off_m.group(1))
            except ValueError:
                pass

    parsed_lines: list[Line] = []

    for raw in lines:
        trimmed = raw.strip()
        if not trimmed:
            continue

        matches = list(TIMESTAMP_REGEX.finditer(trimmed))
        if not matches:
            continue

        last_match_end = max(m.end() for m in matches)
        text_part = trimmed[last_match_end:].strip()

        voice = "lead"
        agent_match = AGENT_REGEX.match(text_part)
        if agent_match:
            raw_agent = agent_match.group(1).lower()
            text_part = text_part[agent_match.end() :].strip()
            if raw_agent in ("v2", "counter", "right") or raw_agent.startswith("v2"):
                voice = "counter"
            elif raw_agent in ("v1000", "group", "all", "bg", "chorus"):
                voice = "group"
            elif raw_agent in ("v1", "lead", "left") or raw_agent.startswith("v1"):
                voice = "lead"
            else:
                voice = raw_agent

        word_matches = list(WORD_TIME_REGEX.finditer(text_part))
        words: list[Word] | None = None
        if word_matches:
            clean_text = ""
            words = []
            for i, wm in enumerate(word_matches):
                w_start = _parse_time(wm.group(1), wm.group(2), wm.group(3)) + offset_ms
                w_text = wm.group(4)
                clean_text += w_text
                if i + 1 < len(word_matches):
                    next_wm = word_matches[i + 1]
                    w_end = _parse_time(next_wm.group(1), next_wm.group(2), next_wm.group(3)) + offset_ms
                else:
                    w_end = w_start + 400
                words.append(Word(start_ms=max(0, w_start), end_ms=max(0, w_end), text=w_text))
            text_part = clean_text.strip()
        else:
            # Strip any remaining metadata tags in text
            text_part = TAG_REGEX.sub("", text_part).strip()

        # For every timestamp on this line, create a Line instance
        for m in matches:
            t_ms = _parse_time(m.group(1), m.group(2), m.group(3)) + offset_ms
            parsed_lines.append(
                Line(
                    start_ms=max(0, t_ms),
                    end_ms=None,
                    text=text_part,
                    words=list(words) if words else None,
                    voice=voice,
                )
            )

    parsed_lines.sort(key=lambda l: l.start_ms)
    return parsed_lines
