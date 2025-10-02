# WiFi Widget Options

| Option                    | Type      | Default                                                                                  | Description                                                     |
| ---------------------     | --------- | -------------------------------------------------------------------------                | --------------------------------------------------------------- |
| `label`                   | string    | `"{wifi_icon}"`                                                                          | The label format for the WiFi widget.                           |
| `label_alt`               | string    | `"{wifi_icon} {wifi_name}"`                                                              | The alternative label format for the WiFi widget.               |
| `update_interval`         | integer   | `1000`                                                                                   | Update interval in milliseconds.                                |
| `class_name`              | string    | `""`                                                                                     | Additional CSS class name for the widget.                       |
| `wifi_icons`              | list      | `[ "\udb82\udd2e", "\udb82\udd1f", "\udb82\udd22", "\udb82\udd25", "\udb82\udd28" ]`     | Icons for different WiFi signal strengths.                      |
| `ethernet_label`          | string    | `"{wifi_icon}"`                                                                          | The label format during active Ethernet connection.             |
| `ethernet_label_alt`      | string    | `"{wifi_icon} {ip_addr}"`                                                                | The alternative label format during active Ethernet connection. |
| `ethernet_icon`           | string    | "\ueba9"                                                                                 | The icon to indicate Ethernet connection.                       |
| `get_exact_wifi_strength` | boolean   | `false`                                                                                  | Whether to get the exact WiFi signal strength.                  |
| `hide_if_ethernet`        | boolean   | `false`                                                                                  | Whether to hide the widget if an Ethernet connection is active. |
| `callbacks`               | dict      | `{ 'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing' }` | Callbacks for mouse events on the widget.                       |
| `animation`               | dict      | `{ 'enabled': True, 'type': 'fadeInOut', 'duration': 200 }`                              | Animation settings for the widget.                              |
| `container_shadow`        | dict      | `None`                                                                                   | Container shadow options.                                       |
| `label_shadow`            | dict      | `None`                                                                                   | Label shadow options.                                           |
| `menu_config`             | dict      | `None`                                                                                   | Popup menu configuration.                                       |

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
      on_left: "toggle_menu"
      on_middle: "exec cmd.exe /c start ms-settings:network"
      on_right: "toggle_label"
    ethernet_label: "<span>{wifi_icon}</span>"
    ethernet_label_alt: "<span>{wifi_icon}</span>{ip_addr}"
    ethernet_icon: "\ueba9"
    get_exact_wifi_strength: false  # Optional. Will require location access permission if true.
    wifi_icons: [
      "\udb82\udd2e",  # Icon for 0% strength
      "\udb82\udd1f",  # Icon for 1-24% strength
      "\udb82\udd22",  # Icon for 25-49% strength
      "\udb82\udd25",  # Icon for 50-74% strength
      "\udb82\udd28"   # Icon for 75-100% strength
    ]
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
    menu_config:
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "System"
      alignment: "right"
      direction: "down"
      offset_top: 6
      offset_left: 0
      wifi_icons_secured: [
        "\ue670",
        "\ue671",
        "\ue672",
        "\ue673",
      ]
      wifi_icons_unsecured: [
        "\uec3c",
        "\uec3d",
        "\uec3e",
        "\uec3f",
      ]
```

## Description of Options
- **label:** The format string for the WiFi Widget. Default is `"{wifi_icon}"`.
- **label_alt:** The format string for the WiFi Widget when the it's in the alternative state. Default is `"{wifi_icon} {wifi_name}"`.
- **update_interval:** The interval in milliseconds at which the widget updates. Default is `1000`.
- **class_name:** Additional CSS class name for the widget. This allows for custom styling. Default is `""`.
- **get_exact_wifi_strength:** A boolean value that determines whether to get the exact WiFi signal strength. This may require location access permissions in Windows 11. Default is `False`.
- **ethernet_label:** The format string for the WiFi Widget during active Ethernet connection. Default is `"{wifi_icon}"`.
- **ethernet_label_alt:** The format string for the WiFi Widget during active Ethernet connection when the widget is in the alternative state. Default is `"{wifi_icon} {ip_addr}"`.
- **ethernet_icon**: The icon that indicates an active Ethernet connection. It will be used as `{wifi_icon}` whenever there's no active WiFi connection. Default is "\ueba9".
- **hide_if_ethernet:** A boolean value that determines whether to hide the widget if an Ethernet connection is active. Default is `False`.
- **wifi_icons:** A list of icons to use for different WiFi signal strengths. Default is `["\udb82\udd2e","\udb82\udd1f","\udb82\udd22","\udb82\udd25","\udb82\udd28",]`.
- **callbacks:** A dictionary of callbacks for mouse events on the widget. Default is `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}`.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.
- **menu_config:** A dictionary of options for the popup menu. It contains the following keys: `blur`, `round_corners`, `round_corners_type`, `border_color`, `alignment`, `direction`, `offset_top`, `offset_left`, `wifi_icons_secured`, and `wifi_icons_unsecured`.

## Notes on WiFi "Location Access" permissions
- YASB might request a "location access" permission from the user. This is the default security behavior of wifi scanning and exact wifi details access in Windows 11. **YASB does not collect or store any location data**.
- Optional exact wifi strength will not work if the location access is disabled in the Windows 11 settings.
- WiFi popup menu will not work if the location access is disabled in the Windows 11 settings and will show an error message.

## Available Style Classes for the Widget
```css
.wifi-widget {}
.wifi-widget.your_class {} /* If you are using class_name option */
.wifi-widget .widget-container {}
.wifi-widget .widget-container .label {}
.wifi-widget .widget-container .label.alt {}
.wifi-widget .widget-container .icon {}
```

## Available Style Classes for the Menu
```css
.wifi-menu {}
.wifi-menu .progress-bar {}
.wifi-menu .progress-bar::chunk {}
.wifi-menu .header {}
.wifi-menu .error-message {}
.wifi-menu .wifi-list {}
.wifi-menu .wifi-item {}
.wifi-menu .wifi-item[active=true] {}
.wifi-menu .wifi-item .icon {}
.wifi-menu .wifi-item .name {}
.wifi-menu .wifi-item .password {}
.wifi-menu .wifi-item .status {}
.wifi-menu .wifi-item .strength {}
.wifi-menu .wifi-item .controls-container {}
.wifi-menu .wifi-item .connect {}
.wifi-menu .footer {}
.wifi-menu .footer .settings-button {}
.wifi-menu .footer .refresh-icon {}

/* Right click menu style */
.context-menu {}
.context-menu .menu-checkbox {}
.context-menu .menu-checkbox .checkbox {}
.context-menu::item {}
```

## Example Style for the Menu
```css
.wifi-menu {
    font-family: 'Segoe UI';
    background-color: rgba(17, 17, 27, 0.4);
    max-height: 350px;
    min-height: 375px;
    min-width: 375px;
}

.wifi-menu .progress-bar {
    max-height: 2px;
}

.wifi-menu .progress-bar::chunk {
    background-color: #4cc2ff;
}

.wifi-menu .header {
    font-family: 'Segoe UI';
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 2px;
    padding: 12px;
    background-color: rgba(17, 17, 27, 0.6);
    color: white;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.wifi-menu .error-message {
    font-family: 'Segoe UI';
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 2px;
    padding: 12px;
    background-color: red;
    color: white;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.wifi-menu .wifi-list {
    background-color: rgba(17, 17, 27, 0.8);
    margin-right: 3px;
}

.wifi-menu .wifi-item {
    min-height: 35px;
    padding: 2px 12px;
    margin: 2px 4px;
}

.wifi-menu .wifi-item:hover {
    background-color: rgba(255, 255, 255, 0.05);
    border-radius: 6px;
}

.wifi-menu .wifi-item[active=true] {
    background-color: rgba(255, 255, 255, 0.15);
    font-size: 14px;
    border-radius: 6px;
    min-height: 80px;
}

.wifi-menu .wifi-item .icon {
    font-family: 'Segoe Fluent Icons';
    font-size: 26px;
    margin-right: 10px;
}

.wifi-menu .wifi-item .name {
    font-family: 'Segoe UI';
    font-size: 14px;
    margin-right: 10px;
}

.wifi-menu .wifi-item .password {
    font-family: 'Segoe UI';
    background-color: transparent;
    font-size: 14px;
}

.wifi-menu .wifi-item .status {
    font-family: 'Segoe UI';
    font-size: 14px;
}

.wifi-menu .wifi-item .strength {
    font-family: 'Segoe UI';
    font-size: 14px;
}

.wifi-menu .wifi-item .controls-container {
    padding-top: 8px;
}

.wifi-menu .wifi-item .connect {
    background-color: rgba(255, 255, 255, 0.15);
    padding: 4px 30px;
    border-radius: 4px;
    border: none;
    font-size: 14px;
}

.wifi-menu .wifi-item .connect:hover {
    background-color: rgba(255, 255, 255, 0.2);
}

.wifi-menu .wifi-item .connect:pressed {
    background-color: rgba(255, 255, 255, 0.3);
}

.wifi-menu .footer {
    font-size: 12px;
    font-weight: 600;
    padding: 12px;
    margin-top: 2px;
    color: #9399b2;
    background-color: rgba(17, 17, 27, 0.6);
    border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.wifi-menu .footer .settings-button {
    font-family: 'Segoe UI';
    background-color: transparent;
    border: none;
    padding: 0 2px;
    min-width: 26px;
    min-height: 26px;
    color: #fff;
}

.wifi-menu .footer .refresh-icon {
    font-family: 'Segoe Fluent Icons';
    background-color: transparent;
    border: none;
    min-width: 26px;
    min-height: 26px;
    color: #fff;
}

.wifi-menu .footer .refresh-icon:hover {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
}
```

## Preview of the Popup Menu
![Popup Menu Demo](assets/457922931-4ba996e6-0ee6-4f68-9528-2a2f14002104.gif)
