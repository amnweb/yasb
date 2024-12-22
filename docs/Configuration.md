# Config file

The configuration uses the YAML file format and is named `config` or `config.yaml`.

Valid directories for this file are `C:/Users/{username}/.config/yasb/` or path where YASB is Installed.
A good starting point is the [default config](https://github.com/amnweb/yasb/blob/main/src/config.yaml).

All valid options for the widgets are listed on the widgets page.


 
## Status Bar Root Configuration
| Option            | Type    | Default       | Description |
|-------------------|---------|---------------|-------------|
| `watch_stylesheet`         | boolean | `true`        | Reload bar when style is changed. |
| `watch_config`         | boolean    | `true`        | Reload bar when config is changed. |
| `debug`      | boolean  | `false`   | Enable debug mode to see more logs |
| `hide_taskbar`      | boolean  | `false`   | Hide Windows taskbar from all screens. Note: for better performance set taskbar auto-hide. |


## Komorebi settings for tray menu
| Option            | Type    | Default       | Description |
|-------------------|---------|---------------|-------------|
| `start_command`         | string | `"komorebic start --whkd"` | Start komorebi with --whkd and default config location. |
| `stop_coommand`         | string    | `"komorebic stop --whkd"` | Stop komorebi. |
| `reload_command`      | string  | `"komorebic reload-configuration"` | Reload komorebi configuration.|



## Status Bar Configuration
| Option            | Type    | Default       | Description |
|-------------------|---------|---------------|-------------|
| `enabled`         | boolean | `true`        | Whether the status bar is enabled. |
| `screens`         | list    | `['*']`       | The screens on which the status bar should be displayed. |
| `class_name`      | string  | `"yasb-bar"`  | The CSS class name for the status bar. |
| `alignment`       | object  | `{position: "top", center: false}` | The alignment settings for the status bar. |
| `blur_effect`     | object  | `{enabled: false, acrylic: false, dark_mode: false, round_corners: false, border_color: System}` | The blur effect settings for the status bar. |
| `window_flags`    | object  | `{always_on_top: false, windows_app_bar: true}` | The window flags for the status bar. |
| `dimensions`      | object  | `{width: "100%", height: 36}` | The dimensions of the status bar. |
| `padding`         | object  | `{top: 4, left: 0, bottom: 4, right: 0}` | The padding for the status bar. |
| `animation`       | object  | `{enabled: true, duration: 500}` | The animation settings for the status bar. Duration is in milliseconds. |
| `widgets`         | list  | `left[],center[],right[]` | Active widgets and position. |

# Multiple Bars Example
> **Note:**
> If you want to have different bars on each screen you will need to define on which screen the bar should be displayed, `screens` inside bar config is your monitor name. You can find your monitor name inside device manager or click on YASB tray icon and select Debug > Information to show all available screens.

```
bars:
  status-bar:
    screens: ['DELL P2419H (1)'] 
    widgets:
      left: ["clock"]
      center: ["cpu"]
      right: ["memory"]

  status-bar-2:
    screens: ['DELL P2419H (2)'] 
    widgets:
      left: ["active_window"]
      center: ["media"]
      right: ["volume","power_menu"]

widgets:
    ...
```

# Blur Options
We used Windows API for blur, and because of this some parts are limited with the OS.

`blur_effect.enabled` Will enable defaul blur.<br>
`blur_effect.acrylic` Enable an acrylic blur effect behind a window. (Windows 10)<br>
`blur_effect.dark_mode` Dark mode and more shadow below bar.<br>
`blur_effect.round_corners` True or False, if set to True Windows will add radius. You can't set a custom value.<br>
`blur_effect.border_color` Border color for bar can be `None`, `System` or `Hex Color` `"#ff0000"`. (This applies to system round_corners and if blur_effect.round_corners is True.)