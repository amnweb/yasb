# Komorebi Layout

Shows the active window arrangement layout in Komorebi (like BSP, columns, rows, or floating). You can click to cycle layouts, toggle monocle or floating states, or open a menu to select a layout with descriptive icons.

| Option          | Type    | Default                                                                 | Description                                                                 |
|-----------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `hide_if_offline` | boolean | `false`                                                                 | Whether to hide the widget if offline.                                      |
| `label`         | string  | `"{icon}"`                                                              | The label format string for the widget.                                     |
| `layouts`       | list    | [See below](#layouts) | The list of layouts available for the widget.                              |
| `layout_icons`  | dict    | [See below](#layout-icons-options) | The icons for each layout.                                                 |
| `layout_menu`   | dict    | [See below](#menu-configuration-layout_menu) | Popup menu for layout selection.                                            |
| `keybindings`   | list    | `[]`                                                                    | Optional hotkeys. See [Keybindings](./Keybindings).                         |
| `callbacks`     | dict    | [See below](#callbacks) | Callbacks for mouse events on the widget.                                   |

## Callbacks

The `callbacks` option maps mouse buttons (`on_left`, `on_middle`, `on_right`) to actions. All keys are optional, the values shown are the defaults.

```yaml
callbacks:
  on_left: "next_layout"
  on_middle: "toggle_monocle"
  on_right: "prev_layout"
```

Available actions:

- `next_layout` - Switch to the next layout.
- `prev_layout` - Switch to the previous layout.
- `flip_layout` - Flip the layout horizontally.
- `flip_layout_horizontal` - Flip the layout horizontally.
- `flip_layout_vertical` - Flip the layout vertically.
- `flip_layout_horizontal_and_vertical` - Flip the layout both horizontally and vertically.
- `first_layout` - Switch to the first layout in `layouts`.
- `toggle_tiling` - Toggle tiling.
- `toggle_float` - Toggle floating for the focused window.
- `toggle_monocle` - Toggle monocle mode.
- `toggle_maximize` - Toggle maximize for the focused window.
- `toggle_pause` - Pause or resume tiling.
- `toggle_layout_menu` - Open or close the layout menu.
- `do_nothing` - Do nothing.
- `exec <command>` - Run a command, for example `exec cmd.exe /c start ms-settings:network`.

## Layouts

The default value of `layouts` is:

```yaml
layouts:
  - "bsp"
  - "columns"
  - "rows"
  - "grid"
  - "scrolling"
  - "vertical_stack"
  - "horizontal_stack"
  - "ultrawide_vertical_stack"
  - "right_main_vertical_stack"
  - "monocle"
  - "maximized"
  - "floating"
  - "paused"
  - "tiling"
```

## Layout Icons Options

The `layout_icons` option accepts the following keys. All keys are optional, the values shown are the defaults.

```yaml
layout_icons:
  bsp: "[\\]"
  columns: "[||]"
  rows: "[==]"
  grid: "[G]"
  scrolling: "[SC]"
  vertical_stack: "[V]="
  horizontal_stack: "[H]="
  ultrawide_vertical_stack: "||="
  right_main_vertical_stack: "=||"
  monocle: "[M]"
  maximized: "[X]"
  floating: "><>"
  paused: "[P]"
  tiling: "[T]"
```

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
```

## Description of Options

- **hide_if_offline**: Whether to hide the widget if offline.
- **label**: The label format string for the widget.
- **layouts**: The list of layouts available for the widget.
- **layout_icons**: The icons for each layout.
- **keybindings**: A list of global hotkeys for this widget. See [Keybindings](./Keybindings).
- **callbacks:** Mouse event callbacks. See [Callbacks](#callbacks).
- **layout_menu**: A dictionary specifying the menu settings for the widget. It contains the following keys:
  - **blur**: Enable blur effect for the menu.
  - **round_corners**: Enable round corners for the menu (this option is not supported on Windows 10).
  - **round_corners_type**: Set the type of round corners for the menu (normal, small) (this option is not supported on Windows 10).
  - **border_color**: Set the border color for the menu (this option is not supported on Windows 10).
  - **alignment**: Set the alignment of the menu (left, right, center).
  - **direction**: Set the direction of the menu (up, down).
  - **offset_top**: Set the offset from the top of the screen.
  - **offset_left**: Set the offset from the left of the screen.
  - **show_layout_icons**: Whether to show icons for each layout in the menu.

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
