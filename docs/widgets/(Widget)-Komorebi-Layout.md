# Komorebi Layout
| Option          | Type    | Default                                                                 | Description                                                                 |
|-----------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `hide_if_offline` | boolean | `true`                                                                  | Whether to hide the widget if offline.                                      |
| `label`         | string  | `"{icon}"`                                                              | The label format string for the widget.                                     |
| `layouts`       | list    | `['bsp', 'columns', 'rows', 'grid', 'vertical_stack', 'horizontal_stack', 'ultrawide_vertical_stack', 'right_main_vertical_stack']` | The list of layouts available for the widget.                              |
| `layout_icons`  | dict    | `{ 'bsp': 'BSP', 'columns': 'COLS', 'rows': 'ROWS', 'grid': 'GRID', 'vertical_stack': 'V-STACK', 'horizontal_stack': 'H-STACK', 'ultrawide_vertical_stack': 'W-STACK', 'right_main_vertical_stack': 'RMV-STACK', 'monocle': 'MONOCLE', 'maximised': 'MAX', 'floating': 'FLOATING', 'paused': 'PAUSED' }` | The icons for each layout.                                                 |
| `callbacks`     | dict    | `{ 'on_left': 'next_layout', 'on_middle': 'toggle_monocle', 'on_right': 'prev_layout' }` | Callbacks for mouse events on the widget.                                   |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.                            |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |

## Example Configuration

```yaml
komorebi_active_layout:
  type: "komorebi.active_layout.ActiveLayoutWidget"
  options:
    hide_if_offline: true
    label: "{icon}"
    layouts: ['bsp', 'columns', 'rows', 'grid', 'vertical_stack', 'horizontal_stack', 'ultrawide_vertical_stack','right_main_vertical_stack']
    layout_icons:
      bsp: "BSP"
      columns: "COLS"
      rows: "ROWS"
      grid: "GRID"
      vertical_stack: "V-STACK"
      horizontal_stack: "H-STACK"
      ultrawide_vertical_stack: "W-STACK"
      right_main_vertical_stack: "RMV-STACK"
      monocle: "MONOCLE"
      maximised: "MAX"
      floating: "FLOATING"
      paused: "PAUSED"
    callbacks:
      on_left: 'next_layout'
      on_middle: 'toggle_monocle'
      on_right: 'prev_layout'
    container_padding: 
      top: 0
      left: 8
      bottom: 0
      right: 8
```

## Description of Options

- **hide_if_offline**: Whether to hide the widget if offline.
- **label**: The label format string for the widget.
- **layouts**: The list of layouts available for the widget.
- **layout_icons**: The icons for each layout.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.
- **callbacks**: A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.

### Allowed Callbacks:
```
"next_layout"
"prev_layout"
"flip_layout"
"flip_layout_horizontal"
"flip_layout_vertical"
"flip_layout_horizontal_and_vertical"
"first_layout"
"toggle_tiling"
"toggle_float"
"toggle_monocle"
"toggle_maximise"
"toggle_pause"
```
## Example Style
```css
.komorebi-active-layout {}
.komorebi-active-layout .widget-container {}
.komorebi-active-layout .label {}
```