import io
import logging
from typing import Any

from core.utils.shell_utils import shell_open
from core.utils.widgets.quick_launch.base_provider import (
    BaseProvider,
    ProviderMenuAction,
    ProviderMenuActionResult,
    ProviderResult,
)
from core.utils.widgets.quick_launch.providers.resources.icons import (
    ICON_CLEAR,
    ICON_CLIPBOARD,
    ICON_CLIPBOARD_IMAGE,
    ICON_CLIPBOARD_TEXT,
    ICON_WARNING,
)

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from winrt.windows.applicationmodel.datatransfer import (
        Clipboard,
        ClipboardHistoryItemsResultStatus,
    )
except Exception:
    Clipboard = None
    ClipboardHistoryItemsResultStatus = None

try:
    from winrt.windows.storage.streams import Buffer, InputStreamOptions
except Exception:
    Buffer = None
    InputStreamOptions = None


class ClipboardHistoryProvider(BaseProvider):
    """Browse and restore Windows Clipboard History entries."""

    name = "clipboard_history"
    display_name = "Clipboard History"
    input_placeholder = "Search clipboard history..."
    icon = ICON_CLIPBOARD

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        cfg = config or {}
        self._max_items: int = max(1, int(cfg.get("max_items", 30)))
        self._history_items: dict[str, Any] = {}

    @staticmethod
    def _trim(value: str, max_chars: int = 120) -> str:
        value = " ".join(value.splitlines()).strip()
        return value if len(value) <= max_chars else value[: max_chars - 1] + "..."

    @staticmethod
    def _format_time(timestamp: Any, fmt: str = "%m/%d/%Y %I:%M %p") -> str:
        try:
            dt = timestamp.datetime if hasattr(timestamp, "datetime") else timestamp
            return dt.strftime(fmt) if hasattr(dt, "strftime") else ""
        except Exception:
            return ""

    @staticmethod
    def _text_stats(text: str) -> tuple[int, int, int]:
        """Return (chars, words, lines) for a text string."""
        chars = len(text)
        words = len(text.split())
        lines = text.count("\n") + 1
        return chars, words, lines

    @staticmethod
    def _format_bytes(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    @staticmethod
    def _get_formats(content: Any) -> list[str]:
        try:
            return list(content.available_formats)
        except Exception:
            return []

    @staticmethod
    def _read_stream_bytes(stream_ref: Any) -> bytes:
        if Buffer is None or InputStreamOptions is None:
            return b""
        stream = stream_ref.open_read_async().get()
        try:
            buf = Buffer(stream.size)
            stream.read_async(buf, buf.capacity, InputStreamOptions.READ_AHEAD).get()
            return bytes(buf)
        finally:
            stream.close()

    def _read_image_bytes(self, stream_ref: Any) -> tuple[bytes, tuple[int, int]]:
        """Read bitmap stream into memory. Returns (raw_bytes, (w, h))."""
        try:
            blob = self._read_stream_bytes(stream_ref)
            if not blob:
                return b"", (0, 0)
            if Image is not None:
                with Image.open(io.BytesIO(blob)) as img:
                    return blob, img.size
            return blob, (0, 0)
        except Exception as exc:
            logging.debug("Clipboard image read failed: %s", exc)
            return b"", (0, 0)

    def _load_history(self) -> tuple[str, list[dict[str, Any]]]:
        if Clipboard is None or ClipboardHistoryItemsResultStatus is None:
            return "unavailable", []

        try:
            result = Clipboard.get_history_items_async().get()
        except Exception as exc:
            logging.debug("Clipboard history query failed: %s", exc)
            return "error", []

        status = result.status
        if status == ClipboardHistoryItemsResultStatus.ACCESS_DENIED:
            return "denied", []
        if status == ClipboardHistoryItemsResultStatus.CLIPBOARD_HISTORY_DISABLED:
            return "disabled", []
        if status != ClipboardHistoryItemsResultStatus.SUCCESS:
            return "error", []

        self._history_items.clear()
        entries: list[dict[str, Any]] = []

        for item in list(result.items)[: self._max_items]:
            item_id = str(item.id)
            content = item.content
            ts_full = self._format_time(item.timestamp)
            ts_short = self._format_time(item.timestamp, "%I:%M %p")
            formats = self._get_formats(content)
            entry: dict[str, Any] = {"id": item_id, "timestamp": ts_short}
            self._history_items[item_id] = item

            # Text
            if "Text" in formats:
                try:
                    text = content.get_text_async().get()
                    if text:
                        chars, words, lines = self._text_stats(text)
                        full_text = text.strip()
                        if len(full_text) > 1500:
                            full_text = full_text[:1499] + "..."
                        stats = f"{words} words, {chars} chars, {lines} lines"
                        has_html = "HTML Format" in formats
                        fmt_label = "Rich Text" if has_html else "Plain Text"
                        entry.update(
                            kind="text",
                            title=self._trim(text, 90),
                            description=f"{fmt_label} - {words} words",
                            icon=ICON_CLIPBOARD_TEXT,
                            preview={
                                "kind": "text",
                                "title": f"{fmt_label} - {stats}",
                                "subtitle": f"{ts_full}\nFormats: {', '.join(formats)}",
                                "text": full_text,
                            },
                        )
                        entries.append(entry)
                        continue
                except Exception:
                    pass

            # Image
            if "Bitmap" in formats:
                try:
                    stream_ref = content.get_bitmap_async().get()
                    if stream_ref:
                        blob, (w, h) = self._read_image_bytes(stream_ref)
                        dim = f"{w}x{h}" if w and h else "Unknown"
                        size_label = f" - {self._format_bytes(len(blob))}" if blob else ""
                        entry.update(
                            kind="image",
                            title=f"Image - {dim}",
                            description=f"Bitmap{size_label}",
                            icon=ICON_CLIPBOARD_IMAGE,
                            preview={
                                "kind": "image",
                                "title": f"Image - {dim}{size_label}",
                                "subtitle": f"{ts_full}\nDimension: {dim}\nFormats: {', '.join(formats)}",
                                "image_data": blob,
                            },
                        )
                        entries.append(entry)
                        continue
                except Exception:
                    pass

            # Unknown format
            entry.update(
                kind="unknown",
                title="Clipboard item",
                description="Unsupported format",
                icon=ICON_CLIPBOARD,
                preview={},
            )
            entries.append(entry)

        return "success", entries

    def _status_result(self, status: str) -> list[ProviderResult]:
        messages = {
            "disabled": (
                "Clipboard history is disabled",
                "Open Settings > System > Clipboard to enable",
                "Press Enter to open Windows Clipboard settings.",
            ),
            "denied": (
                "Clipboard access denied",
                "Try again while YASB is focused",
                "Windows denied clipboard history access in this context.",
            ),
            "unavailable": (
                "Clipboard API unavailable",
                "WinRT DataTransfer package missing or unsupported OS",
                "The WinRT clipboard API is not available.",
            ),
        }
        title, desc, _ = messages.get(
            status,
            (
                "Unable to read clipboard history",
                "Try again in a moment",
                "",
            ),
        )
        result = ProviderResult(
            title=title,
            description=desc,
            icon_char=ICON_WARNING,
            provider=self.name,
        )
        if status == "disabled":
            result.action_data = {"action": "open_settings"}
        return [result]

    def _clear_results(self) -> list[ProviderResult]:
        return [
            ProviderResult(
                title="Clear clipboard history",
                description="Delete all saved history items",
                icon_char=ICON_CLEAR,
                provider=self.name,
                action_data={"action": "clear_history"},
            )
        ]

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text).strip()
        query_lower = query.lower()

        # Clear commands
        if query_lower in {"clear", "clear all", "clear history"}:
            return self._clear_results()

        # Load history
        status, items = self._load_history()
        if status != "success":
            return self._status_result(status)

        if not items:
            return [
                ProviderResult(
                    title="Clipboard history is empty",
                    description="Copy something to start",
                    icon_char=ICON_CLIPBOARD,
                    provider=self.name,
                )
            ]

        # Filter by query
        results: list[ProviderResult] = []
        for entry in items:
            title = entry["title"]
            desc = entry["description"]
            if query_lower and query_lower not in f"{title} {desc}".lower():
                continue
            ts = entry.get("timestamp")
            time_part = f" · {ts}" if ts else ""
            results.append(
                ProviderResult(
                    title=title,
                    description=f"{desc}{time_part}",
                    icon_char=entry.get("icon", ICON_CLIPBOARD),
                    provider=self.name,
                    id=entry["id"],
                    preview=entry.get("preview", {}),
                    action_data={"action": "restore", "item_id": entry["id"]},
                )
            )

        if not results:
            return [
                ProviderResult(
                    title="No clipboard matches",
                    description="Try a different search term",
                    icon_char=ICON_CLIPBOARD,
                    provider=self.name,
                )
            ]

        # Append clear action when showing unfiltered list
        if not query:
            clear = self._clear_results()
            results = results[: self.max_results - len(clear)] + clear

        return results

    def execute(self, result: ProviderResult) -> bool:
        if Clipboard is None:
            return False

        action = result.action_data.get("action")
        try:
            if action == "clear_history":
                Clipboard.clear_history()
                return False

            if action == "open_settings":
                shell_open("ms-settings:clipboard")
                return True

            if action == "restore":
                item_id = str(result.action_data.get("item_id", ""))
                item = self._history_items.get(item_id)
                if not item:
                    # Re-load in case items were stale
                    status, _ = self._load_history()
                    if status == "success":
                        item = self._history_items.get(item_id)
                if item:
                    Clipboard.set_history_item_as_content(item)
                    return True
        except Exception as exc:
            logging.debug("Clipboard execute failed: %s", exc)
            return False

        return False

    def get_context_menu_actions(self, result: ProviderResult) -> list[ProviderMenuAction]:
        action = result.action_data.get("action")
        if action != "restore":
            return []
        actions = [ProviderMenuAction(id="copy", label="Copy to clipboard")]
        if Clipboard is not None:
            actions.append(ProviderMenuAction(id="delete", label="Delete from history", separator_before=True))
        return actions

    def execute_context_menu_action(self, action_id: str, result: ProviderResult) -> ProviderMenuActionResult:
        item_id = str(result.action_data.get("item_id", ""))
        item = self._history_items.get(item_id)

        if action_id == "copy":
            if not item:
                self._load_history()
                item = self._history_items.get(item_id)
            if item:
                try:
                    Clipboard.set_history_item_as_content(item)
                except Exception as exc:
                    logging.debug("Clipboard copy failed: %s", exc)
            return ProviderMenuActionResult(close_popup=True)

        if action_id == "delete":
            if not item:
                self._load_history()
                item = self._history_items.get(item_id)
            if item:
                try:
                    Clipboard.delete_item_from_history(item)
                except Exception as exc:
                    logging.debug("Clipboard delete failed: %s", exc)
            self._history_items.pop(item_id, None)
            return ProviderMenuActionResult(refresh_results=True)

        return ProviderMenuActionResult()
