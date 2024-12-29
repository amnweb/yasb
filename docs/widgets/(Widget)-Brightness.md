# Brightness Screen Widget Configuration

| Option          | Type    | Default                                                                 | Description                                                                 |
|-----------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`         | string  | `"{icon}"`                                                   | The format string for the brightness widget. |
| `label_alt`     | string  | `"Brightness {percent}%"`                                          | The alternative format string for the brightness widget. |
| `tooltip`  | boolean  | `True`        | Whether to show the tooltip on hover. |
| `brightness_icons` | list  | `['\udb80\udcde', '\udb80\udcdd', '\udb80\udcdf', '\udb80\udce0']`                    | A list of icons representing different brightness levels. The icons are used based on the current brightness percentage. |
| `hide_unsupported` | boolean | `True` | Whether to hide the widget if the current system does not support brightness control. |
| `auto_light` | boolean | `False` | Whether to automatically adjust the brightness icon based on the current brightness level. |
| `auto_light_icon` | string | `"\udb80\udce1"` | The icon to use when the auto_light option is enabled. |
| `auto_light_night_level` | int | `50` | The brightness level at which the widget switches to the night. |
| `auto_light_day_level` | int | `100` | The brightness level at which the widget switches to the day. |
| `auto_light_night_start_time` | string | `"20:00"` | The time at which the night starts. |
| `auto_light_night_end_time` | string | `"06:30"` | The time at which the night ends. |
| `callbacks`     | dict    | `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}` | Callbacks for mouse events on the clock widget. |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.      |

## Example Configuration

```yaml
  brightness:
    type: "yasb.brightness.BrightnessWidget"
    options:
      label: "<span>{icon}</span>"
      label_alt: "Brightness {percent}%"
      tooltip: true
      auto_light: false
      auto_light_icon: "\udb80\udce1"
      auto_light_night_level: 35
      auto_light_night_start_time: "19:00"
      auto_light_night_end_time: "06:45"
      auto_light_day_level: 75
      brightness_icons: [
        "\udb80\udcde",  # Icon for 0-25% brightness
        "\udb80\udcdd",  # Icon for 26-50% brightness
        "\udb80\udcdf",  # Icon for 51-75% brightness
        "\udb80\udce0"   # Icon for 76-100% brightness
      ]
      callbacks:
          on_left: "toggle_label"
      container_padding:
        top: 0
        left: 8
        bottom: 0
        right: 8
```

## Description of Options
- **label:** The format string for the clock. You can use placeholders like `{%H:%M:%S}` to dynamically insert time information.
- **label_alt:** The alternative format string for the clock. Useful for displaying additional time details.
- **tooltip:** Whether to show the tooltip on hover.
- **brightness_icons:** A list of icons representing different brightness levels. The icons are used based on the current brightness percentage.
- **hide_unsupported:** Whether to hide the widget if the current system does not support brightness control.
- **auto_light:** Whether to automatically adjust the brightness icon based on the current brightness level.
- **auto_light_icon:** The icon to use when the auto_light option is enabled.
- **auto_light_night_level:** The brightness level at which the widget switches to the night.
- **auto_light_day_level:** The brightness level at which the widget switches to the day.
- **auto_light_night_start_time:** The time at which the night starts.
- **auto_light_night_end_time:** The time at which the night ends.
- **callbacks:** Callbacks for mouse events on the clock widget.
- **container_padding:** Explicitly set padding inside widget container.


## Example Style
```css
.brightness-widget {}
.brightness-widget .widget-container {}
.brightness-widget .widget-container .label {}
.brightness-widget .widget-container .icon {}
```