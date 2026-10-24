# Calculator Widget

A bar widget that opens a full calculator in a popup. Supports basic arithmetic (+, −, ×, ÷), percentages, sign toggling, parentheses (via keyboard), and keyboard input while the popup is open.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `label` | string | `<span>\uf5ec</span>` | The label format displayed on the bar. |
| `label_alt` | string | `Calc` | Alternative label format that can be toggled. |
| `class_name` | string | `""` | Additional CSS class name for the widget. |
| `keybindings` | list | `[]` | Optional hotkeys. See [Keybindings](./Keybindings). |
| `callbacks` | dict | [See below](#available-callbacks) | Configure widget interaction callbacks. |
| `menu` | dict | [See below](#menu-options) | Configure the appearance of the calculator popup. |

## Available Callbacks

| Callback | Description |
|----------|-------------|
| `toggle_menu` | Open or close the calculator popup. |
| `toggle_label` | Toggle between `label` and `label_alt`. |
| `do_nothing` | Do nothing. |

## Menu Options

The `menu` option accepts the following keys. All keys are optional, the values shown are the defaults.

```yaml
menu:
  blur: true
  round_corners: true
  round_corners_type: "normal"  # "normal" or "small"
  border_color: "System"
  alignment: "right"            # "left", "center", or "right"
  direction: "down"             # "up" or "down"
  offset_top: 6
  offset_left: 0
  width: 230
```

## Keyboard Input

With the calculator popup open, you can type directly:

| Key | Action |
|-----|--------|
| `0-9` | Enter digits |
| `+ - * /` | Arithmetic operators |
| `%` | Percentage |
| `.` or `,` | Decimal point |
| `Enter` or `=` | Evaluate expression |
| `Backspace` | Delete last character |
| `Escape` | Clear all (AC) |
| `( )` | Parentheses |

## Example Configuration

```yaml
calculator:
  type: "yasb.calculator.CalculatorWidget"
  options:
    label: "<span>\uf5ec</span>"
    label_alt: "Calc"
    callbacks:
      on_left: "toggle_menu"
      on_right: "toggle_label"
    menu:
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "System"
      alignment: "right"
      direction: "down"
      offset_top: 6
      width: 230
```

## Styling

You can style the calculator popup using CSS. Here is an example with a Catppuccin Mocha-inspired theme:

```css
/* Calculator bar widget */
.widget.calculator-widget {
  padding: 2px 8px;
  margin: 0 4px;
}

/* Popup container */
.calculator-popup {
  background-color: rgba(30, 30, 46, 0.95);
  border: 1px solid rgba(108, 112, 134, 0.4);
  border-radius: 12px;
}

/* Expression (small line above result) */
.calculator-popup .expression {
  color: rgba(166, 227, 161, 0.7);
  font-size: 12px;
  padding: 0 6px;
}

/* Result display */
.calculator-popup .result {
  color: #cdd6f4;
  font-size: 24px;
  font-weight: bold;
  padding: 0 6px;
}

/* Buttons */
.calculator-popup .button {
  border: none;
  border-radius: 8px;
  font-size: 14px;
  color: #cdd6f4;
  background-color: rgba(49, 50, 68, 0.8);
}

.calculator-popup .button:hover {
  background-color: rgba(69, 71, 90, 0.9);
}

.calculator-popup .button:pressed {
  background-color: rgba(88, 91, 112, 0.9);
}

/* Number buttons */
.calculator-popup .button.number {
  background-color: rgba(49, 50, 68, 0.8);
}

/* Operator buttons */
.calculator-popup .button.operator {
  background-color: rgba(137, 180, 250, 0.25);
  color: #89b4fa;
}

.calculator-popup .button.operator:hover {
  background-color: rgba(137, 180, 250, 0.4);
}

/* Utility buttons (AC, backspace, ±, %) */
.calculator-popup .button.utility {
  background-color: rgba(249, 226, 175, 0.2);
  color: #f9e2af;
}

.calculator-popup .button.utility:hover {
  background-color: rgba(249, 226, 175, 0.35);
}

/* Clear button (AC) */
.calculator-popup .button.clear {
  background-color: rgba(243, 139, 168, 0.25);
  color: #f38ba8;
}

.calculator-popup .button.clear:hover {
  background-color: rgba(243, 139, 168, 0.4);
}

/* Equals button */
.calculator-popup .button.equals {
  background-color: rgba(166, 227, 161, 0.3);
  color: #a6e3a1;
}

.calculator-popup .button.equals:hover {
  background-color: rgba(166, 227, 161, 0.45);
}
```
