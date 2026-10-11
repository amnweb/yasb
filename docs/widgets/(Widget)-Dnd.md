# Do Not Disturb Widget Configuration

A widget that allows you to monitor and toggle Windows Focus Assist (Do Not Disturb) directly from your status bar. Works natively on Windows 10 and Windows 11 via the undocumented `QuietHoursSettings` COM API.

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `label` | `str` | `"{icon}"` | The primary text shown on the widget. |
| `label_alt` | `str` | `"{icon} {status}"` | The alternate text shown after calling the `toggle_label` callback. |
| `class_name` | `str` | `""` | A custom CSS class added to the widget container. |
| `tooltip` | `bool` | `true` | Whether to show the status tooltip on hover. |
| `default_active_mode` | `str` | `"priority"` | The mode that will be activated when toggling from "disabled". Valid options: `"priority"` or `"alarms"`. |
| `callbacks` | `dict` | [See below](#callbacks) | Custom mouse actions mapped to widget functions. |
| `icons` | `dict` | [See below](#icons-options) | A dictionary mapping statuses to font/icon strings. |

## Icons Options

The `icons` option accepts the following keys. All keys are optional, the values shown are the defaults.

```yaml
icons:
  disabled: "\uf0f3"
  priority: "\uf186"
  alarms: "\uf1f6"
```

## Callbacks

The `callbacks` option maps mouse buttons (`on_left`, `on_middle`, `on_right`) to actions. All keys are optional, the values shown are the defaults.

```yaml
callbacks:
  on_left: "toggle_status"
  on_middle: "do_nothing"
  on_right: "cycle_status"
```

Available actions:

- `toggle_label` - Toggles between `label` and `label_alt`.
- `toggle_status` - Toggles between "disabled" and the most recent active restricted mode ("priority" or "alarms").
- `cycle_status` - Cycles the mode sequentially: `disabled` -> `priority` -> `alarms` -> `disabled`.
- `do_nothing` - Do nothing.
- `exec <command>` - Run a command, for example `exec cmd.exe /c start ms-settings:network`.

## Label Placeholders

The `label` and `label_alt` options support the following placeholders:

| Placeholder | Output Example | Description |
| :--- | :--- | :--- |
| `{icon}` | `\uf0f3` | The icon corresponding to the current state. |
| `{status}` | `disabled`, `priority`, or `alarms` | The string identifier of the current state. |

## Example Configuration

```yaml
dnd:
  type: "yasb.dnd.DndWidget"
  options:
    label: "{icon}"
    label_alt: "{icon} {status}"
    default_active_mode: "priority"
    callbacks:
      on_left: "toggle_status"
      on_right: "cycle_status"
    icons:
      disabled: "\uf0f3"
      priority: "\uf186" 
      alarms: "\uf1f6" 
```

## Description of Options

- **label**: The primary text shown on the widget. You can use placeholders like `{icon}` and `{status}`.
- **label_alt**: The alternate text shown after calling the `toggle_label` callback.
- **class_name**: Additional CSS class name for the widget container. This allows for custom styling.
- **tooltip**: Whether to show the tooltip on hover.
- **default_active_mode**: The mode that will be activated when toggling from "disabled" for the first time. Valid options are `"priority"` or `"alarms"`. On Windows 11, priority is the default one.
- **callbacks:** Mouse event callbacks. See [Callbacks](#callbacks).
- **icons**: A dictionary mapping statuses to font/icon strings. It contains:
  - **disabled**: Icon displayed when Do Not Disturb is disabled.
  - **priority**: Icon displayed when "Priority Only" is active.
  - **alarms**: Icon displayed when "Alarms Only" is active.

> **Note:** On Windows 11, the native Do Not Disturb toggle button in the taskbar only switches between `disabled` (Off) and `priority` (On). The `alarms` state is typically only activated via Windows Settings or by using the `cycle_status` callback in this widget.

## Style

```css
.dnd-widget {}
.dnd-widget .widget-container {}
.dnd-widget .widget-container .label {}
.dnd-widget .widget-container .label.alt {}
.dnd-widget .widget-container .icon {}
/* Status classes */
.dnd-widget .widget-container .label.status-disabled {}
.dnd-widget .widget-container .label.status-priority {}
.dnd-widget .widget-container .label.status-alarms {}
.dnd-widget .widget-container .icon.status-disabled {}
.dnd-widget .widget-container .icon.status-priority {}
.dnd-widget .widget-container .icon.status-alarms {}
```

## Example Style

```css
.dnd-widget {
    padding: 0 8px;
}

.dnd-widget .icon {
    font-size: 14px;
    margin-right: 6px;
}

.dnd-widget .label {
    font-size: 13px;
    color: #e0e0e0;
}

/* Disabled - Green */
.dnd-widget .icon.status-disabled {
    color: #a6e3a1; 
}
.dnd-widget .label.status-disabled {
    color: #a6e3a1; 
}

/* Priority Only - Yellow */
.dnd-widget .icon.status-priority {
    color: #f9e2af; 
}
.dnd-widget .label.status-priority {
    color: #f9e2af; 
}

/* Alarms Only - Red */
.dnd-widget .icon.status-alarms {
    color: #f38ba8; 
}
.dnd-widget .label.status-alarms {
    color: #f38ba8; 
}
```
