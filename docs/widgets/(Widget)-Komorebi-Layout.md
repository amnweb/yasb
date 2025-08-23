# Komorebi Layout
| Option          | Type    | Default                                                                 | Description                                                                 |
|-----------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `hide_if_offline` | boolean | `true`                                                                  | Whether to hide the widget if offline.                                      |
| `label`         | string  | `"{icon}"`                                                              | The label format string for the widget.                                     |
| `layouts`       | list    | `['bsp', 'columns', 'rows', 'grid', 'scrolling', 'vertical_stack', 'horizontal_stack', 'ultrawide_vertical_stack', 'right_main_vertical_stack']` | The list of layouts available for the widget.                              |
| `layout_icons`  | dict    | `{ 'bsp': 'BSP', 'columns': 'COLS', 'rows': 'ROWS', 'grid': 'GRID', 'scrolling': 'SC', 'vertical_stack': 'V-STACK', 'horizontal_stack': 'H-STACK', 'ultrawide_vertical_stack': 'W-STACK', 'right_main_vertical_stack': 'RMV-STACK', 'monocle': 'MONOCLE', 'maximized': 'MAX', 'floating': 'FLOATING', 'paused': 'PAUSED' }` | The icons for each layout.                                                 |
| `callbacks`     | dict    | `{ 'on_left': 'next_layout', 'on_middle': 'toggle_monocle', 'on_right': 'prev_layout' }` | Callbacks for mouse events on the widget.                                   |
| `animation`         | dict    | `{'enabled': true, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |

## Menu Configuration (`layout_menu`)

The `layout_menu` option allows you to configure the popup menu for layout selection. It accepts the following keys:

| Option              | Type     | Default      | Description                                                                 |
|---------------------|----------|--------------|-----------------------------------------------------------------------------|
| `blur`              | boolean  | `true`       | Enables a blur effect in the menu popup.                                    |
| `round_corners`     | boolean  | `true`       | If `true`, the menu has rounded corners.                                    |
| `round_corners_type`| string   | `"normal"`   | Determines the corner style; allowed values are `normal` and `small`.       |
| `border_color`      | string   | `"System"`   | Sets the border color for the menu. Can be `"System"`, `None` or HEX                                        |
| `alignment`         | string   | `"left"`     | Horizontal alignment of the menu relative to the widget (`left`, `right`, `center`). |
| `direction`         | string   | `"down"`     | Direction in which the menu opens (`down` or `up`).                         |
| `offset_top`        | integer  | `6`          | Vertical offset for fine positioning of the menu.                           |
| `offset_left`       | integer  | `0`          | Horizontal offset for fine positioning of the menu.                         |
| `show_layout_icons` | boolean  | `true`       | Whether to show icons for each layout in the menu.                          |

## Example Configuration

```yaml
komorebi_active_layout:
  type: "komorebi.active_layout.ActiveLayoutWidget"
  options:
    hide_if_offline: true
    label: "{icon} {layout_name}"
    layouts: ['bsp', 'columns', 'rows', 'grid', 'scrolling', 'vertical_stack', 'horizontal_stack', 'ultrawide_vertical_stack','right_main_vertical_stack']
    layout_icons:
      bsp: "\uebeb"
      columns: "\uebf7"
      rows: "\uec01"
      grid: "\udb81\udf58"
      scrolling: "\uebf7"
      vertical_stack: "\uebee"
      horizontal_stack: "\uebf0"
      ultrawide_vertical_stack: "\uebee"
      right_main_vertical_stack: "\uebf1"
      monocle: "\uf06f"
      maximized: "\uf06f"
      floating: "\uf2d2"
      paused: "\udb83\udf89"
      tiling: "\udb81\ude40"
    callbacks:
      on_left: 'toggle_layout_menu'
      on_middle: 'next_layout'
      on_right: 'prev_layout'
    layout_menu:
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "System"
      alignment: "left"
      direction: "down"
      offset_top: 6
      offset_left: 0
      show_layout_icons: true
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Description of Options

- **hide_if_offline**: Whether to hide the widget if offline.
- **label**: The label format string for the widget.
- **layouts**: The list of layouts available for the widget.
- **layout_icons**: The icons for each layout.
- **callbacks**: A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.
- **layout_menu**: A dictionary specifying the menu settings for the widget. It contains the following keys:
  - **blur**: Enable blur effect for the menu.
  - **round_corners**: Enable round corners for the menu (this option is not supported on Windows 10).
  - **round_corners_type**: Set the type of round corners for the menu (normal, small) (this option is not supported on Windows 10).
  - **border_color**: Set the border color for the menu (this option is not supported on Windows 10).
  - **alignment**: Set the alignment of the menu (left, right).
  - **direction**: Set the direction of the menu (up, down).
  - **offset_top**: Set the offset from the top of the screen.
  - **offset_left**: Set the offset from the left of the screen.
  - **show_layout_icons**: Whether to show icons for each layout in the menu.

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
"toggle_maximize"
"toggle_pause"
"toggle_layout_menu"
```
## Example Style
```css
.komorebi-active-layout {}
.komorebi-active-layout .widget-container {}
.komorebi-active-layout .label {}
```

## Example Style for Menu
```css
.komorebi-layout-menu {
    background-color:rgba(17, 17, 27, 0.4)
}
.komorebi-layout-menu .menu-item {
    padding: 8px 16px;
    font-size: 12px;
    color: #cdd6f4; 
    font-weight: 600;
}
.komorebi-layout-menu .menu-item-icon {
    color: #cdd6f4;
    font-size: 16px;
}
.komorebi-layout-menu .menu-item-text {
    font-family: 'Segoe UI';
    padding-left:4px;
    font-size: 12px;
} 
.komorebi-layout-menu .menu-item:hover {
    background-color:rgba(128, 130, 158, 0.15);
    color: #fff;
} 
.komorebi-layout-menu .separator {
    max-height: 1px;
    background-color: rgba(255, 255, 255, 0.15);
}
```
