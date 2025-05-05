# GlazeWM Binding Mode Widget

| Option           | Type     | Default                        | Description                                                                 |
|------------------|----------|--------------------------------|-----------------------------------------------------------------------------|
| `label`             | string  | `'<span>\uf071</span> {binding_mode}'` | The format string for the binding mode. You can use a placeholder `{binding_mode}` to dynamically insert active binding_mode. |
| `label_alt`         | string  | `'<span>\uf071</span> Current mode: {binding_mode}'` | The alternative format string for the binding mode. |
| `glazewm_server_uri` | string | `'ws://localhost:6123'` | Optional GlazeWM server uri. |
| `hide_if_no_active` | boolean  | `True` | Hide the widget when no binding mode is active. |
| `label_if_no_active` | string | `"No binding mode active"` | Label to display when no binding mode is active. |
| `container_padding` | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}` | Explicitly set padding inside widget container. |
| `callbacks` | dict | `{'on_left': 'disable_binding_mode', 'on_middle': 'do_nothing', 'on_right': 'toggle_lable'}` | Callbacks for mouse events on the widget. |
| `animation` | dict | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}` | Animation settings for the widget. |
| `container_shadow` | dict   | `None` | Container shadow options. |
| `label_shadow` | dict | `None` | Label shadow options. |

## Example Configuration

```yaml
glazewm_binding_mode:
    type: "glazewm.binding_mode.GlazewmBindingModeWidget"
    options:
      hide_if_no_active: false
      label_if_no_active: "No binding mode active"
      container_padding:
        top: 0
        left: 0
        bottom: 0
        right: 0
      callbacks:
        on_left: "disable_binding_mode"
        on_middle: "do_nothing"
        on_right: "toggle_label"

    # By default binding mode names are fetched from GlazeWM and "display_name" option takes priority over "name".
```

## Description of Options
- **label:** The format string for the binding mode. You can use a placeholder `{binding_mode}` to dynamically insert active binding_mode.
- **label_alt:** The alternative format string for the binding mode.
- **glazewm_server_uri:** Optional GlazeWM server uri if it ever changes on GlazeWM side.
- **hide_if_no_active:** Hide the widget when no binding mode is active.
- **label_if_no_active:** Label to display when no binding mode is active.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
  - **callback functions**:
    - `toggle_label`: Toggles the label of the widget.
    - `do_nothing`: Does nothing when clicked.
    - `disable_binding_mode`: Disables the binding mode when clicked.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.

## Note on Binding Mode Names
If you need a custom name for each binding mode - use "display_name".

**Example:**

```yaml
binding_modes:
  - name: "resize"
    display_name: "Resize mode"
    keybindings:
        # ...
  - name: "pause"
    display_name: "Paused mode"
    keybindings:
      # ...
  # and so on...
```

## Example Style
```css
.glazewm-binding-mode {
}

.glazewm-binding-mode .label {
}

.glazewm-binding-mode .icon {
}
```

## Example Style for the Binding Mode Widget

```css
.glazewm-binding-mode {
    background-color: var(--crust);
    margin: 4px 0;
    border-radius: 12px;
    border: 0;
}

.glazewm-binding-mode .label {
    color: var(--text);
    font-size: 12px;
}

.glazewm-binding-mode .icon {
    color: var(--red);
}
```