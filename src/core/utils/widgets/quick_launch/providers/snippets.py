import ctypes
import ctypes.wintypes
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from core.utils.utilities import app_data_path
from core.utils.widgets.quick_launch.base_provider import (
    BaseProvider,
    ProviderMenuAction,
    ProviderMenuActionResult,
    ProviderResult,
)
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_SNIPPET

_SNIPPETS_FILE = str(app_data_path("quick_launch_snippets.json"))

# Template variable pattern: {{name}} or {{name:format}}
_VAR_PATTERN = re.compile(r"\{\{(\w+)(?::([^}]+))?\}\}")


def _resolve_variables(text: str) -> str:
    """Replace template variables in snippet content.

    Supported variables:
        {{date}}              Current date (default: %Y-%m-%d)
        {{date:%d/%m/%Y}}     Current date with custom format
        {{time}}              Current time (default: %H:%M:%S)
        {{time:%I:%M %p}}     Current time with custom format
        {{datetime}}          Current date and time (default: %Y-%m-%d %H:%M:%S)
        {{datetime:%A, %B %d}} Current date and time with custom format
        {{clipboard}}         Current clipboard text
        {{username}}          Windows username
    """
    now = datetime.now()

    def _replace(match: re.Match) -> str:
        name = match.group(1).lower()
        fmt = match.group(2)
        if name == "date":
            return now.strftime(fmt or "%Y-%m-%d")
        if name == "time":
            return now.strftime(fmt or "%H:%M:%S")
        if name == "datetime":
            return now.strftime(fmt or "%Y-%m-%d %H:%M:%S")
        if name == "clipboard":
            cb = QApplication.clipboard()
            return cb.text() if cb else ""
        if name == "username":
            return os.getlogin()
        return match.group(0)

    return _VAR_PATTERN.sub(_replace, text)


# SendInput constants
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_size_t)),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_size_t)),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.wintypes.DWORD),
        ("wParamL", ctypes.wintypes.WORD),
        ("wParamH", ctypes.wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.wintypes.DWORD),
        ("_input", _INPUT_UNION),
    ]
    _anonymous_ = ("_input",)


_SendInput = ctypes.windll.user32.SendInput
_SendInput.argtypes = [ctypes.wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
_SendInput.restype = ctypes.wintypes.UINT


def _send_unicode_string(text: str):
    """Type a string into the focused window using SendInput with KEYEVENTF_UNICODE."""
    inputs = []
    for char in text:
        code = ord(char)
        down = _INPUT(type=INPUT_KEYBOARD)
        down.ki.wVk = 0
        down.ki.wScan = code
        down.ki.dwFlags = KEYEVENTF_UNICODE
        inputs.append(down)

        up = _INPUT(type=INPUT_KEYBOARD)
        up.ki.wVk = 0
        up.ki.wScan = code
        up.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        inputs.append(up)

    if inputs:
        n = len(inputs)
        arr = (_INPUT * n)(*inputs)
        _SendInput(n, arr, ctypes.sizeof(_INPUT))


class SnippetsProvider(BaseProvider):
    """Save and type text snippets into the previously focused window."""

    name = "snippets"
    display_name = "Snippets"
    input_placeholder = "Search snippets..."
    icon = ICON_SNIPPET

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._snippets: list[dict] = self._load_snippets()
        self._type_delay: int = self.config.get("type_delay", 200)
        self._editing_id: str | None = None

    def _load_snippets(self) -> list[dict]:
        try:
            if os.path.isfile(_SNIPPETS_FILE):
                with open(_SNIPPETS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return [s for s in data if isinstance(s, dict) and s.get("content")]
        except Exception as e:
            logging.debug(f"Failed to load snippets: {e}")
        return []

    def _save_snippets(self):
        try:
            os.makedirs(os.path.dirname(_SNIPPETS_FILE), exist_ok=True)
            with open(_SNIPPETS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._snippets, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.debug(f"Failed to save snippets: {e}")

    def _find_snippet(self, snippet_id: str) -> dict | None:
        for s in self._snippets:
            if s.get("id") == snippet_id:
                return s
        return None

    def _edit_preview(self, title: str = "", content: str = "") -> dict:
        """Return a preview dict that renders as an inline edit form."""
        return {
            "kind": "edit",
            "fields": [
                {"id": "title", "type": "text", "label": "Title", "placeholder": "Snippet name", "value": title},
                {
                    "id": "content",
                    "type": "multiline",
                    "label": "Content",
                    "placeholder": "Snippet text that will be typed...",
                    "value": content,
                },
            ],
            "action": "save_snippet",
        }

    def match(self, text: str) -> bool:
        if self.prefix:
            return text.strip().startswith(self.prefix)
        return False

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text).strip().lower()

        if not query:
            results = self._sorted_snippets()
            items = [self._snippet_to_result(s) for s in results]
            items.append(
                ProviderResult(
                    title="Create new snippet",
                    description="Add a new text snippet",
                    icon_char=ICON_SNIPPET,
                    provider=self.name,
                    action_data={"action": "create"},
                    preview=self._edit_preview(),
                )
            )
            return items

        results = []
        for s in self._sorted_snippets():
            title = s.get("title", "").lower()
            content = s.get("content", "").lower()
            if query in title or query in content:
                results.append(self._snippet_to_result(s))
        return results

    def _sorted_snippets(self) -> list[dict]:
        return sorted(self._snippets, key=lambda s: s.get("last_used", 0), reverse=True)

    def _snippet_to_result(self, snippet: dict) -> ProviderResult:
        title = snippet.get("title", "Untitled")
        content = snippet.get("content", "")
        snippet_id = snippet.get("id", "")

        # If this snippet is being edited, show the edit form instead
        if self._editing_id == snippet_id:
            return ProviderResult(
                title=title,
                description="Editing...",
                icon_char=ICON_SNIPPET,
                provider=self.name,
                action_data={"snippet_id": snippet_id},
                preview=self._edit_preview(title, content),
            )

        lines = content.split("\n")
        first_line = lines[0] if lines else ""
        if len(first_line) > 80:
            first_line = first_line[:80] + "..."

        return ProviderResult(
            title=title,
            description=first_line,
            icon_char=ICON_SNIPPET,
            provider=self.name,
            action_data={"snippet_id": snippet_id},
            preview={
                "kind": "text",
                "title": title,
                "text": content,
            },
        )

    def execute(self, result: ProviderResult) -> bool | None:
        action = result.action_data.get("action", "")
        if action == "create":
            return None  # Edit form is already in the preview panel

        snippet_id = result.action_data.get("snippet_id", "")
        snippet = self._find_snippet(snippet_id)
        if not snippet:
            return False

        # If this snippet is being edited, don't type — just keep form open
        if self._editing_id == snippet_id:
            return None

        content = snippet.get("content", "")
        if not content:
            return False

        content = _resolve_variables(content)
        snippet["last_used"] = time.time()
        snippet["use_count"] = snippet.get("use_count", 0) + 1
        self._save_snippets()

        # Schedule typing after popup fade-out and OS focus restore
        delay = self._type_delay
        QTimer.singleShot(delay, lambda: _send_unicode_string(content))
        return True

    def get_context_menu_actions(self, result: ProviderResult) -> list[ProviderMenuAction]:
        if result.action_data.get("action") == "create":
            return []

        snippet_id = result.action_data.get("snippet_id", "")
        if not snippet_id:
            return []

        return [
            ProviderMenuAction(id="copy", label="Copy to clipboard"),
            ProviderMenuAction(id="edit", label="Edit snippet"),
            ProviderMenuAction(id="delete", label="Delete snippet", separator_before=True),
        ]

    def execute_context_menu_action(self, action_id: str, result: ProviderResult) -> ProviderMenuActionResult:
        snippet_id = result.action_data.get("snippet_id", "")
        snippet = self._find_snippet(snippet_id)
        if not snippet:
            return ProviderMenuActionResult()

        if action_id == "copy":
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(_resolve_variables(snippet.get("content", "")))
            return ProviderMenuActionResult()

        if action_id == "edit":
            self._editing_id = snippet_id
            return ProviderMenuActionResult(refresh_results=True)

        if action_id == "delete":
            self._snippets = [s for s in self._snippets if s.get("id") != snippet_id]
            self._save_snippets()
            return ProviderMenuActionResult(refresh_results=True)

        return ProviderMenuActionResult()

    def handle_preview_action(self, action_id: str, result: ProviderResult, data: dict) -> ProviderMenuActionResult:
        if action_id == "cancel":
            self._editing_id = None
            return ProviderMenuActionResult(refresh_results=True)

        if action_id == "save_snippet":
            title = data.get("title", "").strip() or "Untitled"
            content = data.get("content", "")
            if not content:
                return ProviderMenuActionResult(refresh_results=True)

            now = time.time()
            snippet_id = result.action_data.get("snippet_id", "")

            if snippet_id:
                # Editing existing
                snippet = self._find_snippet(snippet_id)
                if snippet:
                    snippet["title"] = title
                    snippet["content"] = content
            else:
                # Creating new
                self._snippets.append(
                    {
                        "id": str(uuid.uuid4()),
                        "title": title,
                        "content": content,
                        "created": now,
                        "last_used": now,
                        "use_count": 0,
                    }
                )

            self._editing_id = None
            self._save_snippets()
            return ProviderMenuActionResult(refresh_results=True)

        return ProviderMenuActionResult()
