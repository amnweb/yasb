# UI Components

YASB includes a built-in UI component system based on [WinUI3 design tokens](https://github.com/microsoft/microsoft-ui-xaml). These components handle theming, animations, and accessibility automatically. Use them when building widgets that need dialogs, buttons, toggles, or other interactive elements.

All components live in `src/core/ui/components/` and share the same token-based theming from `src/core/ui/tokens.py`.

## Components

| Component | Import | Description |
|-----------|--------|-------------|
| [Button](#button) | `core.ui.components.button` | Button with `default`, `accent` and `subtle` variants. |
| [DropDownButton](#dropdownbutton) | `core.ui.components.drop_down_button` | Button that opens a menu of actions. |
| [Link](#link) | `core.ui.components.link` | Hyperlink-style button. |
| [TextBlock](#textblock) | `core.ui.components.text_block` | Label with preset typography variants. |
| [TextBox](#textbox) | `core.ui.components.text_box` | Single-line text input with optional icon. |
| [ToggleSwitch](#toggleswitch) | `core.ui.components.toggle_switch` | On/off switch, with or without a text label. |
| [Slider](#slider) | `core.ui.components.slider` | Horizontal slider with a value label. |
| [DropDown](#dropdown) | `core.ui.components.dropdown` | Selector with a popup list. |
| [Card](#card) | `core.ui.components.card` | Container with hover and selection states. |
| [InfoBar](#infobar) | `core.ui.components.info_bar` | Inline notification with a severity icon. |
| [ContentDialog](#contentdialog) | `core.ui.components.content_dialog` | Modal dialog with up to three buttons. |
| [InputDialog](#inputdialog) | `core.ui.components.input_dialog` | Modal dialog with a text field. |
| [StepIndicator](#stepindicator) | `core.ui.components.indicator` | Dash-style step indicator. |
| [Loader](#loader) | `core.ui.components.loader` | `Spinner` and `LoaderLine` loading indicators. |

Every constructor takes an optional `parent` argument. Signatures below list the arguments in order, with their defaults.

### Button

```python
Button(
    text="",
    variant="default",
    padding=None,
    font_family=None,
    font_size=None,
    font_weight=None,
    parent=None,
)
```

- `variant`: `"default"`, `"accent"` or `"subtle"`.
- `padding`: `"l,t,r,b"`, `"h,v"` or `"all"`. Default `"11,5,11,6"`.
- `font_family`: comma-separated family names.
- `font_size`: pixel size. Default `14`.
- `font_weight`: `"thin"`, `"light"`, `"normal"`, `"medium"`, `"demibold"` or `"bold"`.
- Methods: `set_variant(variant)`, plus the usual `setIcon()` and `setIconSize()`.

```python
save_btn = Button("Save", variant="accent", parent=self)
save_btn.clicked.connect(self._on_save)
```

### DropDownButton

A `Button` that opens a menu of actions.

```python
DropDownButton(
    text="",
    icon_svg=None,
    items=None,
    variant="default",
    chevron=True,
    parent=None,
)
```

- `icon_svg`: SVG markup drawn in the button's text color.
- `items`: a list of `(key, label)` or `(key, label, icon_svg)` tuples. Use `None` for a separator.
- `chevron`: draw the down arrow that marks the button as a menu.
- Signal: `triggered(str)` with the `key` of the chosen item.

```python
menu = DropDownButton(
    "Actions",
    items=[("copy", "Copy"), ("paste", "Paste"), None, ("clear", "Clear")],
    parent=self,
)
menu.triggered.connect(lambda key: print(key))
```

### Link

```python
Link(
    text="",
    padding=None,
    font_family=None,
    font_size=None,
    font_weight=None,
    parent=None,
)
```

- `padding`: same format as `Button`. Default `"8,4,8,4"`.
- `font_size` defaults to `14` and `font_weight` to `"normal"`.
- It is a `QPushButton`, so connect to `clicked`.

### TextBlock

```python
TextBlock(text="", variant="body", parent=None)
```

| Variant | Size | Weight |
|---------|------|--------|
| `"title-large"` | 40px | DemiBold |
| `"title"` | 28px | DemiBold |
| `"subtitle"` | 20px | DemiBold |
| `"body"` | 14px | Normal |
| `"body-strong"` | 14px | DemiBold |
| `"body-secondary"` | 14px | Normal, secondary color |
| `"caption"` | 12px | DemiBold, secondary color |
| `"caption-strong"` | 12px | DemiBold |

Methods: `set_color_override(color)` and `reset_color()`.

### TextBox

```python
TextBox(
    text="",
    placeholder="",
    icon_svg=None,
    icon_position="left",
    height=32,
    parent=None,
)
```

- `icon_position`: `"left"` or `"right"`.
- It is a `QLineEdit`, so `text()`, `textChanged` and the other `QLineEdit` API work as usual.

### ToggleSwitch

```python
ToggleSwitch(checked=False, label=None, parent=None)
ToggleSwitchWithLabel(
    text="",
    checked=False,
    on_text=None,
    off_text=None,
    parent=None,
)
```

- `ToggleSwitch` is a `QAbstractButton`: use `isChecked()` and the `toggled(bool)` signal.
- `ToggleSwitchWithLabel` shows a text next to the switch. `on_text` and `off_text` replace `text` depending on the state. It has `isChecked()`, `setChecked(value)` and the `toggled` signal.

```python
toggle = ToggleSwitchWithLabel(
    text="Dark Mode",
    on_text="Enabled",
    off_text="Disabled",
    checked=True,
    parent=self,
)
toggle.toggled.connect(lambda on: print(on))
```

### Slider

```python
Slider(minimum=0, maximum=100, value=50, suffix="%", step=1, parent=None)
```

- Signals: `valueChanged(int)`, and `labelClicked()` when the value label is clicked.
- Methods: `value()` and `set_value(v)`.

### DropDown

```python
DropDown(items=None, parent=None, *, align_selected=True)
```

- `items`: a list of `(key, label)` tuples.
- `align_selected`: align the popup so the selected item sits over the button.
- Signal: `currentChanged(str)` with the `key` of the new selection.
- Methods: `set_current(key)` and `current()`.

```python
dd = DropDown(items=[("en", "English"), ("de", "German")], parent=self)
dd.set_current("en")
dd.currentChanged.connect(lambda key: print(key))
```

### Card

```python
Card(parent=None, hover=True)
```

- `hover`: light up under the cursor. Leave it on for a card the user can click, turn it off for a plain container.
- Methods: `set_selected(selected)` and `is_selected()`.

### InfoBar

```python
InfoBar(
    title="",
    message="",
    severity=InfoBarSeverity.INFORMATIONAL,
    parent=None,
)
```

- `severity`: `InfoBarSeverity.INFORMATIONAL`, `SUCCESS`, `WARNING` or `ERROR`. Import `InfoBarSeverity` from `core.ui.components.info_bar`.
- Methods: `set_severity(severity)`, `set_title(title)` and `set_message(message)`.

### ContentDialog

Modal dialog that centers on its parent behind a smoke layer.

```python
ContentDialog(
    parent,
    title="",
    content="",
    primary_button_text="",
    secondary_button_text="",
    close_button_text="",
    default_button=ContentDialogButton.NONE,
)
```

- A button with empty text is hidden.
- `default_button`: `ContentDialogButton.NONE`, `PRIMARY`, `SECONDARY` or `CLOSE`.
- Signals: `primary_button_click`, `secondary_button_click`, `close_button_click`, `opened` and `closed(ContentDialogResult)`. The result is `ContentDialogResult.NONE`, `PRIMARY` or `SECONDARY`.
- Methods: `show_dialog()`, `hide_dialog()`, `set_title(text)`, `set_content(text)`, `set_content_widget(widget)`, `result()`, and `primary_button()`, `secondary_button()`, `close_button()` to reach the buttons.

```python
dlg = ContentDialog(
    parent=self,
    title="Delete Item?",
    content="This action cannot be undone.",
    primary_button_text="Delete",
    close_button_text="Cancel",
    default_button=ContentDialogButton.PRIMARY,
)
dlg.primary_button_click.connect(self._delete_item)
dlg.show_dialog()
```

### InputDialog

Modal dialog with a text field. It centers on its parent window behind a smoke layer and uses the same open and close animation as `ContentDialog`. A parent is required.

```python
InputDialog(
    title="",
    content="",
    text="",
    placeholder="",
    primary_button_text="OK",
    close_button_text="Cancel",
    parent=None,
)
```

- Signals: `accepted(str)` with the entered text, and `rejected()`.
- Methods: `show_dialog()`, `hide_dialog()`, `text()` and `input_widget()`.

```python
dlg = InputDialog(
    parent=self,
    title="Rename",
    content="Enter a new name.",
    text="Desktop 1",
    primary_button_text="Rename",
)
dlg.accepted.connect(lambda name: print(name))
dlg.show_dialog()
```

### StepIndicator

```python
StepIndicator(count=1, parent=None)
```

Method: `set_current(index)`.

### Loader

```python
Spinner(size=24, color="#FFFFFF", pen_width=None, parent=None)
LoaderLine(parent=None, color=None)
```

- `Spinner` is a circular indeterminate spinner. Method: `set_color(color)`.
- `LoaderLine` is a sliding line at the bottom edge of a widget:
  - `attach_to_widget(widget)` and `detach_from_widget()`.
  - `start()` and `stop()`.
  - `set_color(color)`.
  - `configure(class_name=None, duration_ms=None, easing=None, segment_ratio=None, height=None, color=None)`.

```python
loader = LoaderLine(parent=self)
loader.attach_to_widget(target_widget)
loader.start()
# ...
loader.stop()
```

## Design Tokens

The token system provides 89 color tokens per theme (`dark` and `light`). Values are sourced from the WinUI3 `Common_themeresources_any.xaml`.

```python
from core.ui.theme import get_tokens, theme_key, is_dark, FONT_FAMILIES

tokens = get_tokens()          # Returns dict for current OS theme
tokens["text_primary"]         # "#ffffff" (dark) or "#e3000000" (light)
tokens["accent_fill_default"]  # "#4cc2ff" (dark) or "#0078d4" (light)
```

| Category | Common Tokens | Usage |
|----------|---------------|-------|
| **Text Fill** | `text_primary`, `text_secondary`, `text_tertiary`, `text_disabled` | Label and body text |
| **Accent Fill** | `accent_fill_default`, `accent_fill_secondary`, `accent_fill_tertiary` | Primary actions, highlights |
| **Control Fill** | `control_fill_default`, `control_fill_secondary`, `control_fill_input_active` | Input backgrounds, buttons |
| **Control Stroke** | `control_stroke_default`, `control_stroke_secondary`, `divider_stroke_default` | Borders, dividers |
| **Card** | `card_bg_default`, `card_stroke_default` | Card backgrounds and borders |
| **Subtle Fill** | `subtle_fill_secondary`, `subtle_fill_tertiary` | Hover/pressed for subtle buttons |
| **Solid Background** | `solid_bg_base`, `solid_bg_secondary`, `solid_bg_tertiary` | Window and panel backgrounds |
| **System** | `system_success`, `system_caution`, `system_critical` | Status indicators |
| **Layer** | `layer_default`, `layer_alt` | Section backgrounds |

## Theme Reactivity

All components respond to OS theme changes automatically. To make your own widget theme-reactive:

```python
from core.ui.theme import get_tokens, theme_key

class MyWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._theme_key = theme_key()
        self._apply_styles()
        QApplication.instance().paletteChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self):
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        self._apply_styles()

    def _apply_styles(self):
        tokens = get_tokens()
        self.setStyleSheet(f"color: {tokens['text_primary']};")
```

## Tips for Contributors

- **Always use tokens** - never hardcode colors. Use `get_tokens()` to look up the current theme values.
- **React to theme changes** - connect to `QApplication.instance().paletteChanged` and re-apply styles when the OS theme switches.
- **Use `FONT_FAMILIES`** - import from `core.ui.theme` instead of hardcoding `"Segoe UI"`.
- **Prefer existing components** - check if a component already exists before creating a new one. The system is designed to be reusable.
