# Disk Widget Configuration
| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`           | string  | `'{volume_label} {space[used][percent]}'`                        | The format string for the memory widget. Displays free and total virtual memory. |
| `label_alt`       | string  | `'{volume_label} {space[used][gb]} / {space[total][gb]}'`        | The alternative format string for the memory widget. Displays virtual and swap memory percentages. |
| `volume_label`       | string  | `'C'`        | Partition which you want to show in the bar |
| `decimal_display` | integer | `1`                                                                  | The number of decimal to show, defaul 1 (min 0 max 3) |
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
- **decimal_display:** The number of decimal to show, defaul 1 (min 0 max 3).
- **update_interval:** The interval in seconds to update the disk widget. Must be between 0 and 3600.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
 

## Example Style
```css
.disk-widget {}
.disk-widget .widget-container {}
.disk-widget .widget-container .label {}
.disk-widget .widget-container .label.alt {}
.disk-widget .widget-container .icon {}
```