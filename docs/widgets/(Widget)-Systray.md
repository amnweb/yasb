# Systray Widget
| Option                 | Type    | Default     | Description                                                                             |
|------------------------|---------|-------------|-----------------------------------------------------------------------------------------|
| `class_name`           | string  | `'systray'` | The class name for the base widget.                                                     |
| `label_collapsed`      | string  | `'▼'`       | Label used for the collapse button when unpinned container is hidden.                   |
| `label_expanded`       | string  | `'▶'`       | Label used for the collapse button when unpinned container is shown.                    |
| `label_position`       | string  | `'left'`    | The position of the button that collapses unpinned container. Can be "left" or "right". |
| `icon_size`            | integer | `16`        | The size of the icons in the systray. Can be any integer between 8 and 64.              |
| `pin_click_modifier`   | string  | `'alt'`     | The modifier key used to pin/unpin icons. Can be "ctrl", "alt" or "shift".              |
| `show_unpinned`        | boolean | `true`      | Whether to show unpinned container on startup.                                          |
| `show_unpinned_button` | boolean | `true`      | Whether to show the collapse unpinned icons button.                                     |
| `show_battery`         | boolean | `false`     | Whether to show battery icon (from the original systray).                               |
| `show_volume`          | boolean | `false`     | Whether to show volume icon (from the original systray).                                |
| `show_network`         | boolean | `false`     | Whether to show network icon (from the original systray).


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
```

## Important Notes:
This widget is NOT compatible with "Buttery Taskbar" application. There is no fix.

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
- **show_battery:** Whether to show battery icon (from the original systray).
- **show_volume:** Whether to show volume icon (from the original systray).
- **show_network:** Whether to show network icon (from the original systray).

## Style
```css
.systray {} /* The base widget style */
.systray .unpinned-container {} /* Style for unpinned container */
.systray .pinned-container {} /* Style for pinned container */
.systray .pinned-container[forceshow=true] {} /* Style for pinned container when it is forced to show during dragging operation */
.systray .button {} /* Style for the individual systray buttons/icons */
.systray .button[dragging=true] {} /* Style for systray buttons/icons when dragging operation is in progress */
.systray .unpinned-visibility-btn {} /* Style for the 'collapse unpinned icons' button */
```

## Example CSS
```css
.systray {
    background: transparent;
    border: None;
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

.systray .button[dragging=true] {
    background: orange;
    border-color: #FF8800;
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
```
