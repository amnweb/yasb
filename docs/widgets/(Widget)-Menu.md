# Menu Widget Options

| Option     | Type   | Default | Description                                                                 |
|------------|--------|---------|-----------------------------------------------------------------------------|
| `label`   | string | `""`    | The text label for the menu button. Can be empty if only using an icon.                                      |
| `icon`   | string | `""`    | The icon for the menu button. Can be a Unicode character, emoji, or path to an image file. Can be empty if only using a label.                                      |
| `class_name` | string | `""` | The CSS class name for styling the widget. Optional.                        |
|  `image_icon_size` | int | `14` | The size of the icon in pixels if the icon is an image (for the button in the bar).                      |
|  `popup_image_icon_size` | int | `16` | The size of the icon in pixels for menu items in the popup.                      |
| `menu_items`  | list   | `[]`| Menu items list with icon, launch command, and optional name. |
| `tooltip`  | bool   | `True`| Enable or disable tooltips. |
| `blur`  | bool   | `False`| Enable or disable blur effect on the popup window. |
| `alignment`  | string   | `"left"`| Popup alignment relative to the button: `"left"`, `"right"`, or `"center"`. |
| `direction`  | string   | `"down"`| Popup direction: `"down"` (below button) or `"up"` (above button). |
| `popup_offset`  | dict   | `{"top": 0, "left": 0}`| Offset for the popup position in pixels. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for menu items.                                          |
| `container_padding`  | dict   | `{"top": 0, "left": 0, "bottom": 0, "right": 0}`| Padding for the widget container in the bar. |
| `popup_padding`  | dict   | `{"top": 8, "left": 8, "bottom": 8, "right": 8}`| Padding for the popup window content. |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |

## Example Configuration

```yaml
menu:
  type: "yasb.menu.MenuWidget"
  options:
    label: "Menu"
    icon: "\uf0c9"  # hamburger menu icon
    menu_items:
      - {icon: "\uf0a2", launch: "notification_center", name: "Notification Center"}
      - {icon: "\ueb51", launch: "quick_settings", name: "Quick Settings"}
      - {icon: "\uf422", launch: "search", name: "Search"}
      - {icon: "\uf489", launch: "wt", name: "Windows Terminal"}
      - {icon: "C:\\Users\\marko\\icons\\vscode.png", launch: "C:\\Users\\Username\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe", name: "VS Code"}
      - {icon: "\udb81\udc4d", launch: "\"C:\\Program Files\\Mozilla Firefox\\firefox.exe\" -new-tab www.reddit.com", name: "Reddit"}
    blur: true
    alignment: "left"
    direction: "down"
    popup_offset:
      top: 4
      left: 0
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [1, 1]
```

## Example with Icon Only

```yaml
menu_icon_only:
  type: "yasb.menu.MenuWidget"
  options:
    icon: "\uf013"  # settings icon
    menu_items:
      - {icon: "\uf013", launch: "ms-settings:", name: "Settings"}
      - {icon: "\uf0c7", launch: "control", name: "Control Panel"}
      - {icon: "\uf108", launch: "taskmgr", name: "Task Manager"}
    popup_image_icon_size: 20
    blur: true
```

## Example with Label Only

```yaml
menu_label_only:
  type: "yasb.menu.MenuWidget"
  options:
    label: "Apps"
    menu_items:
      - {icon: "\uf489", launch: "wt", name: "Terminal"}
      - {icon: "\uf07c", launch: "explorer", name: "File Explorer"}
      - {icon: "\uf108", launch: "notepad", name: "Notepad"}
```

## Description of Options

- **label:** The text label displayed on the menu button in the bar. Can be empty if you only want to show an icon.
- **icon:** The icon displayed on the menu button in the bar. Can be a Unicode character (e.g., `\uf0c9`), emoji, or an image file path (e.g., `C:\\path\\to\\icon.png`). Can be empty if you only want to show a label.
- **class_name:** The CSS class name for styling the widget. Optional.
- **image_icon_size:** The size in pixels of the icon on the menu button (if using an image file).
- **popup_image_icon_size:** The size in pixels of the icons for menu items in the popup window.
- **menu_items:** A list of menu items to display in the popup. Each item is a dictionary with the following keys:
  - **icon:** The icon for the menu item. This can be a Unicode character (e.g., `\uf0a2`), an image path (e.g., `C:\\path\\to\\icon.png`), or emoji.
  - **launch:** The command to execute when the menu item is clicked. This can include arguments and should be properly quoted if necessary.
  - **name:** (Optional) The name of the menu item to display next to the icon and as a tooltip.
- **tooltip:** Enable or disable tooltips when hovering over the menu button and items.
- **blur:** Enable blur effect on the popup window background (Windows 10: Acrylic, Windows 11: Mica).
- **alignment:** How the popup is aligned relative to the menu button. Options: `"left"`, `"right"`, or `"center"`.
- **direction:** Whether the popup appears below (`"down"`) or above (`"up"`) the menu button.
- **popup_offset:** Fine-tune the popup position with pixel offsets:
  - **top:** Vertical offset in pixels.
  - **left:** Horizontal offset in pixels.
- **animation:** Animation settings when clicking menu items. Contains:
  - **enabled:** Enable or disable animation.
  - **type:** Animation type (e.g., `fadeInOut`).
  - **duration:** Animation duration in milliseconds.
- **container_padding:** Padding around the widget container in the bar.
- **popup_padding:** Padding around the content inside the popup window.
- **container_shadow:** Shadow options for the widget container in the bar.
- **label_shadow:** Shadow options for the menu button label/icon.

## CSS Styling

The menu widget can be styled using CSS classes:

```css
/* Menu button in the bar */
.menu-widget .widget-container {
    background-color: #1e1e1e;
    border-radius: 4px;
}

.menu-widget .icon {
    color: #ffffff;
    font-size: 14px;
}

.menu-widget .label {
    color: #ffffff;
    padding: 0 8px;
}

/* Popup window */
.menu-popup {
    background-color: #2d2d2d;
    border-radius: 8px;
    border: 1px solid #404040;
}

/* Individual menu items */
.menu-item {
    background-color: transparent;
    border-radius: 4px;
    margin: 2px 0;
}

.menu-item:hover {
    background-color: #3d3d3d;
}

.menu-item .icon {
    color: #ffffff;
    font-size: 16px;
    min-width: 24px;
}

.menu-item .label {
    color: #ffffff;
    font-size: 13px;
}
```

> [!NOTE]  
> - You must specify at least one of `label` or `icon` for the menu button. You can use both together if desired.
> - Menu items automatically close the popup after being clicked.
> - The popup automatically closes when clicking outside of it.
> - Commands in `launch` support the same function map as the applications widget (e.g., `notification_center`, `quick_settings`, etc.).
