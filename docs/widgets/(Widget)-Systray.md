# Systray Widget
| Option                    | Type    | Default     | Description                                                                             |
|---------------------------|---------|-------------|-----------------------------------------------------------------------------------------|
| `class_name`              | string  | `'systray'` | The class name for the base widget.                                                     |
| `label_collapsed`         | string  | `'▼'`       | Label used for the collapse button when unpinned container is hidden.                   |
| `label_expanded`          | string  | `'▶'`       | Label used for the collapse button when unpinned container is shown.                    |
| `label_position`          | string  | `'left'`    | The position of the button that collapses unpinned container. Can be "left" or "right". |
| `icon_size`               | integer | `16`        | The size of the icons in the systray. Can be any integer between 8 and 64.              |
| `pin_click_modifier`      | string  | `'alt'`     | The modifier key used to pin/unpin icons. Can be "ctrl", "alt" or "shift".              |
| `show_unpinned`           | boolean | `true`      | Whether to show unpinned container on startup.                                          |
| `show_unpinned_button`    | boolean | `true`      | Whether to show the collapse unpinned icons button.                                     |
| `show_in_popup`           | boolean | `false`     | Show unpinned icons in a popup grid instead of inline in the bar.                       |
| `icons_per_row`           | integer | `4`         | Number of icon columns in the popup grid (only used when `show_in_popup` is true).      |
| `popup`                   | dict    | see below   | Popup appearance settings (only used when `show_in_popup` is true).                     |
| `show_battery`            | boolean | `false`     | Whether to show battery icon (from the original systray).                               |
| `show_volume`             | boolean | `false`     | Whether to show volume icon (from the original systray).                                |
| `show_network`            | boolean | `false`     | Whether to show network icon (from the original systray).                               |
| `tooltip`                 | boolean | `true`      | Whether to show tooltips when hovering over systray icons.                              |
| `container_shadow`        | dict    | `None`      | Container shadow options.                                                               |
| `unpinned_shadow`         | dict    | `None`      | Unpinned container shadow options.                                                      |
| `pinned_shadow`           | dict    | `None`      | Pinned container shadow options.                                                        |
| `unpinned_vis_btn_shadow` | dict    | `None`      | Unpinned visibility button shadow options.                                              |
| `btn_shadow`              | dict    | `None`      | Systray button (icons) shadow options.                                                  |

### Popup Options
| Option               | Type    | Default    | Description                                                          |
|----------------------|---------|------------|----------------------------------------------------------------------|
| `blur`               | boolean | `true`     | Apply blur/acrylic effect to the popup background.                   |
| `round_corners`      | boolean | `true`     | Round the corners of the popup window.                               |
| `round_corners_type` | string  | `'normal'` | Round corner type. Can be "normal" or "small".                       |
| `border_color`       | string  | `'System'` | Border color for the popup window. Use "System" for the system color.|
| `alignment`          | string  | `'right'`  | Popup alignment relative to the button. Can be "left", "right", or "center". |
| `direction`          | string  | `'down'`   | Popup direction. Can be "up" or "down".                              |
| `offset_top`         | integer | `6`        | Vertical offset in pixels.                                           |
| `offset_left`        | integer | `0`        | Horizontal offset in pixels.                                         |


## Example Configuration
```yaml
systray:
  type: "yasb.systray.SystrayWidget"
  options:
    class_name: "systray"
    label_collapsed: "▼"
    label_expanded: "▶"
    label_position: "left" # Can be "left" or "right"
    icon_size: 16 # Can be any integer between 8 and 64
    pin_click_modifier: "alt" # Can be "ctrl", "alt" or "shift"
    show_unpinned: true
    show_unpinned_button: true
    show_battery: false
    show_volume: false
    show_network: false
    btn_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Example Popup Mode Configuration
When `show_in_popup` is enabled, unpinned icons are shown in a popup grid (similar to Windows) instead of inline in the bar. Pinned icons remain in the bar.
```yaml
systray:
  type: "yasb.systray.SystrayWidget"
  options:
    class_name: "systray"
    label_collapsed: "▼"
    label_expanded: "▶"
    label_position: "right"
    icon_size: 16
    pin_click_modifier: "alt"
    show_in_popup: true
    icons_per_row: 4
    popup:
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: None
      alignment: "center"
      direction: "down"
      offset_top: 6
      offset_left: 0
```

## Note on Shadows
`container_shadow` is applied to the container if it's not transparent.
If it is transparent, container shadows will be applied to the child container and buttons instead.
This can cause double shadows if you already have shadows applied to the child container and buttons.
Apply the shadows only to the container that is actually visible.

## Systray Widget Limitations:
There are some limitations with the systray widget:
- Systray widget will not show icons for apps if they ignore "TaskbarCreated" message. Meaning that if the original developers decided to ignore this message - their systray icons will not be shown. It's rare, but there are such cases (NVIDIA App for example). This is NOT a YASB bug.
- In rare cases systray icon might ignore click events if the original application was already running before YASB was started. Example: Epic Games Launcher. No solution for this so far.

## Description of Options
- **class_name:** The class name for the base widget. Can be changed if multiple systray widgets need to have different styling.
- **label_collapsed:** Label used for the collapse button when unpinned container is hidden.
- **label_expanded:** Label used for the collapse button when unpinned container is shown.
- **label_position:** The position of the button that collapses unpinned container.
- **icon_size:** The size of the icons in the systray. Can be any integer between 8 and 64.
- **pin_click_modifier:** The modifier key used to pin/unpin icons. Can be "ctrl", "alt" or "shift".
- **show_unpinned:** Whether to show unpinned container on startup.
- **show_unpinned_button:** Whether to show the 'collapse unpinned icons' button.
- **show_in_popup:** When enabled, unpinned icons are shown in a popup grid (like Windows system tray overflow) instead of inline. Clicking the expand/collapse button opens the popup. Pinned icons remain in the bar.
- **icons_per_row:** Number of columns in the popup icon grid. Only used when `show_in_popup` is true. Can be 1–12.
- **popup:** Popup window appearance settings. Only used when `show_in_popup` is true. See Popup Options table above.
- **show_battery:** Whether to show battery icon (from the original systray).
- **show_volume:** Whether to show volume icon (from the original systray).
- **show_network:** Whether to show network icon (from the original systray).
- **tooltip:** Whether to show tooltips when hovering over systray icons.
- **container_shadow:** Container shadow options.
- **unpinned_shadow:** Unpinned container shadow options.
- **pinned_shadow:** Pinned container shadow options.
- **unpinned_vis_btn_shadow:** Unpinned visibility button shadow options.
- **btn_shadow:** Systray button (icons) shadow options.

## Debug Options
Show unpinned button has a right click menu that allows you to refresh the systray icons.

## Style
```css
.systray {} /* The base widget style */
.systray .widget-container {} /* Style for the widget container */
.systray .unpinned-container {} /* Style for container with unpinned systray icons */
.systray .pinned-container {} /* Style for container with pinned systray icons */
.systray .pinned-container[forceshow=true] {} /* Style for pinned container when it is forced to show during dragging operation */
.systray .button {} /* Style for the individual systray buttons/icons */
.systray .button.dragging {} /* Style for the icon currently being dragged */
.systray .button.drag-over {} /* Style for the icon being hovered over during a drag */
.systray .pinned-container.drop-target {} /* Style for the pinned container when it is an empty drop target */
.systray .unpinned-visibility-btn {} /* Style for the 'collapse unpinned icons' button */
.systray-popup {} /* Style for the popup window (when show_in_popup is true) */
.systray-popup-container {} /* Style for the popup grid container (when show_in_popup is true) */
```

## Example CSS
```css
.systray {
    background: transparent;
    border: none;
    margin: 0;
}

.systray .unpinned-container {
    background: darkblue;
    border-radius: 8px;
}

.systray .pinned-container {
    background: transparent;
}

.systray .pinned-container[forceshow=true] {
    background: red;
}

.systray .button {
    border-radius: 4px;
    padding: 2px 2px;
}

.systray .button:hover {
    background: #727272;
}
/* Icon being dragged, we already apply some transparency to it so you don't need to use it */
.systray .button.dragging {}

.systray .button.drag-over {
    background: #505050;
}

.systray .pinned-container.drop-target {
    background: rgba(255, 255, 255, 0.1);
    border: 1px dashed #888;
}

.systray .unpinned-visibility-btn {
    border-radius: 4px;
    height: 20px;
    width: 16px;
}

.systray .unpinned-visibility-btn:checked {
    background: darkblue;
}

.systray .unpinned-visibility-btn:hover {
    border: 1px solid #AAAAAA;
    border-radius: 4px;
    border-color: #AAAAAA;
}

/* Popup styles (when show_in_popup is true) */
 
/* The icon the drag is hovering over (drop target icon) */
.systray-popup .button.drag-over {
    background-color: rgba(255, 255, 255, 0.2);
}
/* Icon being dragged, we already apply some transparency to it so you don't need to use it */
.systray-popup .button.dragging {}

.systray .pinned-container.pinned-container.drop-target {
    background-color: rgba(255, 255, 255, 0.1);
}

.systray-popup {
    background-color: rgba(48, 48, 48, 0.6);
    padding: 4px;
}

.systray-popup .button {
    padding: 10px;
    margin: 0;
    border: 0;
    border-radius: 6px;
}
.systray-popup .button:hover {
    background-color: rgba(255, 255, 255, 0.05);
}
```
