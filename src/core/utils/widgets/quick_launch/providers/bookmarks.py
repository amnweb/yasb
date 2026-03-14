import json
import logging
import os
import shutil
import sqlite3
import tempfile

from core.utils.shell_utils import shell_open
from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_BOOKMARK

# Chromium-based browser data dirs relative to %LOCALAPPDATA%
_CHROMIUM_PATHS: dict[str, str] = {
    "chrome": os.path.join("Google", "Chrome", "User Data"),
    "edge": os.path.join("Microsoft", "Edge", "User Data"),
    "brave": os.path.join("BraveSoftware", "Brave-Browser", "User Data"),
    "vivaldi": os.path.join("Vivaldi", "Application", "User Data"),
    "chromium": os.path.join("Chromium", "User Data"),
}

# Firefox-based browser profile dirs relative to %APPDATA%
_FIREFOX_PATHS: dict[str, str] = {
    "firefox": os.path.join("Mozilla", "Firefox", "Profiles"),
    "zen": os.path.join("zen", "Profiles"),
}


class BookmarksProvider(BaseProvider):
    """Search and open browser bookmarks."""

    name = "bookmarks"
    display_name = "Browser Bookmarks"
    input_placeholder = "Search bookmarks..."
    icon = ICON_BOOKMARK

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._bookmarks: list[dict] = []
        self._last_mtime: dict[str, float] = {}
        self._loaded = False

    def _get_sources(self) -> list[tuple[str, str]]:
        """Return [(browser_name, filepath), ...] for bookmark files."""
        browser = self.config.get("browser", "all")

        if browser == "all":
            return self._get_all_sources()

        local = os.environ.get("LOCALAPPDATA", "")

        ff_rel = _FIREFOX_PATHS.get(browser)
        if ff_rel:
            return self._get_firefox_sources(browser, ff_rel)

        rel = _CHROMIUM_PATHS.get(browser)
        if rel:
            profile = self.config.get("profile", "Default")
            bf = os.path.join(local, rel, profile, "Bookmarks")
            if os.path.isfile(bf):
                return [(browser, bf)]
        return []

    def _get_all_sources(self) -> list[tuple[str, str]]:
        """Collect bookmark files from every supported browser found."""
        local = os.environ.get("LOCALAPPDATA", "")
        sources: list[tuple[str, str]] = []

        for browser_name, rel in _CHROMIUM_PATHS.items():
            bf = os.path.join(local, rel, "Default", "Bookmarks")
            if os.path.isfile(bf):
                sources.append((browser_name, bf))

        for name, rel in _FIREFOX_PATHS.items():
            sources.extend(self._get_firefox_sources(name, rel))
        return sources

    @staticmethod
    def _get_firefox_sources(browser_name: str, rel: str) -> list[tuple[str, str]]:
        appdata = os.environ.get("APPDATA", "")
        root = os.path.join(appdata, rel)
        sources: list[tuple[str, str]] = []
        if os.path.isdir(root):
            for p in os.listdir(root):
                db = os.path.join(root, p, "places.sqlite")
                if os.path.isfile(db):
                    sources.append((browser_name, db))
        return sources

    def _needs_reload(self, sources: list[tuple[str, str]]) -> bool:
        if not self._loaded:
            return True
        for _, fpath in sources:
            try:
                if os.path.getmtime(fpath) != self._last_mtime.get(fpath):
                    return True
            except OSError:
                pass
        return False

    def _load_bookmarks(self) -> None:
        sources = self._get_sources()
        if not self._needs_reload(sources):
            return

        bookmarks: list[dict] = []
        for browser_name, fpath in sources:
            try:
                if browser_name in _FIREFOX_PATHS:
                    parsed = self._parse_firefox(fpath)
                else:
                    parsed = self._parse_chromium(fpath)
                for bm in parsed:
                    bm["browser"] = browser_name
                bookmarks.extend(parsed)
                self._last_mtime[fpath] = os.path.getmtime(fpath)
            except OSError:
                pass

        self._bookmarks = bookmarks
        self._loaded = True

    def _parse_chromium(self, filepath: str) -> list[dict]:
        results: list[dict] = []
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            for root_name in ("bookmark_bar", "other", "synced"):
                node = data.get("roots", {}).get(root_name)
                if node:
                    self._walk_node(node, results, "")
        except Exception as e:
            logging.debug("Bookmarks: chromium parse error: %s", e)
        return results

    def _walk_node(self, node: dict, out: list[dict], folder: str) -> None:
        ntype = node.get("type")
        if ntype == "url":
            out.append(
                {
                    "title": node.get("name", ""),
                    "url": node.get("url", ""),
                    "folder": folder,
                }
            )
        elif ntype == "folder":
            name = node.get("name", "")
            sub = f"{folder}/{name}" if folder else name
            for child in node.get("children", []):
                self._walk_node(child, out, sub)

    def _parse_firefox(self, db_path: str) -> list[dict]:
        results: list[dict] = []
        tmp: str | None = None
        try:
            fd, tmp = tempfile.mkstemp(suffix=".sqlite", prefix="yasb_ff_bm_")
            os.close(fd)
            shutil.copy2(db_path, tmp)
            conn = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
            try:
                rows = conn.execute(
                    "SELECT b.title, p.url "
                    "FROM moz_bookmarks b JOIN moz_places p ON b.fk = p.id "
                    "WHERE b.type = 1 AND p.url NOT LIKE 'place:%'"
                ).fetchall()
            finally:
                conn.close()
            for title, url in rows:
                results.append({"title": title or url, "url": url, "folder": ""})
        except Exception as e:
            logging.debug("Bookmarks: firefox parse error: %s", e)
        finally:
            if tmp:
                for suffix in ("", "-shm", "-wal"):
                    try:
                        os.remove(tmp + suffix)
                    except OSError:
                        pass
        return results

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text)
        self._load_bookmarks()

        if not self._bookmarks:
            return [
                ProviderResult(
                    title="No bookmarks found",
                    description="Check browser setting in Quick Launch config",
                    icon_char=ICON_BOOKMARK,
                    provider=self.name,
                )
            ]

        if not query:
            return [self._to_result(bm) for bm in self._bookmarks[:50]]

        ql = query.lower()
        matches = [
            bm
            for bm in self._bookmarks
            if ql in (bm.get("title") or "").lower()
            or ql in (bm.get("url") or "").lower()
            or ql in (bm.get("folder") or "").lower()
        ]

        if not matches:
            return [
                ProviderResult(
                    title=f"No bookmarks matching {query}",
                    description="Try a different search",
                    icon_char=ICON_BOOKMARK,
                    provider=self.name,
                )
            ]

        return [self._to_result(bm) for bm in matches]

    def _to_result(self, bm: dict) -> ProviderResult:
        title = bm.get("title") or bm.get("url", "")
        url = bm.get("url", "")
        folder = bm.get("folder", "")
        browser = bm.get("browser", "")
        parts: list[str] = []
        if browser:
            parts.append(browser.capitalize())
        if folder:
            parts.append(folder)
        parts.append(url)
        desc = "  \u2022  ".join(parts)
        return ProviderResult(
            title=title,
            description=desc,
            icon_char=ICON_BOOKMARK,
            provider=self.name,
            action_data={"url": url},
        )

    def execute(self, result: ProviderResult) -> bool:
        url = result.action_data.get("url", "")
        if url:
            shell_open(url)
        return True
