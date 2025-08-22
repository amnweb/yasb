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
| `animation`         | dict    | `{'enabled': true, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |
| `progress_bar`       | dict    | `{'enabled': False, 'position': 'left', 'size': 14, 'thickness': 2, 'color': '#57948a', 'animation': True}` | Progress bar settings.    |
| `hide_decimal`       | boolean    | `false`                                                                 | Whether to hide decimal places in the memory widget. |

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
      on_middle: "do_nothing"
      on_right: "do_nothing"
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
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
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

The `label` and `label_alt` options use format strings that can include placeholders for memory metrics. These placeholders will be replaced with actual values when the widget is rendered. You can use `{virtual_mem_free}`, `{virtual_mem_percent}`, `{virtual_mem_total}`, `{virtual_mem_avail}`, `{virtual_mem_used}`, `{virtual_mem_outof}`, `{swap_mem_free}`, `{swap_mem_percent}`, `{swap_mem_total}`


## Example Style
```css
.memory-widget {}
.memory-widget.your_class {} /* If you are using class_name option */
.memory-widget .widget-container {}
.memory-widget .label {}
.memory-widget .label.alt {}
.memory-widget .icon {}
.memory-widget .label.status-low {}
.memory-widget .label.status-medium {}
.memory-widget .label.status-high {}
.memory-widget .label.status-critical {}
/* Memory progress bar styles if enabled */
.memory-widget .progress-circle {} 
```