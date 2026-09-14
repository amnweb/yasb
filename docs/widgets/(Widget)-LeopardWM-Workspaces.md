# LeopardWM Workspaces Widget

A single workspace strip for LeopardWM, including inactive workspaces, empty slots,
and tiled/floating application membership. Buttons switch the workspace on their
own monitor, even when another monitor has focus. Default monitor selection uses
the Windows monitor handle, so friendly or duplicate Qt screen names work.

Requires a LeopardWM build supporting `lwm subscribe --events workspace_state`
and monitor-targeted workspace switching. The standalone workspace IPC feature
uses provisional protocol 3; the personal build combining it with Shortcut Guide
uses protocol 4. The widget detects the snapshot capability, not just a version
number. Older LeopardWM releases show the offline state instead of polling a
persisted JSON file.

## Configuration

```yaml
bars:
  primary-bar:
    widgets:
      center: [leopardwm_workspaces]
widgets:
  leopardwm_workspaces:
    type: leopardwm.workspaces.WorkspaceWidget
    options:
      lwm_path: 'C:\path\to\lwm.exe'
      hide_empty_workspaces: true
      app_icons:
        enabled: true
        size: 16
        max_icons: 6
        hide_duplicates: true
```

Use the actual `lwm.exe` path, or leave the default when the executable is on PATH.
Shell commands and command-wrapper scripts are not accepted as `lwm_path`.

| Option | Default | Meaning |
| --- | --- | --- |
| `lwm_path` | `lwm.exe` | LeopardWM CLI executable. |
| `monitor` | `null` | Explicit Windows device name, such as `\\.\DISPLAY2`; otherwise use this bar's screen. |
| `monitor_exclusive` | `true` | Use this bar's monitor when `monitor` is unset; false shows all monitors, ordered by device name. Explicit `monitor` takes precedence. |
| `show_inactive_workspaces` | `true` | Show workspaces that are not active on their monitor. |
| `hide_empty_workspaces` | `false` | Hide empty inactive workspaces. Active workspaces remain visible. |
| `label_workspace_btn` | `{index}` | Empty workspace label. |
| `label_workspace_active_btn` | `{index}` | Active workspace label. |
| `label_workspace_populated_btn` | `{index}` | Populated inactive workspace label. |
| `label_offline` | `LeopardWM Offline` | Text while disconnected or unsupported. |
| `hide_if_offline` | `false` | Hide the strip while disconnected. |
| `enable_scroll_switching` | `true` | Switch workspaces with the mouse wheel. |
| `reverse_scroll_direction` | `false` | Reverse wheel direction. |

Labels accept `{index}` (one-based), `{name}`, `{count}` (all managed members), and
`{monitor}`. Workspace names come from LeopardWM. In all-monitor mode, include
`{monitor}` in labels or use tooltips to distinguish equal workspace numbers.

### Application icons

| `app_icons` option | Default | Meaning |
| --- | --- | --- |
| `enabled` | `false` | Show application icons beside workspace labels. |
| `size` | `16` | Icon size in logical pixels. |
| `max_icons` | `0` | Maximum shown per workspace; 0 is unlimited. Extra icons produce an overflow count. |
| `hide_label` | `false` | Hide the workspace label when icons are displayed. |
| `hide_duplicates` | `false` | Show one icon per application in each workspace. |
| `hide_floating` | `false` | Omit floating-window icons. |
| `monochrome` | `false` | Render native icons in grayscale, preserving transparency. |
| `mode` | `native` | `native` uses YASB's Windows icon lookup; `glyph` uses font glyphs. |
| `glyphs` | `{}` | Executable-basename to glyph mapping, such as `firefox.exe`. |
| `fallback_icon` | `\uE8A5` | Font glyph for an unmapped app or unavailable native icon. |

Icon filters affect presentation only. A workspace containing floating, minimized,
or unresolvable windows remains populated. Native icons use YASB's existing HWND
icon resolver, including packaged-app handling; no generated image folder is used.
Icon extraction runs in background batches and QPixmaps are created on the GUI
thread. The cache follows current HWND membership rather than growing indefinitely.

To use Segoe Fluent Icons for generic symbols:

```yaml
app_icons:
  enabled: true
  mode: glyph
  fallback_icon: "\uE8A5"
  glyphs:
    firefox.exe: "\uE774"
    pwsh.exe: "\uE756"
```

```css
.leopardwm-workspaces .icon {
    font-family: "Segoe Fluent Icons";
    font-size: 16px;
}
```

A font is a glyph collection, not a universal executable-to-logo database. Segoe
Fluent supplies generic symbols; use native mode for application logos, or choose
another installed font and its matching codepoints in `glyphs` and CSS.

## Styling

```css
.leopardwm-workspaces .ws-btn {
    padding: 0 6px;
    margin: 0 2px;
    color: #a2a6ad;
    background-color: transparent;
    border: none;
}
.leopardwm-workspaces .ws-btn.focused { background-color: #303238; }
.leopardwm-workspaces .ws-btn.empty .label { color: #737780; }
.leopardwm-workspaces .ws-btn.active .label { color: #f4f5f7; }
.leopardwm-workspaces .label { font-size: 16px; }
.leopardwm-workspaces .icon { margin: 0 3px; }
.leopardwm-workspaces .overflow { font-size: 11px; }
.leopardwm-workspaces .offline { color: #737780; }
```

The widget root uses `leopardwm-workspaces`; buttons use `ws-btn` plus `empty` or
`populated`, `active` for each monitor's visible workspace, and `focused` for the
active workspace on LeopardWM's focused monitor. Labels/icons/overflow/offline
text have their own classes. Use descendant label rules when styling text inside
buttons, as Qt child labels can override their parent's color.

## Connection and recovery

All strips using the same `lwm_path` share one subscription. Complete snapshots
replace state atomically; partial, malformed, oversized, or lagged snapshots are
never displayed. The service reconnects with backoff after a disconnect, malformed
stream, or liveness timeout, and gets a fresh initial state after daemon restart.
Buttons are disabled/offline while state is unavailable. The service stops its
child processes when the last widget is disposed or YASB exits.

Membership comes from LeopardWM, including inactive workspaces and floating windows.
Hidden scratchpads are omitted; shown scratchpads and sticky windows use the
ownership reported by the daemon. Icon failure does not remove membership.

This widget changes LeopardWM workspaces, not Windows virtual desktops. It does
not start the window manager, change its config, or provide a file-polling fallback.
