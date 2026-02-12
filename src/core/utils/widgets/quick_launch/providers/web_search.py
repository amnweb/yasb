import webbrowser

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult

_ENGINES = {
    "google": {
        "name": "Google",
        "url": "https://www.google.com/search?q={}",
        "icon": "\ue774",
        "description": "Search the web with Google",
    },
    "bing": {
        "name": "Bing",
        "url": "https://www.bing.com/search?q={}",
        "icon": "\uf6fa",
        "description": "Search the web with Bing",
    },
    "duckduckgo": {
        "name": "DuckDuckGo",
        "url": "https://duckduckgo.com/?q={}",
        "icon": "\uea18",
        "description": "Private web search",
    },
    "wikipedia": {
        "name": "Wikipedia",
        "url": "https://en.wikipedia.org/w/index.php?search={}",
        "icon": "\ue82d",
        "description": "Search Wikipedia articles",
    },
    "github": {
        "name": "GitHub",
        "url": "https://github.com/search?q={}",
        "icon": "\ue943",
        "description": "Search GitHub repositories and code",
    },
    "youtube": {
        "name": "YouTube",
        "url": "https://www.youtube.com/results?search_query={}",
        "icon": "\ue714",
        "description": "Search YouTube videos",
    },
    "reddit": {
        "name": "Reddit",
        "url": "https://www.reddit.com/search/?q={}",
        "icon": "\ue8f2",
        "description": "Search Reddit posts and communities",
    },
    "stackoverflow": {
        "name": "Stack Overflow",
        "url": "https://stackoverflow.com/search?q={}",
        "icon": "\ue897",
        "description": "Search programming Q&A",
    },
}


class WebSearchProvider(BaseProvider):
    """Search the web using multiple search engines.

    The configured engine appears first in the results list,
    followed by all remaining engines so the user can pick any of them.
    """

    name = "web_search"

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

    def get_results(self, text: str) -> list[ProviderResult]:
        query = self.get_query_text(text)
        engines = self._ordered_engines()

        if not query:
            preferred_name = engines[0][1]["name"] if engines else "the web"
            return [
                ProviderResult(
                    title=f"Search {preferred_name}...",
                    description="Type your search query",
                    icon_char="\ue774",
                    provider=self.name,
                )
            ]

        results: list[ProviderResult] = []
        for key, info in engines:
            results.append(
                ProviderResult(
                    title=f"Search {info['name']} for \u201c{query}\u201d",
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

            webbrowser.open(engine_info["url"].format(quote_plus(query)))
        return True
