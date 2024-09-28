# Battery Widget Configuration

| Option                  | Type    | Default                                      | Description                                                                 |
|-------------------------|---------|----------------------------------------------|-----------------------------------------------------------------------------|
| `label`                 | string  | `{icon}`                                     | The primary label format.                                                   |
| `label_alt`             | string  | `{percent}%` | Battery percent           | The alternative label format.                                               |
| `update_interval`       | integer | `5000`                                       | The interval in milliseconds to update the widget.                          |
| `time_remaining_natural`| boolean | `False`                                      | Whether to display the remaining time in a natural format.                  |
| `charging_options`      | dict    | `{icon_format: '{charging_icon} {icon}', blink_charging_icon: True}` | Options for charging state display.                                         |
| `status_thresholds`     | dict    | `{critical: 10, low: 25, medium: 75, high: 95, full: 100}` | Thresholds for different battery statuses.                                  |
| `status_icons`          | dict    | `{icon_charging: '\uf0e7', icon_critical: '\uf244', icon_low: '\uf243', icon_medium: '\uf242', icon_high: '\uf241', icon_full: '\uf240'}` | Icons for different battery statuses.                                       |
| `callbacks`             | dict    | `{on_left: 'toggle_label', on_middle: 'do_nothing', on_right: 'do_nothing'}` | Callback functions for different mouse button actions.                      |


## Example Configuration
```yaml
battery:
  type: "yasb.battery.BatteryWidget"
  options:
    label: "<span>{icon}</span>{percent}%"
    label_alt: "{icon} {percent}% | time: {time_remaining}"
    charging_options:
      icon_format: "{charging_icon}"
```


## Description of Options

- `label`: The primary label format for the battery widget. You can use placeholders like `{icon}` to dynamically insert the battery icon.
- `label_alt`: The alternative label format for the battery widget. Useful for displaying additional battery details such as `{percent}%` and `remaining: {time_remaining}`.
- `update_interval`: The interval in milliseconds to update the widget.
- `time_remaining_natural`: A boolean indicating whether to display the remaining time in a natural format.
- `charging_options`: A dictionary specifying options for displaying the charging state. It contains:
  - `icon_format`: The format string for the charging icon. You can use placeholders like `{charging_icon}` and `{icon}`.
  - `blink_charging_icon`: A boolean indicating whether the charging icon should blink.
- `status_thresholds`: A dictionary specifying the thresholds for different battery statuses. It contains:
  - `critical`: The battery percentage threshold for critical status.
  - `low`: The battery percentage threshold for low status.
  - `medium`: The battery percentage threshold for medium status.
  - `high`: The battery percentage threshold for high status.
  - `full`: The battery percentage threshold for full status.
- `status_icons`: A dictionary specifying the icons for different battery statuses. It contains:
  - `icon_charging`: The icon for charging status.
  - `icon_critical`: The icon for critical status.
  - `icon_low`: The icon for low status.
  - `icon_medium`: The icon for medium status.
  - `icon_high`: The icon for high status.
  - `icon_full`: The icon for full status.
- `callbacks`: A dictionary specifying the callbacks for mouse events. It contains:
  - `on_left`: The name of the callback function for left mouse button click.
  - `on_middle`: The name of the callback function for middle mouse button click.
  - `on_right`: The name of the callback function for right mouse button click.