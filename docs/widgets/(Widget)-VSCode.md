# Visual Studio Code Widget

| Option           | Type     | Default                        | Description                                                                 |
|------------------|----------|--------------------------------|-----------------------------------------------------------------------------|
| `label`             | string  | `'<span>\udb82\ude1e</span>'` | The format string for the widget. |
| `label_alt`         | string  | `'<span>\udb82\ude1e</span> recents'` | The alternative format string for the widget. |
| `folder_icon`         | string  | `'\uf114'`                     | The icon for the folders to display in the menu. |
| `file_icon`         | string  | `'\uf016'`                     | The icon for the files to display in the menu. |
| `hide_folder_icon` | bool    | `False`                        | Whether to hide the folder icon in the menu. |
| `hide_file_icon` | bool    | `False`                        | Whether to hide the file icon in the menu. |
| `truncate_to_root` | bool    | `False`                        | Whether to truncate the path to the projects root directory. |
| `max_number_of_folders` | int | `30` | The maximum number of folders to display in the menu. |
| `max_number_of_files` | int | `30` | The maximum number of files to display in the menu. |
| `max_field_size` | int | `100` | The maximum number of characters in the title before truncation. |
| `menu`              | dict    | `{'blur': True, 'round_corners': True, 'round_corners_type': 'normal', 'border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0}` | Menu settings for the widget. |
| `container_padding` | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}` | Explicitly set padding inside widget container. |
| `callbacks` | dict | `{'on_left': 'next_binding_mode', 'on_middle': 'toggle_label', 'on_right': 'disable_binding_mode'}` | Callbacks for mouse events on the widget. |
| `animation` | dict | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}` | Animation settings for the widget. |
| `container_shadow` | dict   | `None` | Container shadow options. |
| `label_shadow` | dict | `None` | Label shadow options. |

## Example Configuration

```yaml
vscode:
    type: "yasb.vscode.VSCodeWidget"
    options:
      max_field_size: 50
      folder_icon: "\uf114"
      file_icon: "\uf016"
      truncate_to_root_dir: false
      hide_folder_icon: false
      hide_file_icon: false
      max_number_of_folders: 30
      max_number_of_files: 30 # set to 0 if you only want folders
      menu:
        blur: true
        round_corners: true
        round_corners_type: "small"
        alignment: 'center'
        offset_top: 0
```

## Description of Options
- **label:** The format string for the widget.
- **label_alt:** The alternative format string for the widget.
- **folder_icon:** The icon for the folders to display in the menu.
- **file_icon:** The icon for the files to display in the menu.
- **hide_folder_icon:** Whether to hide the folder icon in the menu.
- **truncate_to_root:** Whether to truncate the path to the projects root directory. Example `C:\Users\user\Documents\Projects\ProjectName` will be truncated to `ProjectName`.
- **max_number_of_folders:** The maximum number of folders to display in the menu.
- **max_number_of_files:** The maximum number of files to display in the menu (set to 0 if you only want folders).
- **max_field_size:** The maximum number of characters in the title before truncation.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
  - **callback functions**:
    - `toggle_menu`: Toggles the menu of the widget.
    - `toggle_label`: Toggles the label of the widget.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.

## Callbacks in the popup menu
- **left click**: Opens the selected folder or file in Visual Studio Code.
- **right click**: Deletes the selected folder or file from the opened history.

## Widget Style
```css
.vscode-widget {}
.vscode-widget .widget-container {}
.vscode-widget .widget-container .label {}
.vscode-widget .widget-container .icon {}
 /* Popup menu*/
.vscode-menu {}
.vscode-menu .header {}
.vscode-menu .contents {}
.vscode-menu .contents .item {}
.vscode-menu .contents .item .title {}
.vscode-menu .contents .item .folder-icon {}
.vscode-menu .contents .item .file-icon {}
.vscode-menu .no-recent {}
```

## Example Style for the Visual Studio Code Widget

```css
.vscode-widget .widget-container .icon {
    color: #89b4fa;
}

.vscode-menu {
    max-height: 500px;
    min-width: 300px;
}

.vscode-menu .header {
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    font-size: 15px;
    font-weight: 400;
    padding: 8px;
    color: #cdd6f4;
    background-color: rgba(17, 17, 27, 0.4);
}

.vscode-menu .contents {
    background-color: rgba(17, 17, 27, 0.4);
}

.vscode-menu .contents .item {
    min-height: 30px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.075);
}

.vscode-menu .contents .item .title {
    font-size: 12px;
    margin-right: 5px;
}

.vscode-menu .contents .item .folder-icon {
    font-size: 16px;
    margin-left: 8px;
    color: #f2cdcd;
}

.vscode-menu .contents .item .file-icon {
    font-size: 16px;
    margin-left: 8px;
    color: #cba6f7;
}

.vscode-menu .contents .item:hover {
    background-color: #45475a;
    border-bottom: 1px solid rgba(255, 255, 255, 0);
}
```

## Preview of the Widget
![VSCode YASB Widget](assets/ee9942e2-56694a11-2a9c-0b46-0b1f1f5401b0.png)