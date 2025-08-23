# Bluetooth Widget Configuration

| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`           | string  | `'{icon}'`                        | The format string for the bluetooth widget. Displays icons. |
| `label_alt`       | string  | `'{device_name}'`        | The alternative format string for the bluetooth widget. Displays list of connected devices. |
| `class_name`      | string  | `""`                                                                                  | Additional CSS class name for the widget.                                    |
| `label_no_device`       | string  | `'No devices connected'`        | The string to display `{device_name}` when no devices are connected. |
| `label_device_separator` | string  | `', '`        | The string to separate multiple device names. |
| `max_length`        | integer | `None`    | The maximum length of the label text. |
| `max_length_ellipsis` | string | `"..."`  | The ellipsis to use when the label text exceeds the maximum length.   |
| `tooltip`  | boolean  | `true`        | Whether to show the tooltip on hover. |
| `icons`       | dict    | `{'bluetooth_on': '\udb80\udcaf', 'bluetooth_off': '\udb80\udcb2', 'bluetooth_connected': '\udb80\udcb1'}` | Icons for bluetooth widget |
| `device_aliases` | list   | `[]`    | List of device aliases. |
| `callbacks`       | dict    | `{'on_left': 'toggle_mute', 'on_middle': 'toggle_label', 'on_right': 'do_nothing'}` | Callbacks for mouse events on the bluetooth widget. |
| `animation`         | dict    | `{'enabled': true, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |

## Example Configuration

```yaml
bluetooth:
  type: "yasb.bluetooth.BluetoothWidget"
  options:
    label: "<span>{icon}</span> {device_count}"
    label_alt: "{device_name}"
    label_no_device: "No devices connected"
    label_device_separator: ", "
    max_length: 10
    max_length_ellipsis: "..."
    icons: 
      bluetooth_on: "\udb80\udcaf"
      bluetooth_off: "\udb80\udcb2"
      bluetooth_connected: "\udb80\udcb1"
    device_aliases:
      - name: "T5.0"
        alias: "\uf025"
    callbacks:
      on_left: "toggle_label"
      on_right: "exec cmd.exe /c start ms-settings:bluetooth"
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Description of Options

- **label:** The format string for the bluetooth widget. Displays the bluetooth icon.
- **label_alt:** The alternative format string for the bluetooth widget. Displays list of connected devices.
- **class_name:** Additional CSS class name for the widget. This allows for custom styling.
- **label_no_device:** The string to display `{device_name}` when no devices are connected.
- **label_device_separator:** The string to separate multiple device names.
- **max_length:** The maximum number of characters of the label text. If the text exceeds this length, it will be truncated.
- **max_length_ellipsis:** The string to append to truncated label text.
- **tooltip:** Whether to show the tooltip on hover.
- **icons:** A dictionary specifying the icons for the bluetooth widget. The keys are `bluetooth_on`, `bluetooth_off`, and `bluetooth_connected`, and the values are the unicode characters for the icons.
- **device_aliases:** A list of dictionaries specifying device aliases. Each dictionary should contain a `name` and an `alias`. The `name` is the real name of the device, and the `alias` is the text to display for that device.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.

## Example Style
```css
.bluetooth-widget {}
.bluetooth-widget.your_class {} /* If you are using class_name option */
.bluetooth-widget .widget-container {}
.bluetooth-widget .label {}
.bluetooth-widget .label.alt {}
.bluetooth-widget .icon {}
```