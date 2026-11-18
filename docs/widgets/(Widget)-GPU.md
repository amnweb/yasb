# GPU Widget Configuration

## Optional Libre fan RPM

`menu.show_fan_rpm: true` adds native Cooling cards for the selected adapter's Libre
fan sensors. This is separate from the existing `menu.show_fan_speed` percentage card.
The local Libre endpoint is shared with the temperature widget and is read-only.
Fans are matched by exact normalized hardware name, or by the existing `libre_sensor_map`
hardware ID override for the adapter's Windows index. Ambiguous matches remain unavailable.
Multiple reported GPU fans each get a card; a valid stopped fan displays `0 RPM`.
An adapter without a reported fan (such as an integrated GPU) displays an em dash.
Switching adapters updates the cooling cards in place. No fan speed setting is changed.

This option defaults to disabled. Cooling inherits the native stat-card styles;
`.gpu-popup .cooling-title` styles its section title.

## Optional adapter selector, clocks and memory bars

The native popup can select adapters without opening another window, show Core/Memory clocks from Libre Hardware Monitor, and add memory bars to its existing statistics cards.

```yaml
gpu:
  type: yasb.gpu.GpuWidget
  options:
    gpu_index: 0
    libre_host: "127.0.0.1"
    libre_port: 8085
    callbacks:
      on_left: toggle_menu
    menu:
      enabled: true
      adapter_selector: true
      adapter_order: dedicated_first
      show_clocks: true
      show_combined_memory: true
      show_memory_bars: true
      show_graph_fill: false
      show_temperature: false
      show_power: false
      show_fan_speed: false
```

- All new features are opt-in. Existing GPU configurations keep their system index, native layout and native sensor fields.
- `adapter_selector` adds checkable GPU buttons inside the original popup header. They change its data in place, without a dropdown window or popup resize. The selector collects all DXGI adapters, including idle adapters.
- `adapter_order` defaults to `system`; `dedicated_first` orders by dedicated capacity, then name/identity. With the selector enabled, `gpu_index` chooses the default position in that display order on opening. Real Windows indices and adapter LUIDs are retained internally. Each adapter has its own rolling utilization and temperature history while YASB runs.
- `show_clocks` adds Core/Memory clock cards. Libre must have its web server running. Requests run on the native GPU worker with a bounded timeout. Matching uses an exact normalized adapter name, never the order of Libre sensors. Ambiguous/missing/offline readings show an em dash. For identical adapter names, set `libre_sensor_map: {0: "/gpu-amd/5"}` using the real Windows GPU index and Libre hardware identifier.
- `show_combined_memory` adds used/total dedicated-plus-shared amounts. Shared capacity is the system RAM sharing limit, not extra physical VRAM. `show_memory_bars` adds horizontal utilization bars to the dedicated ("In Use"), shared and combined native cards. Capacities of zero are handled without division errors.
- `show_temperature`, `show_power`, and `show_fan_speed` default to `true`; disable them to keep the GPU popup focused on utilization/clocks/memory while a separate temperature widget is used.
- `show_graph_fill` defaults to `true`; set it to `false` for a line-only chart with no shading or gradients.
- `highlight_usage` defaults to `false`. Enabling it adds the `primary` CSS class to the usage card and its label/value, matching the RAM highlight mechanism while preserving the native grid.

Keeps track of your graphics card's usage, memory, and temperature. You can display usage graphs, toggle between metric and imperial temperature units, set warning thresholds, and click it to open a detailed status popup.

| Option                | Type    | Default                                                                 | Description                                                                 |
|-----------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`               | string  | `"{info[utilization]}%"`                                                | The primary label format.                                                   |
| `label_alt`           | string  | `"{info[mem_used]}/{info[mem_total]}"`                                    | The alternative label format.                                               |
| `class_name`          | string  | `""`                                                                    | Additional CSS class name for the widget.                                   |
| `gpu_index`           | integer | `0`                                                                     | The index of the GPU to monitor (0 for the first GPU, 1 for the second, etc.). |
| `update_interval`     | integer | `2000`                                                                  | The interval in milliseconds to update the widget (2000–60000).             |
| `histogram_icons`     | list    | [See below](#histogram-icons) | Exactly 9 icons representing GPU utilization histograms.                    |
| `histogram_num_columns` | integer | `10`                                                                  | The number of columns in the histogram (1–128).                             |
| `callbacks`           | dict    | [See below](#callbacks) | Callback functions for different mouse button actions.                      |
| `gpu_thresholds`      | dict    | `{'low': 30, 'medium': 60, 'high': 90}`                                 | Thresholds for GPU utilization levels.                                      |
| `progress_bar`       | dict    | [See below](#progress-bar-options) | Progress bar settings.    |
| `hide_decimal`        | bool    | `false`                                                                 | Hide decimal places for utilization, temperature, and power draw values.    |
| `units`               | string  | `"metric"`                                                              | Temperature unit: `"metric"` for Celsius, `"imperial"` for Fahrenheit.     |
| `menu`                | dict    | [See below](#menu-options) | Configuration for the popup menu with graph and stats. |
| `keybindings`         | list    | `[]`                                                                    | Optional hotkeys. See [Keybindings](./Keybindings).                         |

> **About `gpu_index`:** If you have multiple GPUs, set `gpu_index` to select which one to monitor. Create multiple GPU widgets with different `gpu_index` values (e.g., 0, 1, 2, ...) to display stats for each card separately.

## Callbacks

The `callbacks` option maps mouse buttons (`on_left`, `on_middle`, `on_right`) to actions. All keys are optional, the values shown are the defaults.

```yaml
callbacks:
  on_left: "toggle_label"
  on_middle: "do_nothing"
  on_right: "do_nothing"
```

Available actions:

- `toggle_label` - Switch between `label` and `label_alt`.
- `toggle_menu` - Open or close the popup menu.
- `do_nothing` - Do nothing.
- `exec <command>` - Run a command, for example `exec cmd.exe /c start ms-settings:network`.

## Menu Options

The `menu` option accepts the following keys. All keys are optional, the values shown are the defaults.

```yaml
menu:
  enabled: false
  blur: true
  round_corners: true
  round_corners_type: "normal"
  border_color: "System"
  alignment: "right"
  direction: "down"
  offset_top: 6
  offset_left: 0
  graph_history_size: 60
  show_graph: true
  show_graph_grid: false
  pin_icon: "\ue718"
  unpin_icon: "\ue77a"
```

## Histogram Icons

The default value of `histogram_icons` is:

```yaml
histogram_icons:
  - "\u2581"
  - "\u2581"
  - "\u2582"
  - "\u2583"
  - "\u2584"
  - "\u2585"
  - "\u2586"
  - "\u2587"
  - "\u2588"
```

## Progress Bar Options

The `progress_bar` option accepts the following keys. All keys are optional, the values shown are the defaults.

```yaml
progress_bar:
  enabled: false
  progress_type: "circular"
  size: 18
  thickness: 3
  radius: 0
  color: "#00C800"
  background_color: "#3C3C3C"
  position: "left"
  animation: true
```

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
- **gpu_index**: The index of the GPU to monitor (`0` for the first GPU). Default `0`.
- **units**: Temperature unit, `metric` for Celsius or `imperial` for Fahrenheit. Default `metric`.
- **update_interval**: The interval in milliseconds at which the widget updates its information. Must be between 2000 and 60000 ms.
- **gpu_thresholds:** A dictionary specifying the thresholds for GPU utilization levels. The keys are `low`, `medium`, and `high`, and the values are the percentage thresholds.
- **hide_decimal**: Whether to hide decimal places in the GPU widget.
- **histogram_icons**: A list of icons representing different levels of GPU utilization in the histogram. Exactly 9 icons are required, representing usage from 0% to 80%+.
- **histogram_num_columns**: The number of columns to display in the GPU utilization histogram (1–128).
- **keybindings**: A list of global hotkeys for this widget. See [Keybindings](./Keybindings).
- **callbacks:** Mouse event callbacks. See [Callbacks](#callbacks).
- **progress_bar**: A dictionary containing settings for the progress bar. It includes:
  - **enabled**: Whether the progress bar is enabled.
  - **progress_type**: The type of progress bar. Options are `"circular"`, `"linear_horizontal"`, or `"linear_vertical"`.
  - **position**: The position of the progress bar, either "left" or "right".
  - **size**: The length of the progress bar (or diameter if circular). Minimum is 1, maximum is 200.
  - **thickness**: The thickness of the progress bar. Minimum is 1, maximum is 100.
  - **radius**: The border radius for the linear progress bar corners. Minimum is 0, maximum is 100.
  - **color**: The color of the progress bar. Color can be a single color or a gradient. For example, `color: "#57948a"` or `color: ["#57948a", "#ff0000"]` for a gradient.
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
.gpu-widget .progress-container {}
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
