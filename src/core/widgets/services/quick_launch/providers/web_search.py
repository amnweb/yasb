from core.utils.shell_utils import shell_open
from core.widgets.services.quick_launch.base_provider import BaseProvider, ProviderResult
from core.widgets.services.quick_launch.providers.resources.icons import (
    ICON_WEB_BING,
    ICON_WEB_BRAVE,
    ICON_WEB_DUCKDUCKGO,
    ICON_WEB_GITHUB,
    ICON_WEB_GOOGLE,
    ICON_WEB_REDDIT,
    ICON_WEB_SEARCH,
    ICON_WEB_STACKOVERFLOW,
    ICON_WEB_WIKIPEDIA,
    ICON_WEB_X_TWITTER,
    ICON_WEB_YOUTUBE,
)

_ENGINES = {
    "google": {
        "name": "Google",
        "url": "https://www.google.com/search?q={}",
        "icon": ICON_WEB_GOOGLE,
        "description": "Search the web with Google",
    },
    "bing": {
        "name": "Bing",
        "url": "https://www.bing.com/search?q={}",
        "icon": ICON_WEB_BING,
        "description": "Search the web with Bing",
    },
    "brave": {
        "name": "Brave",
        "url": "https://search.brave.com/search?q={}",
        "icon": ICON_WEB_BRAVE,
        "description": "Private web search with Brave",
    },
    "duckduckgo": {
        "name": "DuckDuckGo",
        "url": "https://duckduckgo.com/?q={}",
        "icon": ICON_WEB_DUCKDUCKGO,
        "description": "Private web search",
    },
    "wikipedia": {
        "name": "Wikipedia",
        "url": "https://en.wikipedia.org/w/index.php?search={}",
        "icon": ICON_WEB_WIKIPEDIA,
        "description": "Search Wikipedia articles",
    },
    "github": {
        "name": "GitHub",
        "url": "https://github.com/search?q={}",
        "icon": ICON_WEB_GITHUB,
        "description": "Search GitHub repositories and code",
    },
    "youtube": {
        "name": "YouTube",
        "url": "https://www.youtube.com/results?search_query={}",
        "icon": ICON_WEB_YOUTUBE,
        "description": "Search YouTube videos",
    },
    "reddit": {
        "name": "Reddit",
        "url": "https://www.reddit.com/search/?q={}",
        "icon": ICON_WEB_REDDIT,
        "description": "Search Reddit posts and communities",
    },
    "x": {
        "name": "X (Twitter)",
        "url": "https://twitter.com/search?q={}",
        "icon": ICON_WEB_X_TWITTER,
        "description": "Search X (formerly Twitter) posts",
    },
    "stackoverflow": {
        "name": "Stack Overflow",
        "url": "https://stackoverflow.com/search?q={}",
        "icon": ICON_WEB_STACKOVERFLOW,
        "description": "Search programming Q&A",
    },
}


class WebSearchProvider(BaseProvider):
    """Search the web using multiple search engines.

    The configured engine appears first in the results list,
    followed by all remaining engines so the user can pick any of them.
    """

    name = "web_search"
    display_name = "Web Search"
    input_placeholder = "Search the web..."
    icon = ICON_WEB_SEARCH

    def __init__(self, config=None):
        super().__init__(config)
        custom_engines = self.config.get("custom_engines")
        engines_to_remove = self.config.get("remove_engines")
        if custom_engines.count is not None:
            for engine in custom_engines:
                _ENGINES[engine["engine"]] = engine
        if engines_to_remove is not None:
            for engine in engines_to_remove:
                _ENGINES.pop(engine, None)

    def match(self, text: str) -> bool:
        if self.prefix:
            return text.strip().startswith(self.prefix)
        return True

    def _ordered_engines(self) -> list[tuple[str, dict]]:
        """Return engines with the preferred one first."""
        preferred = self.config.get("engine", "google")
        ordered: list[tuple[str, dict]] = []
        for key, info in _ENGINES.items():
            if key == preferred:
                ordered.insert(0, (key, info))
            else:
                ordered.append((key, info))
        return ordered

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text)
        engines = self._ordered_engines()

        if not query:
            preferred_name = engines[0][1]["name"] if engines else "the web"
            return [
                ProviderResult(
                    title=f"Search {preferred_name}...",
                    description="Type your search query",
                    icon_char=ICON_WEB_SEARCH,
                    provider=self.name,
                )
            ]

        results: list[ProviderResult] = []
        for key, info in engines:
            icon = info["icon"]
            results.append(
                ProviderResult(
                    title=f'Search {info["name"]} for "{query}"',
                    description=info["description"],
                    icon_char=ICON_WEB_SEARCH if not icon else icon,
                    provider=self.name,
                    action_data={"query": query, "engine": key},
                )
            )
        return results

    def execute(self, result: ProviderResult) -> bool:
        query = result.action_data.get("query", "")
        engine = result.action_data.get("engine", "google")
        engine_info = _ENGINES.get(engine, _ENGINES["google"])
        if query:
            from urllib.parse import quote_plus

            shell_open(engine_info["url"].format(quote_plus(query)))
        return True
