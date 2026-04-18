# Shellwright Workspaces Widget

Displays workspace buttons and the active tiling layout for a single monitor, fed live from the [shellwright](https://github.com/your-org/shellwright) window manager over a named pipe (`\\.\pipe\shellwright`). The widget reconnects automatically when shellwright restarts.

| Option                          | Type      | Default        | Description                                                                                                                                                                                                                                                  |
| ------------------------------- | --------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `label_offline`                 | string    | `''`           | Text shown when shellwright is not running.                                                                                                                                                                                                                  |
| `label_workspace_btn`           | string    | `''`           | Format string for empty/default workspace buttons. Supports `{name}` and `{index}`.                                                                                                                                                                          |
| `label_workspace_active_btn`    | string    | `''`           | Format string for the active workspace button. Supports `{name}` and `{index}`.                                                                                                                                                                              |
| `label_workspace_populated_btn` | string    | `''`           | Format string for populated (non-active) workspace buttons. Supports `{name}` and `{index}`.                                                                                                                                                                 |
| `monitor_index`                 | integer   | `-1`           | 0-based index of the monitor this bar lives on. `-1` = auto-detect from Qt screen API. Override only when auto-detection gives the wrong monitor.                                                                                                            |
| `monitor_index_remap`           | list[int] | `[]`           | Optional remapping when the Qt screen order differs from the shellwright monitor order. Index = Qt screen index, value = shellwright monitor index. Example: `[2, 0, 1]` maps Qt screen 0 → shellwright monitor 2. Empty list uses Qt screen index directly. |
| `hide_if_offline`               | boolean   | `true`         | Hide the entire widget when shellwright is not running.                                                                                                                                                                                                      |
| `hide_empty_workspaces`         | boolean   | `false`        | Hide workspace buttons that contain no windows.                                                                                                                                                                                                              |
| `show_layout`                   | boolean   | `false`        | Show the active tiling layout for this monitor's focused workspace.                                                                                                                                                                                          |
| `label_layout`                  | string    | `'[{layout}]'` | Format string for the layout label. Supports `{layout}` (one of: `fibonacci`, `bsp`, `columns`, `monocle`, `center_main`, `float`).                                                                                                                          |
| `container_padding`             | dict      | `None`         | Inner padding for the widget container.                                                                                                                                                                                                                      |
| `btn_shadow`                    | dict      | `None`         | Shadow options applied to each workspace button.                                                                                                                                                                                                             |
| `label_shadow`                  | dict      | `None`         | Shadow options applied to the offline and layout labels.                                                                                                                                                                                                     |
| `container_shadow`              | dict      | `None`         | Shadow options applied to the outer widget container.                                                                                                                                                                                                        |

## Example Configuration

```yaml
shellwright_workspaces:
  type: "shellwright.workspaces.WorkspaceWidget"
  options:
    label_offline: "SW Offline"
    label_workspace_btn: "{index}"
    label_workspace_active_btn: "{index}"
    label_workspace_populated_btn: "{index}"
    hide_if_offline: true
    hide_empty_workspaces: true
    show_layout: true
    label_layout: " [{layout}]"
    monitor_index: -1
    monitor_index_remap: []
    btn_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [1, 1]
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [1, 1]
```

## Description of Options

- **label_offline:** Text shown in the bar when shellwright is not running. Hidden automatically once the pipe connects.
- **label_workspace_btn:** Format string for workspace buttons in the default (empty) state. Use `{name}` for the workspace name set in `config.toml`, or `{index}` for the 1-based position.
- **label_workspace_active_btn:** Format string for the button of the workspace that is currently focused on this monitor.
- **label_workspace_populated_btn:** Format string for buttons whose workspace contains at least one window but is not currently active.
- **monitor_index:** Which shellwright monitor index this widget instance represents. Use `-1` (default) to let YASB auto-detect the monitor from its own screen position. Set an explicit value only when the Qt screen order and the shellwright monitor order do not match.
- **monitor_index_remap:** Fine-grained override for the Qt → shellwright monitor mapping. Provide a list where position _i_ holds the shellwright monitor index for Qt screen _i_. Takes precedence over `monitor_index` auto-detect when non-empty.
- **hide_if_offline:** When `true`, the widget is completely hidden until shellwright connects. When `false` (default), the `label_offline` text is shown instead.
- **hide_empty_workspaces:** When `true`, buttons for workspaces that contain no windows are hidden.
- **show_layout:** When `true`, a layout label is appended after the workspace buttons showing the tiling strategy active on this monitor's focused workspace.
- **label_layout:** Format string for the layout label. `{layout}` is replaced with the current layout name. Available layout names: `fibonacci`, `bsp`, `columns`, `monocle`, `center_main`, `float`.
- **container_padding:** Padding around the widget's inner layout (top, right, bottom, left in pixels).
- **btn_shadow:** Drop-shadow applied to every workspace button.
- **label_shadow:** Drop-shadow applied to the offline label and the layout label.
- **container_shadow:** Drop-shadow applied to the outer widget frame.

## Style

```css
.shellwright-workspaces {
} /* Outer widget frame */
.shellwright-workspaces .widget-container {
} /* Inner container */
.shellwright-workspaces .sw-offline {
} /* "Offline" label (shown when disconnected) */
.shellwright-workspaces .ws-btn {
} /* Every workspace button */
.shellwright-workspaces .ws-btn.empty {
} /* Empty workspace (no windows) */
.shellwright-workspaces .ws-btn.populated {
} /* Has windows, not the active workspace */
.shellwright-workspaces .ws-btn.active {
} /* Active (focused) workspace on this monitor */
.shellwright-workspaces .sw-layout {
} /* Layout label (visible when show_layout = true) */
```

> [!NOTE]
> You can combine state classes with button position for per-workspace styling, e.g. `.shellwright-workspaces .ws-btn.active` targets only the active workspace button.

## Example Style

```css
/* Minimal dot-style workspace indicators */
.shellwright-workspaces .ws-btn {
  background: transparent;
  border: none;
  min-width: 8px;
  min-height: 8px;
  border-radius: 4px;
  margin: 0 3px;
  padding: 0;
  font-size: 0; /* hide text, show only background shape */
}
.shellwright-workspaces .ws-btn.empty {
  background-color: #555555;
  border-radius: 50%;
}
.shellwright-workspaces .ws-btn.populated {
  background-color: #ffffff;
  border-radius: 50%;
}
.shellwright-workspaces .ws-btn.active {
  background-color: #5294e2;
  border-radius: 2px;
  min-width: 18px;
}
.shellwright-workspaces .sw-layout {
  color: #888888;
  font-size: 11px;
  margin-left: 4px;
}
.shellwright-workspaces .sw-offline {
  color: #555555;
  font-size: 11px;
}
```

## Named Pipe Protocol

shellwright broadcasts a newline-terminated JSON object on `\\.\pipe\shellwright` after every state change (window create/destroy/focus, workspace switch, layout change, float/fullscreen toggle). The schema mirrors the komorebi pipe format for compatibility:

```json
{
  "monitors": {
    "elements": [
      {
        "name": "Monitor 1",
        "index": 0,
        "workspaces": {
          "elements": [
            {
              "name": "1",
              "index": 0,
              "layout": "fibonacci",
              "focused_window": "Window Title",
              "windows": {
                "elements": [{ "id": 0 }, { "id": 1 }],
                "focused": 0
              }
            }
          ],
          "focused": 0
        }
      }
    ],
    "focused": 0
  }
}
```

| Field                                     | Description                                                                 |
| ----------------------------------------- | --------------------------------------------------------------------------- |
| `monitors.focused`                        | 0-based index of the monitor with keyboard focus.                           |
| `monitors.elements[i].index`              | 0-based monitor index (matches `monitor_index` option).                     |
| `monitors.elements[i].workspaces.focused` | Local 0-based index of the active workspace on this monitor.                |
| `workspaces.elements[j].name`             | Workspace name from `config.toml`.                                          |
| `workspaces.elements[j].layout`           | Active layout: `fibonacci` `bsp` `columns` `monocle` `center_main` `float`. |
| `workspaces.elements[j].focused_window`   | Title of the focused window on this workspace (empty string if none).       |
| `workspaces.elements[j].windows.elements` | One `{"id": N}` entry per managed window on this workspace.                 |
