# WiFi Widget Options

| Option              | Type    | Default                                                                 | Description                                                                 |
|---------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`   | string  | `"{wifi_icon}"`    | The label format for the WiFi widget. |
| `label_alt`   | string  | `"{wifi_name} {wifi_strength}%"`  | The alternative label format for the WiFi widget. |
| `update_interval` | integer  | `1000`   | Update interval in milliseconds.  |
| `wifi_icons`  | list    | `[ "\udb82\udd2e", "\udb82\udd1f", "\udb82\udd22", "\udb82\udd25", "\udb82\udd28" ]`   | Icons for different WiFi signal strengths.    |
| `ethernet_icon` | string | "\ueba9" | The icon to indicate Ethernet connection. |
| `callbacks`   | dict    | `{ 'on_left': 'next_layout', 'on_middle': 'toggle_monocle', 'on_right': 'prev_layout' }` | Callbacks for mouse events on the widget.    |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.      |

> **Note:** Available label replacements: "{wifi_icon}", "{wifi_name}", "{wifi_strength}", "{ip_addr}"

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
    ethernet_icon: "\ueba9"
    wifi_icons: [
      "\udb82\udd2e",  # Icon for 0% strength
      "\udb82\udd1f",  # Icon for 1-24% strength
      "\udb82\udd22",  # Icon for 25-49% strength
      "\udb82\udd25",  # Icon for 50-74% strength
      "\udb82\udd28"   # Icon for 75-100% strength
    ]
```

## Description of Options
- **label:** The format string for the active window title. You can use placeholders like `{win[title]}` to dynamically insert window information. Default is `"{icon}"`.
- **label_alt:** The format string for the active window title when the widget is in the alternative state. Default is `"{wifi_name} {wifi_strength}%"`.
- **update_interval:** The interval in milliseconds at which the widget updates. Default is `1000`.
- **ethernet_icon**: The icon that indicates an active Ethernet connection. It will be used as `{wifi_icon}` whenever there's no active WiFi connection. Default is "\ueba9".
- **wifi_icons:** A list of icons to use for different WiFi signal strengths. Default is `["\udb82\udd2e","\udb82\udd1f","\udb82\udd22","\udb82\udd25","\udb82\udd28",]`.
- **callbacks:** A dictionary of callbacks for mouse events on the widget. Default is `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}`.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.

## Example Style
```css
.wifi-widget {}
.wifi-widget .widget-container {}
.wifi-widget .widget-container .label {}
.wifi-widget .widget-container .label.alt {}
.wifi-widget .widget-container .icon {}
```
