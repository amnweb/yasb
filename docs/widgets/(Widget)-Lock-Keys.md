# Lock Keys Widget Configuration

Displays the current Caps Lock and Num Lock states on the bar. The widget checks the Windows keyboard toggle state at a short interval and updates only when a state changes.

## Options

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `label` | string | `"{caps_lock} {num_lock}"` | Primary label. Supports `{caps_lock}` and `{num_lock}`. |
| `label_alt` | string | `"Caps: {caps_lock} Num: {num_lock}"` | Alternate label shown by the `toggle_label` callback. |
| `update_interval` | integer | `200` | How often to check the states, in milliseconds. Allowed range: 50–5000. |
| `class_name` | string | `""` | Additional CSS class for this widget. |
| `state_labels` | dictionary | See below | Text displayed for each on/off state. |
| `callbacks` | dictionary | `on_left: toggle_label` | Mouse callbacks for the widget. |

### State labels

| Option | Default |
| :--- | :--- |
| `caps_lock_on` | `"CAPS"` |
| `caps_lock_off` | `""` |
| `num_lock_on` | `"NUM"` |
| `num_lock_off` | `""` |

The state labels may contain text, symbols, or icon-font characters. Empty off-state labels make the indicator visible only while the corresponding lock is enabled.

## Example configuration

```yaml
lock_keys:
  type: "yasb.lock_keys.LockKeysWidget"
  options:
    label: "{caps_lock} {num_lock}"
    label_alt: "Caps: {caps_lock} | Num: {num_lock}"
    update_interval: 200
    state_labels:
      caps_lock_on: "CAPS ON"
      caps_lock_off: "caps off"
      num_lock_on: "NUM ON"
      num_lock_off: "num off"
    callbacks:
      on_left: "toggle_label"
      on_middle: "do_nothing"
      on_right: "do_nothing"
```

## Style

The widget container always has one Caps Lock class and one Num Lock class:

- `caps-lock-on` or `caps-lock-off`
- `num-lock-on` or `num-lock-off`

```css
.lock-keys-widget {
  padding: 0 8px;
}

.lock-keys-widget .label {
  color: #888888;
}

.lock-keys-widget .widget-container.caps-lock-on .label {
  color: #f9e2af;
}

.lock-keys-widget .widget-container.num-lock-on .label {
  font-weight: 700;
}
```
