# GlazeWM Workspaces Widget
| Option                   | Type    | Default                                          | Description                                                                 |
|--------------------------|---------|--------------------------------------------------|-----------------------------------------------------------------------------|
| `offline_label`          | string  | `'GlazeWM Offline'`                              | The label to display when GlazeWM is offline.                               |
| `populated_label`        | string  | `'{name}'`                                       | Optional label for populated workspaces.                                    |
| `empty_label`            | string  | `'{name}'`                                       | Optional label for empty workspaces.                                        |
| `active_populated_label` | string  | `'{name}'`                                       | Optional label for the currently focused workspace (has opened windows).    |
| `active_empty_label`     | string  | `'{name}'`                                       | Optional label for the currently focused workspace (has no windows opened). |
| `hide_empty_workspaces`  | boolean | `true`                                           | Whether to hide empty workspaces.                                           |
| `hide_if_offline`        | boolean | `false`                                          | Whether to hide workspaces widget if GlazeWM is offline.                    |
| `glazewm_server_uri`     | string  | `'ws://localhost:6123'`                          | Optional GlazeWM server uri.                                                |
| `enable_scroll_switching` | boolean | `true`      | Enable scroll switching between workspaces.                                 |
| `reverse_scroll_direction` | boolean | `false`      | Reverse scroll direction.                                                  |
| `container_padding`      | dict    | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}` | Explicitly set padding inside widget container.                             |
| `container_shadow`       | dict    | `None`                                           | Container shadow options.                                                   |
| `btn_shadow`             | dict    | `None`                                           | Workspace button shadow options.                                            |

## Example Configuration

```yaml
glazewm_workspaces:
  type: "glazewm.workspaces.GlazewmWorkspacesWidget"
  options:
    offline_label: "GlazeWM Offline"
    hide_empty_workspaces: true
    hide_if_offline: false
    enable_scroll_switching: true
    btn_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
    container_padding: 
      top: 0
      left: 8
      bottom: 0
      right: 8

    # By default workspace names are fetched from GlazeWM and "display_name" option takes priority over "name".
    # However, you can customize populated and empty labels here using {name} and {display_name} placeholders if needed.
    # {name} will be replaced with workspace name (index) from GlazeWM.
    # {display_name} will be replaced with workspace display_name from GlazeWM.

    # populated_label: "{name} {display_name} \uebb4"
    # empty_label: "{name} {display_name} \uebb5"
```

## Description of Options
- **offline_label:** The label to display when GlazeWM is offline.
- **populated_label:** Optional label for populated workspaces. If not set, name or display_name from GlazeWM will be used.
- **empty_label:** Optional label for empty workspaces. If not set, name or display_name from GlazeWM will be used.
- **active_populated_label:** Optional label for the currently focused workspace (has windows opened). If not set, name or display_name from GlazeWM will be used.
- **active_empty_label:** Optional label for the currently focused workspace (has no windows opened). If not set, name or display_name from GlazeWM will be used.
- **hide_empty_workspaces:** Whether to hide empty workspaces.
- **hide_if_offline:** Whether to hide workspaces widget if GlazeWM is offline.
- **glazewm_server_uri:** Optional GlazeWM server uri if it ever changes on GlazeWM side.
- **enable_scroll_switching:** Enable scroll switching between workspaces.
- **reverse_scroll_direction:** Reverse scroll direction for switching workspaces.amnwe
- **container_padding:** Explicitly set padding inside widget container.
- **container_shadow:** Container shadow options.
- **btn_shadow:** Workspace button shadow options.

## Note on Shadows
`container_shadow` is applied to the container if it's not transparent.
If it is transparent, container shadows will be applied to the `btn` instead.
This can cause double shadows if you have `btn_shadow` already.
Apply the shadows only to the container that is actually visible.

## Note on Workspace Names
In GlazeWM config use "1", "2", "3" for workspace "name" and NOT some custom string. This will ensure proper sorting of workspaces.

If you need a custom name for each workspace - use "display_name".

**Example:**

```yaml
workspaces:
  - name: "1"
    display_name: "Work" # Optional
  - name: "2"
    display_name: "Browser" # Optional
  - name: "3"
    display_name: "Music" # Optional
  # and so on...
```

## Style
```css
.glazewm-workspaces {} /*Style for widget.*/
.glazewm-workspaces .ws-btn {} /*Style for workspace buttons.*/
.glazewm-workspaces .ws-btn.active_populated {} /*Style for active populated workspace button.*/
.glazewm-workspaces .ws-btn.active_empty {} /*Style for active empty workspace button.*/
.glazewm-workspaces .ws-btn.populated {} /*Style for populated workspace button.*/
.glazewm-workspaces .ws-btn.empty {} /*Style for empty workspace button.*/
.glazewm-workspaces .offline-status {} /*Style for offline status label.*/
```

## Example CSS
```css
.glazewm-workspaces {
    margin: 0;
}

.glazewm-workspaces .ws-btn {
    font-size: 14px;
    background-color: transparent;
    border: none;
    padding: 0px 4px 0px 4px;
    margin: 0 2px 0 2px;
    color: #CDD6F4;
}

.glazewm-workspaces .ws-btn.active_populated {
    color: #C2DAF7;
    background-color: #727272;
}
.glazewm-workspaces .ws-btn.active_empty {
    color: #7D8B9D;
    background-color: #727272;
}

.glazewm-workspaces .ws-btn.populated {
    color: #C2DAF7;
}

.glazewm-workspaces .ws-btn.empty {
    color: #7D8B9D;
}

.glazewm-workspaces .ws-btn:hover,
.glazewm-workspaces .ws-btn.populated:hover,
.glazewm-workspaces .ws-btn.empty:hover {
    background-color: #727272;
}
```
