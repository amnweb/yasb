# Memory Widget Configuration
| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`           | string  | `'\uf4bc {virtual_mem_free}/{virtual_mem_total}'`                        | The format string for the memory widget. Displays free and total virtual memory. |
| `label_alt`       | string  | `'\uf4bc VIRT: {virtual_mem_percent}% SWAP: {swap_mem_percent}%'`        | The alternative format string for the memory widget. Displays virtual and swap memory percentages. |
| `class_name`        | string  | `""`                                                                                  | Additional CSS class name for the widget.                                    |
| `update_interval` | integer | `5000`                                                                  | The interval in milliseconds to update the memory widget. Must be between 0 and 60000. |
| `callbacks`       | dict    | `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}` | Callbacks for mouse events on the memory widget. |
| `histogram_icons`     | list    | `["\u2581", "\u2581", "\u2582", "\u2583", "\u2584", "\u2585", "\u2586", "\u2587", "\u2588"]` | Icons representing RAM usage histograms.                                    |
| `memory_thresholds` | dict  | `{'low': 25, 'medium': 50, 'high': 90}`                                 | Thresholds for memory usage levels. |
| `progress_bar`       | dict    | `{'enabled': False, 'position': 'left', 'size': 14, 'thickness': 2, 'color': '#57948a', 'animation': True}` | Progress bar settings.    |
| `hide_decimal`       | boolean    | `false`                                                                 | Whether to hide decimal places in the memory widget. |
| `menu`               | dict    | See below                                                               | Configuration for the popup menu with graph and stats. |

## Example Configuration

```yaml
memory:
  type: "yasb.memory.MemoryWidget"
  options:
    label: "<span>\uf4bc</span> {virtual_mem_free}/{virtual_mem_total}"
    label_alt: "<span>\uf4bc</span> VIRT: {virtual_mem_percent}% SWAP: {swap_mem_percent}%"
    update_interval: 5000
    callbacks:
      on_left: "toggle_label"
      on_right: "toggle_menu"
    memory_thresholds:
      low: 25
      medium: 50
      high: 90
    histogram_icons:
      - "\u2581" # 0%
      - "\u2581" # 10%
      - "\u2582" # 20%
      - "\u2583" # 30%
      - "\u2584" # 40%
      - "\u2585" # 50%
      - "\u2586" # 60%
      - "\u2587" # 70%
      - "\u2588" # 80%+
    menu:
      enabled: true
      show_graph: true
      show_graph_grid: true
      graph_history_size: 60
```

## Description of Options

- **label:** The format string for the memory widget. Displays free and total virtual memory.
- **label_alt:** The alternative format string for the memory widget. Displays virtual and swap memory percentages.
- **class_name:** Additional CSS class name for the widget. This allows for custom styling.
- **update_interval:** The interval in milliseconds to update the memory widget. Must be between 0 and 60000.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **memory_thresholds:** A dictionary specifying the thresholds for memory usage levels. The keys are `low`, `medium`, and `high`, and the values are the percentage thresholds.
- **hide_decimal:** Whether to hide decimal places in the memory widget.
- **histogram_icons**: A list of icons representing different levels of memory usage in the histogram. 9 icons are typically used, representing usage from 0% to 80%+. Can be used by putting `{histogram}` in the label.
- **menu**: Configuration for the popup menu that displays a usage graph and detailed memory statistics. It includes:
  - **enabled**: Whether the popup menu is enabled. Default: `false`.
  - **blur**: Whether to apply a blur effect to the popup background. Default: `true`.
  - **round_corners**: Whether the popup has rounded corners. Default: `true`.
  - **round_corners_type**: The type of rounded corners, either `"normal"` or `"small"`. Default: `"normal"`.
  - **border_color**: The border color of the popup. Default: `"System"`.
  - **alignment**: Horizontal alignment of the popup relative to the widget: `"left"`, `"center"`, or `"right"`. Default: `"right"`.
  - **direction**: Whether the popup opens `"up"` or `"down"`. Default: `"down"`.
  - **offset_top**: Vertical offset in pixels from the widget. Default: `6`.
  - **offset_left**: Horizontal offset in pixels from the widget. Default: `0`.
  - **show_graph**: Whether to show the usage history graph. Default: `true`.
  - **show_graph_grid**: Whether to display a square grid overlay on the graph. Default: `false`.
  - **graph_history_size**: Number of data points to keep in the graph history. Must be between 10 and 180. Default: `60`.
  - **pin_icon**: Icon displayed on the pin button when the popup is unpinned. Default: `"\ue718"`.
  - **unpin_icon**: Icon displayed on the pin button when the popup is pinned. Default: `"\ue77a"`.
- **progress_bar**: A dictionary containing settings for the progress bar. It includes:
  - **enabled**: Whether the progress bar is enabled.
  - **position**: The position of the progress bar, either "left" or "right".
  - **size**: The size of the progress bar.
  - **thickness**: The thickness of the progress bar.
  - **color**: The color of the progress bar. Color can be single color or gradient. For example, `color: "#57948a"` or `color: ["#57948a", "#ff0000"]"` for a gradient.
  - **background_color**: The background color of the progress bar.
  - **animation**: Whether to enable smooth change of the progress bar value.

The `label` and `label_alt` options use format strings that can include placeholders for memory metrics. These placeholders will be replaced with actual values when the widget is rendered. You can use `{virtual_mem_free}`, `{virtual_mem_percent}`, `{virtual_mem_total}`, `{virtual_mem_avail}`, `{virtual_mem_used}`, `{virtual_mem_outof}`, `{swap_mem_free}`, `{swap_mem_percent}`, `{swap_mem_total}`


## Example Style
```css
.memory-widget {}
.memory-widget .widget-container {}
.memory-widget .widget-container .label {}
.memory-widget .widget-container .label.alt {}
.memory-widget .widget-container .icon {}

/* Status classes based on memory_thresholds */
.memory-widget .widget-container .label.status-low {}
.memory-widget .widget-container .label.status-medium {}
.memory-widget .widget-container .label.status-high {}
.memory-widget .widget-container .label.status-critical {}

/* Icon status classes */
.memory-widget .widget-container .icon.status-low {}
.memory-widget .widget-container .icon.status-medium {}
.memory-widget .widget-container .icon.status-high {}
.memory-widget .widget-container .icon.status-critical {}

/* Progress bar styles (if enabled) */
.memory-widget .progress-circle {}

/* Custom class styling */
.memory-widget.your-class-name {}
.memory-widget.your-class-name .label {}
```

### Popup Menu Styles
```css
.memory-popup {
    background-color: rgba(28, 28, 28, 0.7);
    min-width: 400px;
}

.memory-popup .header {
    background: transparent;
    padding: 12px 16px;
}
.memory-popup .header .text {
    font-size: 16px;
    font-family: "Segoe UI";
    color: rgb(255, 255, 255);
}
.memory-popup .header .pin-btn {
    font-size: 14px;
    background: transparent;
    font-family: "Segoe Fluent Icons";
    border: none;
    padding: 6px;
    color: rgba(255, 255, 255, 0.6);
}
.memory-popup .header .pin-btn:hover {
    color: rgba(255, 255, 255, 0.6);
}
.memory-popup .header .pin-btn.pinned {
    color: #ffffff;
}
/* Graph area */
.memory-popup .graph-container {
    background:  transparent;
    min-height: 64px;
}
.memory-popup .memory-graph {
    color: #0f6bff;   /* <-- set the graph line/fill color */
}
.memory-popup .memory-graph-grid {
    color: rgba(255, 255, 255, 0.05);  /* set the grid line color */
}
.memory-popup .graph-title {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.5);
    font-family: 'Segoe UI';
    padding: 0px 0px 4px 14px;
}
/* Stats grid */
.memory-popup .stats {
    background: transparent;
    padding: 16px;
}
.memory-popup .stats .stat-item {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.04);
    border-radius: 8px;
    padding: 8px 12px;
    margin: 8px;
}
.memory-popup .stats .stat-label {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.65);
    font-family: 'Segoe UI';
    font-weight: 400;
    padding: 6px 4px 2px 4px;
}
.memory-popup .stats .stat-value {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    font-family: 'Segoe UI';
    padding: 0 4px 12px 4px;
}
```

## Full CSS Example
```css
.memory-widget {
    padding: 0 8px;
}

.memory-widget .widget-container .label {
    font-size: 13px;
    color: #cdd6f4;
}

.memory-widget .widget-container .icon {
    font-size: 14px;
    color: #89b4fa;
}

.memory-widget .widget-container .label.status-low {
    color: #a6e3a1; /* Green */
}

.memory-widget .widget-container .label.status-medium {
    color: #f9e2af; /* Yellow */
}

.memory-widget .widget-container .label.status-high {
    color: #fab387; /* Orange */
}

.memory-widget .widget-container .label.status-critical {
    color: #f38ba8; /* Red */
}

/* Progress bar customization */
.memory-widget .progress-circle {
    margin-right: 6px;
}
```