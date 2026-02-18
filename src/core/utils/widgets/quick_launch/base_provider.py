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
    preview: dict = field(default_factory=dict)
    css_class: str = ""


@dataclass
class ProviderMenuAction:
    """A context-menu action exposed by a provider."""

    id: str
    label: str
    enabled: bool = True
    separator_before: bool = False


@dataclass
class ProviderMenuActionResult:
    """Execution result returned by a provider context-menu action."""

    refresh_results: bool = False
    close_popup: bool = False


class BaseProvider(ABC):
    """Abstract base for Quick Launch search providers."""

    name: str = ""
    display_name: str = ""
    icon: str = ""
    input_placeholder: str = "Type to search..."

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        raw = self.config.get("prefix", "*")
        self.prefix: str | None = None if raw == "*" else raw
        self.priority: int = self.config.get("priority", 0)
        self.max_results: int = self.config.get("_max_results", 50)
        self.request_refresh: Callable[[], None] | None = None

    def match(self, text: str) -> bool:
        """Return True if this provider should handle the query."""
        if self.prefix:
            return text.strip().startswith(self.prefix + " ")
        return True

    @abstractmethod
    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        """Return results for the given search text."""

    @abstractmethod
    def execute(self, result: ProviderResult) -> bool | None:
        """Execute a selected result. Return True to close popup, False to refresh, None to do nothing."""

    def get_context_menu_actions(self, result: ProviderResult) -> list[ProviderMenuAction]:
        """Return context-menu actions for a result. Empty list means no menu."""
        return []

    def execute_context_menu_action(self, action_id: str, result: ProviderResult) -> ProviderMenuActionResult:
        """Execute a context-menu action for a result."""
        return ProviderMenuActionResult()

    def handle_preview_action(self, action_id: str, result: ProviderResult, data: dict) -> ProviderMenuActionResult:
        """Handle an action from an inline edit form in the preview panel."""
        return ProviderMenuActionResult()

    def get_query_text(self, text: str) -> str:
        """Strip prefix from query text."""
        if self.prefix and text.startswith(self.prefix):
            return text[len(self.prefix) :].strip()
        return text.strip()
