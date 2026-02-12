from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class ProviderResult:
    """A single result item returned by a provider."""

    title: str
    description: str = ""
    icon_path: str = ""
    icon_char: str = ""
    provider: str = ""
    id: str = ""
    action_data: dict = field(default_factory=dict)


class BaseProvider(ABC):
    """Abstract base for Quick Launch search providers."""

    name: str = ""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        raw = self.config.get("prefix", "*")
        self.prefix: str | None = None if raw == "*" else raw
        self.priority: int = self.config.get("priority", 0)
        self.request_refresh: Callable[[], None] | None = None

    def match(self, text: str) -> bool:
        """Return True if this provider should handle the query."""
        if self.prefix:
            return text.strip().startswith(self.prefix)
        return True

    @abstractmethod
    def get_results(self, text: str) -> list[ProviderResult]:
        """Return results for the given search text."""

    @abstractmethod
    def execute(self, result: ProviderResult) -> bool:
        """Execute a selected result. Return True if popup should close."""

    def get_query_text(self, text: str) -> str:
        """Strip prefix from query text."""
        if self.prefix and text.startswith(self.prefix):
            return text[len(self.prefix) :].strip()
        return text.strip()
