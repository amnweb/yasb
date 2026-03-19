# GPU Widget Configuration


| Option                | Type    | Default                                                                 | Description                                                                 |
|-----------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`               | string  | `"<span>\uf4bc</span> {info[utilization]}%"`                              | The primary label format.                                                   |
| `label_alt`           | string  | `"<span>\uf4bc</span> {info[temp]}°C | {info[mem_used]} / {info[mem_total]}"` | The alternative label format.                                               |
| `class_name`          | string  | `""`                                                                    | Additional CSS class name for the widget.                                   |
| `gpu_index`           | integer | `0`                                                                     | The index of the GPU to monitor (0 for the first GPU, 1 for the second, etc.). |
| `update_interval`     | integer | `1000`                                                                  | The interval in milliseconds to update the widget.                          |
| `histogram_icons`     | list    | `["\u2581", "\u2581", "\u2582", "\u2583", "\u2584", "\u2585", "\u2586", "\u2587", "\u2588"]` | Icons representing GPU utilization histograms.                              |
| `histogram_num_columns` | integer | `10`                                                                  | The number of columns in the histogram.                                     |
| `callbacks`           | dict    | `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}` | Callback functions for different mouse button actions.                      |
| `gpu_thresholds`      | dict    | `{'low': 25, 'medium': 50, 'high': 90}`                                 | Thresholds for GPU utilization levels.                                      |
| `animation`           | dict    | `{'enabled': true, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`    | dict    | `{"enabled": False, "color": "black", "offset": [1, 1], "radius": 3}`  | Container shadow options.                                                   |
| `label_shadow`        | dict    | `{"enabled": False, "color": "black", "offset": [1, 1], "radius": 3}`  | Label shadow options.                                                       |
| `progress_bar`        | dict    | `{'enabled': false, 'position': 'left', 'size': 14, 'thickness': 2, 'color': '#57948a', 'animation': false}` | Progress bar settings.                                                      |
| `hide_decimal`        | bool    | `false`                                                                 | Hide decimal places for utilization, temperature, and power draw values.    |
| `units`               | string  | `"metric"`                                                              | Temperature unit: `"metric"` for Celsius, `"imperial"` for Fahrenheit.     |
| `menu`                | dict    | See below                                                               | Configuration for the popup menu with graph and stats. |

> **About `gpu_index`:** If you have multiple GPUs, set `gpu_index` to select which one to monitor. Create multiple GPU widgets with different `gpu_index` values (e.g., 0, 1, 2, ...) to display stats for each card separately.

## Example Configuration

```yaml
gpu:
  type: "yasb.gpu.GpuWidget"
  options:
    label: "<span>\uf4bc</span> {info[utilization]}%"
    label_alt: "<span>\uf4bc</span> {info[temp]}°C | {info[mem_used]} / {info[mem_total]}"
    update_interval: 2000
    gpu_thresholds:
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
    menu:
      enabled: true
      show_graph: true
      show_graph_grid: true
      graph_history_size: 60
```

## Description of Options

- **label**: The format string for the GPU usage label. You can use placeholders like `{info[utilization]}` and `{info[temp]}` to dynamically insert GPU information.
- **label_alt**: The alternative format string for the GPU usage label. Useful for displaying additional GPU details, such as a histogram.
- **class_name:** Additional CSS class name for the widget. This allows for custom styling.
- **update_interval**: The interval in milliseconds at which the widget updates its information. Minimum is 1000 ms (1 second).
- **gpu_thresholds:** A dictionary specifying the thresholds for GPU utilization levels. The keys are `low`, `medium`, and `high`, and the values are the percentage thresholds.
- **hide_decimal**: Whether to hide decimal places in the GPU widget.
- **histogram_icons**: A list of icons representing different levels of GPU utilization in the histogram. 8 or 9 icons are typically used, representing usage from 0% to 80%+.
- **histogram_num_columns**: The number of columns to display in the GPU utilization histogram.
- **callbacks**: A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.
- **progress_bar**: A dictionary containing settings for the progress bar. It includes:
  - **enabled**: Whether the progress bar is enabled.
  - **position**: The position of the progress bar, either "left" or "right".
  - **size**: The size of the progress bar.
  - **thickness**: The thickness of the progress bar.
  - **color**: The color of the progress bar. Color can be single color or gradient.
  - **background_color**: The background color of the progress bar.
  - **animation**: Whether to enable smooth change of the progress bar value.
- **menu**: Configuration for the popup menu that displays a usage graph and detailed GPU statistics. It includes:
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

| Placeholder | Description |
|-------------|-------------|
| `{info[index]}` | GPU index (starting from 0) |
| `{info[name]}` | GPU name |
| `{info[utilization]}` | GPU utilization (%) |
| `{info[mem_total]}` | Total dedicated VRAM |
| `{info[mem_used]}` | Dedicated VRAM in use |
| `{info[mem_free]}` | Dedicated VRAM free |
| `{info[mem_shared_total]}` | Total shared system memory available to the GPU (useful for integrated GPUs) |
| `{info[mem_shared_used]}` | Shared system memory currently in use by the GPU |
| `{info[temp]}` | GPU temperature (°C or °F depending on `units`) |
| `{info[fan_speed]}` | Fan speed (%, 0 if unavailable) |
| `{info[power_draw]}` | Power draw (W, 0 if unavailable) |
| `{info[histograms][utilization]}` | Utilization history histogram |
| `{info[histograms][mem_used]}` | Memory usage history histogram |

> **Note on `mem_shared_*`:** Integrated GPUs (e.g., Intel HD Graphics, AMD Radeon integrated) have little or no dedicated VRAM and use system RAM instead. For these GPUs use `mem_shared_total` / `mem_shared_used` to see the actual memory usage.


## Example Style

```css
.gpu-widget {}
.gpu-widget.your_class {} /* If you are using class_name option */
.gpu-widget .widget-container {}
.gpu-widget .widget-container .label {}
.gpu-widget .widget-container .label.alt {}
.gpu-widget .widget-container .icon {}
.gpu-widget .label.status-low {}
.gpu-widget .label.status-medium {}
.gpu-widget .label.status-high {}
.gpu-widget .label.status-critical {}
/* GPU progress bar styles if enabled */
.gpu-widget .progress-circle {}
```

### Popup Menu Styles
```css
.gpu-popup {
    background-color: rgba(28, 28, 28, 0.7);
    min-width: 400px;
}

.gpu-popup .header {
    background: transparent;
    padding: 12px 16px;
}
.gpu-popup .header .text {
    font-size: 16px;
    font-family: "Segoe UI";
    color: rgb(255, 255, 255);
}
.gpu-popup .header .pin-btn {
    font-size: 14px;
    background: transparent;
    font-family: "Segoe Fluent Icons";
    border: none;
    padding: 6px;
    color: rgba(255, 255, 255, 0.6);
}
.gpu-popup .header .pin-btn:hover {
    color: rgba(255, 255, 255, 0.6);
}
.gpu-popup .header .pin-btn.pinned {
    color: #ffffff;
}
/* Graph area */
.gpu-popup .graph-container {
    background:  transparent;
    min-height: 64px;
}
.gpu-popup .gpu-graph {
    color: #0f6bff;   /* set the graph line/fill color */
}
.gpu-popup .gpu-graph-grid {
    color: rgba(255, 255, 255, 0.05);  /* set the grid line color */
}
.gpu-popup .gpu-temp-graph {
    color: #ff6b35;  /* orange for temperature */
}
.gpu-popup .gpu-temp-graph-grid {
    color: rgba(255, 255, 255, 0.05);  /* set the grid line color */
}
.gpu-popup .graph-title {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.5);
    font-family: 'Segoe UI';
    padding: 0px 0px 4px 14px;
    margin-top: 12px; /* Add top margin to separate from 2nd graph */
}
.gpu-popup .graph-title.first {
    margin-top: 0px; /* Remove top margin for the first graph title */
}
/* Stats grid */
.gpu-popup .stats {
    background: transparent;
    padding: 16px;
}
.gpu-popup .stats .stat-item {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.04);
    border-radius: 8px;
    padding: 8px 12px;
    margin: 8px;
}
.gpu-popup .stats .stat-label {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.65);
    font-family: 'Segoe UI';
    font-weight: 400;
    padding: 6px 4px 2px 4px;
}
.gpu-popup .stats .stat-value {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    font-family: 'Segoe UI';
    padding: 0 4px 12px 4px;
}
```
