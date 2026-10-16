# Writing a New Widget

## 1. Create a class that inherits from the base widget class:

```py
class MyWidget(BaseWidget):
    validation_schema = MyWidgetConfig
    def __init__(self, config: MyWidgetConfig):
        super().__init__(class_name="my-widget")
        # Your initialization code here
```

## 2. Define options, callbacks, and layout:

-   Constructor only accepts one parameter: `config`.
-   `config` is a Pydantic `BaseModel` defined in `src/core/validation/widgets/`.
-   Handle animations, container padding, or special keys.

## 3. Set up the widget container and layout:

Use the `_init_container()` method inherited from `BaseWidget` to create the standard container:

```py
self._init_container()
```

This creates `self._widget_container_layout` (QHBoxLayout), `self._widget_container` (QFrame with class `"widget-container"`), adds it to `self.widget_layout`, and initializes `self._widgets` and `self._widgets_alt` as empty lists.

## 4. Use **self.build_widget_label(label, label_alt)** for dynamic labels:

-   This method (inherited from `BaseWidget`) allows you to create labels with icons and text dynamically.

```py
self.build_widget_label(self.config.label, self.config.label_alt)
```
or without alt label:
```py
self.build_widget_label(self.config.label, None)
```

-   Full signature:

```py
self.build_widget_label(
    content,
    content_alt=None,
    label_placeholder=None,
    hide_icons=False,
)
```

-   `content`: the primary label string. It can contain `<span>` elements, usually for icons.
-   `content_alt`: the optional alternative label string, hidden until you toggle it.
-   `label_placeholder`: text shown in the text labels until real data arrives.
-   `hide_icons`: hide the icon labels.

How the string is turned into labels:

1. The string is split at `<span>...</span>` elements.
2. A span becomes a `QLabel` with the text inside it. Its CSS class comes from the span's `class` attribute and defaults to `icon`.
3. Any other text becomes a `QLabel` with the class `label` (`label alt` for `content_alt`).
4. All labels are center-aligned and added to the widget container layout. Cursors and other visuals are styled with CSS, not set in code.
5. Labels from `content` are stored in `self._widgets` and shown. Labels from `content_alt` are stored in `self._widgets_alt` and hidden.

## 5. Create validation schema for your widget options:

-   validation files are located in `src/core/validation/widgets/`
-   `validation_schema` is Pydantic model that inherits from `CustomBaseModel` located in `src/core/validation/widgets/base_model.py`
-   `strict` typing is required for all fields in the validation model. Otherwise, Pydantic validation will fail.
-   main validation model name should be in the format of `<WidgetName>Config` for example `CpuConfig` or `BrightnessConfig`.
-   secondary validation models (also inherited from `CustomBaseModel`) must use the format `<WidgetName><FieldName>Config`, for example `BrightnessProgressBarConfig` or `NotesMenuConfig`.
-   model class names must be unique across the whole project. Deprecations in `src/core/validation/deprecation.py` are scoped by class name, so two widgets sharing a name like `MenuConfig` would silently apply each other's deprecated fields. Unique names also keep the generated `schema.json` readable.
-   `base_model.py` also contains shared models like `KeybindingConfig`, `CallbacksConfig`, etc.
-   if custom defaults are required for those shared models then a new secondary model should be defined and it should inherit from on of those base shared models.
-   mutable defaults are accepted in Pydantic models (for example `keybindings: list[KeybindingConfig] = []`). `default_factory` is not required unless specifically needed in that case.

```py
from core.validation.widgets.yasb.my_widget import MyWidgetConfig

class MyWidget(BaseWidget):
    validation_schema = MyWidgetConfig
```

```py
# Secondary model inheriting from CustomBaseModel
class BrightnessProgressBarConfig(CustomBaseModel):
    enabled: bool = False
    size: int = Field(default=18, ge=8, le=64)
    thickness: int = Field(default=3, ge=1, le=10)
    color: str | list[str] = "#00C800"
    background_color: str = "#3C3C3C"
    position: str = "left"
    animation: bool = True

# Secondary model inheriting from shared CallbacksConfig
class BrightnessCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_label"

# Main model inheriting from CustomBaseModel
class BrightnessConfig(CustomBaseModel):
    label: str = "{icon}"
    label_alt: str = "Brightness {percent}%"
    progress_bar: BrightnessProgressBarConfig = BrightnessProgressBarConfig()
    callbacks: BrightnessCallbacksConfig = BrightnessCallbacksConfig()
    keybindings: list[KeybindingConfig] = [] # <-- Mutable defaults are accepted in Pydantic models
    # other fields...
```

For more information on Pydantic models refer to the [Pydantic documentation](https://docs.pydantic.dev/latest/usage/models/).

## 6. Use real-world examples for reference:

-   [`CustomWidget`](https://github.com/amnweb/yasb/blob/main/src/core/widgets/yasb/custom.py)
-   [`ApplicationsWidget`](https://github.com/amnweb/yasb/blob/main/src/core/widgets/yasb/applications.py)
-   [`HomeWidget`](https://github.com/amnweb/yasb/blob/main/src/core/widgets/yasb/home.py)
-   [`CpuWidget`](https://github.com/amnweb/yasb/blob/main/src/core/widgets/yasb/cpu.py)

## 7. Register callbacks and methods:

```py
self.register_callback("toggle_label", self._toggle_label)
```

-   Implement your logic within these callbacks.

## 8. Reference your new widget in your configuration:

```yaml
my_widget:
    type: "yasb.my_widget.MyWidget"
    options:
        label: "<span>\ue71a</span>"
```

## 9. Using `PopupWidget` for dropdown menus

`PopupWidget` is in `core.utils.utilities`. It creates a frameless popup window with a fade animation. You attach it to a bar widget and it closes when the user clicks outside or switches to another window.

### Constructor options

```py
PopupWidget(
    parent,                         # the bar widget this popup belongs to
    blur=False,                     # enable blur background
    round_corners=False,            # round the window corners
    round_corners_type="normal",    # "normal" or "small"
    border_color="None",            # border colour string, "None", or "System"
    dark_mode=False,                # dark mode hint for the blur effect
    persistent=False,               # keep widget in memory on close instead of deleting it
    pinnable=False,                 # allow the popup to be pinned open and dragged
)
```

| Option | Default | Notes |
|---|---|---|
| `blur` | `False` | Blur effect |
| `round_corners` | `False` | Rounded window corners |
| `persistent` | `False` | Widget is hidden on close, not destroyed - good for popups that are expensive to build |
| `pinnable` | `False` | Uses the `Tool` window type so the popup is not auto-dismissed by Qt. Enables `set_pinned(bool)` |

### Example 1 - Basic popup

Build the popup, add your content, call `adjustSize()` and `setPosition()`, then `show()`.

```py
from PyQt6.QtWidgets import QLabel, QVBoxLayout
from core.utils.utilities import PopupWidget

def show_menu(self):
    self._menu = PopupWidget(
        self,
        blur=self.config.menu.blur,
        round_corners=self.config.menu.round_corners,
        round_corners_type=self.config.menu.round_corners_type,
        border_color=self.config.menu.border_color,
    )
    self._menu.setProperty("class", "my-menu")

    layout = QVBoxLayout(self._menu)
    layout.addWidget(QLabel("Hello from popup"))

    self._menu.adjustSize()
    self._menu.setPosition(
        alignment=self.config.menu.alignment,   # "left", "right", or "center"
        direction=self.config.menu.direction,   # "down" or "up"
        offset_left=self.config.menu.offset_left,
        offset_top=self.config.menu.offset_top,
    )
    self._menu.show()
```

The popup closes when the user clicks outside it or switches to another window.

### Example 2 - Persistent popup

Use `persistent=True` when building the popup is slow (network calls, heavy layout, etc.) and you want to reuse the same widget instead of rebuilding it each time.

```py
def show_menu(self):
    # build once, reuse afterwards
    if not hasattr(self, "_menu") or self._menu is None:
        self._menu = PopupWidget(
            self,
            blur=self.config.menu.blur,
            round_corners=self.config.menu.round_corners,
            round_corners_type=self.config.menu.round_corners_type,
            border_color=self.config.menu.border_color,
            persistent=True,
        )
        self._menu.setProperty("class", "my-menu")
        layout = QVBoxLayout(self._menu)
        self._label = QLabel("Loading...")
        layout.addWidget(self._label)

    # refresh content before showing
    self._label.setText("Updated content")
    self._menu.adjustSize()
    self._menu.setPosition(
        alignment=self.config.menu.alignment,
        direction=self.config.menu.direction,
        offset_left=self.config.menu.offset_left,
        offset_top=self.config.menu.offset_top,
    )
    self._menu.show()
```

### Example 3 - Pinnable popup

Use `pinnable=True` when you want a pin button that keeps the popup open. When pinned the popup ignores outside clicks and can be dragged by the user. When unpinned it goes back to closing normally on outside click or focus loss - no flickering or rebuilding happens.

```py
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from core.utils.utilities import PopupWidget, refresh_widget_style
from core.utils.tooltip import set_tooltip

def show_menu(self):
    self._menu = PopupWidget(
        self,
        blur=self.config.menu.blur,
        round_corners=self.config.menu.round_corners,
        round_corners_type=self.config.menu.round_corners_type,
        border_color=self.config.menu.border_color,
        pinnable=True,
    )
    self._menu.setProperty("class", "my-menu")

    main_layout = QVBoxLayout(self._menu)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    # header with title on the left and pin button on the right
    header = QFrame()
    header.setProperty("class", "header")
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(0, 0, 0, 0)
    header_layout.setSpacing(0)

    title = QLabel("My Widget")
    title.setProperty("class", "text")
    header_layout.addWidget(title)
    header_layout.addStretch()

    pin_btn = QPushButton("\ueb8a")   # pin icon
    pin_btn.setCheckable(True)
    pin_btn.setProperty("class", "pin-btn")
    set_tooltip(pin_btn, "Pin this window")

    def on_pin_toggled(checked: bool):
        pin_btn.setText("\ueb8b" if checked else "\ueb8a")
        pin_btn.setProperty("class", "pin-btn pinned" if checked else "pin-btn")
        set_tooltip(
            pin_btn,
            "Unpin this window" if checked else "Pin this window",
        )
        refresh_widget_style(pin_btn)
        self._menu.set_pinned(checked)

    pin_btn.toggled.connect(on_pin_toggled)
    header_layout.addWidget(pin_btn)
    main_layout.addWidget(header)

    main_layout.addWidget(QLabel("Popup content here"))

    self._menu.adjustSize()
    self._menu.setPosition(
        alignment=self.config.menu.alignment,
        direction=self.config.menu.direction,
        offset_left=self.config.menu.offset_left,
        offset_top=self.config.menu.offset_top,
    )
    self._menu.show()
```

When `pinnable=True`:

| State | Click outside | Window loses focus | Drag |
|---|---|---|---|
| `set_pinned(False)` | closes | closes | no |
| `set_pinned(True)` | stays open | stays open | yes |

`set_pinned()` does nothing when `pinnable=False`, so it is safe to call it from a generic callback without checking first.

## 10. Showing app, window and file icons

Use `IconService` for every app, window, process or file icon. It loads icons on its own thread, keeps them in memory and picks the right picture for the size, so a widget never calls Windows icon functions itself.

Say where the icon comes from with one of these:

| Source | For |
|---|---|
| `WindowIcon(hwnd)` | An open window: the icon the window shows, as on the Windows taskbar. |
| `ProcessIcon(pid)` | Any running process: the icon of the program it runs, or of its Store app. A process of another account, such as a system service, gives the icon of one of its windows, else the default app icon. |
| `AppIcon(aumid)` | An app by its App User Model ID, as listed in `shell:AppsFolder`: Store apps and desktop apps such as `MSEdge`. An unknown ID gives the default app icon. |
| `FileIcon(path)` | A file, folder or shortcut, or a shell item such as `shell:::{20D04FE0-3AEA-1069-A2D8-08002B30309D}` (This PC). |

Use the source that matches what the widget shows:

-   A button or row for an open window, as in the taskbar, window switcher and workspace widgets: `WindowIcon(hwnd)`. A window can show an icon of its own, such as an Explorer window showing the folder it is in, so do not use its process instead.
-   Something that has a process but no window, such as an app in the volume mixer or a program listening on a port: `ProcessIcon(pid)`.
-   An app known by its ID, such as a pinned Store app or an app from `shell:AppsFolder`: `AppIcon(aumid)`.
-   Something the user opens from a path, such as a Start menu shortcut, a pinned folder or an exe: `FileIcon(path)`. Pass the shortcut itself, not its target: a shortcut can have an icon of its own.

```py
from core.utils.icons.service import IconService, WindowIcon

class MyWidget(BaseWidget):
    def __init__(self, config: MyWidgetConfig):
        super().__init__(class_name="my-widget")
        ...
        self._icons = IconService.instance()
        self._icons.icons_changed.connect(self._update_icon)

    def _update_icon(self):
        pixmap = self._icons.get_icon(WindowIcon(self._hwnd), 16, self.devicePixelRatioF())
        if pixmap is not None:
            self._icon_label.setPixmap(pixmap)
```

-   `get_icon(source, size, dpr, grayscale=False)` returns a `QPixmap` at once: the icon when it is in memory, otherwise a transparent pixmap of the same size while it loads, so the widget keeps its size. `icons_changed` is emitted when the icon is ready, and the widget asks again. Use the same method to show the icon and to handle `icons_changed`, as above.
-   `get_icon` returns `None` only when there is no icon to show: a size of 0, or a source that names nothing, such as `ProcessIcon(0)` or `AppIcon("")`.
-   `size` is in logical pixels, like the `icon_size` options. `dpr` is the screen's device pixel ratio: `self.devicePixelRatioF()` or `self.screen().devicePixelRatio()`.
-   Do not keep your own icon cache. Asking again is cheap, and the service notices when a window handle or process ID is reused by another app.
-   `preload(sources, size, dpr)` loads icons the widget will show later, such as the items of a popup, after the icons widgets show now.
-   `grayscale=True` returns a gray version, for example for a muted app.
-   Call these from the UI thread.

To save an icon to a file, for example when the user adds an app, use `load_icon(source, size).image` from `core.utils.icons.sources`. It returns a PIL image and waits for Windows, so do not call it while painting or on a timer.

## 11. Python Code Style

-  Format and lint with Ruff, see [Contributing](./Contributing) for the commands.
-  Add type hints. Pyright runs in strict mode.
-  Keep methods focused and concise.

## 12. Test your widget:

-   Ensure it behaves as expected in the application.
-   Check for any errors or issues in the console.
-   Validate the widget's functionality with different configurations.
-   Ensure the widget is responsive and works well with different screen sizes.
-   Be sure that the widget does not cause any memory leaks or performance issues.
-   Use thread-safe methods for any background tasks or long-running processes.
-   Ensure that the widget does not block the main thread and remains responsive to user interactions.

## 13. Document your widget:

-   Write clear documentation for your widget, including its purpose, options, and styling.
-   Doc file should be located in `docs/` folder and linked in the main documentation and readme.

## 14. Submit PR:

-   Once your widget is complete and tested, submit a pull request to the main repository.
-   Ensure that your code follows the project's coding standards and guidelines.
-   Include a description of your changes and any relevant information for reviewers.
-   Address any feedback or changes requested by reviewers.
-   Use clear, descriptive commit messages
-   Ensure your code is well-documented and follows the project's coding standards.
-   Include tests for your widget if applicable.
-   If your PR contains multiple commits, they should be squashed into a single commit before merging
-   The final commit message should summarize the entire change, not individual development steps
-   Be responsive to feedback and make requested changes promptly.
