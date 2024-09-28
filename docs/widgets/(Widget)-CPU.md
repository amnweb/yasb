# CPU Widget Configuration

| Option                | Type    | Default                                                                 | Description                                                                 |
|-----------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`               | string  | `"\uf200 {info[histograms][cpu_percent]}"`                              | The primary label format.                                                   |
| `label_alt`           | string  | `"<span>\uf437</span> {info[histograms][cpu_percent]}"` | Histograms | The alternative label format.                                               |
| `update_interval`     | integer | `1000`                                                                  | The interval in milliseconds to update the widget.                          |
| `histogram_icons`     | list    | `['\u2581', '\u2581', '\u2582', '\u2583', '\u2584', '\u2585', '\u2586', '\u2587', '\u2588']` | Icons representing CPU usage histograms.                                    |
| `histogram_num_columns` | integer | `10`                                                                    | The number of columns in the histogram.                                     |
| `callbacks`           | dict    | `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}` | Callback functions for different mouse button actions.                      |

## Example Configuration

```yaml
cpu:
  type: "yasb.cpu.CpuWidget"
  options:
    label: "<span>\uf4bc</span> {info[percent][total]}%"
    label_alt: "<span>\uf437</span> {info[histograms][cpu_percent]}"
    update_interval: 2000
    histogram_icons:
      - '\u2581' # 0%
      - '\u2581' # 10%
      - '\u2582' # 20%
      - '\u2583' # 30%
      - '\u2584' # 40%
      - '\u2585' # 50%
      - '\u2586' # 60%
      - '\u2587' # 70%
      - '\u2588' # 80%+
    histogram_num_columns: 8
    callbacks:
      on_right: "exec cmd /c Taskmgr"
```

# Description of Options

- **label**: The format string for the CPU usage label. You can use placeholders like `{info[percent][total]}` to dynamically insert CPU information.
- **label_alt**: The alternative format string for the CPU usage label. Useful for displaying additional CPU details.
- **update_interval**: The interval in milliseconds at which the widget updates its information.
- **histogram_icons**: A list of icons representing different levels of CPU usage in the histogram.
- **histogram_num_columns**: The number of columns to display in the CPU usage histogram.
- **callbacks**: A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.