# Taskbar Widget Configuration

Puts your running apps on the status bar, working just like a standard taskbar. You can pin your favorite apps, group every window of an app under one icon, drag and drop buttons to reorder them, hover to see window preview thumbnails, and right-click to minimize, focus, or close windows.

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
| `preview`           | dict    | `{'enabled': False, 'width': 240, 'delay': 400, 'padding': 8, 'margin': 8, 'blur': False, 'peek': False}` | Configuration for window preview thumbnails.                                |
| `grouping`          | dict    | `{'enabled': False, 'show_count': True}` | Combine all windows of the same app into a single button. |
| `animation`         | dict    | `{'enabled': True, 'duration': 200}` | Configuration for animations when switching between applications. |

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
      duration: 200
    preview:
      enabled: false
      width: 240
      delay: 400
      padding: 8
      margin: 8
      blur: false
      peek: false
    grouping:
      enabled: false
      show_count: true
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

- **icon_size:** The size of icons which will show in the widget. Set to `0` to disable icons completely and show only title labels.
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
- **preview:** A dictionary specifying the configuration for window preview thumbnails. It includes:
  - enabled: A boolean flag to enable or disable window previews.
  - width: The width of the preview thumbnail in pixels. (minimum 100px)
  - delay: The delay in milliseconds before showing the preview after hovering over an application icon.
  - padding: The padding around the preview thumbnail in pixels.
  - margin: The margin between the preview thumbnail and the taskbar widget in pixels.
  - blur: A boolean flag to apply the Windows blur backdrop behind the preview.
  - peek: A boolean flag to fade every other window on the desktop while a thumbnail is hovered, the same as Aero Peek.
- **grouping:** A dictionary specifying how windows of the same application are combined. It includes:
  - enabled: A boolean flag to combine every window of an application into a single taskbar button.
  - show_count: A boolean flag to show the number of windows on a grouped button. The counter is hidden while the button holds only one window.

> Note:
> When **preview** is enabled **tooltip** are automatically disabled to avoid overlap.

> Note:
> Applications are grouped by the same identity used for pinning, so a grouped button also takes over the slot of its pinned app. File Explorer windows are identified by their folder, which is what lets you pin folders separately, so they group per folder. The folder is read when the window opens, navigating an existing window does not move it to another group.

## Available CSS Classes
```css
.taskbar-widget {} /* Main container for the taskbar widget */
.taskbar-widget .widget-container {} /* Container for the widget */
/* Application containers */
.taskbar-widget .app-container {} /* container for each app */
.taskbar-widget .app-container.foreground {} /* container for the focused app */
.taskbar-widget .app-container.flashing {} /* flashing container for the app (window is flashing) */
.taskbar-widget .app-container.running {} /* container for running apps (not focused) */
.taskbar-widget .app-container.running.minimized {} /* container for apps whose windows are all minimized */
.taskbar-widget .app-container.grouped {} /* container holding more than one window of the same app */
.taskbar-widget .app-container .app-icon {} /* Icon inside the container */
.taskbar-widget .app-container .app-title {} /* Label inside the container */
.taskbar-widget .app-container .app-count {} /* Window counter, only shown on grouped containers */
/* Taskbar preview popup is very limited in styling options, do not use margins/paddings here */
.taskbar-preview {}
.taskbar-preview .preview-item {} /* One window inside the preview: header, thumbnail and the padding around them */
.taskbar-preview .preview-item:hover {} /* Hovered window of a grouped preview */
.taskbar-preview .header {}
.taskbar-preview .header .title {}
.taskbar-preview .close-button {} /* Close button on the preview */
```

## Style Example
```css
.taskbar-widget .app-container {
    margin: 0 2px;
    border-radius: 4px;
    padding: 0 8px;
    border: 1px solid transparent
}
.taskbar-widget .app-container.foreground {
    background-color: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.1);
}
.taskbar-widget .app-container.running {
    background-color: transparent;
}
.taskbar-widget .app-container.running.minimized .app-icon {
    opacity: 0.5;
}
.taskbar-widget .app-container:hover {
    background-color: rgba(255, 255, 255, 0.15);
}
.taskbar-widget .app-container .app-title {
    padding-left: 4px; 
    font-size: 12px;
}
.taskbar-widget .app-container .app-count {
    background-color: rgba(255, 255, 255, 0.1);
    padding: 0 4px;
    margin-left: 4px;
    margin-right: 0;
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
    font-size: 12px;
}
.taskbar-widget .app-container.grouped {
    background-color: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding-right: 0;
}
/* Flashing always needs to go last so it doesn't get overwritten. */
.taskbar-widget .app-container.flashing {
    background-color: rgba(241, 127, 127, 0.45);
}
.taskbar-widget .app-container.flashing .app-count {
    background-color: rgba(241, 127, 127, 0.3);
}

/* The taskbar preview is really limited on styling options, so don't use margins or paddings here. Use the config for that instead. */
.taskbar-preview {
    border-radius: 8px;
    background-color: rgba(38, 38, 38, 0.8); 
}
.taskbar-preview .preview-item {
    background-color: rgba(38, 38, 38, 0.01); 
}
.taskbar-preview .preview-item:hover {
    background-color: rgba(255, 255, 255, 0.1); 
}
.taskbar-preview .preview-item.flashing { 
    background-color: rgba(241, 127, 127, 0.45);
}
.taskbar-preview .header {
    padding-bottom: 8px;
    padding-top: 0;
}
.taskbar-preview .preview-item .header .title {
    color: #d6d6d6;
    font-family: "Segoe UI";
    font-weight: 600;
    font-size: 13px;
}
.taskbar-preview .preview-item .close-button {
    font-size: 10px;
    min-width: 24px;
    min-height: 24px;
    border-radius: 4px;
    color: #eee;
    background-color: transparent;
    font-family: "Segoe Fluent Icons";
}
.taskbar-preview .preview-item .close-button:hover {
    color: #ffffff;
    background-color: #c42b1c;
}
```