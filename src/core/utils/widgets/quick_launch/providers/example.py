"""
Example Quick Launch Provider

Copy this file, rename it, and build your own provider.
This file is NOT registered - it only exists as a starting template.


How to create your own provider

1. Copy this file and rename it (e.g. my_provider.py).
2. Rename the class and set a unique ``name``.
3. Implement get_results() and execute().
4. Register it in three places:

   a) providers/__init__.py - add a wildcard import:

       from .my_provider import *

   b) service.py - add the class to PROVIDER_REGISTRY:

       "my_provider": MyProvider,

   c) core/validation/widgets/yasb/quick_launch.py - add a config model:

       class MyProviderConfig(CustomBaseModel):
           enabled: bool = True
           prefix: str = "!"
           priority: int = 0

      Then add it to QuickLaunchProvidersConfig:

       my_provider: MyProviderConfig = MyProviderConfig()


What's required

    name            Class attribute. Unique string that ties results back to your
                    provider. Must match the config key.

    get_results()   Return a list of ProviderResult for the given search text.
                    Runs on a background thread - do NOT touch Qt widgets here.
                    The **kwargs parameter is required in the signature.

    execute()       Called when the user picks a result.
                    Return True to close the popup, False to refresh results,
                    or None to do nothing (e.g. an edit form is shown).


What's optional

    Class attributes:
        display_name       Label shown on the home page shortcut tile.
        icon               Inline SVG string for the home page tile.
        input_placeholder  Placeholder text when the prefix is active.

    After super().__init__() you get:
        self.config        Raw dict from the user's YAML config.
        self.prefix        Prefix string, or None when set to "*".
        self.priority      Sort weight (lower = higher in the list).
        self.max_results   Global result cap. Usually you don't need this - the
                           service trims results automatically. Useful when you
                           query an external API that accepts a limit.

    Helper method:
        self.get_query_text(text)   Strips the prefix from the raw query string.
                                    Always use this instead of parsing the prefix yourself.

    Refresh from outside a query:
        Call self.request_refresh() to re-trigger the current search, for example
        after loading data in the background.


ProviderResult fields

    title         Required. Main text shown for the result.
    provider      Required. Set to self.name so the service knows the owner.
    description   Optional. Secondary line below the title.
    icon_path     Optional. Path to an image file (.png, .ico, .bmp, etc).
    icon_char     Optional. Inline SVG string (or a single emoji/glyph as
                  fallback). Used when icon_path is empty.
    id            Optional. Unique identifier. Needed for late-loaded icons.
    action_data   Optional. Dict passed back to execute() when the user picks
                  this result. If it contains a "path" key with a file path,
                  the result becomes draggable (the user can drag it into
                  Explorer, media players, etc).
    preview       Optional. Dict that shows a preview pane on the right side.
                  See "Preview pane" below.
    css_class     Optional. Extra CSS class(es) added to the item. The widget
                  always adds "item provider-<name>" automatically.


Preview pane

    Shows on the right side when the selected result has a non-empty preview dict.

    Text preview:
        preview = {
            "kind": "text",
            "title": "Heading",
            "subtitle": "Line 1\\nLine 2",
            "text": "Scrollable text content.",
        }

    Image preview:
        preview = {
            "kind": "image",
            "title": "Image title",
            "subtitle": "Extra info",
            "image_data": b"<raw PNG/BMP bytes>",
        }

    Inline edit form:
        preview = {
            "kind": "edit",
            "fields": [
                {"id": "name", "type": "text", "label": "Name:", "placeholder": "...", "value": ""},
                {"id": "body", "type": "multiline", "label": "Content:", "placeholder": "...", "value": ""},
            ],
            "action": "save_item",
        }

    When the user clicks Save, the widget calls handle_preview_action(action_id,
    result, data) on your provider with the collected field values. Look at the
    snippets provider for a full working example.


Context menu

    Override get_context_menu_actions() to add a right-click menu to results.
    Return a list of ProviderMenuAction(id, label, enabled, separator_before).
    The widget builds a QMenu from these and calls execute_context_menu_action()
    when the user picks one.

    execute_context_menu_action() returns ProviderMenuActionResult with two flags:
        refresh_results   Re-run the search so results update (e.g. after delete).
        close_popup       Dismiss the popup (e.g. after opening something).


Cancellation

    The service passes cancel_event (a threading.Event) through **kwargs.
    For quick lookups you don't need to worry about it, but if your provider
    does something slow (network call, big file scan), check it periodically:

        cancel_event = kwargs.get("cancel_event")
        for item in slow_source:
            if cancel_event and cancel_event.is_set():
                break


Tips

    - Keep get_results() fast. Users expect results as they type.
    - Don't import Qt widgets at the top of your provider file unless you
      need them in execute(). The search runs on a thread where Qt widget
      access is not safe.
    - Use action_data to pass whatever execute() needs - URLs, file paths,
      IDs, etc.
    - If action_data contains a "path" key pointing to a real file, the
      result automatically becomes draggable.
    - You can add custom settings to your config model (api_key, max_items,
      etc.) and read them from self.config in __init__.
"""

from core.utils.shell_utils import shell_open
from core.utils.widgets.quick_launch.base_provider import (
    BaseProvider,
    ProviderMenuAction,
    ProviderMenuActionResult,
    ProviderResult,
)
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_EXAMPLE


class ExampleProvider(BaseProvider):
    """A tiny provider that searches a hardcoded list and opens URLs.

    Activate with the prefix (default ``#``), e.g. ``# docs`` or ``# github``.
    """

    # Required class attributes
    name = "example"  # unique key - must match the config key
    display_name = "Example"  # shown on the home page shortcut
    icon = ICON_EXAMPLE  # inline SVG shown on the home page tile

    # Optional class attributes
    input_placeholder = "Search examples..."  # placeholder when prefix is active

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        # After super().__init__() you get for free:
        #   self.config   – raw dict from the YAML config
        #   self.prefix   – prefix string, or None when set to "*"
        #   self.priority – sort weight (lower = higher in the list)

        # A simple hardcoded data source. Yours could be a file, API, DB, etc.
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

    # Required: get_results
    # Runs on a BACKGROUND THREAD - never touch Qt widgets here.
    # **kwargs is required; the service passes cancel_event through it.
    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text).lower()

        # No query -> show a friendly hint
        if not query:
            return [
                ProviderResult(
                    title="Example provider",
                    description="Type something to search",
                    icon_char=ICON_EXAMPLE,
                    provider=self.name,
                )
            ]

        # Filter the list
        results: list[ProviderResult] = []
        for item in self._items:
            if query in item["title"].lower() or query in item["description"].lower():
                results.append(
                    ProviderResult(
                        title=item["title"],
                        description=item["description"],
                        icon_char=ICON_EXAMPLE,
                        provider=self.name,
                        action_data={"url": item["url"]},
                    )
                )
        return results

    # Required: execute
    # Called when the user selects a result (Enter or click).
    # Return True  -> close the popup
    # Return False -> keep the popup open and refresh results
    # Return None  -> do nothing (useful for inline edit forms)
    def execute(self, result: ProviderResult) -> bool | None:
        url = result.action_data.get("url", "")
        if url:
            shell_open(url)
            return True
        return False

    # Optional: context menu
    # Right-click menu on a result. Skip these two methods if you don't need one.
    def get_context_menu_actions(self, result: ProviderResult) -> list[ProviderMenuAction]:
        url = result.action_data.get("url", "")
        if not url:
            return []
        return [
            ProviderMenuAction(id="open_url", label="Open in browser"),
            ProviderMenuAction(id="copy_url", label="Copy URL"),
        ]

    def execute_context_menu_action(self, action_id: str, result: ProviderResult) -> ProviderMenuActionResult:
        url = result.action_data.get("url", "")
        if action_id == "open_url" and url:
            shell_open(url)
            return ProviderMenuActionResult(close_popup=True)
        if action_id == "copy_url" and url:
            from PyQt6.QtWidgets import QApplication

            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(url)
            return ProviderMenuActionResult()
        return ProviderMenuActionResult()
