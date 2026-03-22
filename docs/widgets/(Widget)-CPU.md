# CPU Widget Configuration

| Option                | Type    | Default                                                                 | Description                                                                 |
|-----------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`               | string  | `"\uf200 {info[histograms][cpu_percent]}"`                              | The primary label format.                                                   |
| `label_alt`           | string  | `"<span>\uf437</span> {info[histograms][cpu_percent]}"` | The alternative label format.                                               |
| `class_name`        | string  | `""`                                                                                  | Additional CSS class name for the widget.                                    |
| `update_interval`     | integer | `1000`                                                                  | The interval in milliseconds to update the widget.                          |
| `histogram_icons`     | list    | `["\u2581", "\u2581", "\u2582", "\u2583", "\u2584", "\u2585", "\u2586", "\u2587", "\u2588"]` | Icons representing CPU usage histograms.                                    |
| `histogram_num_columns` | integer | `10`                                                                    | The number of columns in the histogram.                                     |
| `callbacks`           | dict    | `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}` | Callback functions for different mouse button actions.                      |
| `cpu_thresholds` | dict  | `{'low': 25, 'medium': 50, 'high': 90}`                                 | Thresholds for CPU usage levels. |
| `animation`         | dict    | `{'enabled': true, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |
| `progress_bar`       | dict    | `{'enabled': false, 'position': 'left', 'size': 14, 'thickness': 2, 'color': '#57948a', 'animation': false}` | Progress bar settings.                                                      |
| `hide_decimal`       | bool    | `false`                                                                 | Whether to hide decimal places in the CPU widget.                          |
| `menu`               | dict    | See below                                                               | Configuration for the popup menu with graph and stats. |

## Example Configuration

```yaml
cpu:
  type: "yasb.cpu.CpuWidget"
  options:
    label: "<span>\uf4bc</span> {info[percent][total]}%"
    label_alt: "<span>\uf437</span> {info[freq][current]} MHz"
    update_interval: 2000
    cpu_thresholds:
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
    histogram_num_columns: 8
    callbacks:
      on_left: "toggle_label"
      on_right: "toggle_menu"
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
    menu:
      enabled: true
      show_graph: true
      show_graph_grid: true
      graph_history_size: 60
```

## Description of Options

- **label**: The format string for the CPU usage label. You can use placeholders like `{info[percent][total]}` to dynamically insert CPU information.
- **label_alt**: The alternative format string for the CPU usage label. Useful for displaying additional CPU details.
- **class_name:** Additional CSS class name for the widget. This allows for custom styling.
- **update_interval**: The interval in milliseconds at which the widget updates its information. Minimum is 1000 ms (1 second).
- **cpu_thresholds:** A dictionary specifying the thresholds for CPU usage levels. The keys are `low`, `medium`, and `high`, and the values are the percentage thresholds.
- **hide_decimal**: Whether to hide decimal places in the CPU widget.
- **histogram_icons**: A list of icons representing different levels of CPU usage in the histogram. 8 icons are typically used, representing usage from 0% to 80%+.
- **histogram_num_columns**: The number of columns to display in the CPU usage histogram.
- **callbacks**: A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.
- **progress_bar**: A dictionary containing settings for the progress bar. It includes:
  - **enabled**: Whether the progress bar is enabled.
  - **position**: The position of the progress bar, either "left" or "right".
  - **size**: The size of the progress bar.
  - **thickness**: The thickness of the progress bar.
  - **color**: The color of the progress bar. Color can be single color or gradient. For example, `color: "#57948a"` or `color: ["#57948a", "#ff0000"]"` for a gradient.
  - **background_color**: The background color of the progress bar.
  - **animation**: Whether to enable smooth change of the progress bar value.
- **menu**: Configuration for the popup menu that displays a usage graph and detailed CPU statistics. It includes:
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

## Available Placeholders

#### Core Information
- `{info[cores][physical]}` - Number of physical CPU cores
- `{info[cores][total]}` - Total number of CPU cores (including logical/hyperthreaded cores)

#### Frequency Information
- `{info[freq][current]}` - Current CPU frequency in MHz (includes turbo boost, matches Windows Task Manager)
- `{info[freq][max]}` - Base/nominal CPU frequency in MHz  

#### Usage Percentages
- `{info[percent][total]}` - Total CPU usage percentage (0-100)
- `{info[percent][core]}` - List of per-core CPU usage percentages

#### Histograms
- `{info[histograms][cpu_freq]}` - CPU frequency histogram using configured icons
- `{info[histograms][cpu_percent]}` - CPU percentage histogram using configured icons
- `{info[histograms][cores]}` - Per-core usage histogram using configured icons

> **Note**: The CPU widget uses Windows Performance Data Helper (PDH) API for accurate real-time metrics. If PDH counters are corrupted, the widget will display default values. To repair broken PDH counters, run `lodctr /r` as Administrator.

## Example Style
```css
.cpu-widget {}
.cpu-widget .widget-container {}
.cpu-widget .widget-container .label {}
.cpu-widget .widget-container .label.alt {}
.cpu-widget .widget-container .icon {}

/* Status classes based on cpu_thresholds */
.cpu-widget .widget-container .label.status-low {}
.cpu-widget .widget-container .label.status-medium {}
.cpu-widget .widget-container .label.status-high {}
.cpu-widget .widget-container .label.status-critical {}

/* Icon status classes */
.cpu-widget .widget-container .icon.status-low {}
.cpu-widget .widget-container .icon.status-medium {}
.cpu-widget .widget-container .icon.status-high {}
.cpu-widget .widget-container .icon.status-critical {}

/* Progress bar styles (if enabled) */
.cpu-widget .progress-circle {}

/* Custom class styling */
.cpu-widget.your-class-name {}
.cpu-widget.your-class-name .label {}
```

### Popup Menu Styles
```css
.cpu-popup {
    background-color: rgba(28, 28, 28, 0.7);
    min-width: 400px;
}

.cpu-popup .header {
    background: transparent;
    padding: 12px 16px;
}
.cpu-popup .header .text {
    font-size: 16px;
    font-family: "Segoe UI";
    color: rgb(255, 255, 255);
}
.cpu-popup .header .pin-btn {
    font-size: 14px;
    background: transparent;
    font-family: "Segoe Fluent Icons";
    border: none;
    padding: 6px;
    color: rgba(255, 255, 255, 0.6);
}
.cpu-popup .header .pin-btn:hover {
    color: rgba(255, 255, 255, 0.6);
}
.cpu-popup .header .pin-btn.pinned {
    color: #ffffff;
}
/* Graph area */
.cpu-popup .graph-container {
    background:  transparent;
    min-height: 64px;
}
.cpu-popup .cpu-graph {
    color: #0f6bff;   /* <-- set the graph line/fill color */
}
.cpu-popup .cpu-graph-grid {
    color: rgba(255, 255, 255, 0.05);  /* set the grid line color */
}
.cpu-popup .graph-title {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.5);
    font-family: 'Segoe UI';
    padding: 0px 0px 4px 14px;
}
/* Stats grid */
.cpu-popup .stats {
    background: transparent;
    padding: 16px;
}
.cpu-popup .stats .stat-item {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.04);
    border-radius: 8px;
    padding: 8px 12px;
    margin: 8px;
}
.cpu-popup .stats .stat-label {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.65);
    font-family: 'Segoe UI';
    font-weight: 400;
    padding: 6px 4px 2px 4px;
}
.cpu-popup .stats .stat-value {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    font-family: 'Segoe UI';
    padding: 0 4px 12px 4px;
}
```

## Full CSS Example
```css
.cpu-widget {
    padding: 0 8px;
}

.cpu-widget .widget-container .label {
    font-size: 13px;
    color: #cdd6f4;
}

.cpu-widget .widget-container .icon {
    font-size: 14px;
    color: #89b4fa;
}

.cpu-widget .widget-container .label.status-low {
    color: #a6e3a1; /* Green */
}

.cpu-widget .widget-container .label.status-medium {
    color: #f9e2af; /* Yellow */
}

.cpu-widget .widget-container .label.status-high {
    color: #fab387; /* Orange */
}

.cpu-widget .widget-container .label.status-critical {
    color: #f38ba8; /* Red */
}

/* Progress bar customization */
.cpu-widget .progress-circle {
    margin-right: 6px;
}
```