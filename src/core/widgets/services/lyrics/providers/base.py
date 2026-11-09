from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Hit, Query


class LyricsProvider(ABC):
    name: str = "Base"
    trust: int = 0
    supports_multi_voice: bool = False

    @abstractmethod
    def search(self, query: Query) -> list[Hit]:
        raise NotImplementedError
