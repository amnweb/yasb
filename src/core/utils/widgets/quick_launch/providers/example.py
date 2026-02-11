"""
Example Quick Launch Provider
==============================

A minimal working provider you can use as a starting point for your own.
Just copy this file, rename the class, and wire it up - the rest is up to you.

Note: this provider is intentionally *not* registered in the service. It exists
purely as a reference. You won't find it in PROVIDER_REGISTRY or in the
validation config, and that's by design.

How to create your own provider
-------------------------------
1. Copy this file and give it a meaningful name (e.g. my_provider.py).
2. Rename the class and set a unique name (used as the config key).
3. Implement get_results() and execute() - that's the core of it.
4. Optionally override match() if you need custom logic for when your
   provider should respond to a query. The default checks for a prefix match,
   which works for most cases.
5. Register it in service.py:
   - Import your class at the top.
   - Add an entry to PROVIDER_REGISTRY, e.g.::

       "my_provider": MyProvider,

6. Add a config model in core/validation/widgets/yasb/quick_launch.py::

       class MyProviderConfig(CustomBaseModel):
           enabled: bool = True
           prefix: str = "!"  # or "*" for no prefix
           priority: int = 0

7. Add your new config to QuickLaunchProvidersConfig::

       my_provider: MyProviderConfig = MyProviderConfig()


Configuration fields (available to every provider via self.config):
    - enabled  (bool)   - Whether this provider is active.
    - prefix   (string) - The trigger character. Use "*" if the
                              provider should always participate (no prefix).
    - priority (int)    - Sort weight. Lower values appear first when
                              multiple providers return results.

ProviderResult fields:
    - title       - Main text shown for the result.
    - description - Secondary line below the title (optional).
    - icon_path   - Absolute path to an image file (optional). If your
                        data source provides icons (e.g. app shortcuts), use
                        this. When empty, icon_char is used instead.
    - icon_char   - A single glyph for a font icon, typically from Segoe
                        Fluent Icons (optional).
    - id          - Optional unique identifier for the result. Useful if
                        you need to track or deduplicate items.
    - provider    - Set this to self.name so the widget knows which
                        provider owns the result.
    - action_data - An arbitrary dict that gets passed back to
                        execute() when the user picks this result. Put
                        anything you'll need there - URLs, paths, flags, etc.

Good to know:
    - get_results() runs on a background thread, not on the main UI thread.
      Avoid touching Qt widgets directly in there. Anything you return will be
      safely handed back to the UI by the service.
    - If you ever need to refresh the result list from outside a query (say,
      after launching an external process), call self.request_refresh()
      to re-trigger the current search. The service wires this up for you
      automatically — no extra imports needed.
"""

import webbrowser

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult

_ICON_EXAMPLE = "\ue8a7"


class ExampleProvider(BaseProvider):
    """Searches a small hardcoded list and opens URLs.

    Activate by typing the prefix (default #) followed by a query,
    e.g. #docs or #github.
    """

    # This must be unique across all providers - it's used as the config key
    # and to identify which provider a result belongs to.
    name = "example"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        # After super().__init__, you have access to:
        #   self.config   - the raw config dict
        #   self.prefix   - the resolved prefix (None when "*")
        #   self.priority - sort weight
        #
        # Pull any custom settings you defined in your config model:
        # self._api_key = self.config.get("api_key", "")

        # Your data source - could be an API, a local file, a database, etc.
        self._items = [
            {
                "title": "YASB Documentation",
                "description": "Official wiki and guides",
                "url": "https://github.com/amnweb/yasb/wiki",
            },
            {
                "title": "YASB GitHub Repository",
                "description": "Source code and issues",
                "url": "https://github.com/amnweb/yasb",
            },
            {
                "title": "Python Documentation",
                "description": "Official Python docs",
                "url": "https://docs.python.org/3/",
            },
        ]

    # -- You can override match() if you need custom activation logic.
    # The default version (from BaseProvider) checks if the input starts
    # with your prefix, which is usually all you need. Override it when
    # your provider should match based on patterns, regex, etc.
    #
    # def match(self, text: str) -> bool:
    #     return text.strip().startswith("some_pattern")

    def get_results(self, text: str) -> list[ProviderResult]:
        """Return matching results for the search text.

        text is the raw input from the search field, prefix included.
        Call self.get_query_text(text) to strip the prefix and whitespace.

        This method runs on a background thread, so don't touch any Qt
        widgets here. Just return your results and the service takes care
        of the rest.
        """
        query = self.get_query_text(text).lower()

        # Nothing typed yet - show a placeholder / hint
        if not query:
            return [
                ProviderResult(
                    title="Example provider",
                    description="Type a search term to filter the list",
                    icon_char=_ICON_EXAMPLE,
                    provider=self.name,
                )
            ]

        # Filter items by query
        results: list[ProviderResult] = []
        for item in self._items:
            if query in item["title"].lower() or query in item["description"].lower():
                results.append(
                    ProviderResult(
                        title=item["title"],
                        description=item["description"],
                        # Use icon_char for a font glyph (Segoe Fluent Icons).
                        # If your data has real images, use icon_path instead:
                        #   icon_path="C:/path/to/icon.png",
                        icon_char=_ICON_EXAMPLE,
                        provider=self.name,
                        # Stash whatever execute() will need later
                        action_data={"url": item["url"]},
                    )
                )
        return results

    def execute(self, result: ProviderResult) -> bool:
        """Called when the user picks a result.

        Return True to close the popup afterwards.
        Return False to keep it open - useful when you want the user to
        stay in the launcher (e.g. toggling something, copying to clipboard).
        """
        url = result.action_data.get("url", "")
        if url:
            webbrowser.open(url)
            return True  # Close popup
        return False  # Keep popup open
