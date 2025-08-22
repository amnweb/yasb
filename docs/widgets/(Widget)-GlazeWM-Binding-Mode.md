# GlazeWM Binding Mode Widget

| Option           | Type     | Default                        | Description                                                                 |
|------------------|----------|--------------------------------|-----------------------------------------------------------------------------|
| `label`             | string  | `'<span>{icon}</span> {binding_mode}'` | The format string for the binding mode. You can use a placeholder `{binding_mode}` to dynamically insert active binding_mode. |
| `label_alt`         | string  | `'<span>{icon}</span> Current mode: {binding_mode}'` | The alternative format string for the binding mode. |
| `glazewm_server_uri` | string | `'ws://localhost:6123'` | Optional GlazeWM server uri. |
| `hide_if_no_active` | boolean  | `true` | Hide the widget when no binding mode is active. |
| `label_if_no_active` | string | `"No binding mode active"` | Label to display when no binding mode is active. |
| `default_icon` | string | `'\uf071'` | Default icon for the binding modes where no other icon is specified. |
| `icons` | dict | `{'none': '', 'resize': '\uf071', 'pause': '\uf28c'}` | Specified icons for each Binding Mode; if a binding mode is not specified then the `default_icon` will be used. |
| `binding_modes_to_cycle_through` | list | `['none', 'resize', 'pause']` | Binding Mode names to cycle through with callbacks `next_binding_mode` and `prev_binding_mode` |
| `callbacks` | dict | `{'on_left': 'next_binding_mode', 'on_middle': 'toggle_label', 'on_right': 'disable_binding_mode'}` | Callbacks for mouse events on the widget. |
| `animation` | dict | `{'enabled': true, 'type': 'fadeInOut', 'duration': 200}` | Animation settings for the widget. |
| `container_shadow` | dict   | `None` | Container shadow options. |
| `label_shadow` | dict | `None` | Label shadow options. |

## Example Configuration

```yaml
glazewm_binding_mode:
    type: "glazewm.binding_mode.GlazewmBindingModeWidget"
    options:
      hide_if_no_active: false
      label_if_no_active: "No binding mode active"
      default_icon: "\uf071"
      icons: 
        none: ""
        resize: "\uf071"
        pause: "\uf28c"
      binding_modes_to_cycle_through: [
        "none", # none handles if no binding mode is active
        "resize",
        "pause"
      ]
      callbacks:
        on_left: "next_binding_mode"
        on_middle: "toggle_label"
        on_right: "disable_binding_mode"

    # By default binding mode names are fetched from GlazeWM and "display_name" option takes priority over "name".
```

## Description of Options
- **label:** The format string for the binding mode. You can use a placeholder `{binding_mode}` to dynamically insert active binding_mode.
- **label_alt:** The alternative format string for the binding mode.
- **glazewm_server_uri:** Optional GlazeWM server uri if it ever changes on GlazeWM side.
- **hide_if_no_active:** Hide the widget when no binding mode is active.
- **label_if_no_active:** Label to display when no binding mode is active.
- **default_icon:** Default icon for the binding modes where no other icon is defined.
- **icons:** A dictionary mapping binding mode names to their respective icons. The keys are the binding mode names, and the values are the icon strings. If no icon is defined for a binding mode, the `default_icon` will be used. `'none'` represents no binding mode active.
- **binding_modes_to_cycle_through:** Binding Mode names to cycle through with callbacks `next_binding_mode` and `prev_binding_mode`. Use `'none'` to handle no binding mode active.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
  - **callback functions**:
    - `toggle_label`: Toggles the label of the widget.
    - `do_nothing`: Does nothing when clicked.
    - `disable_binding_mode`: Disables the binding mode when clicked.
    - `next_binding_mode`: Switches to the next binding mode.
    - `prev_binding_mode`: Switches to the previous binding mode.
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

.glazewm-binding-mode .label-offline {
}

.glazewm-binding-mode .icon.none {
}

.glazewm-binding-mode .icon.pause {
}

.glazewm-binding-mode .icon.resize {
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

.glazewm-binding-mode .label-offline {
    color: var(--subtext0);
    font-size: 10px;
}

.glazewm-binding-mode .icon.none {
    color: var(--blue);
}

.glazewm-binding-mode .icon.resize {
    color: var(--yellow);
}

.glazewm-binding-mode .icon.pause {
    color: var(--red);
}
```