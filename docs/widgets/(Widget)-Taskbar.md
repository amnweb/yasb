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
| `hide_empty`        | boolean | `False` | Whether to hide the taskbar widget when there are no applications to display. |
| `callbacks`         | dict    | `{'on_left': 'toggle_window', 'on_middle': 'do_nothing', 'on_right': 'context_menu'}` | Callbacks for mouse events on the widget.                                   |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `preview`           | dict    | `{'enabled': False, 'width': 240, 'delay': 400, 'padding': 8, 'margin': 8}` | Configuration for window preview thumbnails.                                |

## Example Configuration

```yaml
taskbar:
  type: "yasb.taskbar.TaskbarWidget"
  options:
    icon_size: 16
    tooltip: true
    show_only_visible: false
    strict_filtering: true
    monitor_exclusive: false
    animation:
      enabled: true
    preview:
      enabled: false
      width: 240
      delay: 400
      padding: 8
      margin: 8
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
- **hide_empty:** A boolean indicating whether to hide the taskbar widget when there are no applications to display. If set to `True`, the taskbar will automatically hide itself when there are no open applications that meet the filtering criteria.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions, which can be `toggle_window`, `do_nothing`, `close_app` or `context_menu`.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds. When animation is enabled, it will be used both for click effects and for animating the addition or removal of applications in the taskbar (such as when apps are opened or closed).
- **preview:** A dictionary specifying the configuration for window preview thumbnails. It includes:
  - enabled: A boolean flag to enable or disable window previews.
  - width: The width of the preview thumbnail in pixels. (minimum 100px)
  - delay: The delay in milliseconds before showing the preview after hovering over an application icon.
  - padding: The padding around the preview thumbnail in pixels.
  - margin: The margin between the preview thumbnail and the taskbar in pixels.

> Note:
> When **preview** is enabled **tooltip** are automatically disabled to avoid overlap.

## Style
```css
.taskbar-widget {} /* Main container for the taskbar widget */
.taskbar-widget .widget-container {} /* Container for the widget */
/* Application containers */
.taskbar-widget .app-container {} /* container for each app */
.taskbar-widget .app-container.foreground {} /* container for the focused app */
.taskbar-widget .app-container.flashing {} /* flashing container for the app (window is flashing) */
.taskbar-widget .app-container.running {} /* container for running apps (not focused) */
.taskbar-widget .app-container .app-icon {} /* Icon inside the container */
.taskbar-widget .app-container .app-title {} /* Label inside the container */
/* Taskbar preview popup is very limited in styling options, do not use margins/paddings here */
.taskbar-preview {}
.taskbar-preview .header {}
.taskbar-preview .header .title {}
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
.taskbar-widget .app-container.running {
    background-color: rgba(255, 255, 255, 0.25);
}
.taskbar-widget .app-container:hover {
    background-color: rgba(255, 255, 255, 0.15);
}
.taskbar-widget .app-container .app-title {
    padding-left: 4px;
}
/* Taskbar preview popup is very limited in styling options, do not use margins/paddings here */
.taskbar-preview {
    border-radius: 8px; 
    background-color: #2b2c2d; 
}
.taskbar-preview.flashing { 
    background-color: #7f434a;
}
.taskbar-preview .header {
    padding-bottom: 12px;
    padding-top: 4px;
}
.taskbar-preview .header .title {
    color: #d6d6d6;
    font-family: "Segoe UI";
    font-weight: 600;
    font-size: 13px;
}
```