# Komorebi Stack Widget
This widget displays information about each window in the currently active Komorebi stack.
| Option                     | Type    | Default                  | Description                                                                 |
|----------------------------|---------|--------------------------|-----------------------------------------------------------------------------|
| `label_offline`          | string  | `'Komorebi Offline'`     | The label to display when Komorebi is offline.                              |
| `label_window`    | string  | `'{title}'`              | The format string for window buttons.                                    |
| `label_window_active` | string | `'{title}'`              | The format string for the active window button.                          |
| `label_no_window`       | string  | `''`                     | The label to display when no window is in focus.                                         |
| `label_zero_index`        | boolean | `false`    | Whether to use zero-based indexing for window labels.                    |
| `show_icons`        | string | `never`                                                                  | Whether to display app icons.                                  |
| `icon_size`   | integer | `16`                                                                    | The size of the icon displayed.                              |
| `max_length`        | integer | `None`    | 	The maximum length of the label text.              |
| `max_length_active`        | integer | `None`    | 	The maximum length of the label text for the active window.              |
| `max_length_overall`        | integer | `None`    | 	If specified, `max_length` will be calculated as `max_length_overall` divided by the number of inactive windows.       |
| `max_length_ellipsis`        | string | `'...'`    | 		The ellipsis to use when the label text exceeds the maximum length.              |
| `hide_if_offline`       | boolean | `false`         | Whether to hide the widget if Komorebi is offline.                          |
| `show_only_stack`       | boolean | `false`         | Whether to hide the widget if no stacked windows in focus.                |
| `enable_scroll_switching` | boolean | `false`      | Enable scroll switching between windows.                                 |
| `reverse_scroll_direction` | boolean | `false`      | Reverse scroll direction.                                                  |
| `animation`  | boolean | `false`      | Buttons animation.                                           |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.
| `container_shadow`      | dict    | `None`                  | Container shadow options.                                |
| `label_shadow`            | dict    | `None`                  | Label shadow options.                       |
| `btn_shadow`            | dict    | `None`                  | Window button shadow options.                         |

## Example Configuration

```yaml
komorebi_stack:
  type: "komorebi.stack.StackWidget"
  options:
    label_offline: "Offline"
    label_window: "{process}"
    label_window_active: "{title}"
    label_no_window: "No Window"
    label_zero_index: false
    show_icons: "always"
    icon_size: 14
    max_length: 10
    max_length_active: 20
    max_length_ellipsis: ".."
    hide_if_offline: false
    show_only_stack: false
    animation: true
    enable_scroll_switching : true
    container_shadow:
      enabled: true
      color: "#000000"
      offset: [0, 1]
      radius: 2
    btn_shadow:
      enabled: true
      color: "#000000"
      offset: [0, 1]
      radius: 2
    label_shadow:
      enabled: true
      color: "#000000"
      offset: [0, 1]
      radius: 2
```

## Description of Options
- **label_offline:** The label to display when Komorebi is offline.
- **label_window:** The format string for window buttons, can be {title}, {index}, {process}, or {hwnd}.
- **label_window_active:** The format string for the active window button, can be {title}, {index}, {process}, or {hwnd}.
- **label_no_window:** The label to display when no window is in focus.  
- **label_zero_index:** Whether to use zero-based indexing for workspace labels.
- **show_icons:** Whether to display app icons. Options are `always`, `never`, or `focused`.
- **max_length:** The maximum number of characters to display for the label. If the title exceeds this length, it will be truncated.
- **max_length_active:** The maximum number of characters to display for the active window label. If the title exceeds this length, it will be truncated.
- **max_length_ellipsis:** The string to append to truncated window titles.  
- **hide_if_offline:** Whether to hide the widget if Komorebi is offline.
- **show_only_stack:** Whether to hide the widget if no stacked windows in focus.   
- **enable_scroll_switching:** Enable scroll switching between workspaces.
- **reverse_scroll_direction:** Reverse scroll direction.
- **animation:** Buttons animation.
- **container_padding:** Explicitly set padding inside widget container.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options for labels, including icons and labels within each window button.
- **btn_shadow:** Window button shadow options.

## Style
```css
.komorebi-stack {} /*Style for widget.*/
.komorebi-stack .widget-container {} /*Style for widget container.*/
.komorebi-stack .window {} /*Style for buttons.*/
.komorebi-stack .window .label {} /*Style for the window label.*/
.komorebi-stack .window .icon {} /*Style for the window icon.*/
.komorebi-stack .window.active {} /*Style for the active window button.*/
.komorebi-stack .window.active .label {} /*Style for the active window label.*/
.komorebi-stack .window.active .icon {} /*Style for the active window icon.*/
.komorebi-stack .window.button-1 {} /*Style for first button.*/
.komorebi-stack .window.button-2 {} /*Style for second  button.*/
.komorebi-stack .offline-status{} /*Style for offline status label.*/
.komorebi-stack .no-window{} /*Style for no window label.*/
```

## Example Style
```css
.komorebi-stack {
    margin: 4px 0;
}
.komorebi-stack .widget-container {
    background-color: #282936; 
    border-radius: 4px;
}
.komorebi-stack .window {
    background-color: transparent;
    border: none;
    margin: 0px 8px;
    padding: 0 4px;
}
.komorebi-stack .window.active {
    background-color: #45475a;
    border-radius: 4px;
    height: auto;
    margin: 0;
}
```
