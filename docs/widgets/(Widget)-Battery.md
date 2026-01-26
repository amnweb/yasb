# Battery Widget Configuration

| Option                  | Type    | Default                                      | Description                                                                 |
|-------------------------|---------|----------------------------------------------|-----------------------------------------------------------------------------|
| `label`                 | string  | `{icon}`                                     | The primary label format.                                                   |
| `label_alt`             | string  | `{percent}%` | Battery percent           | The alternative label format.                                               |
| `class_name`            | string  | `""`                                         | Additional CSS class name for the widget.                                    |
| `update_interval`       | integer | `5000`                                       | The interval in milliseconds to update the widget.                          |
| `time_remaining_natural`| boolean | `False`                                      | Whether to display the remaining time in a natural format.                  |
| `hide_unsupported`| boolean | `True`                                      | Whether to hide the widget if the current system does not have battery info.                  |
| `charging_options`      | dict    | `{icon_format: '{charging_icon}', blink_charging_icon: True, blink_interval: 500}` | Options for charging state display.                                         |
| `status_thresholds`     | dict    | `{critical: 10, low: 25, medium: 75, high: 95, full: 100}` | Thresholds for different battery statuses.                                  |
| `status_icons`          | dict    | `{icon_charging: '\uf0e7', icon_critical: '\uf244', icon_low: '\uf243', icon_medium: '\uf242', icon_high: '\uf241', icon_full: '\uf240'}` | Icons for different battery statuses.                                       |
| `callbacks`             | dict    | `{on_left: 'toggle_label', on_middle: 'do_nothing', on_right: 'do_nothing'}` | Callback functions for different mouse button actions.                      |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |

## Label Placeholders

| Placeholder           | Description                                      | Example Output |
|-----------------------|--------------------------------------------------|----------------|
| `{icon}`              | Battery icon based on current status             | `{icon}`       |
| `{percent}`           | Current battery percentage                       | `75`           |
| `{time_remaining}`    | Time remaining (or "unlimited"/"unknown")        | `2:30:00`      |
| `{is_charging}`       | Whether battery is charging                      | `yes` or `no`  |
| `{power}`             | Power drain/charge rate in watts                 | `15.5`         |
| `{voltage}`           | Current voltage in volts                         | `12.45`        |
| `{capacity}`          | Current capacity in mWh                          | `45000`        |
| `{full_capacity}`     | Full charge capacity in mWh                      | `60000`        |
| `{designed_capacity}` | Original design capacity in mWh                  | `62000`        |
| `{temperature}`       | Battery temperature in Celsius                   | `35.5`         |
| `{cycle_count}`       | Battery charge cycle count                       | `250`          |
| `{health}`            | Battery health percentage                        | `96.8`         |
| `{chemistry}`         | Battery chemistry type                           | `LiP`          |

> **Note:** Extended battery info (`{power}`, `{voltage}`, `{temperature}`, etc.) requires hardware support. If not available, displays `N/A`.

## Example Configuration
```yaml
battery:
  type: "yasb.battery.BatteryWidget"
  options:
    label: "<span>{icon}</span> {percent}%"
    label_alt: "<span>{icon}</span> {percent}% | {power}W | {time_remaining}"
    update_interval: 5000
    time_remaining_natural: False
    hide_unsupported: True
    charging_options:
      icon_format: "{charging_icon}"
      blink_charging_icon: true
      blink_interval: 500
    status_thresholds:
      critical: 10
      low: 25
      medium: 75
      high: 95
      full: 100
    status_icons:
      icon_charging: "\uf0e7"
      icon_critical: "\uf244"
      icon_low: "\uf243"
      icon_medium: "\uf242"
      icon_high: "\uf241"
      icon_full: "\uf240"
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```


## Description of Options

- **label**: The primary label format for the battery widget. You can use placeholders like `{icon}` to dynamically insert the battery icon.
- **label_alt**: The alternative label format for the battery widget. Useful for displaying additional battery details such as `{percent}%` and `remaining: {time_remaining}`.
- **class_name**: Additional CSS class name for the widget. This allows for custom styling.
- **update_interval**: The interval in milliseconds to update the widget.
- **time_remaining_natural**: A boolean indicating whether to display the remaining time in a natural format.
- **hide_unsupported**: A boolean indicating whether to hide the widget if the current system does not have battery information.
- **charging_options**: A dictionary specifying options for displaying the charging state. It contains:
  - **icon_format**: The format string for the charging icon. You can use placeholders like `{charging_icon}` and `{icon}`.
  - **blink_charging_icon**: A boolean indicating whether to blink the charging icon when the battery is charging. (to create a blinking effect use class `blink` in CSS)
  - **blink_interval**: The interval in milliseconds for the blinking effect.
- **status_thresholds**: A dictionary specifying the thresholds for different battery statuses. It contains:
  - **critical**: The battery percentage threshold for critical status.
  - **low**: The battery percentage threshold for low status.
  - **medium**: The battery percentage threshold for medium status.
  - **high**: The battery percentage threshold for high status.
  - **full**: The battery percentage threshold for full status.
- **status_icons**: A dictionary specifying the icons for different battery statuses. It contains:
  - **icon_charging**: The icon for charging status.
  - **icon_critical**: The icon for critical status.
  - **icon_low**: The icon for low status.
  - **icon_medium**: The icon for medium status.
  - **icon_high**: The icon for high status.
  - **icon_full**: The icon for full status.
- **callbacks**: A dictionary specifying the callbacks for mouse events. It contains:
  - **on_left**: The name of the callback function for left mouse button click.
  - **on_middle**: The name of the callback function for middle mouse button click.
  - **on_right**: The name of the callback function for right mouse button click.
- **animation**: A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow**: Container shadow options.
- **label_shadow**: Label shadow options.

## Style
```css
.battery-widget {}
.battery-widget .widget-container {}
.battery-widget .widget-container .label {}
.battery-widget .widget-container .label.alt {}
.battery-widget .widget-container .icon {}
/* Status classes */
.battery-widget .widget-container .label.status-critical {}
.battery-widget .widget-container .label.status-low {}
.battery-widget .widget-container .label.status-medium {}
.battery-widget .widget-container .label.status-high {}
.battery-widget .widget-container .label.status-full {}
.battery-widget .widget-container .label.status-charging {}
.battery-widget .widget-container .icon.status-critical {}
.battery-widget .widget-container .icon.status-low {}
.battery-widget .widget-container .icon.status-medium {}
.battery-widget .widget-container .icon.status-high {}
.battery-widget .widget-container .icon.status-full {}
.battery-widget .widget-container .icon.status-charging {}
.battery-widget .widget-container .icon.status-charging.blink {}
```

## Style Example
```css
.battery-widget {
    padding: 0 8px;
}
.battery-widget .label {
    font-size: 13px;
    color: #e0e0e0;
}
.battery-widget .icon {
    font-size: 14px;
    margin-right: 6px;
}
/* Critical - red */
.battery-widget .icon.status-critical {
    color: #ff4444;
}
.battery-widget .label.status-critical {
    color: #ff6b6b;
}
/* Low - orange */
.battery-widget .icon.status-low {
    color: #ff9800;
}
.battery-widget .label.status-low {
    color: #ffb74d;
}
/* Medium - yellow */
.battery-widget .icon.status-medium {
    color: #ffc107;
}
/* High - light green */
.battery-widget .icon.status-high {
    color: #8bc34a;
}
/* Full - green */
.battery-widget .icon.status-full {
    color: #4caf50;
}
/* Charging - cyan */
.battery-widget .icon.status-charging {
    color: #00bcd4;
}
.battery-widget .label.status-charging {
    color: #4dd0e1;
}
```