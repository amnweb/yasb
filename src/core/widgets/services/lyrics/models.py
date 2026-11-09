from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Voice = Literal["lead", "counter"]


@dataclass
class Word:
    start_ms: int
    end_ms: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Word:
        return cls(
            start_ms=int(data["start_ms"]),
            end_ms=int(data["end_ms"]),
            text=str(data["text"]),
        )


@dataclass
class Lane:
    start_ms: int
    end_ms: int | None
    text: str
    romanized: str | None = None
    translation: str | None = None
    words: list[Word] | None = None

    def worded(self) -> bool:
        return bool(self.words)

    def sung_end(self) -> int:
        if self.words:
            for w in reversed(self.words):
                if w.text.strip():
                    return max(w.end_ms, w.start_ms, self.start_ms)
        return self.end_ms if self.end_ms is not None else self.start_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "text": self.text,
            "romanized": self.romanized,
            "translation": self.translation,
            "words": [w.to_dict() for w in self.words] if self.words is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Lane:
        words_data = data.get("words")
        words = [Word.from_dict(w) for w in words_data] if words_data is not None else None
        return cls(
            start_ms=int(data["start_ms"]),
            end_ms=int(data["end_ms"]) if data.get("end_ms") is not None else None,
            text=str(data["text"]),
            romanized=data.get("romanized"),
            translation=data.get("translation"),
            words=words,
        )


@dataclass
class Line:
    start_ms: int
    end_ms: int | None
    text: str
    romanized: str | None = None
    translation: str | None = None
    words: list[Word] | None = None
    secondary: list[Lane] = field(default_factory=list[Lane])
    voice: Voice | str = "lead"

    def worded(self) -> bool:
        return bool(self.words) or any(lane.worded() for lane in self.secondary)

    def sung_end(self) -> int:
        primary = self.end_ms if self.end_ms is not None else self.start_ms
        if self.words:
            for w in reversed(self.words):
                if w.text.strip():
                    primary = max(w.end_ms, w.start_ms, self.start_ms)
                    break
        ends = [primary]
        for lane in self.secondary:
            ends.append(lane.sung_end())
        return max(ends)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "text": self.text,
            "romanized": self.romanized,
            "translation": self.translation,
            "words": [w.to_dict() for w in self.words] if self.words is not None else None,
            "secondary": [lane.to_dict() for lane in self.secondary],
            "voice": self.voice,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Line:
        words_data = data.get("words")
        words = [Word.from_dict(w) for w in words_data] if words_data is not None else None
        secondary = [Lane.from_dict(lane) for lane in data.get("secondary", [])]
        return cls(
            start_ms=int(data["start_ms"]),
            end_ms=int(data["end_ms"]) if data.get("end_ms") is not None else None,
            text=str(data["text"]),
            romanized=data.get("romanized"),
            translation=data.get("translation"),
            words=words,
            secondary=secondary,
            voice=data.get("voice", "lead"),
        )


@dataclass
class Lyrics:
    lines: list[Line] | None = None
    plain: str | None = None

    def is_empty(self) -> bool:
        if self.lines is not None:
            return len(self.lines) == 0
        if self.plain is not None:
            return not self.plain.strip()
        return True

    def synced(self) -> bool:
        return self.lines is not None and len(self.lines) > 0

    @property
    def is_synced(self) -> bool:
        return self.synced()

    def worded(self) -> bool:
        if not self.lines:
            return False
        return any(line.worded() for line in self.lines)

    @property
    def is_worded(self) -> bool:
        return self.worded()

    def span_ms(self) -> int | None:
        if not self.lines:
            return None
        return max(line.sung_end() for line in self.lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lines": [line.to_dict() for line in self.lines] if self.lines is not None else None,
            "plain": self.plain,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Lyrics:
        lines_data = data.get("lines")
        lines = [Line.from_dict(line) for line in lines_data] if lines_data is not None else None
        return cls(
            lines=lines,
            plain=data.get("plain"),
        )


@dataclass
class Hit:
    source: str
    trust: int
    lyrics: Lyrics
    instrumental: bool
    title: str
    artist: str
    duration_s: float | None = None
    writers: list[str] = field(default_factory=list[str])

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "trust": self.trust,
            "lyrics": self.lyrics.to_dict(),
            "instrumental": self.instrumental,
            "title": self.title,
            "artist": self.artist,
            "duration_s": self.duration_s,
            "writers": self.writers,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Hit:
        return cls(
            source=str(data["source"]),
            trust=int(data.get("trust", 0)),
            lyrics=Lyrics.from_dict(data["lyrics"]),
            instrumental=bool(data.get("instrumental", False)),
            title=str(data["title"]),
            artist=str(data["artist"]),
            duration_s=float(data["duration_s"]) if data.get("duration_s") is not None else None,
            writers=list(data.get("writers", [])),
        )


@dataclass
class Query:
    title: str
    artist: str
    duration_s: float | None = None

    def clean_key(self) -> str:
        """Returns a normalized string suitable for cache keying and comparisons."""

        def norm(s: str | None) -> str:
            if not s:
                return ""
            return "".join(c.lower() for c in s if c.isalnum())

        t = norm(self.title)
        a = norm(self.artist)
        d = str(round(self.duration_s)) if self.duration_s is not None else "0"
        return f"{a}|{t}|{d}"
