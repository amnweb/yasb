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
| `cpu_thresholds` | dict  | `{'low': 25, 'medium': 50, 'high': 90}`                                 | Thresholds for Cpu usage levels. |
| `animation`         | dict    | `{'enabled': true, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |
| `progress_bar`       | dict    | `{'enabled': false, 'position': 'left', 'size': 14, 'thickness': 2, 'color': '#57948a', 'animation': false}` | Progress bar settings.                                                      |
| `hide_decimal`       | bool    | `false`                                                                 | Whether to hide decimal places in the CPU widget.                          |

## Example Configuration

```yaml
cpu:
  type: "yasb.cpu.CpuWidget"
  options:
    label: "<span>\uf4bc</span> {info[percent][total]}%"
    label_alt: "<span>\uf437</span> {info[histograms][cpu_percent]}"
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
      on_right: "exec cmd /c Taskmgr"
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Description of Options

- **label**: The format string for the CPU usage label. You can use placeholders like `{info[percent][total]}` to dynamically insert CPU information.
- **label_alt**: The alternative format string for the CPU usage label. Useful for displaying additional CPU details.
- **class_name:** Additional CSS class name for the widget. This allows for custom styling.
- **update_interval**: The interval in milliseconds at which the widget updates its information. Minimum is 1000 ms (1 second).
- **cpu_thresholds:** A dictionary specifying the thresholds for cpu usage levels. The keys are `low`, `medium`, and `high`, and the values are the percentage thresholds.
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

## Available Placeholders

#### Core Information
- `{info[cores][physical]}` - Number of physical CPU cores
- `{info[cores][total]}` - Total number of CPU cores (including logical/hyperthreaded cores)

#### Frequency Information
- `{info[freq][min]}` - Minimum CPU frequency in MHz
- `{info[freq][max]}` - Maximum CPU frequency in MHz  
- `{info[freq][current]}` - Current CPU frequency in MHz

#### Usage Percentages
- `{info[percent][total]}` - Total CPU usage percentage
- `{info[percent][core]}` - List of per-core CPU usage percentages

#### CPU Statistics
- `{info[stats][context_switches]}` - Number of context switches
- `{info[stats][interrupts]}` - Number of interrupts
- `{info[stats][soft_interrupts]}` - Number of soft interrupts
- `{info[stats][sys_calls]}` - Number of system calls

#### Histograms
- `{info[histograms][cpu_freq]}` - CPU frequency histogram using configured icons
- `{info[histograms][cpu_percent]}` - CPU percentage histogram using configured icons
- `{info[histograms][cores]}` - Per-core usage histogram using configured icons

## Example Style
```css
.cpu-widget {}
.cpu-widget.your_class {} /* If you are using class_name option */
.cpu-widget .widget-container {}
.cpu-widget .widget-container .label {}
.cpu-widget .widget-container .label.alt {}
.cpu-widget .widget-container .icon {}
.cpu-widget .label.status-low {}
.cpu-widget .label.status-medium {}
.cpu-widget .label.status-high {}
.cpu-widget .label.status-critical {}
/* CPU progress bar styles if enabled */
.cpu-widget .progress-circle {} 
```