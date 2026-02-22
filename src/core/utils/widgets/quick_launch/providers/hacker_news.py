import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from xml.etree import ElementTree

from PyQt6.QtWidgets import QApplication

from core.utils.shell_utils import shell_open
from core.utils.utilities import app_data_path
from core.utils.widgets.quick_launch.base_provider import (
    BaseProvider,
    ProviderMenuAction,
    ProviderMenuActionResult,
    ProviderResult,
)
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_HACKER_NEWS

_HNRSS_BASE = "https://hnrss.org"
_CACHE_FILE = str(app_data_path("hacker_news_cache.json"))

_TOPICS: dict[str, dict[str, str]] = {
    "frontpage": {
        "name": "Front Page",
        "description": "Top stories on Hacker News right now",
        "path": "frontpage",
    },
    "newest": {
        "name": "Newest",
        "description": "Most recently submitted stories",
        "path": "newest",
    },
    "best": {
        "name": "Best",
        "description": "Highest-voted stories overall",
        "path": "best",
    },
    "ask": {
        "name": "Ask HN",
        "description": "Questions and discussions from the community",
        "path": "ask",
    },
    "show": {
        "name": "Show HN",
        "description": "Community projects and launches",
        "path": "show",
    },
    "jobs": {
        "name": "Jobs",
        "description": "Job postings from YC companies",
        "path": "jobs",
    },
    "bestcomments": {
        "name": "Best Comments",
        "description": "Highly voted comments from across Hacker News",
        "path": "bestcomments",
    },
    "active": {
        "name": "Active",
        "description": "Posts with the most active ongoing discussions",
        "path": "active",
    },
}

_POINTS_RE = re.compile(r"Points:\s*(\d+)", re.IGNORECASE)
_COMMENTS_RE = re.compile(r"Comments:\s*(\d+)", re.IGNORECASE)

_USER_AGENT = "YASB Quick Launch HackerNews/1.0"


class HackerNewsProvider(BaseProvider):
    """Browse Hacker News stories by topic.

    Activate with the prefix (default ``hn``).
    Type the prefix alone to see available topics, then pick one to load stories.
    Append a keyword after the topic to filter, e.g. ``hn newest rust``.
    """

    name = "hacker_news"
    display_name = "Hacker News"
    icon = ICON_HACKER_NEWS
    input_placeholder = "Search Hacker News..."

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._cache: dict[str, tuple[float, list[dict]]] = {}
        self._cache_ttl: int = self.config.get("cache_ttl", 300)
        self._max_items: int = self.config.get("max_items", 30)
        self._disk_loaded = False

    def match(self, text: str) -> bool:
        if self.prefix:
            stripped = text.strip()
            return stripped == self.prefix or stripped.startswith(self.prefix + " ")
        return True

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        cancel_event = kwargs.get("cancel_event")
        query = self.get_query_text(text).strip()
        parts = query.split(None, 1)

        # No query → show topic tiles
        if not query:
            return self._topic_tiles()

        topic_key = parts[0].lower()
        keyword = parts[1].strip() if len(parts) > 1 else ""

        # Exact topic match → fetch stories
        if topic_key in _TOPICS:
            return self._fetch_topic(topic_key, keyword, cancel_event)

        # Fuzzy-filter topic list; if no topics match, search HN directly
        filtered = self._filter_topics(query)
        if filtered:
            return filtered
        return self._search_hn(query, cancel_event)

    def execute(self, result: ProviderResult) -> bool | None:
        data = result.action_data
        url = data.get("url", "")
        if url:
            shell_open(url)
            return True
        return None

    def get_context_menu_actions(self, result):

        actions: list[ProviderMenuAction] = []
        data = result.action_data
        if data.get("comments_url"):
            actions.append(ProviderMenuAction(id="open_comments", label="Open HN comments"))
        if data.get("url"):
            actions.append(ProviderMenuAction(id="copy_url", label="Copy URL"))
        return actions

    def execute_context_menu_action(self, action_id, result):

        data = result.action_data
        if action_id == "open_comments":
            url = data.get("comments_url", "")
            if url:
                shell_open(url)
            return ProviderMenuActionResult(close_popup=True)
        if action_id == "copy_url":
            url = data.get("url", "")
            if url:
                clipboard = QApplication.clipboard()
                if clipboard:
                    clipboard.setText(url)
            return ProviderMenuActionResult()
        return ProviderMenuActionResult()

    def get_query_text(self, text: str) -> str:
        """Strip prefix, handling the two-char 'hn' prefix correctly."""
        if self.prefix and text.strip().startswith(self.prefix):
            return text.strip()[len(self.prefix) :].strip()
        return text.strip()

    def _topic_tiles(self) -> list[ProviderResult]:
        results: list[ProviderResult] = []
        for key, info in _TOPICS.items():
            results.append(
                ProviderResult(
                    title=info["name"],
                    description=info["description"],
                    icon_char=ICON_HACKER_NEWS,
                    provider=self.name,
                    action_data={"_home": True, "prefix": self.prefix, "initial_text": key},
                )
            )
        return results

    def _filter_topics(self, query: str) -> list[ProviderResult]:
        q = query.lower()
        results: list[ProviderResult] = []
        for key, info in _TOPICS.items():
            if q in key or q in info["name"].lower() or q in info["description"].lower():
                results.append(
                    ProviderResult(
                        title=info["name"],
                        description=info["description"],
                        icon_char=ICON_HACKER_NEWS,
                        provider=self.name,
                        action_data={"_home": True, "prefix": self.prefix, "initial_text": key},
                    )
                )
        return results

    def _search_hn(self, query: str, cancel_event) -> list[ProviderResult]:
        """Search all of Hacker News when input doesn't match any topic."""
        return self._fetch_topic("newest", query, cancel_event)

    def _fetch_topic(self, topic: str, keyword: str, cancel_event) -> list[ProviderResult]:
        cache_key = f"{topic}:{keyword}"
        now = time.time()

        # Check in-memory cache
        if cache_key in self._cache:
            ts, items = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return self._items_to_results(items)

        # Check disk cache
        disk_items = self._load_disk_cache(cache_key)
        if disk_items is not None:
            ts, items = disk_items
            if now - ts < self._cache_ttl:
                self._cache[cache_key] = (ts, items)
                return self._items_to_results(items)

        # Fetch from network
        try:
            items = self._fetch_rss(topic, keyword, cancel_event)
            self._cache[cache_key] = (now, items)
            self._save_disk_cache(cache_key, now, items)
            return self._items_to_results(items)
        except urllib.error.URLError:
            logging.warning("Hacker News: Failed to connect, no internet or host unreachable")
        except Exception:
            logging.warning("Hacker News: Failed to load stories")
        # Fallback to stale cache
        if cache_key in self._cache:
            _, items = self._cache[cache_key]
            return self._items_to_results(items)
        return [
            ProviderResult(
                title="Failed to load stories",
                description="Check your internet connection and try again",
                icon_char=ICON_HACKER_NEWS,
                provider=self.name,
            )
        ]

    def _fetch_rss(self, topic: str, keyword: str, cancel_event) -> list[dict]:
        path = _TOPICS[topic]["path"]
        url = f"{_HNRSS_BASE}/{path}?count={self._max_items}"
        if keyword:
            url += f"&q={urllib.parse.quote(keyword)}"

        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if cancel_event and cancel_event.is_set():
                return []
            xml_data = resp.read()

        if cancel_event and cancel_event.is_set():
            return []

        root = ElementTree.fromstring(xml_data)
        items: list[dict] = []
        for item_el in root.iter("item"):
            if cancel_event and cancel_event.is_set():
                break
            title = _el_text(item_el, "title") or "Untitled"
            link = _el_text(item_el, "link") or ""
            description = _el_text(item_el, "description") or ""
            pub_date = _el_text(item_el, "pubDate") or ""
            creator = _el_text(item_el, "{http://purl.org/dc/elements/1.1/}creator") or ""
            comments_url = _el_text(item_el, "comments") or ""

            points = _extract_int(_POINTS_RE, description)
            comments = _extract_int(_COMMENTS_RE, description)

            date_str = _format_date(pub_date)

            items.append(
                {
                    "title": title,
                    "link": link,
                    "creator": creator,
                    "date": date_str,
                    "points": points,
                    "comments": comments,
                    "comments_url": comments_url,
                }
            )
        return items

    def _items_to_results(self, items: list[dict]) -> list[ProviderResult]:
        results: list[ProviderResult] = []
        for item in items:
            parts: list[str] = []
            if item["points"] is not None:
                parts.append(f"{item['points']} points")
            if item["comments"] is not None:
                parts.append(f"{item['comments']} comments")
            if item["creator"]:
                parts.append(f"by {item['creator']}")
            if item["date"]:
                parts.append(item["date"])
            desc = " \u2502 ".join(parts)

            results.append(
                ProviderResult(
                    title=item["title"],
                    description=desc,
                    icon_char=ICON_HACKER_NEWS,
                    provider=self.name,
                    action_data={
                        "url": item["link"],
                        "comments_url": item["comments_url"],
                    },
                )
            )
        return results

    def _load_disk_cache(self, cache_key: str) -> tuple[float, list[dict]] | None:
        if not self._disk_loaded:
            self._disk_loaded = True
            try:
                with open(_CACHE_FILE, encoding="utf-8") as f:
                    all_cache: dict = json.load(f)
                for key, entry in all_cache.items():
                    if key not in self._cache:
                        self._cache[key] = (entry["ts"], entry["items"])
            except FileNotFoundError, json.JSONDecodeError, KeyError:
                pass

        if cache_key in self._cache:
            return self._cache[cache_key]
        return None

    def _save_disk_cache(self, cache_key: str, ts: float, items: list[dict]) -> None:
        try:
            try:
                with open(_CACHE_FILE, encoding="utf-8") as f:
                    all_cache: dict = json.load(f)
            except FileNotFoundError, json.JSONDecodeError:
                all_cache = {}

            all_cache[cache_key] = {"ts": ts, "items": items}

            # Prune old entries
            now = time.time()
            all_cache = {k: v for k, v in all_cache.items() if now - v.get("ts", 0) < self._cache_ttl * 6}

            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(all_cache, f)
        except Exception:
            logging.debug("Failed to save Hacker News cache to disk", exc_info=True)


def _el_text(parent: ElementTree.Element, tag: str) -> str | None:
    el = parent.find(tag)
    return el.text if el is not None else None


def _extract_int(pattern: re.Pattern, text: str) -> int | None:
    m = pattern.search(text)
    return int(m.group(1)) if m else None


def _format_date(pub_date: str) -> str:
    if not pub_date:
        return ""
    try:
        # hnrss dates: "Thu, 01 Jan 2026 12:00:00 +0000"
        dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")
        now = datetime.now(timezone.utc)
        delta = now - dt
        if delta.days == 0:
            hours = delta.seconds // 3600
            if hours == 0:
                mins = delta.seconds // 60
                return f"{mins}m ago" if mins > 0 else "just now"
            return f"{hours}h ago"
        if delta.days == 1:
            return "1 day ago"
        if delta.days < 30:
            return f"{delta.days} days ago"
        return dt.strftime("%b %d, %Y")
    except Exception:
        return pub_date
