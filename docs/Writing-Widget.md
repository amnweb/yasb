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

-   Or use a custom function if needed - the **build_widget_label()** method:

```py
 """
 This method creates dynamic QLabel widgets from text content that may include HTML span elements.

 # Parameters
 - `content` (str): The primary content string to display, which may contain HTML spans with class attributes.
 - `content_alt` (str): An alternative content string to create hidden labels for later use.

 # Behavior
 1. The method parses both content strings, splitting them at span tags.
 2. For each part:
     - If it's a span element, it extracts the class name and text content.
     - If it's plain text, it creates a standard label with class "label".
 3. All labels are:
     - Center-aligned
     - Given a pointing hand cursor
     - Added to the widget container layout
 4. Labels from `content` are visible by default.
 5. Labels from `content_alt` are hidden by default.

 # Returns
 The method stores two lists as instance variables:
 - `self._widgets`: Visible labels created from the primary content
 - `self._widgets_alt`: Hidden labels created from the alternative content
 """

 def build_widget_label(self, content: str, content_alt: str):
     def process_content(content, is_alt=False):
         label_parts = re.split('(<span.*?>.*?</span>)', content)
         label_parts = [part for part in label_parts if part]
         widgets = []
         for part in label_parts:
             part = part.strip()
             if not part:
                 continue
             if '<span' in part and '</span>' in part:
                 class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                 class_result = class_name.group(2) if class_name else 'icon'
                 icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                 label = QLabel(icon)
                 label.setProperty("class", class_result)
             else:
                 label = QLabel(part)
                 label.setProperty("class", "label")
             label.setAlignment(Qt.AlignmentFlag.AlignCenter)
             self._widget_container_layout.addWidget(label)
             widgets.append(label)
             if is_alt:
                 label.hide()
             else:
                 label.show()
         return widgets
     self._widgets = process_content(content)
     self._widgets_alt = process_content(content_alt, is_alt=True)
```

## 5. Create validation schema for your widget options:

-   validation files are located in `src/core/validation/widgets/`
-   `validation_schema` is Pydantic model that inherits from `CustomBaseModel` located in `src/core/validation/widgets/base_model.py`
-   `strict` typing is required for all fields in the validation model. Otherwise, Pydantic validation will fail.
-   main validation model name should be in the format of `<WidgetName>Config` for example `CpuConfig` or `BrightnessConfig`.
-   secondary validation models (also inherited from `CustomBaseModel`) can be named arbitrarily, but it's recommended to use `<FieldName>Config` for consistency.
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
class ProgressBarConfig(CustomBaseModel):
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
    progress_bar: ProgressBarConfig = ProgressBarConfig()
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
        animation:
            enabled: true
            type: "fadeInOut"
            duration: 200
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
        set_tooltip(pin_btn, "Unpin this window" if checked else "Pin this window")
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

### 10. Python Code Style

-  Follow PEP 8 guidelines
-  Use type hints where applicable
-  Write docstrings for classes and methods
-  Keep methods focused and concise
-  Comment complex logic
-  Include TODOs for future improvements

## 11. Test your widget:

-   Ensure it behaves as expected in the application.
-   Check for any errors or issues in the console.
-   Validate the widget's functionality with different configurations.
-   Ensure the widget is responsive and works well with different screen sizes.
-   Be sure that the widget does not cause any memory leaks or performance issues.
-   Use thread-safe methods for any background tasks or long-running processes.
-   Ensure that the widget does not block the main thread and remains responsive to user interactions.

## 12. Document your widget:

-   Write clear documentation for your widget, including its purpose, options, and styling.
-   Doc file should be located in `docs/` folder and linked in the main documentation and readme.

## 13. Submit PR:

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
