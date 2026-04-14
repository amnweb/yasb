# UI Components

YASB includes a built-in UI component system based on [WinUI3 design tokens](https://github.com/microsoft/microsoft-ui-xaml). These components handle theming, animations, and accessibility automatically. Use them when building widgets that need dialogs, buttons, toggles, or other interactive elements.

All components live in `src/core/ui/components/` and share the same token-based theming from `src/core/ui/tokens.py`.

## Design Tokens

The token system provides ~150 color tokens organized by theme (`dark` / `light`). Values are sourced from the WinUI3 `Common_themeresources_any.xaml`.

```python
from core.ui.theme import get_tokens, theme_key, is_dark, FONT_FAMILIES

tokens = get_tokens()          # Returns dict for current OS theme
tokens["text_primary"]         # "#ffffff" (dark) or "#e3000000" (light)
tokens["accent_fill_default"]  # "#4cc2ff" (dark) or "#0078d4" (light)
```

### Token Categories

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

## Components

### Button

Interactive button with three variants and animated state transitions.

```python
from core.ui.components.button import Button
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | `""` | Button label |
| `variant` | `str` | `"default"` | `"default"`, `"accent"`, or `"subtle"` |
| `padding` | `str \| None` | `"11,5,11,6"` | Padding as `"l,t,r,b"`, `"h,v"`, or `"all"` |
| `font_size` | `int \| None` | `14` | Font size in pixels |
| `font_weight` | `str \| None` | `"normal"` | Font weight name |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Variants:**

| Variant | Appearance |
|---------|-----------|
| `"default"` | Standard control fill background with text |
| `"accent"` | Accent-colored background with on-accent text |
| `"subtle"` | Transparent background, text only (hover shows fill) |

**Example:**

```python
save_btn = Button("Save", variant="accent", parent=self)
save_btn.setFixedHeight(32)
save_btn.clicked.connect(self._on_save)

cancel_btn = Button("Cancel", variant="default", parent=self)
cancel_btn.clicked.connect(self._on_cancel)
```

---

### TextBlock

Themed label with preset typography variants matching WinUI3 type ramp.

```python
from core.ui.components.text_block import TextBlock
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | `""` | Text content |
| `variant` | `str` | `"body"` | Typography variant |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Variants:**

| Variant | Size | Weight |
|---------|------|--------|
| `"title-large"` | 40px | DemiBold |
| `"title"` | 28px | DemiBold |
| `"subtitle"` | 20px | DemiBold |
| `"body"` | 14px | Normal |
| `"body-strong"` | 14px | DemiBold |
| `"body-secondary"` | 14px | Normal (secondary color) |
| `"caption"` | 12px | DemiBold (secondary color) |
| `"caption-strong"` | 12px | DemiBold |

**Example:**

```python
title = TextBlock("Settings", variant="subtitle", parent=self)
description = TextBlock("Configure your preferences.", variant="body-secondary", parent=self)
```

---

### ToggleSwitch

Animated on/off switch matching the WinUI3 toggle.

```python
from core.ui.components.toggle_switch import ToggleSwitch, ToggleSwitchWithLabel
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `checked` | `bool` | `False` | Initial state |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Signals:**

- `toggled(bool)` — Emitted when the switch state changes.

**Example:**

```python
toggle = ToggleSwitch(checked=False, parent=self)
toggle.toggled.connect(lambda on: print(f"Switch: {on}"))

# With label:
toggle = ToggleSwitchWithLabel(
    text="Dark Mode",
    on_text="Enabled",
    off_text="Disabled",
    checked=True,
    parent=self,
)
```

---

### Card

Selectable card container with hover and selection states.

```python
from core.ui.components.card import Card
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Methods:**

- `set_selected(selected: bool)` — Toggle the accent selection state.
- `is_selected() -> bool` — Check if currently selected.

**Example:**

```python
card = Card(parent=self)
card_layout = QVBoxLayout(card)
card_layout.addWidget(QLabel("Option A"))
card.set_selected(True)
```

---

### ContentDialog

Modal overlay dialog that centers on a parent widget with a smoke layer. Best suited for views and panels. For bar widgets, use `InputDialog` instead.

```python
from core.ui.components.content_dialog import ContentDialog, ContentDialogButton, ContentDialogResult
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `parent` | `QWidget` | — | Parent widget (dialog centers on this) |
| `title` | `str` | `""` | Dialog title |
| `content` | `str` | `""` | Body text |
| `primary_button_text` | `str` | `""` | Primary action button (hidden if empty) |
| `secondary_button_text` | `str` | `""` | Secondary action button (hidden if empty) |
| `close_button_text` | `str` | `""` | Close/cancel button (hidden if empty) |
| `default_button` | `ContentDialogButton` | `NONE` | Button focused by default |

**Signals:**

- `primary_button_click` — Primary button clicked.
- `secondary_button_click` — Secondary button clicked.
- `close_button_click` — Close button clicked.
- `closed(ContentDialogResult)` — Dialog closed with result (`PRIMARY`, `SECONDARY`, or `NONE`).

**Example:**

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

---

### InputDialog

Standalone input dialog that appears at the cursor position. Uses DWM blur and rounded corners. Does not require a parent widget — ideal for bar widgets and context menu actions.

```python
from core.ui.components.input_dialog import InputDialog
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | `str` | `""` | Dialog title |
| `content` | `str` | `""` | Descriptive text below the title |
| `text` | `str` | `""` | Initial input value |
| `placeholder` | `str` | `""` | Placeholder text |
| `primary_button_text` | `str` | `"OK"` | Accept button label |
| `close_button_text` | `str` | `"Cancel"` | Cancel button label |

**Signals:**

- `accepted(str)` — User pressed the primary button (emits trimmed text).
- `rejected()` — User cancelled or pressed Escape.

**Example:**

```python
dlg = InputDialog(
    title="Rename Desktop",
    content="Enter a new name for this desktop.",
    text="Desktop 1",
    primary_button_text="Rename",
    close_button_text="Cancel",
)
dlg.accepted.connect(lambda name: print(f"Renamed to: {name}"))
dlg.show_dialog()
```

---

### DropDown

Styled dropdown selector with a blurred popup.

```python
from core.ui.components.dropdown import DropDown
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `items` | `list[tuple[str, str]] \| None` | `None` | List of `(key, label)` pairs |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Signals:**

- `currentChanged(str)` — Emitted when selection changes (provides the key).

**Example:**

```python
dd = DropDown(
    items=[("en", "English"), ("de", "German"), ("ja", "Japanese")],
    parent=self,
)
dd.set_current("en")
dd.currentChanged.connect(lambda key: print(f"Language: {key}"))
```

---

### Slider

Horizontal slider with a value label and accent-colored track.

```python
from core.ui.components.slider import Slider
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `minimum` | `int` | `0` | Minimum value |
| `maximum` | `int` | `100` | Maximum value |
| `value` | `int` | `50` | Initial value |
| `suffix` | `str` | `"%"` | Suffix shown after value label |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Signals:**

- `valueChanged(int)` — Emitted when the value changes.

**Example:**

```python
slider = Slider(minimum=0, maximum=100, value=75, suffix="%", parent=self)
slider.valueChanged.connect(lambda v: print(f"Volume: {v}%"))
```

---

### InfoBar

Status notification bar with severity levels and corresponding icons.

```python
from core.ui.components.info_bar import InfoBar, InfoBarSeverity
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | `str` | `""` | Bold title text |
| `message` | `str` | `""` | Body message |
| `severity` | `InfoBarSeverity` | `INFORMATIONAL` | Severity level |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Severity Levels:**

| Level | Icon | Color Token |
|-------|------|-------------|
| `INFORMATIONAL` | ℹ Info | `accent_fill_default` |
| `SUCCESS` | ✓ Checkmark | `system_success` |
| `WARNING` | ! Exclamation | `system_caution` |
| `ERROR` | ✕ Cross | `system_critical` |

**Example:**

```python
bar = InfoBar(
    title="Saved",
    message="Your settings have been saved.",
    severity=InfoBarSeverity.SUCCESS,
    parent=self,
)
```

---

### StepIndicator

Animated horizontal step indicator (dot/dash style).

```python
from core.ui.components.indicator import StepIndicator
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `count` | `int` | `1` | Number of steps |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Methods:**

- `set_current(index: int)` — Animate to a step (0-indexed).

**Example:**

```python
indicator = StepIndicator(count=4, parent=self)
indicator.set_current(0)  # First step active
```

---

### Link

Hyperlink-styled button using accent text colors.

```python
from core.ui.components.link import Link
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | `""` | Link text |
| `padding` | `str \| None` | `"8,4,8,4"` | Padding as `"l,t,r,b"` |
| `font_size` | `int \| None` | `14` | Font size in pixels |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Example:**

```python
link = Link("Learn more", parent=self)
link.clicked.connect(self._open_docs)
```

---

### Loader

Two loading indicator variants: circular spinner and horizontal progress line.

```python
from core.ui.components.loader import Spinner, LoaderLine
```

#### Spinner

```python
spinner = Spinner(size=24, color="#4cc2ff", parent=self)
```

#### LoaderLine

```python
loader = LoaderLine(parent=self)
loader.attach_to_widget(target_widget)  # Auto-positions at bottom edge
loader.start()
# ...
loader.stop()
```

## Tips for Contributors

- **Always use tokens** — never hardcode colors. Use `get_tokens()` to look up the current theme values.
- **React to theme changes** — connect to `QApplication.instance().paletteChanged` and re-apply styles when the OS theme switches.
- **Use `FONT_FAMILIES`** — import from `core.ui.theme` instead of hardcoding `"Segoe UI"`.
- **Prefer existing components** — check if a component already exists before creating a new one. The system is designed to be reusable.
