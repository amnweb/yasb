# Taskbar Widget Configuration
| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `icon_size`           | integer  | 16                        | The size of icons |
| `ignore_apps`       | dict    | `processes:[],titles[],classes:[]` | Ignore some apps. |
| `animation`  | boolean | `false`      | Icons animation.                                           |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.

## Example Configuration

```yaml
taskbar:
  type: "yasb.taskbar.TaskbarWidget"
  options:
    icon_size: 16
    animation: true
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
- **animation:** Icons animation.
- **container_padding:** Explicitly set padding inside widget container.
- **ignore_apps:** A dictionary that allows you to specify which applications should be ignored by the taskbar widget. It includes:
- processes: A list of process names to ignore.
- titles: A list of window titles to ignore.
- classes: A list of window classes to ignore.
 


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