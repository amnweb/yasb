# Taskbar Widget Configuration
| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `icon_size`           | integer  | 16                        | The size of icons |
| `show_only_visible` | boolean | `false` | Whether to show only visible applications in the taskbar. |
| `strict_filtering` | boolean | `true` | Whether to enforce strict filtering of applications based on their properties. |
| `ignore_apps`       | dict    | `processes:[], titles[], classes:[]` | Ignore applications by process name, title, or class. |
| `tooltip`  | boolean  | `True`        | Whether to show the tooltip on hover. |
| `title_label`       | dict    | `{'enabled': False, 'show': 'focused', 'min_length': 10, 'max_length': 30}`                     | Title label configuration for displaying window titles.                     |
| `monitor_exclusive` | boolean | `False` | Whether the application should be exclusive to the monitor. |
| `callbacks`         | dict    | `{'on_left': 'toggle_window', 'on_middle': 'do_nothing', 'on_right': 'close_app'}` | Callbacks for mouse events on the widget.                                   |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |

## Example Configuration

```yaml
taskbar:
  type: "yasb.taskbar.TaskbarWidget"
  options:
    icon_size: 16
    animation:
      enabled: true
    title_label:
      enabled: false
      show: "always"
      min_length: 10
      max_length: 30
    ignore_apps:
      processes: []
      titles: []
      classes: []
```

## Description of Options

- **icon_size:** The size of icons which will show in the widget.
- **show_only_visible:** If set to `True`, the taskbar will only show applications that are currently visible on the screen.
- **strict_filtering:** If set to `True`, the taskbar will enforce strict filtering of applications based on their properties, such as whether they can be minimized or are tool windows, splash screens, etc. This is useful for ensuring that only valid applications are displayed in the taskbar.
- **tooltip:** Whether to show the tooltip on hover.
- **title_label:** A dictionary specifying the configuration for window title labels. It includes:
  - enabled: A boolean flag to enable or disable title labels.
  - show: A string that determines the display behavior (either `"focused"` or `"always"`).
  - min_length: The minimum length of the title label.
  - max_length: The maximum length of the title label.
- **monitor_exclusive:** A boolean indicating whether the application should be exclusive to the monitor. If set to `True`, the taskbar will only show applications on the monitor where the application is running.
- **ignore_apps:** A dictionary that allows you to specify which applications should be ignored by the taskbar widget. It includes:
  - processes: A list of process names to ignore.
  - titles: A list of window titles to ignore.
  - classes: A list of window classes to ignore.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions, which can be `toggle_window`, `do_nothing`, or `close_app`.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds. When animation is enabled, it will be used both for click effects and for animating the addition or removal of applications in the taskbar (such as when apps are opened or closed).

## Style
```css
.taskbar-widget {} /* Main container for the taskbar widget */
.taskbar-widget .widget-container {} /* Container for the widget */
/* Application containers */
.taskbar-widget .app-container {} /* container for each app */
.taskbar-widget .app-container.foreground {} /* container for the focused app */
.taskbar-widget .app-container.flashing {} /* flashing container for the app (window is flashing) */
.taskbar-widget .app-container .app-icon {} /* Icon inside the container */
.taskbar-widget .app-container .app-title {} /* Label inside the container */
```

## Style Example
```css
.taskbar-widget .app-container {
    margin: 4px 2px;
    border-radius: 4px;
    padding: 0 4px;
}
.taskbar-widget .app-container.foreground {
    background-color: rgba(255, 255, 255, 0.1);
}
.taskbar-widget .app-container.flashing {
    background-color: rgba(255, 106, 106, 0.63);
}
.taskbar-widget .app-container .app-title {
    padding-left: 4px;
}
```