# Clock Widget Configuration

| Option              | Type    | Default                                                                               | Description                                                                                                         |
| ------------------- | ------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `label`             | string  | `'\uf017 {%H:%M:%S}'`                                                                 | The format string for the clock. You can use placeholders like `{%H:%M:%S}` to dynamically insert time information. |
| `label_alt`         | string  | `'\uf017 {%d-%m-%y %H:%M:%S}'`                                                        | The alternative format string for the clock. Useful for displaying additional time details.                         |
| `tooltip`           | boolean | `True`                                                                                | Whether to show the tooltip on hover.                                                                               |
| `locale`            | string  | `""`                                                                                  | The locale to use for the clock. If not specified, it defaults to an empty string.                                  |
| `update_interval`   | integer | `1000`                                                                                | The interval in milliseconds to update the clock. Must be between 0 and 60000.                                      |
| `timezones`         | list    | `[]`                                                                                  | A list of timezones to cycle through. Each timezone should be a valid timezone string.                              |
| `callbacks`         | dict    | `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'next_timezone'}` | Callbacks for mouse events on the clock widget.                                                                     |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`                             | Animation settings for the widget.                                                                                  |
| `container_padding` | dict    | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`                                      | Explicitly set padding inside widget container.                                                                     |

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
    callbacks:
      on_left: "toggle_label"
      on_middle: "do_nothing"
      on_right: "next_timezone"
```

## Description of Options

- **label:** The format string for the clock. You can use placeholders like `{%H:%M:%S}` to dynamically insert time information.
- **label_alt:** The alternative format string for the clock. Useful for displaying additional time details.
- **locale:** The locale to use for the clock. If not specified, it defaults to an empty string.
- **tooltip:** Whether to show the tooltip on hover.
- **update_interval:** The interval in milliseconds to update the clock. Must be between 0 and 60000.
- **timezones:** A list of timezones to cycle through. If value is empty YASB will looking up time zone info from registry
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.

Clock format https://docs.python.org/3/library/time.html#time.strftime

## Example Style

```css
.clock-widget {
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

