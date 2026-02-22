from core.utils.shell_utils import shell_open
from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult
from core.utils.widgets.quick_launch.providers.resources.icons import (
    ICON_BING,
    ICON_DUCKDUCKGO,
    ICON_GITHUB,
    ICON_GOOGLE,
    ICON_REDDIT,
    ICON_STACKOVERFLOW,
    ICON_WEB_SEARCH,
    ICON_WIKIPEDIA,
    ICON_X_TWITTER,
    ICON_YOUTUBE,
)

_ENGINES = {
    "google": {
        "name": "Google",
        "url": "https://www.google.com/search?q={}",
        "icon": ICON_GOOGLE,
        "description": "Search the web with Google",
    },
    "bing": {
        "name": "Bing",
        "url": "https://www.bing.com/search?q={}",
        "icon": ICON_BING,
        "description": "Search the web with Bing",
    },
    "duckduckgo": {
        "name": "DuckDuckGo",
        "url": "https://duckduckgo.com/?q={}",
        "icon": ICON_DUCKDUCKGO,
        "description": "Private web search",
    },
    "wikipedia": {
        "name": "Wikipedia",
        "url": "https://en.wikipedia.org/w/index.php?search={}",
        "icon": ICON_WIKIPEDIA,
        "description": "Search Wikipedia articles",
    },
    "github": {
        "name": "GitHub",
        "url": "https://github.com/search?q={}",
        "icon": ICON_GITHUB,
        "description": "Search GitHub repositories and code",
    },
    "youtube": {
        "name": "YouTube",
        "url": "https://www.youtube.com/results?search_query={}",
        "icon": ICON_YOUTUBE,
        "description": "Search YouTube videos",
    },
    "reddit": {
        "name": "Reddit",
        "url": "https://www.reddit.com/search/?q={}",
        "icon": ICON_REDDIT,
        "description": "Search Reddit posts and communities",
    },
    "x": {
        "name": "X (Twitter)",
        "url": "https://twitter.com/search?q={}",
        "icon": ICON_X_TWITTER,
        "description": "Search X (formerly Twitter) posts",
    },
    "stackoverflow": {
        "name": "Stack Overflow",
        "url": "https://stackoverflow.com/search?q={}",
        "icon": ICON_STACKOVERFLOW,
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
            results.append(
                ProviderResult(
                    title=f'Search {info["name"]} for "{query}"',
                    description=info["description"],
                    icon_char=info["icon"],
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
