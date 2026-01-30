# GPU Widget Configuration

> [!NOTE]
> This widget currently works only with NVIDIA GPUs and requires the `nvidia-smi` tool to be available (either in your system PATH or accessible by full path). In most cases, `nvidia-smi` is installed automatically with the NVIDIA driver and added to your PATH, but on some systems you may need to add it manually or use the full path to the executable. It will not function with AMD or Intel GPUs.

**How to verify `nvidia-smi` is available:**

Open a terminal or command prompt and run:

```sh
nvidia-smi
```

If you see a table with your GPU information, `nvidia-smi` is available. If you get an error like "command not found" or "not recognized as an internal or external command," you may need to add it to your PATH or use the full path to the executable (e.g., `C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe`).

| Option                | Type    | Default                                                                 | Description                                                                 |
|-----------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`               | string  | `"<span>\uf4bc</span> {info[utilization]}%"`                              | The primary label format.                                                   |
| `label_alt`           | string  | `"<span>\uf4bc</span> {info[temp]}°C | {info[mem_used]} / {info[mem_total]}"`                 | The alternative label format.                                               |
| `class_name`        | string  | `""`                                                                                  | Additional CSS class name for the widget.                                    |
| `gpu_index`          | integer | `0`                                                                     | The index of the GPU to monitor (0 for the first GPU, 1 for the second, etc.). |
| `update_interval`     | integer | `1000`                                                                  | The interval in milliseconds to update the widget.                          |
| `histogram_icons`     | list    | `["\u2581", "\u2581", "\u2582", "\u2583", "\u2584", "\u2585", "\u2586", "\u2587", "\u2588"]` | Icons representing GPU utilization histograms.                              |
| `histogram_num_columns` | integer | `10`                                                                    | The number of columns in the histogram.                                     |
| `callbacks`           | dict    | `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}` | Callback functions for different mouse button actions.                      |
| `gpu_thresholds`      | dict    | `{'low': 25, 'medium': 50, 'high': 90}`                                 | Thresholds for GPU utilization levels.                                      |
| `animation`           | dict    | `{'enabled': true, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`    | dict    | `{"enabled": False, "color": "black", "offset": [1, 1], "radius": 3}`                                                                  | Container shadow options.                                                   |
| `label_shadow`        | dict    | `{"enabled": False, "color": "black", "offset": [1, 1], "radius": 3}`                                                                  | Label shadow options.                                                       |
| `progress_bar`        | dict    | `{'enabled': false, 'position': 'left', 'size': 14, 'thickness': 2, 'color': '#57948a', 'animation': false}` | Progress bar settings.                                                      |
| `hide_decimal`        | bool    | `false`                                                                 | Whether to hide decimal places in the GPU widget.                          |
| `units`               | string  | `"metric"`                                                              | Whether the temperature is converted to Fahrenheit (if set to `"imperial"`) or Celsius (if not set or explicitly set to `"metric"`) |

> **About `index`:** If you have multiple NVIDIA GPUs, you can set the `gpu_index` option to select which GPU to monitor. Create multiple GPU widgets with different `gpu_index` values (e.g., 0, 1, 2, ...) to display stats for each card separately.

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

## Available Placeholders

- `{info[index]}` - GPU index (index of the GPU in the system, starting from 0)
- `{info[utilization]}` - GPU utilization percentage
- `{info[mem_total]}` - Total GPU memory
- `{info[mem_used]}` - Used GPU memory
- `{info[mem_free]}` - Free GPU memory
- `{info[temp]}` - GPU temperature (°C)
- `{info[fan_speed]}` - GPU fan speed (if available, in percentage)
- `{info[power_draw]}` - GPU power draw exactly in watts if available.
- `{info[histograms][utilization]}` - GPU utilization histogram using configured icons
- `{info[histograms][mem_used]}` - GPU memory usage histogram using configured icons


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
