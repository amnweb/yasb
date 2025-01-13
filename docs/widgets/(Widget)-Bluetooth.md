# Bluetooth Widget Configuration

| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`           | string  | `'{icon}'`                        | The format string for the bluetooth widget. Displays icons. |
| `label_alt`       | string  | `'{device_name}'`        | The alternative format string for the bluetooth widget. Displays list of connected devices. |
| `tooltip`  | boolean  | `True`        | Whether to show the tooltip on hover. |
| `icons`       | dict    | `{'bluetooth_on', 'bluetooth_off', 'bluetooth_connected'` | Icons for bluetooth widget |
| `callbacks`       | dict    | `{'on_left': 'toggle_mute', 'on_middle': 'toggle_label', 'on_right': 'do_nothing'}` | Callbacks for mouse events on the memory widget. |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |

## Example Configuration

```yaml
bluetooth:
  type: "yasb.bluetooth.BluetoothWidget"
  options:
    label: "<span>{icon}</span>"
    label_alt: "{device_name}"
    icons: 
      bluetooth_on: "\udb80\udcaf"
      bluetooth_off: "\udb80\udcb2"
      bluetooth_connected: "\udb80\udcb1"
    callbacks:
      on_right: "exec cmd.exe /c start ms-settings:bluetooth"
```

## Description of Options

- **label:** The format string for the bluetooth widget. Displays the bluetooth icon.
- **label_alt:** The alternative format string for the bluetooth widget. Displays list of connected devices.
- **tooltip:** Whether to show the tooltip on hover.
- **icons:** A dictionary specifying the icons for the bluetooth widget. The keys are `bluetooth_on`, `bluetooth_off`, and `bluetooth_connected`, and the values are the unicode characters for the icons.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.

## Example Style
```css
.bluetooth-widget {}
.bluetooth-widget .widget-container {}
.bluetooth-widget .label {}
.bluetooth-widget .label.alt {}
.bluetooth-widget .icon {}
```