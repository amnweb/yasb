# Clock Widget Configuration

| Option              | Type    | Default                                                                               | Description                                                                                                         |
| ------------------- | ------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `label`             | string  | `'\uf017 {%H:%M:%S}'`                                                                 | The format string for the clock. You can use placeholders like `{%H:%M:%S}` to dynamically insert time information. |
| `label_alt`         | string  | `'\uf017 {%d-%m-%y %H:%M:%S}'`                                                        | The alternative format string for the clock. Useful for displaying additional time details.                         |
| `class_name`        | string  | `""`                                                                                  | Additional CSS class name for the widget.                                    |
| `tooltip`           | boolean | `True`                                                                                | Whether to show the tooltip on hover.                                                                               |
| `locale`            | string  | `""`                                                                                  | The locale to use for the clock. If not specified, it defaults to an empty string.                                  |
| `update_interval`   | integer | `1000`                                                                                | The interval in milliseconds to update the clock. Must be between 0 and 60000.                                      |
| `timezones`         | list    | `[]`                                                                                  | A list of timezones to cycle through. Each timezone should be a valid timezone string.                              |
| `calendar` | dict | `{'blur': True, 'round_corners': True, 'round_corners_type': 'normal', 'border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0}` | Calendar settings for the widget. |
| `callbacks`         | dict    | `{'on_left': 'toggle_calendar', 'on_middle': 'next_timezone', 'on_right': 'toggle_label'}` | Callbacks for mouse events on the clock widget.                                                                     |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`                             | Animation settings for the widget.                                                                                  |
| `container_padding` | dict    | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`                                      | Explicitly set padding inside widget container.                                                                     |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |

## Example Configuration

```yaml
clock:
  type: "yasb.clock.ClockWidget"
  options:
    label: "\uf017 {%H:%M:%S}"
    label_alt: "\uf017 {%d-%m-%y %H:%M:%S}"
    locale: ""
    update_interval: 1000
    timezones: []
    calendar: 
      blur: True
      round_corners: True
      round_corners_type: "normal"
      border_color: "System"
      alignment: "center"
      direction: "down"
    callbacks:
      on_left: "toggle_label"
      on_middle: "do_nothing"
      on_right: "next_timezone"
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Description of Options

- **label:** The format string for the clock. You can use placeholders like `{%H:%M:%S}` to dynamically insert time information.
- **label_alt:** The alternative format string for the clock. Useful for displaying additional time details.
- **class_name:** Additional CSS class name for the widget. This can be used to apply custom styles.
- **locale:** The locale to use for the clock. If not specified, it defaults to an empty string.
- **tooltip:** Whether to show the tooltip on hover.
- **update_interval:** The interval in milliseconds to update the clock. Must be between 0 and 60000.
- **timezones:** A list of timezones to cycle through. If value is empty YASB will looking up time zone info from registry
- **calendar:** A dictionary specifying the calendar settings for the widget. It contains the following keys:
  - **blur:** Enable blur effect for the calendar.
  - **round_corners:** Enable round corners for the calendar (this option is not supported on Windows 10).
  - **round_corners_type:** Set the type of round corners for the calendar (normal, small) (this option is not supported on Windows 10).
  - **border_color:** Set the border color for the calendar (this option is not supported on Windows 10).
  - **alignment:** Set the alignment of the calendar (left, right).
  - **direction:** Set the direction of the calendar (up, down).
  - **offset_top:** Set the offset from the top of the widget container.
  - **offset_left:** Set the offset from the left of the widget container.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.

Clock format https://docs.python.org/3/library/time.html#time.strftime

## Example Style

```css
.clock-widget {
}
/* If you suing class_name option, you can add custom styles here */
.clock-widget.your_class {
}
.clock-widget .widget-container {
}
.clock-widget .widget-container .label {
}
.clock-widget .widget-container .label.alt {
}
.clock-widget .widget-container .icon {
}
```

## Example Style for the Calendar

```css
.calendar {
    background-color: rgba(17, 17, 27, 0.4);
}
.calendar .calendar-table,
.calendar .calendar-table::item {
    background-color: rgba(17, 17, 27, 0);
    color: rgba(162, 177, 196, 0.85);
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 0;
    padding: 0;
    border: none;
    outline: none;  
}
.calendar .calendar-table::item:selected {
    color: rgb(255, 255, 255);
}
.calendar .day-label {
    margin-top: 20px;
}
.calendar .day-label,
.calendar .month-label,
.calendar .date-label {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 16px;
    color: #fff;
    font-weight: 700;
    min-width: 180px;
    max-width: 180px;
}
.calendar .month-label {
    font-weight: normal;
}
.calendar .date-label {
    font-size: 88px;
    font-weight: 900;
    color: rgb(255, 255, 255);
    margin-top: -20px;
}
```

## Preview of the Widget
![GitHub YASB Widget](assets/792254956-fr651bd1-gtdc-8966-e89a5edca704.png)
