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
| `label_workspace_empty_btn` | `null` | Optional label for every empty workspace, overriding active/empty templates. Use `"○"` for a dot, `"{index}"` for a number, or custom template text. `null` preserves existing label selection. |
| `workspace_separator` | `""` | Text only between visible workspace groups, e.g. `"|"` or `"·"`. Empty disables separators. |
| `show_focus_indicator` | `false` | Adds `focus-indicator` to the globally focused button for CSS styling, such as an underline. |
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
| `focused_monochrome` | `null` | Native icon grayscale override for the globally focused workspace. `null` inherits `monochrome`. |
| `inactive_monochrome` | `null` | Native icon grayscale override for every other workspace, including an active workspace on an unfocused monitor. `null` inherits `monochrome`. |
| `cell_width` | `null` | Optional icon cell width (8–128 logical pixels), clamped to at least `size`. `null` keeps CSS/default sizing. |
| `inactive_cell_width` | `null` | Icon cell width for nonfocused workspaces. `null` inherits `cell_width`; use equal widths for stable spacing. |
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

### Icon-only groups with focus styling

```yaml
options:
  hide_empty_workspaces: true
  label_workspace_empty_btn: "○" # "{index}" shows a number instead
  workspace_separator: "|"      # "" disables separators
  show_focus_indicator: true
  app_icons:
    enabled: true
    hide_label: true
    size: 16
    cell_width: 28
    inactive_cell_width: 28     # 20 is more compact, without overlapping art
    focused_monochrome: false
    inactive_monochrome: true
```

The empty label remains visible when there are no icons. `hide_label` hides text
only when at least one icon is displayed, so filtering all icons still leaves a
workspace identifiable. Tooltips and accessibility names retain the actual monitor,
workspace number/name and membership count regardless of the visual label.

Use this CSS with `show_focus_indicator` for a thin underline. Reserving the same
border on every button prevents focus changes from changing layout dimensions:

```css
.leopardwm-workspaces .ws-btn {
    border: none;
    border-bottom: 2px solid transparent;
}
.leopardwm-workspaces .ws-btn.focus-indicator {
    border-bottom-color: #f4f5f7;
}
.leopardwm-workspaces .separator {
    color: #737780;
    font-family: "Segoe UI";
    font-size: 16px;
    padding: 0 4px 6px;
}
```

The separator example centers a 16px Segoe UI pipe on the 16px icon row; the
bottom padding compensates for the glyph baseline and reserved underline space.
Adjust the padding when using a different separator font, symbol, or icon size.

Separators are decorative and cannot activate a workspace. They disappear when
adjacent groups are hidden or state goes offline; no leading/trailing separator
is drawn. In all-monitor mode they also separate groups across monitor boundaries.

Color/grayscale variants are cached together and selected on focus changes without
new Windows icon queries. The per-state overrides affect native pixmaps; font
icons use CSS colors (for example `.ws-btn.focused .icon`). Set `monochrome: false`
and leave both overrides `null` for color everywhere, or set `monochrome: true`
with null overrides for grayscale everywhere. An explicit override wins over
`monochrome`. If no monitor is focused, every group uses the inactive treatment.

Explicit cell-width options size the cells around the icon rather than resizing
its artwork. Avoid conflicting CSS `min-width`/`max-width` rules when using them;
leave these options null if CSS should control sizing. Overlapping icons are not
implemented; widths below the icon size are clamped to keep the full artwork visible.

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
