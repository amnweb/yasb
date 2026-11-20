# Wireless Battery Widget Configuration

Shows the battery level of your wireless mouse, keyboard, headset and controller. The widget reads the levels from [BatteryHub](https://github.com/krisgfx9/Wireless-Device-Battery-Monitor) (formerly *Wireless Battery*), a small Windows app that supports Logitech, Razer, SteelSeries, Corsair, HyperX, Glorious, PlayStation, Xbox, Bluetooth devices and many more.

> [!IMPORTANT]
> Install BatteryHub first and make sure `BatteryHub.exe` is on your `PATH`, or set the full path in the `executable` option. YASB only runs `BatteryHub.exe --json` and reads its output. You do not need to keep the BatteryHub taskbar widget open. You can hide the BatteryHub taskbar widget if YASB shows the levels.

The widget shows one entry per device. Each entry has its own CSS classes, so you can colour low, charging or sleeping devices.

| Option               | Type    | Default                                          | Description                                                                                       |
|----------------------|---------|--------------------------------------------------|---------------------------------------------------------------------------------------------------|
| `executable`         | string  | `"BatteryHub.exe"`                               | Name or full path of the BatteryHub executable.                                                   |
| `label`              | string  | `"<span>{icon}</span> {percent}%"`               | Format of each device entry. See [Available Placeholders](#available-placeholders).               |
| `label_charging`     | string  | `null`                                           | Format for a device that is charging. When `null`, `label` is used.                               |
| `label_unknown`      | string  | `"<span>{icon}</span> --"`                       | Format for a connected device that has no battery reading right now.                              |
| `label_disconnected` | string  | `"<span>{icon}</span> ×"`                   | Format for a disconnected device (only used with `show_disconnected`).                            |
| `class_name`         | string  | `""`                                             | Additional CSS class name for the widget.                                                         |
| `update_interval`    | integer | `60000`                                          | Time in milliseconds between two BatteryHub reads (5000–3600000).                                 |
| `devices`            | list    | `[]`                                             | Only show devices whose name contains one of these texts (case-insensitive), or whose key matches. Empty shows all. |
| `kinds`              | list    | `[]`                                             | Only show these kinds: `mouse`, `keyboard`, `headset`, `gamepad`, `phone`, `microphone`, `other`. Empty shows all. |
| `show_disconnected`  | boolean | `false`                                          | Also show devices that BatteryHub reports as disconnected.                                        |
| `hide_when_empty`    | boolean | `true`                                           | Hide the whole widget when there is no device to show.                                            |
| `sort_by`            | string  | `"kind"`                                         | Order of the devices: `"kind"`, `"name"` or `"percent"` (lowest first).                           |
| `icons`              | dict    | [See below](#icons)                              | Icon for each kind of device.                                                                     |
| `thresholds`         | dict    | `{critical: 15, low: 30}`                        | Percentages at or below which a device gets the `critical` or `low` CSS class.                    |
| `tooltip`            | boolean | `true`                                           | Show a tooltip with the device name, connection, level and voltage.                               |
| `keybindings`        | list    | `[]`                                             | Optional hotkeys. See [Keybindings](./Keybindings).                                               |
| `callbacks`          | dict    | [See below](#callbacks)                          | Callback functions for mouse buttons.                                                             |

## Callbacks

The `callbacks` option maps mouse buttons (`on_left`, `on_middle`, `on_right`) to actions.

```yaml
callbacks:
  on_left: "refresh"
  on_middle: "do_nothing"
  on_right: "do_nothing"
```

Available callbacks: `refresh` (read BatteryHub right away), `exec <command>` and `do_nothing`.

## Icons

The default icons are from the Segoe Fluent Icons font. Use any font icon you like.

```yaml
icons:
  mouse: ""
  keyboard: ""
  headset: ""
  gamepad: ""
  phone: ""
  microphone: ""
  default: ""      # any other kind of device
  charging: ""     # used instead of the kind icon while charging
  disconnected: "" # used instead of the kind icon when disconnected
```

## Example Configuration

```yaml
wireless_battery:
  type: "yasb.wireless_battery.WirelessBatteryWidget"
  options:
    label: "<span>{icon}</span> {percent}%"
    label_charging: "<span>{icon}</span> {percent}% <span></span>"
    update_interval: 60000
    kinds: ["mouse", "keyboard", "headset"]
    sort_by: "kind"
    thresholds:
      critical: 15
      low: 30
    callbacks:
      on_left: "refresh"
```

Use the widget in the bar like other widgets:

```yaml
bars:
  primary-bar:
    widgets:
      right: ["wireless_battery"]
```

## Description of Options

- **executable**: Name or full path of `BatteryHub.exe`. The widget runs `BatteryHub.exe --json` in a background thread, so the bar never waits for it.
- **label**, **label_charging**, **label_unknown**, **label_disconnected**: Format of one device entry. Text in `<span>...</span>` becomes an icon label (CSS class `icon`, or the class you write in the `class` attribute). All other text becomes a text label (CSS class `label`).
- **update_interval**: Time in milliseconds between two reads. BatteryHub itself refreshes every 60 seconds by default, so a shorter time rarely helps.
- **devices**: Filter by device name or key. `["mx master"]` shows only the devices that have "mx master" in the name.
- **kinds**: Filter by kind of device.
- **show_disconnected**: BatteryHub reports a device as disconnected only when its driver says the wireless link is offline. A device that only missed one poll is not reported as disconnected.
- **thresholds**: A device at or below `critical` gets the CSS class `critical`. A device at or below `low` gets `low`. Other devices get `normal`.
- **sort_by**: `kind` groups devices of the same kind, `name` sorts by name, `percent` puts the lowest battery first.

## Available Placeholders

| Placeholder    | Description                                                                 |
|----------------|-----------------------------------------------------------------------------|
| `{icon}`       | The icon of the device (see [Icons](#icons)).                               |
| `{percent}`    | Battery level 0–100, or `--` when unknown.                                  |
| `{name}`       | Device name (as given by BatteryHub, including any name you set there).     |
| `{kind}`       | `mouse`, `keyboard`, `headset`, `gamepad`, `phone`, `microphone` or `other`. |
| `{via}`        | Connection, for example `2.4 GHz receiver`, `Bluetooth` or `USB cable`.     |
| `{level}`      | Text level for devices that only report coarse levels, for example `Low`.   |
| `{detail}`     | Extra detail from the driver, for example `L 80%, R 75%, case 40%`.         |
| `{millivolts}` | Battery voltage in mV, or `--`.                                             |
| `{charging}`   | `True` when the device is charging.                                         |
| `{asleep}`     | `True` when the device is asleep (the last known level is shown).           |
| `{key}`        | The stable BatteryHub key of the device.                                    |

Example with the device name: `label: "<span>{icon}</span> {name} {percent}%"`.

## CSS Classes

Every device is a `.device` frame. It also has its kind as a class (`.mouse`, `.headset`...) and one or more status classes:

| Class           | When                                               |
|-----------------|----------------------------------------------------|
| `.normal`       | Level above `thresholds.low`.                      |
| `.low`          | Level at or below `thresholds.low`.               |
| `.critical`     | Level at or below `thresholds.critical`.          |
| `.charging`     | The device is charging.                            |
| `.asleep`       | The device is asleep, the last level is shown.     |
| `.unknown`      | No battery reading right now.                      |
| `.disconnected` | The wireless link is offline.                      |

## Example Style

```css
.wireless-battery-widget {
    padding: 0 6px;
}
.wireless-battery-widget .device {
    padding: 0 6px;
}
.wireless-battery-widget .device .icon {
    font-size: 14px;
    padding-right: 4px;
}
.wireless-battery-widget .device.low .label,
.wireless-battery-widget .device.low .icon {
    color: #e5c07b;
}
.wireless-battery-widget .device.critical .label,
.wireless-battery-widget .device.critical .icon {
    color: #e06c75;
}
.wireless-battery-widget .device.charging .icon {
    color: #61afef;
}
.wireless-battery-widget .device.asleep,
.wireless-battery-widget .device.disconnected {
    opacity: 0.5;
}
```
