# Disk Widget Configuration
| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`           | string  | `'{volume_label} {space[used][percent]}'`                        | The format string for the memory widget. Displays free and total virtual memory. |
| `label_alt`       | string  | `'{volume_label} {space[used][gb]} / {space[total][gb]}'`        | The alternative format string for the memory widget. Displays virtual and swap memory percentages. |
| `volume_label`       | string  | `'C'`        | Partition which you want to show in the bar |
| `update_interval` | integer | `60`                                                                  | The interval in seconds to update the disk widget. Must be between 0 and 3600. |
| `callbacks`       | dict    | `{'on_left': 'do_nothing', 'on_middle': 'do_nothing', 'on_right': "exec explorer C:\\"}` | Callbacks for mouse events. |


## Example Configuration

```yaml
disk:
  type: "yasb.disk.DiskWidget"
  options:
      label: "{volume_label} {space[used][percent]}"
      label_alt: "{volume_label} {space[used][gb]} / {space[total][gb]}"
      volume_label: "C"
      update_interval: 60
      callbacks:
        on_middle: "do_nothing"
        on_right: "exec explorer C:\\" # Open disk C in file explorer
```

## Description of Options

- **label:** The format string for the disk widget. Displays free space in percent.
- **label_alt:** The alternative format string for the disk widget.
- **volume_label:** Partition/volume which you want to show in the bar.
- **update_interval:** The interval in seconds to update the disk widget. Must be between 0 and 3600.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
 

The `label` and `label_alt` options use format strings that can include placeholders for disk widget. These placeholders will be replaced with actual values when the widget is rendered. You can use `{space[used][percent]}`, `{space[used][mb]}`, `{space[used][gb]}`, `{space[free][percent]}`, `{space[free][mb]}`, `{space[free][gb]}`, `{space[total][mb]}`, `{space[total][gb]}`