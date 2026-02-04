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

```py
self._widget_container_layout = QHBoxLayout()
self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
self._widget_container = QFrame()
self._widget_container.setLayout(self._widget_container_layout)
self.widget_layout.addWidget(self._widget_container)
```

## 4. Use **build_widget_label(self, label, label_alt, shadow)** for dynamic labels:

-   This method allows you to create labels with icons and text dynamically.

```py
from core.utils.utilities import build_widget_label
build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)
```
or without shadow and alt label:
```py
from core.utils.utilities import build_widget_label
build_widget_label(self, self._label_content, None, None)
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
             label.setCursor(Qt.CursorShape.PointingHandCursor)
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
-   `base_model.py` also contains shared models like `ShadowConfig`, `KeybindingConfig`, `CallbacksConfig`, etc.
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
-   [`CPU`](https://github.com/amnweb/yasb/blob/main/src/core/widgets/yasb/cpu.py)

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

### 9. Python Code Style

-  Follow PEP 8 guidelines
-  Use type hints where applicable
-  Write docstrings for classes and methods
-  Keep methods focused and concise
-  Comment complex logic
-  Include TODOs for future improvements

## 10. Test your widget:

-   Ensure it behaves as expected in the application.
-   Check for any errors or issues in the console.
-   Validate the widget's functionality with different configurations.
-   Ensure the widget is responsive and works well with different screen sizes.
-   Be sure that the widget does not cause any memory leaks or performance issues.
-   Use thread-safe methods for any background tasks or long-running processes.
-   Ensure that the widget does not block the main thread and remains responsive to user interactions.

## 11. Document your widget:

-   Write clear documentation for your widget, including its purpose, options, and styling.
-   Doc file should be located in `docs/` folder and linked in the main documentation and readme.

## 12. Submit PR:

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
