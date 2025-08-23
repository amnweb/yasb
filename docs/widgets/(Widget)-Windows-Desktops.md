# Windows Desktops Widget
| Option                     | Type    | Default                  | Description                                                                 |
|----------------------------|---------|--------------------------|-----------------------------------------------------------------------------|
| `label_workspace_btn`    | string  | `'{index}'`              | The format string for workspace buttons.                                    |
| `label_workspace_active_btn` | string | `'{index}'`              | The format string for the active workspace button.                          |
| `switch_workspace_animation` | string | `'true'`                 | The OS animation to use when switching workspaces.                             |
| `animation`                | bool   | `false`                   | Buttons animation.   |
| `container_shadow`      | dict    | `None`                  | Container shadow options.                                |
| `btn_shadow`            | dict    | `None`                  | Workspace button shadow options.                         |

## Example Configuration

```yaml
windows_workspaces:
  type: "yasb.windows_desktops.WorkspaceWidget"
  options:
    label_workspace_btn: "\udb81\udc3d"
    label_workspace_active_btn: "\udb81\udc3e"
    btn_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Description of Options
- **label_workspace_btn:** The format string for workspace buttons, can be icon, {index} or {name}.
- **label_workspace_active_btn:** The format string for the active workspace button, can be icon, {index} or {name}.
- **switch_workspace_animation:** The OS animation to use when switching workspaces. (currently unsupported)
- **animation:** Buttons animation.
- **container_shadow:** Container shadow options.
- **btn_shadow:** Workspace button shadow options.

## Style
```css
.windows-desktops {} /*Style for widget.*/
.windows-desktops .widget-container {} /*Style for widget container.*/
.windows-desktops .ws-btn {} /*Style for buttons.*/
.windows-desktops .ws-btn.active {} /*Style for the active workspace button.*/
.windows-workspaces .ws-btn.button-1 {} /*Style for first button.*/
.windows-workspaces .ws-btn.button-2 {} /*Style for second  button.*/
.windows-workspaces .ws-btn.active.button-1 {} /*Style for the active first workspace button.*/
.windows-workspaces .ws-btn.active.button-2 {} /*Style for the active second workspace button.*/

.windows-desktops .context-menu {} /*Style for context menu.*/
.windows-desktops .context-menu .menu-item {} /*Style for context menu items.*/
.windows-desktops .context-menu .menu-item:hover {} /*Style for selected context menu items.*/
.windows-desktops .context-menu .separator {} /*Style for context menu separator.*/

.windows-desktops .rename-dialog {} /*Style for rename dialog.*/
.windows-desktops .rename-dialog QPushButton{} /*Style for rename dialog buttons.*/
.windows-desktops .rename-dialog QPushButton:hover{} /*Style for rename dialog buttons hover.*/
.windows-desktops .rename-dialog QLabel {} /*Style for rename dialog labels.*/
.windows-desktops .rename-dialog QLineEdit {} /*Style for rename dialog line edit.*/
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

.windows-desktops .rename-dialog {
    background-color: rgba(17, 17, 27, 0.75);   
}
.windows-desktops .rename-dialog QPushButton{
    background-color:rgba(255,255,255,0.1);
    color: #ffffff;
    border: none;
    padding: 4px 12px;
    border-radius: 4px;
}
.windows-desktops .rename-dialog QPushButton:hover{
    background-color: #585858;
    color: #ffffff;
    border: none;
    padding: 4px 12px;
    border-radius: 4px;
}
 
.windows-desktops .rename-dialog QLabel {
    color: #ffffff;
}
.windows-desktops .rename-dialog QLineEdit {
    background-color: transparent;
    border: 1px solid #89b4fa;
    padding: 4px;
    color: #ffffff;
}
```

> [!NOTE]  
> You can use `button-x` to style each button separately. Where x is the index of the button. Index starts from 1.