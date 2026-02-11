import json
import logging
import os
import sys

from PyQt6.QtWidgets import QApplication

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult

_ICON = "\ue76e"

_EMOJI_DATA: list[dict] | None = None
if getattr(sys, "frozen", False):
    _DATA_FILE = os.path.join(os.path.dirname(sys.executable), "lib", "emoji.json")
else:
    _DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "emoji.json")


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

    def match(self, text: str) -> bool:
        text = text.strip()
        if self.prefix and text.startswith(self.prefix):
            return True
        return False

    def get_results(self, text: str) -> list[ProviderResult]:
        query = self.get_query_text(text).strip().lower()
        if not query:
            return [
                ProviderResult(
                    title="Emoji Search",
                    description="Type a name to search emojis - e.g. smile, heart, fire",
                    icon_char=_ICON,
                    provider=self.name,
                )
            ]

        emojis = _load_emoji_data()
        if not emojis:
            return [
                ProviderResult(
                    title="Emoji data not available",
                    description="The emoji.json data file could not be loaded",
                    icon_char=_ICON,
                    provider=self.name,
                )
            ]

        results: list[ProviderResult] = []
        for entry in emojis:
            if self._matches(query, entry):
                emoji_char = entry.get("emoji", "")
                name = entry.get("name", "")
                group = entry.get("group", "")
                results.append(
                    ProviderResult(
                        title=name,
                        description=f"{group} - press Enter to copy",
                        icon_char=emoji_char,
                        provider=self.name,
                        action_data={"emoji": emoji_char, "name": name},
                    )
                )
                if len(results) >= 30:
                    break
        return results

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
