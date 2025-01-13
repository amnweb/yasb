# Taskbar Widget Configuration
| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `icon_size`           | integer  | 16                        | The size of icons |
| `ignore_apps`       | dict    | `processes:[],titles[],classes:[]` | Ignore some apps. |
| `tooltip`  | boolean  | `True`        | Whether to show the tooltip on hover. |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.
| `callbacks`         | dict    | `{'on_left': 'toggle_window', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}` | Callbacks for mouse events on the widget.                                   |
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
- **container_padding:** Explicitly set padding inside widget container.
- **ignore_apps:** A dictionary that allows you to specify which applications should be ignored by the taskbar widget. It includes:
- processes: A list of process names to ignore.
- titles: A list of window titles to ignore.
- classes: A list of window classes to ignore.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions, which can be `toggle_window`.
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
```

> [!IMPORTANT]  
> Taskbar apps will work only if they are minimized so that YASB can restore them on click; if you close the app to go in the system tray, YASB can't work in that way.