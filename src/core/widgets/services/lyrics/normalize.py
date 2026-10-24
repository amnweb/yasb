from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

from .models import Lane, Line, Word
from .romanize import detect_writing_system, romanize_text

LABELS: tuple[str, ...] = (
    "artist:",
    "title:",
    "album:",
    "song:",
    "by:",
    "lyrics:",
    "written by",
    "composed by",
    "arranged by",
    "produced by",
    "lyrics by",
    "music by",
    "mixed by",
    "mastered by",
    "recorded by",
    "engineered by",
    "vocals by",
    "backing vocals by",
    "vocal production by",
    "co-production",
    "programmer",
    "composer",
    "lyricist",
    "arranger",
    "producer",
    "作词",
    "作曲",
    "编曲",
    "作詞",
    "編曲",
    "制作",
    "監製",
    "监制",
    "混音",
    "母带",
    "和声",
    "词：",
    "曲：",
    "词:",
    "曲:",
    "作词：",
    "作曲：",
    "编曲：",
    "制作：",
)

RIGHTS: tuple[str, ...] = (
    "all rights reserved",
    "used by permission",
    "administered by",
    "published by",
    "publishing",
    "copyright",
    "\u00a9",  # ©
    "\u2117",  # ℗
)

STRUCTURAL_PATTERN = re.compile(
    r"^[\[\(]\s*(?:chorus|verse|bridge|outro|intro|hook|refrain|drop|pre-chorus|interlude|solo|break)(?:\s*\d+)?\s*[\]\)]$",
    re.IGNORECASE,
)

HOMOGLYPHS: dict[str, str] = {
    "а": "a",
    "в": "b",
    "е": "e",
    "к": "k",
    "м": "m",
    "н": "h",
    "о": "o",
    "р": "p",
    "с": "c",
    "т": "t",
    "у": "y",
    "х": "x",
    "і": "i",
    "ј": "j",
    "ѕ": "s",
    "ԁ": "d",
    "А": "A",
    "В": "B",
    "Е": "E",
    "К": "K",
    "М": "M",
    "Н": "H",
    "О": "O",
    "Р": "P",
    "С": "C",
    "Т": "T",
    "У": "Y",
    "Х": "X",
    "І": "I",
    "Ј": "J",
    "Ѕ": "S",
    "Α": "A",
    "Β": "B",
    "Ε": "E",
    "Ζ": "Z",
    "Η": "H",
    "Ι": "I",
    "Κ": "K",
    "Μ": "M",
    "Ν": "N",
    "Ο": "O",
    "Ρ": "P",
    "Τ": "T",
    "Υ": "Y",
    "Χ": "X",
    "ο": "o",
    "ρ": "p",
    "τ": "t",
    "ι": "i",
}

WIDE_MARKS: dict[str, str] = {
    "\uff07": "'",
    "\u02bc": "'",
    "\u2032": "'",
    "\u00b4": "'",
    "`": "'",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\uff02": '"',
    "\u3000": " ",
}


def is_wide_char(ch: str) -> bool:
    code = ord(ch)
    return (
        (0x3040 <= code <= 0x30FF)
        or (0x3400 <= code <= 0x4DBF)
        or (0x4E00 <= code <= 0x9FFF)
        or (0xAC00 <= code <= 0xD7AF)
    )


def is_latin_labelled(text: str) -> bool:
    if "：" in text:
        parts = text.split("：", 1)
        label = parts[0].strip()
        if label and len(label) <= 48 and any(c.isalnum() for c in label) and not any(is_wide_char(c) for c in label):
            return True
    return False


def loosely(haystack: str, needle: str) -> bool:
    h = "".join(c.lower() for c in haystack if c.isalnum())
    n = "".join(c.lower() for c in needle if c.isalnum())
    return bool(n and n in h)


def is_named_header(text: str, title: str, artists: Sequence[str]) -> bool:
    has_sep = any(sep in text for sep in ("-", "–", "—", "/"))
    # Strip (feat. ...), [Remix], etc.
    clean_title = (
        re.sub(
            r"\s*[\(\[][^\)\]]*(?:feat|ft|with|remix|version|edit|live|bonus|deluxe)[^\)\]]*[\)\]]",
            "",
            title,
            flags=re.I,
        )
        .split(" - ")[0]
        .strip()
    )
    base_title = clean_title.split(",")[0].split(" - ")[0].strip() if clean_title else title
    targets = [t for t in (title, clean_title, base_title) if t]

    for target in targets:
        if loosely(text, target):
            if artists and any(loosely(text, a) for a in artists if len(a) > 2):
                return True
            if has_sep:
                return True
    return False


def is_header_line(text: str, title: str = "", artists: Sequence[str] = ()) -> bool:
    low = text.strip().lower()
    if not low:
        return False
    if any(low.startswith(lbl) for lbl in LABELS):
        return True
    if any(r in low for r in RIGHTS):
        return True
    if is_latin_labelled(text):
        return True
    # Colon-separated attribute like "Guitar: John" or "作词: ..."
    if ":" in text or "\uff1a" in text:
        parts = re.split(r"[:\uff1a]", text, maxsplit=1)
        if len(parts) == 2:
            left = parts[0].strip().lower()
            if left in LABELS or any(lbl.rstrip(":") == left or lbl.rstrip("：") == left for lbl in LABELS):
                return True
    if title or artists:
        if is_named_header(text, title, artists):
            return True
    return False


def is_structural_line(text: str) -> bool:
    return bool(STRUCTURAL_PATTERN.match(text.strip()))


def unwiden(text: str) -> str:
    res: list[str] = []
    for ch in text:
        res.append(WIDE_MARKS.get(ch, ch))
    return "".join(res)


def unspoof(text: str) -> str:
    res: list[str] = []
    for ch in text:
        res.append(HOMOGLYPHS.get(ch, ch))
    return "".join(res)


def collapse_whitespace(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def recapitalize(lines: list[Line]) -> None:
    if not lines:
        return
    upper_cnt = 0
    lower_cnt = 0
    for line in lines:
        t = line.text.strip()
        if t and t[0].isalpha():
            if t[0].isupper():
                upper_cnt += 1
            elif t[0].islower():
                lower_cnt += 1

    total = upper_cnt + lower_cnt
    if total == 0:
        return

    should_fix = (upper_cnt == total) or (lower_cnt == total)
    if not should_fix:
        return

    for line in lines:
        t = line.text.strip()
        if t:
            line.text = t[0].upper() + (t[1:].lower() if upper_cnt == total else t[1:])


class Parenthetical:
    __slots__ = ("outer_start", "outer_end", "inner_start", "inner_end")

    def __init__(self, outer_start: int, outer_end: int, inner_start: int, inner_end: int) -> None:
        self.outer_start = outer_start
        self.outer_end = outer_end
        self.inner_start = inner_start
        self.inner_end = inner_end


def parenthetical_spans(text: str) -> list[Parenthetical]:
    spans: list[Parenthetical] = []
    opened: int | None = None
    depth = 0
    for idx, ch in enumerate(text):
        if ch in ("(", "（"):
            if depth == 0:
                opened = idx
            depth += 1
        elif ch in (")", "）") and depth > 0:
            depth -= 1
            if depth == 0 and opened is not None:
                spans.append(Parenthetical(opened, idx + 1, opened + 1, idx))
                opened = None
    return spans


def place_words(text: str, words: list[Word]) -> list[tuple[int, int]] | None:
    placed: list[tuple[int, int]] = []
    cursor = 0
    for w in words:
        rem = text[cursor:]
        rel = rem.find(w.text)
        if rel == -1:
            return None
        start = cursor + rel
        end = start + len(w.text)
        placed.append((start, end))
        cursor = end
    return placed


def word_without_spans(text: str, placed: tuple[int, int], spans: list[Parenthetical]) -> str:
    p_start, p_end = placed
    cursor = p_start
    res: list[str] = []
    for span in spans:
        if span.outer_start < p_end and span.outer_end > p_start:
            end = min(span.outer_start, p_end)
            if cursor < end:
                res.append(text[cursor:end])
            cursor = max(cursor, min(span.outer_end, p_end))
    if cursor < p_end:
        res.append(text[cursor:p_end])
    return "".join(res)


def without_spans(text: str, spans: list[Parenthetical]) -> str:
    res: list[str] = []
    cursor = 0
    for span in spans:
        res.append(text[cursor : span.outer_start])
        cursor = span.outer_end
    res.append(text[cursor:])
    return " ".join("".join(res).split())


def separate_background(line: Line) -> None:
    """Move parenthesized vocals into secondary lanes."""
    original = line.text
    spans = parenthetical_spans(original)
    if not spans:
        return

    placements = place_words(original, line.words) if line.words else None
    lanes: list[Lane] = []

    for span in spans:
        inner_text = original[span.inner_start : span.inner_end].strip()
        if not inner_text:
            continue

        lane_words: list[Word] | None = None
        if line.words and placements:
            lane_words = []
            for w, placed in zip(line.words, placements):
                w_start, w_end = placed
                s_start = max(w_start, span.inner_start)
                s_end = min(w_end, span.inner_end)
                if s_start < s_end:
                    txt = original[s_start:s_end]
                    if txt.strip():
                        lane_words.append(Word(start_ms=w.start_ms, end_ms=w.end_ms, text=txt))
            if not lane_words:
                lane_words = None

        start = lane_words[0].start_ms if lane_words else line.start_ms
        end = lane_words[-1].end_ms if lane_words else line.end_ms
        bracketed_text = f"({inner_text})"
        if lane_words:
            if not lane_words[0].text.startswith("("):
                lane_words[0].text = "(" + lane_words[0].text
            if not lane_words[-1].text.endswith(")"):
                lane_words[-1].text = lane_words[-1].text.rstrip() + ")"
        lanes.append(
            Lane(
                start_ms=start,
                end_ms=end,
                text=bracketed_text,
                words=lane_words,
            )
        )

    if not lanes:
        return

    if line.words and placements:
        kept: list[Word] = []
        for w, placed in zip(line.words, placements):
            w_txt = word_without_spans(original, placed, spans)
            if w_txt.strip():
                w.text = w_txt
                kept.append(w)
        line.words = kept if kept else None

    line.text = without_spans(original, spans)
    line.secondary.extend(lanes)


def close_lines(lines: list[Line], max_line_duration_ms: int = 12000) -> None:
    for i in range(len(lines)):
        cur = lines[i]
        if i + 1 < len(lines):
            next_start = lines[i + 1].start_ms
            if cur.end_ms is None or cur.end_ms > next_start or cur.end_ms <= cur.start_ms:
                cur.end_ms = next_start
        else:
            if cur.end_ms is None or cur.end_ms <= cur.start_ms:
                cur.end_ms = cur.start_ms + min(5000, max_line_duration_ms)

        if cur.end_ms - cur.start_ms > max_line_duration_ms:
            cur.end_ms = cur.start_ms + max_line_duration_ms


def normalize_lines(
    lines: list[Line],
    title: str = "",
    artists: Sequence[str] = (),
    do_romanize: bool = True,
) -> list[Line]:
    """Clean parsed lines and optionally add romanized text."""
    if not lines:
        return []

    lines.sort(key=lambda l: l.start_ms)

    close_lines(lines)

    cleaned: list[Line] = []
    header_budget = 16  # allow checking first 16 lines for credit headers
    for idx, line in enumerate(lines):
        t = line.text.strip()
        if not t:
            continue
        if is_structural_line(t):
            continue
        if idx < header_budget and is_header_line(t, title=title, artists=artists):
            continue
        cleaned.append(line)

    for line in cleaned:
        t = unicodedata.normalize("NFKC", line.text)
        t = unwiden(t)
        t = unspoof(t)
        t = collapse_whitespace(t)
        line.text = t

        separate_background(line)

        for lane in line.secondary:
            lane.text = collapse_whitespace(unspoof(unwiden(unicodedata.normalize("NFKC", lane.text))))

    recapitalize(cleaned)

    if do_romanize:
        all_texts: list[str] = []
        for line in cleaned:
            all_texts.append(line.text)
            for lane in line.secondary:
                all_texts.append(lane.text)
        system = detect_writing_system(all_texts)
        if system:
            for line in cleaned:
                if not line.romanized:
                    line.romanized = romanize_text(line.text, system=system)
                for lane in line.secondary:
                    if not lane.romanized:
                        lane.romanized = romanize_text(lane.text, system=system)

    return cleaned


def clean_for_matching(text: str) -> str:
    """
    Cleans title or artist for matching comparisons:
    Strips parenthesized extra info like (feat. X), [Remastered], ' - Remastered',
    and keeps only alphanumeric lowercase characters.
    """
    if not text:
        return ""
    # Strip brackets/parentheses
    t = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", text)
    # Strip dash suffixes (e.g. " - Live at ...", " - Remastered")
    if " - " in t:
        t = t.split(" - ")[0]
    return "".join(c.lower() for c in t if c.isalnum())


def matching_keys(text: str | None) -> set[str]:
    """
    Returns a set of normalized alphanumeric matching keys for a title or artist,
    including the cleaned native string and any transliterated/romanized variants
    (e.g., Hangul, Pinyin, Kanji transliteration for cross-language matching).
    """
    if not text:
        return set()

    keys: set[str] = set()
    cleaned = clean_for_matching(text)
    if cleaned:
        keys.add(cleaned)

    try:
        romanized = romanize_text(text)
        if romanized:
            cleaned_rom = clean_for_matching(romanized)
            if cleaned_rom:
                keys.add(cleaned_rom)
                # Also add collapsed single-vowel variant (e.g. yohaani -> yohani)
                collapsed = re.sub(r"([aeiou])\1+", r"\1", cleaned_rom)
                if collapsed:
                    keys.add(collapsed)
                # Map phonetic digraphs (ee -> i, oo -> u) common in Indic/Singlish transliteration
                vowel_alt = cleaned_rom.replace("ee", "i").replace("oo", "u")
                if vowel_alt:
                    keys.add(vowel_alt)
                    keys.add(re.sub(r"([aeiou])\1+", r"\1", vowel_alt))
    except Exception:
        pass

    return keys
