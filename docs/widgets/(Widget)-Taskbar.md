# Taskbar Widget Configuration
| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `icon_size`           | integer  | 16                        | The size of icons |
| `ignore_apps`       | dict    | `processes:[],titles[],classes:[]` | Ignore some apps. |
| `tooltip`  | boolean  | `True`        | Whether to show the tooltip on hover. |
| `title_label`       | dict    | `{'enabled': False, 'show': 'focused', 'min_length': 10, 'max_length': 30}`                     | Title label configuration for displaying window titles.                     |
| `monitor_exclusive` | boolean | `False` | Whether the application should be exclusive to the monitor. |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.
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
      duration: 200
      type: "fadeInOut"
    title_label:
      enabled: false
      show: "focused"
      min_length: 10
      max_length: 30
    ignore_apps:
      processes: []
      titles: []
      classes: []
    container_padding: 
      top: 0
      left: 8
      bottom: 0
      right: 8
```

## Description of Options

- **icon_size:** The size of icons which will show in the widget.
- **tooltip:** Whether to show the tooltip on hover.
- **title_label:** A dictionary specifying the configuration for window title labels. It includes:
  - enabled: A boolean flag to enable or disable title labels.
  - show: A string that determines the display behavior (either "focused" or "always").
  - min_length: The minimum length of the title label.
  - max_length: The maximum length of the title label.
- **monitor_exclusive:** A boolean indicating whether the application should be exclusive to the monitor. If set to `True`, the taskbar will only show applications on the monitor where the application is running.
- **container_padding:** Explicitly set padding inside widget container.
- **ignore_apps:** A dictionary that allows you to specify which applications should be ignored by the taskbar widget. It includes:
- processes: A list of process names to ignore.
- titles: A list of window titles to ignore.
- classes: A list of window classes to ignore.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions, which can be `toggle_window`, `do_nothing`, or `close_app`.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.

## Style
```css
.taskbar-widget {
    padding: 0;
    margin: 0;
}
.taskbar-widget .app-icon {
    padding:0 6px;
}
.taskbar-widget .app-icon.foreground{
    background-color: rgba(0, 0, 0, 0.4);
}
/* if title_label is enabled: */
.taskbar-widget .app-title {}
.taskbar-widget .app-title.foreground {}
```

> [!IMPORTANT]  
> The title label is disabled by default. If you decide to enable it, keep in mind that it may result in slightly higher CPU usage.