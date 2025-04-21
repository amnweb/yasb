# Memory Widget Configuration
| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`           | string  | `'\uf4bc {virtual_mem_free}/{virtual_mem_total}'`                        | The format string for the memory widget. Displays free and total virtual memory. |
| `label_alt`       | string  | `'\uf4bc VIRT: {virtual_mem_percent}% SWAP: {swap_mem_percent}%'`        | The alternative format string for the memory widget. Displays virtual and swap memory percentages. |
| `update_interval` | integer | `5000`                                                                  | The interval in milliseconds to update the memory widget. Must be between 0 and 60000. |
| `callbacks`       | dict    | `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}` | Callbacks for mouse events on the memory widget. |
| `memory_thresholds` | dict  | `{'low': 25, 'medium': 50, 'high': 90}`                                 | Thresholds for memory usage levels. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.                            |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |

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
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Description of Options

- **label:** The format string for the memory widget. Displays free and total virtual memory.
- **label_alt:** The alternative format string for the memory widget. Displays virtual and swap memory percentages.
- **update_interval:** The interval in milliseconds to update the memory widget. Must be between 0 and 60000.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **memory_thresholds:** A dictionary specifying the thresholds for memory usage levels. The keys are `low`, `medium`, and `high`, and the values are the percentage thresholds.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.

The `label` and `label_alt` options use format strings that can include placeholders for memory metrics. These placeholders will be replaced with actual values when the widget is rendered. You can use `{virtual_mem_free}`, `{virtual_mem_percent}`, `{virtual_mem_total}`, `{virtual_mem_avail}`, `{virtual_mem_used}`, `{virtual_mem_outof}`, `{swap_mem_free}`, `{swap_mem_percent}`, `{swap_mem_total}`


## Example Style
```css
.memory-widget {}
.memory-widget .widget-container {}
.memory-widget .label {}
.memory-widget .label.alt {}
.memory-widget .icon {}
.memory-widget .label.status-low {}
.memory-widget .label.status-medium {}
.memory-widget .label.status-high {}
.memory-widget .label.status-critical {}
```