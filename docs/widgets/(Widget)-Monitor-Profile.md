# Monitor Profile Widget

Saves and switches between monitor layout profiles (which monitors are active, their positions, resolution, refresh rate and orientation) — similar to the classic "Monitor Profile Switcher" tool. The current layout is captured via the Windows CCD API and stored as a profile; applying a profile restores that exact arrangement.

## Options

| Option       | Type   | Default                                                                             | Description                                                                                                                                        |
| ------------ | ------ | ----------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `label`      | string | `"\uf3e2 {active_profile}"`                                                         | Main label template. Use `{active_profile}` to insert the active profile name (`Custom` when the current layout does not match any saved profile). |
| `label_alt`  | string | `"\uf3e2 Monitor Profile"`                                                          | Alternate label shown when toggled via `toggle_label`.                                                                                             |
| `class_name` | string | `""`                                                                                | Additional CSS class name for the widget.                                                                                                          |
| `menu`       | dict   | `{}`                                                                                | Popup menu options (see **Menu Options** below).                                                                                                   |
| `callbacks`  | dict   | `{'on_left': 'toggle_menu', 'on_middle': 'toggle_label', 'on_right': 'do_nothing'}` | Click handlers: `on_left`, `on_middle`, `on_right`.                                                                                                |

## Menu Options

| Option               | Type   | Default    | Description                                                                          |
| -------------------- | ------ | ---------- | ------------------------------------------------------------------------------------ |
| `blur`               | bool   | `true`     | Blur background behind the popup.                                                    |
| `round_corners`      | bool   | `true`     | Enable rounded corners on the popup.                                                 |
| `round_corners_type` | string | `"normal"` | Rounding style: `"small"`, `"normal"`.                                               |
| `border_color`       | string | `"system"` | Border color can be `None`, `system` or `Hex Color` `"#ff0000"`                      |
| `alignment`          | string | `"right"`  | Horizontal alignment of the menu relative to the widget (`left`, `right`, `center`). |
| `direction`          | string | `"down"`   | Vertical opening direction: `"up"` or `"down"`.                                      |
| `offset_top`         | int    | `6`        | Vertical offset in pixels.                                                           |
| `offset_left`        | int    | `0`        | Horizontal offset in pixels.                                                         |
| `monitors_section`   | bool   | `true`     | Show the **Monitors** section with per-monitor enable/disable controls.              |

## Example Configuration

```yaml
monitor_profile:
  type: "yasb.monitor_profile.MonitorProfileWidget"
  options:
    label: "<span>\uf3e2</span> {active_profile}"
    label_alt: "<span>\uf3e2</span> Monitor Profiles"
    menu:
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "system"
      alignment: "center"
      direction: "down"
      offset_top: 6
      offset_left: 0
    callbacks:
      on_left: "toggle_menu"
      on_middle: "toggle_label"
      on_right: "save_profile"
```

## Description of Options

- **label**: Main label template. Use `{active_profile}` to insert the active profile name. When the current display layout does not match any saved profile, the label shows `Custom`.
- **label_alt**: Alternate label shown when toggled via `toggle_label`.
- **class_name**: Additional CSS class name for the widget. This allows for custom styling.
- **menu**: Popup menu options.
- **callbacks**: Click handlers for left, middle, and right mouse buttons.

## Saving and Applying Profiles

- Click **Save current layout...** in the menu to store the current monitor arrangement as a named profile. Profiles are saved as JSON files in `%USERPROFILE%\.config\yasb\monitor_profiles\`.
- Clicking a profile in the menu applies it. Windows re-arranges the monitors to the saved positions/resolutions/refresh rates.
- Each profile row has a **⋯ (options) button** on the right with a dropdown menu: **Apply**, **Set Hotkey...**, **Remove Hotkey** (when set), **Rename...** and **Delete Profile**.
- The label automatically shows the name of the profile matching the current layout, or `Custom` if the current layout was modified outside the widget (e.g. via Windows display settings).

## Profile & Monitor Hotkeys

Use the **⋯** button on any profile or monitor row → **Set Hotkey...** to bind a global key combination:

- Press the desired combination in the dialog (e.g. `Ctrl+Alt+1`), then click **Save**.
- Hotkeys are stored in `%USERPROFILE%\.config\yasb\monitor_profiles\hotkeys.json` and registered immediately — no restart needed.
- The current hotkey is shown at the top of the row's ⋯ menu; use **Remove Hotkey** to unbind.
- Profile hotkeys apply the profile; monitor hotkeys toggle the monitor (hide it when active, show it when disabled).
- Supported keys: letters, digits, `F1`-`F24`, and named keys (`space`, `enter`, `esc`, arrows, etc.) with `ctrl`/`alt`/`shift`/`win` modifiers.

> [!NOTE]
> Hotkeys registered here are global (system-wide) and take priority over identical bindings in other apps. If a hotkey is already taken, registration fails and a warning is logged.

## Monitors Section

When `menu.monitors_section` is enabled (default) and more than one display is present, the menu shows a **Monitors** section:

- Every active monitor is listed with a **⋯ (options)** button on the right — open it to **Hide Monitor** (disable without unplugging) or **Set Hotkey** for toggling.
- Monitors that are connected but currently disabled appear in italic; their ⋯ menu offers **Show Monitor** and hotkey options.
- The section is hidden entirely when only one monitor is present and none is disabled.

> [!NOTE]
> Applying a profile only succeeds when the monitors in that profile are currently connected. If a monitor has been disconnected, Windows rejects the layout and the error is logged.

## Available Callbacks

- `toggle_label`: Toggles the visibility of the label.
- `toggle_menu`: Toggles the visibility of the monitor profile menu popup.
- `save_profile`: Opens a dialog to save the current monitor layout as a new profile.
- `next_profile`: Applies the next profile in the list (wraps around).
- `prev_profile`: Applies the previous profile in the list (wraps around).

## Keybindings Example

```yaml
monitor_profile:
  type: "yasb.monitor_profile.MonitorProfileWidget"
  options:
    keybindings:
      - keys: "ctrl+alt+1"
        action: "next_profile"
      - keys: "ctrl+alt+2"
        action: "toggle_menu"
```

## Available Styles

```css
.monitor-profile-widget {
}
.monitor-profile-widget.your_class {
} /* If you are using class_name option */
.monitor-profile-widget .widget-container {
}
.monitor-profile-widget .label {
}
.monitor-profile-widget .label.active {
} /* Current layout matches a saved profile */
.monitor-profile-widget .label.unsaved {
} /* Current layout is "Custom" */
.monitor-profile-widget .icon {
}
.monitor-profile-menu {
}
.monitor-profile-menu .menu-block.profiles-block {
}
.monitor-profile-menu .menu-block.monitors-block {
}
.monitor-profile-menu .menu-content {
}
.monitor-profile-menu .menu-content .profile-row {
}
.monitor-profile-menu .menu-content .profile-row .button {
}
.monitor-profile-menu .menu-content .profile-row .button.delete {
}
.monitor-profile-menu .menu-content .profile-row .button.more {
}
.monitor-profile-menu .menu-content .button.save {
}
.monitor-profile-menu .menu-content .separator {
}
.monitor-profile-menu .menu-content .monitor-row {
}
.monitor-profile-menu .menu-content .monitor-row .button.monitor {
}
.monitor-profile-menu
  .menu-content
  .monitor-row
  .button.monitor.disabled-monitor {
}
.monitor-profile-menu .menu-content .monitor-row .button.more {
}
.monitor-profile-popup .rename-input {
}
.monitor-profile-popup {
}
.monitor-profile-popup .monitor-profile-popup-container {
}
.monitor-profile-popup .popup-title {
}
.monitor-profile-popup .popup-description {
}
.monitor-profile-popup .rename-input {
}
.monitor-profile-popup .monitor-profile-popup-footer {
}
.monitor-profile-popup .monitor-profile-popup-footer .button {
}
```

## Example Style

```css
.monitor-profile-widget {
  padding: 0 6px 0 6px;
}
.monitor-profile-widget .label {
  font-size: 12px;
}
.monitor-profile-widget .icon {
  font-size: 12px;
  padding-right: 4px;
}

.monitor-profile-menu {
  background-color: rgba(24, 25, 27, 0.6);
}
.monitor-profile-menu .menu-content .button {
  padding: 6px 12px;
  border-radius: 4px;
}
.monitor-profile-menu .menu-content .button.active {
  background-color: rgba(255, 255, 255, 0.12);
}
```
