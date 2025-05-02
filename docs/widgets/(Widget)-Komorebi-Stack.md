# Komorebi Workspaces Widget
| Option                     | Type    | Default                  | Description                                                                 |
|----------------------------|---------|--------------------------|-----------------------------------------------------------------------------|
| `label_offline`          | string  | `'Komorebi Offline'`     | The label to display when Komorebi is offline.                              |
| `label_window`    | string  | `'{index}'`              | The format string for window buttons.                                    |
| `label_window_active` | string | `'{index}'`              | The format string for the active window button.                          |
| `label_no_window`       | string  | `''`                     | The label to display when no window is in focus.                                         |
| `label_zero_index`        | boolean | `false`    | Whether to use zero-based indexing for workspace labels.                    |
| `max_length`        | boolean | `None`    | 	The maximum length of the label text.              |
| `max_length_active`        | boolean | `None`    | 	The maximum length of the label text for the active window.              |
| `max_length_ellipsis`        | boolean | `None`    | 		The ellipsis to use when the label text exceeds the maximum length.              |
| `hide_if_offline`       | boolean | `false`         | Whether to hide the widget if Komorebi is offline.                          |
| `enable_scroll_switching` | boolean | `false`      | Enable scroll switching between windows.                                 |
| `reverse_scroll_direction` | boolean | `false`      | Reverse scroll direction.                                                  |
| `animation`  | boolean | `false`      | Buttons animation.                                           |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.
| `container_shadow`      | dict    | `None`                  | Container shadow options.                                |
| `label_shadow`            | dict    | `None`                  | Label shadow options.                       |

## Example Configuration

```yaml
komorebi_stack:
  type: "komorebi.stack.StackWidget"
  options:
    label_offline: "Offline"
    label_window: "{index} {process}"
    label_window_active: "{index} {title}"
    label_no_window: "No Window"
    label_zero_index: false
    max_length: 10
    max_length_active: 20
    max_length_ellipsis: ".."
    hide_if_offline: false
    animation: true
    enable_scroll_switching : true
    container_shadow:
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
- **max_length:** The maximum number of characters to display for the window title. If the title exceeds this length, it will be truncated.
- **max_length_active:** The maximum number of characters to display for the active window title. If the title exceeds this length, it will be truncated.
- **max_length_ellipsis:** The string to append to truncated window titles.  
- **hide_if_offline:** Whether to hide the widget if Komorebi is offline.
- **enable_scroll_switching:** Enable scroll switching between workspaces.
- **reverse_scroll_direction:** Reverse scroll direction.
- **animation:** Buttons animation.
- **container_padding:** Explicitly set padding inside widget container.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options for labels.

## Style
```css
.komorebi-workspaces {} /*Style for widget.*/
.komorebi-workspaces .widget-container {} /*Style for widget container.*/
.komorebi-workspaces .window {} /*Style for buttons.*/
.komorebi-workspaces .window.active {} /*Style for the active window button.*/
.komorebi-workspaces .window.button-1 {} /*Style for first button.*/
.komorebi-workspaces .window.button-2 {} /*Style for second  button.*/

> [!NOTE]  
> You can use `button-x` to style each button separately. Where x is the index of the button.
