# Windows Desktops Widget

Displays your Windows virtual desktops in the status bar so you can switch between them. You can click to change desktops, see custom indicators for the active desktop and for desktops that still have windows open, and show names or numbers for each desktop.

| Option                     | Type    | Default                  | Description                                                                 |
|----------------------------|---------|--------------------------|-----------------------------------------------------------------------------|
| `label_workspace_btn`    | string  | `'{index}'`              | The format string for workspace buttons.                                    |
| `label_workspace_active_btn` | string | `'{index}'`              | The format string for the active workspace button.                          |
| `label_workspace_populated_btn` | string | `None`               | The format string for buttons of desktops that have windows open. |
| `enable_scroll_switching` | boolean | `false`                 | Switch desktops with the mouse wheel over the widget.                       |
| `reverse_scroll_direction` | boolean | `false`                | Reverse the mouse wheel direction for switching desktops.                   |
| `keybindings`            | list    | `[]`                     | Optional hotkeys. See [Keybindings](./Keybindings).                         |
| `callbacks`             | dict    | [See below](#available-callbacks) | Callbacks for mouse events on workspace buttons. |

## Example Configuration

```yaml
windows_workspaces:
  type: "yasb.windows_desktops.WorkspaceWidget"
  options:
    label_workspace_btn: "\udb81\udc3d"
    label_workspace_active_btn: "\udb81\udc3e"
    callbacks:
      on_left: "activate_workspace"
      on_middle: "do_nothing"
      on_right: "toggle_context_menu"
```

## Description of Options
- **label_workspace_btn:** The format string for workspace buttons, can be icon, {index} or {name}.
- **label_workspace_active_btn:** The format string for the active workspace button, can be icon, {index} or {name}.
- **label_workspace_populated_btn:** The format string for buttons of desktops that are not active but have at least one window open, can be icon, {index} or {name}. If not set, `label_workspace_btn` is used. A window counts when it appears in Alt+Tab, windows pinned to all desktops are ignored.
- **enable_scroll_switching:** Scroll down over the widget for the next desktop and up for the previous one. Going past the last desktop wraps around to the first.
- **reverse_scroll_direction:** Swap the scroll directions, so scrolling up goes to the next desktop.
- **keybindings:** A list of global hotkeys for this widget. See [Keybindings](./Keybindings) and the [example below](#keybindings-example).
- **callbacks:** Mouse event callbacks. See [Callbacks](#available-callbacks).

### Available Callbacks

The `callbacks` option maps mouse buttons (`on_left`, `on_middle`, `on_right`) to actions. All keys are optional, the values shown are the defaults.

```yaml
callbacks:
  on_left: "activate_workspace"
  on_middle: "do_nothing"
  on_right: "toggle_context_menu"
```

Available actions:

| Callback               | Description                                                              |
|------------------------|--------------------------------------------------------------------------|
| `activate_workspace`   | Switch to the desktop associated with the clicked button.                |
| `toggle_context_menu`  | Show the right-click context menu options.                               |
| `move_window_here`     | Move the currently focused window to the desktop of the clicked button.  |
| `delete_workspace`     | Delete the desktop associated with the clicked button.                   |
| `create_desktop`       | Create a new virtual desktop and stay on the current one.                |
| `rename_desktop`       | Open a dialog to rename the desktop of the clicked button.               |
| `switch_desktop N`     | Switch to desktop N, where 1 is the first desktop.                       |
| `move_window_to N`     | Move the currently focused window to desktop N.                          |
| `delete_desktop`       | Delete the current desktop. Its windows move to the first desktop, or to the second if you delete the first. Add a number, like `delete_desktop 3`, to delete that desktop instead. |
| `next_desktop`         | Switch to the next desktop, wrapping around to the first.                |
| `prev_desktop`         | Switch to the previous desktop, wrapping around to the last.             |
| `do_nothing`           | No action.                                                               |

`activate_workspace`, `toggle_context_menu`, `move_window_here`, `delete_workspace` and `rename_desktop` act on the clicked button, so use them for mouse callbacks only. Every other action also works as a keybinding.

### Keybindings Example

Windows has shortcuts for the next and previous desktop, but none to jump to a specific desktop or to send a window there, and `Win+Ctrl+D` always switches to the desktop it creates. Keybindings can add all of these:

```yaml
windows_workspaces:
  type: "yasb.windows_desktops.WorkspaceWidget"
  options:
    keybindings:
      - keys: "alt+1"
        action: "switch_desktop 1"
      - keys: "alt+2"
        action: "switch_desktop 2"
      - keys: "alt+shift+1"
        action: "move_window_to 1"
      - keys: "alt+shift+2"
        action: "move_window_to 2"
      - keys: "alt+shift+n"
        action: "create_desktop"
      - keys: "alt+shift+d"
        action: "delete_desktop"
```

Avoid combinations of `win` with a number key: Windows already uses them for taskbar apps, so those hotkeys fail to register.

## Style
```css
.windows-desktops {} /*Style for widget.*/
.windows-desktops .widget-container {} /*Style for widget container.*/
.windows-desktops .ws-btn {} /*Style for buttons.*/
.windows-desktops .ws-btn.active {} /*Style for the active workspace button.*/
.windows-desktops .ws-btn.populated {} /*Style for buttons of other desktops that have windows open.*/
.windows-workspaces .ws-btn.button-1 {} /*Style for first button.*/
.windows-workspaces .ws-btn.button-2 {} /*Style for second  button.*/
.windows-workspaces .ws-btn.active.button-1 {} /*Style for the active first workspace button.*/
.windows-workspaces .ws-btn.active.button-2 {} /*Style for the active second workspace button.*/

.windows-desktops .context-menu {} /*Style for context menu.*/
.windows-desktops .context-menu .menu-item {} /*Style for context menu items.*/
.windows-desktops .context-menu .menu-item:hover {} /*Style for selected context menu items.*/
.windows-desktops .context-menu .separator {} /*Style for context menu separator.*/

.windows-desktops-popup.rename {} /*Style for rename dialog.*/
.windows-desktops-popup.rename .windows-desktops-popup-container {} /*Style for rename dialog content area.*/
.windows-desktops-popup.rename .windows-desktops-popup-footer {} /*Style for rename dialog footer with the buttons.*/
.windows-desktops-popup .popup-title {} /*Style for rename dialog title.*/
.windows-desktops-popup .popup-description {} /*Style for rename dialog description.*/
.windows-desktops-popup .rename-input {} /*Style for rename dialog input.*/
.windows-desktops-popup .button {} /*Style for rename dialog buttons.*/
.windows-desktops-popup .button.save {} /*Style for rename dialog save button.*/
.windows-desktops-popup .button.cancel {} /*Style for rename dialog cancel button.*/
```

### Example
```css
.windows-desktops {
    padding: 0 4px 0 14px;
}
.windows-desktops .widget-container {
    background-color: #11111b;
    margin: 4px 0 4px 0;
    border-radius: 12px;
}
.windows-desktops .ws-btn {
    color: #7f849c;
    border: none;
    font-size: 14px;
    margin: 0 3px;
    padding: 0 
}
.windows-desktops .ws-btn.active {
    color: #89b4fa;
} 
.windows-desktops .ws-btn.populated {
    color: #cdd6f4;
}

.windows-desktops .context-menu {
    background-color:rgba(17, 17, 27, 0.75);
    border: none;
    border-radius: 2px;
    padding: 8px 0;
}
.windows-desktops .context-menu .menu-item {
    padding: 6px 16px;
}
.windows-desktops .context-menu .menu-item:hover {
    background-color: rgba(255,255,255,0.05);
    color: #ffffff;
}
.windows-desktops .context-menu .separator {
    margin: 2px 0px 2px 0px;
    height: 1px;
    background-color: rgba(255,255,255,0.1);
}


.windows-desktops-popup.rename {
    min-width: 320px;
    background-color: rgb(43, 43, 43);
}
.windows-desktops-popup.rename .windows-desktops-popup-container {
    padding: 16px;
}
.windows-desktops-popup.rename .windows-desktops-popup-footer {
    padding: 16px;
    background-color:rgb(32, 32, 32)
}
.windows-desktops-popup .popup-title {
    font-size: 16px;
    font-family: "Segoe UI Variable", "Segoe UI";
    font-weight: 600;
    color: rgba(255, 255, 255, 0.9);
    margin-bottom: 4px;
}
.windows-desktops-popup .popup-description {
    font-size: 13px;
    font-family: "Segoe UI Variable", "Segoe UI";
    font-weight: 400;
    color: rgba(255, 255, 255, 0.9);
    margin-bottom: 12px;
}
.windows-desktops-popup .rename-input {
    font-size: 14px;
    font-family: "Segoe UI Variable", "Segoe UI";
    font-weight: 600;
    color: rgba(255, 255, 255, 0.9);
    background-color: rgba(255, 255, 255, 0.1);
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 8px;
    outline: none;
    min-width: 280px;
}
.windows-desktops-popup .rename-input:focus {
    border: 1px solid #4cc2ff;
}
.windows-desktops-popup .button {
    border-radius: 4px;
    font-family: "Segoe UI Variable", "Segoe UI";
    font-size: 13px;
    min-height: 28px;
    min-width: 120px;
    margin: 4px 0;
    background-color: rgb(43, 43, 43);
}
.windows-desktops-popup .button.save {
    margin-right: 8px;
    color: #000000;
    background-color: #4cc2ff;
}
.windows-desktops-popup .button:hover {
    background-color: rgba(255, 255, 255, 0.15);
}
.windows-desktops-popup .button.save:hover {
    background-color: #48b2e9;
}
```

> [!NOTE]  
> You can use `button-x` to style each button separately. Where x is the index of the button. Index starts from 1.
