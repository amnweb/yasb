from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence

from ..models import Lane, Line, Word
from ..normalize import normalize_lines

logger = logging.getLogger("core.widgets.services.lyrics.parsing.ttml")


def parse_timestamp(stamp: str | None) -> int | None:
    """Parse a TTML timestamp into milliseconds."""
    if not stamp:
        return None
    s = stamp.strip()
    if s.endswith("ms"):
        try:
            return int(float(s[:-2]))
        except ValueError:
            return None
    if s.endswith("s"):
        try:
            return int(float(s[:-1]) * 1000)
        except ValueError:
            return None

    parts = s.split(":")
    try:
        if len(parts) == 3:
            h = float(parts[0])
            m = float(parts[1])
            sec = float(parts[2])
            return int((h * 3600 + m * 60 + sec) * 1000)
        elif len(parts) == 2:
            m = float(parts[0])
            sec = float(parts[1])
            return int((m * 60 + sec) * 1000)
        elif len(parts) == 1:
            return int(float(parts[0]) * 1000)
    except ValueError:
        return None
    return None


def parse_ttml(
    xml_text: str,
    title: str | None = None,
    artists: Sequence[str] | None = None,
) -> tuple[list[Line], list[str]]:
    """Parse TTML lyrics and return lines with songwriter names."""
    lines: list[Line] = []
    writers: list[str] = []

    try:
        root = ET.fromstring(xml_text.strip())
    except ET.ParseError:
        try:
            # Fallback for malformed XML: strip namespace prefix declarations and prefix tags cleanly
            cleaned_xml = re.sub(r"<(/?)\w+:", r"<\1", xml_text)
            cleaned_xml = re.sub(r"\s\w+:(\w+=)", r" \1", cleaned_xml)
            cleaned_xml = re.sub(r'\sxmlns(?::\w+)?="[^"]*"', "", cleaned_xml)
            root = ET.fromstring(cleaned_xml.strip())
        except ET.ParseError as e:
            logger.warning("Failed to parse TTML XML: %s", e)
            return lines, writers

    # Extract songwriters / credits
    for node in root.iter():
        tag = node.tag.split("}")[-1].lower()
        if tag in ("songwriter", "writer", "composer", "lyricist"):
            txt = (node.text or "").strip()
            if txt and txt not in writers:
                writers.append(txt)

    def _extract_agent(el: ET.Element | None) -> str | None:
        if el is None:
            return None
        for k, v in el.attrib.items():
            if k.endswith("agent") or k.split("}")[-1] == "agent":
                return v.strip().lower()
        return None

    parent_map = {c: p for p in root.iter() for c in p}

    # Locate paragraph lines (<p>)
    for p in root.iter():
        tag = p.tag.split("}")[-1].lower()
        if tag != "p":
            continue

        raw_agent = _extract_agent(p) or _extract_agent(parent_map.get(p))
        voice = "lead"
        if raw_agent:
            if raw_agent in ("v2", "counter", "right") or raw_agent.startswith("v2"):
                voice = "counter"
            elif raw_agent in ("v1000", "group", "all", "bg", "chorus"):
                voice = "group"
            elif raw_agent in ("v1", "lead", "left") or raw_agent.startswith("v1"):
                voice = "lead"
            else:
                voice = raw_agent

        p_begin = parse_timestamp(p.attrib.get("begin"))
        p_end = parse_timestamp(p.attrib.get("end"))

        words: list[Word] = []
        secondary_lanes: list[Lane] = []
        lead_text_parts: list[str] = []
        romanized_parts: list[str] = []

        # Parse spans inside paragraph
        for child in p:
            c_tag = child.tag.split("}")[-1].lower()
            if c_tag != "span":
                continue

            role = child.attrib.get("role", "")
            if not role:
                for k, v in child.attrib.items():
                    if k.endswith("role") or k.split("}")[-1] == "role":
                        role = v
                        break
            raw_span_text = "".join(child.itertext())
            span_text = raw_span_text.strip()
            if not span_text:
                continue

            s_begin = parse_timestamp(child.attrib.get("begin")) or p_begin or 0
            s_end = parse_timestamp(child.attrib.get("end")) or p_end

            if role == "x-bg" or "background" in role:
                bg_child_spans = [sub for sub in child if sub.tag.split("}")[-1].lower() == "span"]
                bg_words: list[Word] = []
                if bg_child_spans:
                    for sub in bg_child_spans:
                        sub_raw = "".join(sub.itertext())
                        sub_tail = " " if (sub.tail and any(c.isspace() for c in sub.tail)) else ""
                        sub_text = (sub_raw + sub_tail) if not sub_raw.endswith(" ") else sub_raw
                        sub_b = parse_timestamp(sub.attrib.get("begin")) or s_begin
                        sub_e = parse_timestamp(sub.attrib.get("end")) or (s_end or sub_b)
                        if sub_raw.strip():
                            bg_words.append(Word(start_ms=sub_b, end_ms=sub_e, text=sub_text))
                    bg_start = bg_words[0].start_ms if bg_words else s_begin
                    bg_end = bg_words[-1].end_ms if bg_words else s_end
                else:
                    bg_start = s_begin
                    bg_end = s_end
                    if s_end is not None and s_end > s_begin and span_text:
                        bg_words.append(Word(start_ms=s_begin, end_ms=s_end, text=span_text))

                secondary_lanes.append(
                    Lane(
                        start_ms=bg_start,
                        end_ms=bg_end,
                        text=span_text,
                        words=bg_words if bg_words else None,
                    )
                )
            elif role in ("x-roman", "x-translation"):
                romanized_parts.append(span_text)
            else:
                # Lead vocals span / words
                child_tail = " " if (child.tail and any(c.isspace() for c in child.tail)) else ""
                child_spans = [sub for sub in child if sub.tag.split("}")[-1].lower() == "span"]
                if child_spans:
                    for sub in child_spans:
                        sub_raw = "".join(sub.itertext())
                        sub_tail = " " if (sub.tail and any(c.isspace() for c in sub.tail)) else ""
                        sub_text = (sub_raw + sub_tail) if not sub_raw.endswith(" ") else sub_raw
                        sub_b = parse_timestamp(sub.attrib.get("begin")) or s_begin
                        sub_e = parse_timestamp(sub.attrib.get("end")) or (s_end or sub_b)
                        words.append(Word(start_ms=sub_b, end_ms=sub_e, text=sub_text))
                        lead_text_parts.append(sub_text)
                    if child_tail and words and not words[-1].text.endswith(" "):
                        words[-1].text += " "
                        lead_text_parts.append(" ")
                else:
                    word_text = (raw_span_text + child_tail) if not raw_span_text.endswith(" ") else raw_span_text
                    if s_end is not None and s_end > s_begin:
                        words.append(Word(start_ms=s_begin, end_ms=s_end, text=word_text))
                    lead_text_parts.append(word_text)

        # Fallback if no spans had direct text
        if not lead_text_parts and not words and not secondary_lanes:
            direct_text = "".join(p.itertext()).strip()
            if direct_text:
                lead_text_parts.append(direct_text)

        full_text = re.sub(r"\s+", " ", "".join(lead_text_parts)).strip()
        if not full_text and not secondary_lanes:
            continue

        start_ms = p_begin or (words[0].start_ms if words else (secondary_lanes[0].start_ms if secondary_lanes else 0))
        end_ms = p_end or (words[-1].end_ms if words else None)

        lines.append(
            Line(
                start_ms=start_ms,
                end_ms=end_ms,
                text=full_text,
                romanized=" ".join(romanized_parts) if romanized_parts else None,
                words=words if words else None,
                secondary=secondary_lanes,
                voice=voice,
            )
        )

    if lines:
        lines = normalize_lines(lines, title=title or "", artists=artists or ())

    return lines, writers
