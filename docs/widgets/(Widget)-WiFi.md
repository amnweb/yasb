# WiFi Widget Options

| Option              | Type    | Default                                                                 | Description                                                                 |
|---------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`   | string  | `"{icon}"`    | The label format for the WiFi widget. |
| `label_alt`   | string  | `"{wifi_name} {wifi_strength}%"`  | The alternative label format for the WiFi widget. |
| `update_interval` | integer  | `1000`   | Update interval in milliseconds.  |
| `wifi_icons`  | list    | `[ "\udb82\udd2e", "\udb82\udd1f", "\udb82\udd22", "\udb82\udd25", "\udb82\udd28" ]`   | Icons for different WiFi signal strengths.    |
| `callbacks`   | dict    | `{ 'on_left': 'next_layout', 'on_middle': 'toggle_monocle', 'on_right': 'prev_layout' }` | Callbacks for mouse events on the widget.    |


## Example Configuration

```yaml
wifi:
  type: "yasb.wifi.WifiWidget"
  options:
    label: "<span>{wifi_icon}</span>"
    label_alt: "{wifi_name} {wifi_strength}%"
    update_interval: 5000
    callbacks:
      on_left: "exec cmd.exe /c start ms-settings:network"
      on_middle: "do_nothing"
      on_right: "toggle_label"
    wifi_icons: [
      "\udb82\udd2e",  # Icon for 0% strength
      "\udb82\udd1f",  # Icon for 1-20% strength
      "\udb82\udd22",  # Icon for 21-40% strength
      "\udb82\udd25",  # Icon for 41-80% strength
      "\udb82\udd28"   # Icon for 81-100% strength
    ]
```

## Description of Options
- **label:** The format string for the active window title. You can use placeholders like `{win[title]}` to dynamically insert window information. Default is `"{icon}"`.
- **label_alt:** The format string for the active window title when the widget is in the alternative state. Default is `"{wifi_name} {wifi_strength}%"`.
- **update_interval:** The interval in milliseconds at which the widget updates. Default is `1000`.
- **wifi_icons:** A list of icons to use for different WiFi signal strengths. Default is `["\udb82\udd2e","\udb82\udd1f","\udb82\udd22","\udb82\udd25","\udb82\udd28",]`.
- **callbacks:** A dictionary of callbacks for mouse events on the widget. Default is `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}`.

## Example Style
```css
.wifi-widget {}
.wifi-widget .widget-container {}
.wifi-widget .widget-container .label {}
.wifi-widget .widget-container .label.alt {}
.wifi-widget .widget-container .icon {}
```
