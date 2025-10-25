# Config file

The configuration uses the YAML file format and is named `config` or `config.yaml`.

Valid directories for this file are `C:/Users/{username}/.config/yasb/` or ENV variable `YASB_CONFIG_HOME` if set.
A good starting point is the [default config](https://github.com/amnweb/yasb/blob/main/src/config.yaml).

All valid options for the widgets are listed on the widgets page.


# Environment Variables Support

YASB supports loading environment variables from a `.env` file.  
This allows you to securely store sensitive information (such as API keys or tokens) outside of your main `config.yaml`.

- The `.env` file should be placed in your config directory:  
  `C:/Users/{username}/.config/yasb/.env`  
  or in the directory specified by the `YASB_CONFIG_HOME` environment variable.
- Variables defined in `.env` can be referenced in your `config.yaml` by setting the value to `env` (for example, `api_key: env` or `api_key: "$env:YASB_WEATHER_API_KEY"`).
- The `.env` file is loaded automatically on startup.

**Example `.env` file:**
```
YASB_FONT_ENGINE=native
YASB_WEATHER_API_KEY=your_api_key_here
YASB_GITHUB_TOKEN=your_github_token_here
YASB_WEATHER_LOCATION=your_location_here
# Some Qt settings
QT_SCREEN_SCALE_FACTORS="1.25;1"
QT_SCALE_FACTOR_ROUNDING_POLICY="PassThrough"
```

## YASB Font Engine
YASB supports different font engines to improve text rendering quality.
You can set the font engine by defining the `YASB_FONT_ENGINE` environment variable in your `.env` file or in OS environment variables.
Valid options are:
- `native`: Uses the DirectWrite font rendering engine.
- `gdi`: Uses the GDI font rendering engine.
- `freetype`: Uses the FreeType font rendering engine.


## Status Bar Root Configuration
| Option            | Type    | Default       | Description |
|-------------------|---------|---------------|-------------|
| `watch_stylesheet`         | boolean | `true`        | Reload bar when style is changed. |
| `watch_config`         | boolean    | `true`        | Reload bar when config is changed. |
| `debug`      | boolean  | `false`   | Enable debug mode to see more logs |
| `update_check`      | boolean  | `true`   | Enable automatic update check. This works only if the application is installed. |
| `show_systray`      | boolean  | `true`   | Show or hide the YASB system tray icon. |
| `komorebi`      | object  | [See below](#komorebi-settings-for-tray-menu)   | Komorebi configuration for tray menu. |
| `glazewm`      | object  | [See below](#glazewm-settings-for-tray-menu)   | Glazewm configuration for tray menu. |


## Komorebi settings for tray menu
| Option            | Type    | Default       | Description |
|-------------------|---------|---------------|-------------|
| `start_command`         | string | `"komorebic start --whkd"` | Start komorebi with --whkd and default config location. |
| `stop_command`         | string    | `"komorebic stop --whkd"` | Stop komorebi. |
| `reload_command`      | string  | `"komorebic reload-configuration"` | Reload komorebi configuration.|


## Glazewm settings for tray menu
| Option            | Type    | Default       | Description |
|-------------------|---------|---------------|-------------|
| `start_command`         | string | `"glazewm.exe start"` | Start
| `stop_command`         | string    | `"glazewm.exe command wm-exit"` | Stop glazewm. |
| `reload_command`      | string  | `"glazewm.exe command wm-exit && glazewm.exe start"` | Reload glazewm configuration.|


## Status Bar Configuration
| Option            | Type    | Default       | Description |
|-------------------|---------|---------------|-------------|
| `enabled`         | boolean | `true`        | Whether the status bar is enabled. |
| `screens`         | list    | `['*']`       | The screens on which the status bar should be displayed. Use `['*']` for all unassigned screens, `['**']` for all screens (including assigned), or specify screen names like `['DELL P2419H (1)']`. |
| `class_name`      | string  | `"yasb-bar"`  | The CSS class name for the status bar. |
| `alignment`       | object  | [See below](#bar-alignment) | The alignment settings for the status bar. |
| `blur_effect`     | object  | [See below](#blur-effect-configuration) | The blur effect settings for the status bar. |
| `window_flags`    | object  | [See below](#window-flags-configuration) | The window flags for the status bar. |
| `dimensions`      | object  | `{width: "100%", height: 36}` | The dimensions of the status bar. Width can be a number (pixels), percentage string (e.g., `"100%"`, `"50%"`), or `"auto"` to resize based on content. When using `"auto"`, the bar will automatically resize as widget content changes, with a maximum width of the available screen width minus padding. |
| `padding`         | object  | `{top: 4, left: 0, bottom: 4, right: 0}` | The padding for the status bar. |
| `animation`       | object  | `{enabled: true, duration: 500}` | The animation settings for the status bar. Duration is in milliseconds. Animation is used to show/hide the bar smoothly. |
| `widgets`         | list  | `left[], center[], right[]` | Active widgets and position. |
| `layouts`         | object  | [See below](#layouts-configuration) | Configuration for widget layouts in each section (left, center, right). |

> **note:**
> Setting the width to `"auto"` is not recommended for widgets that constantly update data, such as CPU, memory, clock, etc. This can cause the bar to constantly resize, which may lead to flickering or performance issues.

> **Note:**
> `screens` can be specified as a list of monitor names. If you want the bar to appear on all screens, use `['*']`. To specify a single screen, use `['DELL P2419H (1)']` or a similar name based on your monitor setup. To show the bar only and always on the primary screen, use `['primary']`.


### Bar Alignment
| Option            | Type    | Default       | Description |
|-------------------|---------|---------------|-------------|
| `position`        | string  | `"top"`       | The position of the status bar, can be `"top"` or `"bottom"` |
| `align`          | string |  `"center"` | The alignment of the status bar, can be `"left"`, `"center"`, or `"right"` |


### Blur Effect Configuration
| Option            | Type    | Default       | Description |
|-------------------|---------|---------------|-------------|
| `enabled`         | boolean | `false`       | Whether the blur effect is enabled. |
| `acrylic`         | boolean | `false`       | Whether to use an acrylic blur effect (Windows 10). |
| `dark_mode`       | boolean | `false`       | Whether to enable dark mode and more shadow below the bar. |
| `round_corners`   | boolean | `false`       | Whether to enable rounded corners for the bar. Note: This is only effective on Windows 11. |
| `round_corners_type` | string | `'normal'` | The type of rounded corners, can be `normal` or `small`. Note: This is only effective on Windows 11. |
| `border_color`    | string  | `'system'`   | The border color for the bar, can be `None`, `"system"`, or a hex color (e.g., `"#ff0000"`). Note: This is only effective on Windows 11. |


### Window Flags Configuration
| Option            | Type    | Default       | Description |
|-------------------|---------|---------------|-------------|
| `always_on_top`   | boolean | `false`       | Whether the status bar should always stay on top of other windows. |
| `windows_app_bar` | boolean | `true`        | Whether the status bar should behave like a Windows app bar. |
| `hide_on_fullscreen` | boolean | `false`    | Whether the status bar should hide when a window is in fullscreen mode. |
| `auto_hide` | boolean | `false`    | Whether the status bar should auto-hide when not in use. |

### Layouts Configuration
Each section (left, center, right) can be configured with the following properties:

| Option            | Type    | Default       | Description |
|-------------------|---------|---------------|-------------|
| `alignment`       | string  | Section-dependent | Widget alignment within section ("left", "center", "right") |
| `stretch`         | boolean | `true`        | Whether widgets should stretch to fill available space |

Example:
```yaml
layouts:
  left:
    alignment: "left"
    stretch: true
  center:
    alignment: "center"
    stretch: true
  right:
    alignment: "right"
    stretch: true
```

# Multiple Bars Example
> **Note:**
> If you want to have different bars on each screen you will need to define on which screen the bar should be displayed, `screens` inside bar config is your monitor name. You can find your monitor names using `yasbc monitor-information` or inside device manager.

## Screen Assignment Options:
- `screens: ['*']` - Show on all **unassigned** screens (screens not explicitly assigned to other bars)
- `screens: ['**']` - Show on **all screens** (including screens assigned to other bars)
- `screens: ['SCREEN_NAME']` - Show on specific screen(s)

```
bars:
  status-bar:
    screens: ['DELL P2419H (1)']  # Show only on monitor 1
    widgets:
      left: ["clock"]
      center: ["cpu"]
      right: ["memory"]

  status-bar-2:
    screens: ['DELL P2419H (2)']  # Show only on monitor 2
    widgets:
      left: ["active_window"]
      center: ["media"]
      right: ["volume","power_menu"]

  status-bar-3:
    screens: ['*']  # Show on all unassigned screens
    widgets:
      center: ["weather"]

  global-taskbar:
    screens: ['**']  # Show on ALL screens (including monitors 1 and 2)
    widgets:
      left: ["taskbar"]

widgets:
    ...
```
