# Clock Widget Configuration

| Option              | Type    | Default                                                                               | Description                                                                                                         |
| ------------------- | ------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `label`             | string  | `'\uf017 {%H:%M:%S}'`                                                                 | The format string for the clock. You can use placeholders like `{%H:%M:%S}` or `{icon}` to dynamically insert time information. |
| `label_alt`         | string  | `'\uf017 {%d-%m-%y %H:%M:%S}'`                                                        | The alternative format string for the clock. Useful for displaying additional time details.                         |
| `class_name`        | string  | `""`                                                                                  | Additional CSS class name for the widget.                                    |
| `tooltip`           | boolean | `true`                                                                                | Whether to show the tooltip on hover.                                                                               |
| `locale`            | string  | `""`                                                                                  | The locale to use for the clock. If not specified, it defaults to an empty string.                                  |
| `update_interval`   | integer | `1000`                                                                                | The interval in milliseconds to update the clock. Must be between 0 and 60000.                                      |
| `timezones`         | list    | `[]`                                                                                  | A list of timezones to cycle through. Each timezone should be a valid timezone string.                              |
| `icons`         | dict    | `{ 'clock_01': '\udb85\udc3f', ..., 'clock_12': '\udb85\udc4a'[, 'clock_13': '\udb85\udc3f', ..., 'clock_22': '\udb85\udc48','clock_23': '\udb85\udc49']}` | A dictionary of icons for the different times of day. |
| `calendar` | dict | `{'blur': True, 'round_corners': True, 'round_corners_type': 'normal', 'border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0, 'country_code': None, 'subdivision': None, 'show_holidays': False, 'holiday_color': "#FF6464", 'show_week_numbers': False}` | Calendar settings for the widget. |
| `callbacks`         | dict    | `{'on_left': 'toggle_calendar', 'on_middle': 'next_timezone', 'on_right': 'toggle_label'}` | Callbacks for mouse events on the clock widget.                                                                     |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`                             | Animation settings for the widget.                                                                                  |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |

## Example Configuration

```yaml
clock:
  type: "yasb.clock.ClockWidget"
  options:
    label: "<span>{icon}</span> {%H:%M:%S}"
    label_alt: "\uf017 {%d-%m-%y %H:%M:%S}"
    locale: ""
    update_interval: 1000
    timezones: []
    icons:
      clock_01 : "\udb85\udc3f"
      clock_02 : "\udb85\udc40"
      clock_03 : "\udb85\udc41"
      clock_04 : "\udb85\udc42"
      clock_05 : "\udb85\udc43"
      clock_06 : "\udb85\udc44"
      clock_07 : "\udb85\udc45"
      clock_08 : "\udb85\udc46"
      clock_09 : "\udb85\udc47"
      clock_10 : "\udb85\udc48"
      clock_11 : "\udb85\udc49"
      clock_12 : "\udb85\udc4a"
      clock_16 : "SNACK TIME !"
      clock_21 : "Zzz..."
      clock_22 : "Zzz..."
      clock_23 : "Zzz..."
    calendar: 
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "system"
      alignment: "center"
      direction: "down"
      show_holidays: false
      show_week_numbers: true
      country_code: "AR"
      holiday_color: "#FF6464"
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

- **label:** The format string for the clock. You can use placeholders like `{%H:%M:%S}` or `{icon}` to dynamically insert time information.
- **label_alt:** The alternative format string for the clock. Useful for displaying additional time details.
- **class_name:** Additional CSS class name for the widget. This can be used to apply custom styles.
- **locale:** The locale to use for the clock. If not specified, it defaults to an empty string.
- **tooltip:** Whether to show the tooltip on hover.
- **update_interval:** The interval in milliseconds to update the clock. Must be between 0 and 60000.
- **timezones:** A list of timezones to cycle through. If the value is empty, YASB will look up time zone info from the registry.
- **icons:** A dictionary mapping clock hours to icons. Keys are in the format clock_HH where HH is the hour in 24h format (00–23). By default, `clock_13` to `clock_23` reuse the icons from `clock_01` to `clock_11`, unless explicitly defined.
- **calendar:** A dictionary specifying the calendar settings for the widget. It contains the following keys:
  - **blur:** Enable blur effect for the calendar.
  - **round_corners:** Enable round corners for the calendar (this option is not supported on Windows 10).
  - **round_corners_type:** Set the type of round corners for the calendar (normal, small) (this option is not supported on Windows 10).
  - **border_color:** Set the border color for the calendar (this option is not supported on Windows 10).
  - **alignment:** Set the alignment of the calendar (left, right).
  - **direction:** Set the direction of the calendar (up, down).
  - **offset_top:** Set the offset from the top of the widget container.
  - **offset_left:** Set the offset from the left of the widget container.
  - **country_code:** The country code for holidays (e.g., "US", "AR").
  - **subdivision:** The subdivision code for holidays (e.g., "CA" for California, "Z" for Buenos Aires).
  - **show_holidays:** Whether to show holidays in the calendar.
  - **holiday_color:** The color used to highlight holidays in the calendar (hex format, e.g., "#00A300").
  - **show_week_numbers:** Whether to show week numbers in the calendar.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.

Clock format https://docs.python.org/3/library/time.html#time.strftime

**Note about holidays:**
- `country_code` specifies the country for which holidays are shown (e.g., "US" for United States, "AR" for Argentina). If you do not specify a country code, YASB will try to use the default country code based on your system settings.
- `subdivision` allows you to select a specific region or state within the country (e.g., "CA" for California, "Z" for Buenos Aires).
- For a full list of supported country codes and subdivisions, see the [holidays available countries documentation](https://github.com/vacanza/holidays?tab=readme-ov-file#available-countries).

## Example Style

```css
.clock-widget {}
/* If you are using class_name option, you can add custom styles here */
.clock-widget.your_class {}
.clock-widget .widget-container {}
.clock-widget .widget-container .label {}
.clock-widget .widget-container .label.alt {}
.clock-widget .widget-container .icon {}
.clock-widget .icon {}
.clock-widget .icon.clock_02 {}
.clock-widget .label.clock_15 {}
/* Calendar styles */
.calendar {}
.calendar .calendar-table {}
.calendar .calendar-table::item {}
.calendar .calendar-table::item:selected {}
.calendar .day-label {}
.calendar .month-label {}
.calendar .date-label {}
.calendar .week-label {}
.calendar .holiday-label {}
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
    background-color: #007acc;
    border-radius: 10px;
}
.calendar .day-label {
    margin-top: 20px;
}
.calendar .day-label,
.calendar .month-label,
.calendar .date-label,
.calendar .week-label,
.calendar .holiday-label {
    font-family: 'Segoe UI';
    font-size: 16px;
    color: #fff;
    font-weight: 700;
    min-width: 180px;
    max-width: 180px;
}
.calendar .week-label,
.calendar .holiday-label {
    font-size: 12px;
    font-weight: 600;
    color: rgba(162, 177, 196, 0.85);
}
.calendar .holiday-label {
    color: rgba(162, 177, 196, 0.85);
    font-weight: 700;
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
