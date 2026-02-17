import json
import logging
import os
import sys

from PyQt6.QtWidgets import QApplication

from core.utils.utilities import app_data_path
from core.utils.widgets.quick_launch.base_provider import (
    BaseProvider,
    ProviderMenuAction,
    ProviderMenuActionResult,
    ProviderResult,
)
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_EMOJI

_EMOJI_DATA: list[dict] | None = None
if getattr(sys, "frozen", False):
    _DATA_FILE = os.path.join(os.path.dirname(sys.executable), "lib", "emoji.json")
else:
    _DATA_FILE = os.path.join(os.path.dirname(__file__), "resources", "emoji.json")

_PINNED_FILE = str(app_data_path("quick_launch_emoji_pins.json"))


def _load_emoji_data() -> list[dict]:
    """Load emoji data from the bundled JSON file."""
    global _EMOJI_DATA
    if _EMOJI_DATA is not None:
        return _EMOJI_DATA
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            _EMOJI_DATA = json.load(f)
    except Exception as e:
        logging.error(f"Failed to load emoji data: {e}")
        _EMOJI_DATA = []
    return _EMOJI_DATA


class EmojiProvider(BaseProvider):
    """Search and copy emojis to clipboard."""

    name = "emoji"
    display_name = "Emoji Search"
    input_placeholder = "Search emojis..."
    icon = ICON_EMOJI

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._pinned: dict[str, str] = self._load_pinned()

    def _load_pinned(self) -> dict[str, str]:
        try:
            if os.path.isfile(_PINNED_FILE):
                with open(_PINNED_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return {
                        str(emoji): str(name)
                        for emoji, name in data.items()
                        if isinstance(emoji, str) and emoji.strip() and isinstance(name, str)
                    }
        except Exception as e:
            logging.debug(f"Failed to load pinned emojis: {e}")
        return {}

    def _save_pinned(self):
        try:
            os.makedirs(os.path.dirname(_PINNED_FILE), exist_ok=True)
            with open(_PINNED_FILE, "w", encoding="utf-8") as f:
                json.dump(self._pinned, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.debug(f"Failed to save pinned emojis: {e}")

    def pin_emoji(self, emoji: str, name: str):
        if not emoji:
            return
        self._pinned[emoji] = name or emoji
        self._save_pinned()

    def unpin_emoji(self, emoji: str):
        if not emoji:
            return
        if emoji in self._pinned:
            self._pinned.pop(emoji, None)
            self._save_pinned()

    def is_pinned(self, emoji: str) -> bool:
        return bool(emoji and emoji in self._pinned)

    def match(self, text: str) -> bool:
        text = text.strip()
        if self.prefix and text.startswith(self.prefix):
            return True
        return False

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text).strip().lower()
        if not query:
            results: list[ProviderResult] = []
            if self._pinned:
                for emoji_char, name in list(self._pinned.items())[: self.max_results]:
                    results.append(
                        ProviderResult(
                            title=name,
                            description="Pinned emoji - press Enter to copy",
                            icon_char=emoji_char,
                            provider=self.name,
                            action_data={"emoji": emoji_char, "name": name},
                            css_class="emoji-result",
                        )
                    )
            results.append(
                ProviderResult(
                    title="Emoji Search",
                    description="Type a name to search emojis - e.g. smile, heart, fire",
                    icon_char=ICON_EMOJI,
                    provider=self.name,
                )
            )
            return results

        emojis = _load_emoji_data()
        if not emojis:
            return [
                ProviderResult(
                    title="Emoji data not available",
                    description="The emoji.json data file could not be loaded",
                    icon_char=ICON_EMOJI,
                    provider=self.name,
                )
            ]

        pinned_results: list[ProviderResult] = []
        regular_results: list[ProviderResult] = []
        limit = self.max_results
        for entry in emojis:
            if self._matches(query, entry):
                emoji_char = entry.get("emoji", "")
                name = entry.get("name", "")
                group = entry.get("group", "")
                pinned = self.is_pinned(emoji_char)
                result = ProviderResult(
                    title=name,
                    description=f"{group}{' - pinned' if pinned else ''} - press Enter to copy",
                    icon_char=emoji_char,
                    provider=self.name,
                    action_data={"emoji": emoji_char, "name": name, "pinned": pinned},
                    css_class="emoji-result",
                )
                if pinned:
                    pinned_results.append(result)
                else:
                    regular_results.append(result)
                    if len(regular_results) >= limit:
                        break
        return (pinned_results + regular_results)[:limit]

    @staticmethod
    def _matches(query: str, entry: dict) -> bool:
        name = entry.get("name", "").lower()
        aliases = entry.get("aliases", [])
        tags = entry.get("tags", [])
        if query in name:
            return True
        for alias in aliases:
            if query in alias.lower():
                return True
        for tag in tags:
            if query in tag.lower():
                return True
        return False

    def execute(self, result: ProviderResult) -> bool:
        emoji = result.action_data.get("emoji", "")
        if emoji:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(emoji)
        return True

    def get_context_menu_actions(self, result: ProviderResult) -> list[ProviderMenuAction]:
        emoji = result.action_data.get("emoji", "")
        if not emoji:
            return []
        pinned = self.is_pinned(emoji)
        return [
            ProviderMenuAction(id="copy", label="Copy"),
            ProviderMenuAction(id="toggle_pin", label="Unpin emoji" if pinned else "Pin emoji"),
        ]

    def execute_context_menu_action(self, action_id: str, result: ProviderResult) -> ProviderMenuActionResult:
        emoji = result.action_data.get("emoji", "")
        name = result.action_data.get("name", result.title)
        if not emoji:
            return ProviderMenuActionResult()

        if action_id == "copy":
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(emoji)
            return ProviderMenuActionResult()

        if action_id == "toggle_pin":
            if self.is_pinned(emoji):
                self.unpin_emoji(emoji)
            else:
                self.pin_emoji(emoji, name)
            return ProviderMenuActionResult(refresh_results=True)

        return ProviderMenuActionResult()
