import json
import logging
import os
import sqlite3
import urllib.parse
from pathlib import Path

from core.utils.shell_utils import shell_open
from core.utils.widgets.quick_launch.base_provider import (
    BaseProvider,
    ProviderResult,
)
from core.utils.widgets.quick_launch.fuzzy import fuzzy_score
from core.utils.widgets.quick_launch.providers.resources.icons import (
    ICON_CODE,
    ICON_FILE,
    ICON_FOLDER,
    ICON_IMAGE,
    ICON_TEXT,
    ICON_VSCODE,
)
from core.utils.win32.constants import SW_HIDE

_EXT_ICON_MAP: dict[str, str] = {}
for _icon, _exts in (
    (
        ICON_TEXT,
        (".txt", ".log", ".md", ".rtf", ".csv", ".ini", ".cfg", ".yaml", ".yml", ".toml", ".json", ".xml", ".env"),
    ),
    (
        ICON_IMAGE,
        (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico"),
    ),
    (
        ICON_CODE,
        (
            ".py",
            ".pyw",
            ".js",
            ".mjs",
            ".cjs",
            ".d.ts",
            ".ts",
            ".tsx",
            ".jsx",
            ".c",
            ".cpp",
            ".cc",
            ".cxx",
            ".h",
            ".hpp",
            ".cs",
            ".java",
            ".class",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".html",
            ".htm",
            ".css",
            ".scss",
            ".sass",
            ".less",
            ".sh",
            ".bash",
            ".zsh",
            ".bat",
            ".cmd",
            ".ps1",
            ".psm1",
            ".psd1",
            ".sql",
            ".vue",
            ".svelte",
            ".dart",
            ".swift",
            ".kt",
            ".kts",
        ),
    ),
):
    for _ext in _exts:
        _EXT_ICON_MAP[_ext] = _icon


def _get_vscode_icon(name: str, is_folder: bool) -> str:
    if is_folder:
        return ICON_FOLDER
    ext = os.path.splitext(name)[1].lower()
    return _EXT_ICON_MAP.get(ext, ICON_FILE)


class VSCodeProvider(BaseProvider):
    """Search and launch recently opened projects and files in VSCode."""

    name = "vscode"
    display_name = "VSCode"
    input_placeholder = "Search VSCode recents..."
    icon = ICON_VSCODE

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._db_path = os.path.expandvars(r"%APPDATA%\Code\User\globalStorage\state.vscdb")

    def _get_recents(self) -> list[dict]:
        if not os.path.exists(self._db_path):
            return []

        try:
            uri = f"file:{self._db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM ItemTable WHERE key = 'history.recentlyOpenedPathsList'")
            row = cursor.fetchone()
            conn.close()

            if row and row[0]:
                data = json.loads(row[0])
                if "entries" in data:
                    return data["entries"]
        except Exception as e:
            logging.error(f"Failed to read VSCode recents: {e}")

        return []

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text).lower()
        cancel_event = kwargs.get("cancel_event")

        recents = self._get_recents()
        results: list[ProviderResult] = []

        scored_items = []

        for entry in recents:
            if cancel_event and cancel_event.is_set():
                break

            uri = entry.get("fileUri") or entry.get("folderUri") or (entry.get("workspace", {}).get("configPath"))
            if not uri:
                continue

            is_folder = "folderUri" in entry or "workspace" in entry

            unquoted = urllib.parse.unquote(uri)
            if unquoted.startswith("file:///"):
                unquoted = unquoted[8:]
            elif unquoted.startswith("vscode-remote://"):
                unquoted = unquoted.replace("vscode-remote://", "")

            path = Path(unquoted)
            name = entry.get("label") or path.name

            score = 0
            if query:
                query_words = query.split()
                path_lower = str(path).lower()
                name_lower = name.lower()

                # Fuzzy scores
                fs_name = fuzzy_score(query, name)
                fs_path = fuzzy_score(query, str(path))

                # If query has spaces, try without spaces for subsequence match
                query_no_spaces = query.replace(" ", "")
                fs_name_ns = fuzzy_score(query_no_spaces, name)
                fs_path_ns = fuzzy_score(query_no_spaces, str(path))

                highest_fs = max((fs_name or 0), (fs_path or 0), (fs_name_ns or 0) - 0.5, (fs_path_ns or 0) - 0.5)

                # Check keyword matching
                has_all_words = all(word in name_lower or word in path_lower for word in query_words)
                has_exact = query in name_lower or query in path_lower

                if highest_fs > 0:
                    score = highest_fs
                elif has_exact:
                    score = 2.5
                elif has_all_words:
                    score = 1.0
                else:
                    continue

            scored_items.append((score, is_folder, uri, unquoted, path, name))

        if query:
            # Sort by score descending, then keep original recency order
            scored_items.sort(key=lambda x: x[0], reverse=True)

        for score, is_folder, uri, unquoted, path, name in scored_items:
            action_data = {
                "uri": uri,
                "is_folder": is_folder,
            }

            icon = _get_vscode_icon(name, is_folder)

            results.append(
                ProviderResult(
                    title=name,
                    description=str(path),
                    icon_char=icon,
                    provider=self.name,
                    action_data=action_data,
                )
            )

            if len(results) >= self.max_results:
                break

        return results

    def execute(self, result: ProviderResult) -> bool | None:
        uri = result.action_data.get("uri")
        is_folder = result.action_data.get("is_folder")
        if not uri:
            return False

        try:
            flag = "--folder-uri" if is_folder else "--file-uri"
            shell_open("code", parameters=f"{flag} {uri}", show_cmd=SW_HIDE)
            return True
        except Exception as e:
            logging.error(f"Failed to open VSCode: {e}")
            return False
