# Window Controls Widget Configuration

Window Controls widget provides buttons for minimizing, maximizing/restoring, and closing the focused window, along with an optional label showing the application's name. It can be configured to only appear for maximized windows or for any focused window, and can be set to only respond to windows on the same monitor.

| Option              | Type    | Default                                                                 | Description                                                                 |
|---------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `class_name`        | string  | `""`                                                                    | Additional CSS class name for the widget.                                   |
| `show_app_name`     | boolean | `false`                                                                 | Show the friendly application name (e.g., "Firefox", "Windows Terminal") as a label next to the buttons. |
| `maximized_only`    | boolean | `true`                                                                  | When `true`, widget only appears for maximized windows. When `false`, appears for any focused window. |
| `buttons`           | list    | `["minimize", "maximize", "close"]`                                     | Ordered list of buttons to display. Valid values: `minimize`, `maximize`, `restore`, `close`. |
| `button_labels`     | dict    | `{minimize: "\uea71", maximize: "\uea71", restore: "\uea71", close: "\uea71"}` | Custom labels/icons for each button. |
| `monitor_exclusive` | boolean | `true`                                                                  | Whether the widget should only respond to windows on the same monitor. |
| `animation_duration`| integer | `120`                                                                   | The duration of the show/hide animation in milliseconds. Must be between 0 and 2000. Set to 0 to disable animation. |

## Example Configuration

```yaml
window_controls:
  type: "yasb.window_controls.WindowControlsWidget"
  options:
    show_app_name: true
    maximized_only: false
    buttons: ["minimize", "maximize", "close"]
    button_labels:
      minimize: "\uea71"
      maximize: "\uea71"
      restore: "\uea71"
      close: "\uea71"
    monitor_exclusive: true
    animation_duration: 120
```

## Description of Options

- **class_name:** Additional CSS class name for the widget. This allows for custom styling.
- **show_app_name:** When `true`, displays the friendly application name (e.g., "Firefox", "Windows Terminal", "Visual Studio Code") as a label next to the buttons.
- **maximized_only:** When `true` (default), the widget only appears when a maximized window is focused, and hides when the window is restored. When `false`, the widget appears for any focused window regardless of its state.
- **buttons:** An ordered list of buttons to display. You can include any combination of `minimize`, `maximize`, `restore`, and `close` in any order. The `maximize` button automatically toggles between maximize and restore icons based on window state. The `restore` button always restores.
- **button_labels:** A dictionary mapping each button name to its display text or icon. The `maximize` button uses `maximize` label when the window is normal and `restore` label when maximized.
- **monitor_exclusive:** When `true`, the widget only appears when the focused window is on the same monitor as the bar containing this widget. When `false`, it appears for any focused window regardless of monitor.
- **animation_duration:** The duration of the slide+fade animation when the widget appears or disappears, in milliseconds. Must be between 0 and 1000. Set to `0` to disable animation (instant show/hide).


## Available Styles
```css
.window-controls-widget {}
.window-controls-widget.your_class {} /* If you are using class_name option */
.window-controls-widget .widget-container {}
.window-controls-widget .app-name {}
.window-controls-widget .btn {}
.window-controls-widget .btn.minimize {}
.window-controls-widget .btn.maximize {}
.window-controls-widget .btn.restore {}
.window-controls-widget .btn.close {}
```

## Example Style
```css
.window-controls-widget {
    padding: 0;
    margin: 0;
}
.window-controls-widget .btn {
    font-family: "JetBrainsMono NFP";
    font-size: 18px;
    min-width: 18px;
    min-height: 18px;
    margin: 0;
    background-color: transparent;
    border: none;
}
.window-controls-widget .btn.minimize {
    color: #FFBD2E;
}
.window-controls-widget .btn.minimize:hover {
    color: #ffc853;
}
.window-controls-widget .btn.maximize {
    color: #28C840;
}
.window-controls-widget .btn.maximize:hover {
    color: #60ff78;
}
.window-controls-widget .btn.restore {
    color: #28C840;
}
.window-controls-widget .btn.restore:hover {
    color: #60ff78;
}
.window-controls-widget .btn.close {
    color: #FF5F57;
}
.window-controls-widget .btn.close:hover {
    color: #ff8a84;
}
.window-controls-widget .app-name {
    font-family: "Segoe UI";
    font-size: 12px;
    padding-left: 4px;  
    font-weight: 600;    
}
```
