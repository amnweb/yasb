# Clipboard Widget for YASB

A lightweight clipboard manager for YASB that integrates directly with the native Windows Clipboard History (Win + V). This widget provides real-time access to your system's clip buffer without the need for heavy local storage or complex background monitoring.

## Features
- **Native Windows Sync**: Syncs in real-time with your official Windows Clipboard History.
- **Search**: Built-in real-time search bar to filter through your text-based history.
- **History**: View your Clipboard history and delete a single history item or your entire history.
- **Image Support**: Full support for re-copying images directly from the history list.
- **Long text preview**: Hover over a copied long piece of text to display text preview (configurable).
- **Image list info**: Show image dimensions, size, and date in the history list (configurable).
- **Feedback**: Visual feedback when content is copied.
- **Customizable tooltips**: Enable/disable tooltips and adjust delay.

## Options

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `type` | `string` | `yasb.clipboard.ClipboardWidget` | The widget class identifier. |
| `label` | `string` | `<span>\udb80\udd4d</span>` | Primary label format. |
| `label_alt` | `string` | `CLIPBOARD` | Alternative label format (swapped on right-click). |
| `max_history` | `integer` | `50` | Maximum number of history items to fetch from Windows. |
| `class_name` | `string` | `""` | Additional CSS class for the widget container. |
| `copied_feedback` | `string` | `\uf00c` | Feedback message when copying. |
| `menu` | `dict` | (See Schema) | Configuration for the popup menu. |
| `icons` | `dict` | (See Schema) | Custom icons for clipboard actions. |
| `animation` | `dict` | (See Schema) | Animation configuration for label toggling. |
| `label_shadow` | `dict` | (See Schema) | Shadow configuration for the label. |
| `container_shadow` | `dict` | (See Schema) | Shadow configuration for the widget container. |

## Icons Configuration Defaults

| Key | Default | Description |
| :--- | :--- | :--- |
| `clear_icon` | `\uf1f8` | Clear all history icon. |
| `delete_icon` | `\uf1f8` | Delete item icon. |

## Menu Configuration Defaults

| Key | Default | Description |
| :--- | :--- | :--- |
| `blur` | `true` | Enable blur effect on popup. |
| `round_corners` | `true` | Enable rounded corners on popup. |
| `round_corners_type` | `"normal"` | Corner radius style (`"normal"` or `"small"`). |
| `border_color` | `"System"` | Border color for the popup. |
| `alignment` | `"right"` | Horizontal alignment relative to widget (`"left"`, `"right"`, `"center"`). |
| `direction` | `"down"` | Vertical direction for popup (`"up"` or `"down"`). |
| `offset_top` | `6` | Top offset in pixels. |
| `offset_left` | `0` | Left offset in pixels. |
| `max_item_length` | `50` | Max characters to display for text items (10-200). |
| `tooltip_enabled` | `true` | Enable custom tooltips for history items. |
| `tooltip_delay` | `400` | Delay in milliseconds before showing tooltip (0-2000). |
| `show_image_thumbnail` | `true` | Show image thumbnail in history list. If false, shows `image_replacement_text` instead. |
| `image_replacement_text` | `"[Image]"` | Text to display for image items in history list when `show_image_thumbnail` is false. |
| `show_image_list_info` | `true` | Show image dimensions, date, and size below the image in the history list. |

## Callbacks

| Function | Description |
| :--- | :--- |
| `toggle_menu` | Opens/closes the clipboard history popup (Scheduled asynchronously). |
| `toggle_label` | Switches display between `label` and `label_alt` on the bar. |

---


## Configuration Example

```yaml

  clipboard:
    type: "yasb.clipboard.ClipboardWidget"
    options:
      label: "<span>\uf0ea</span>"
      label_alt: "<span>CLIPBOARD</span>"
      icons:
        delete_icon: "\uf1f8"
        clear_icon: "\uf1f8"
      copied_feedback: "\uf00c"
      menu:
        blur: true
        round_corners: true
        alignment: "right"
        direction: "down"
        tooltip_enabled: true
        tooltip_delay: 400
        show_image_thumbnail: true
        image_replacement_text: "[IMAGE]"
        show_image_list_info: true
      callbacks:
        on_left: "toggle_menu"
        on_right: "toggle_label"
```

## Styling

### Example CSS

```css
/* Widget on the bar */
.clipboard-widget {
  font-family: "JetBrainsMono Nerd Font", "Segoe UI Variable";
}

.clipboard-widget .label {
}

/* Main Popup Container */
.clipboard-menu {
  background-color: #1e1e2e;
  border: 1px solid #11111b;
  border-radius: 10px;
  padding: 8px;
}

/* Search Bar */
.clipboard-menu .search-input {
  background-color: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 6px 10px;
  margin-bottom: 6px;
  color: #cdd6f4;
  font-size: 13px;
}

.clipboard-menu .search-input:focus {
  border: 1px solid #89b4fa;
}

/* Global Clear Button */
.clipboard-menu .clear-button {
  background-color: #cb3b42;
  border-radius: 6px;
  padding: 5px;
  margin-bottom: 8px;
  font-weight: bold;
  font-size: 11px;
}

.clipboard-menu .clear-button:hover {
  background-color: #cc6a6f;
}

/* Clipboard Items */
.clipboard-menu .clipboard-item {
  background-color: rgba(255, 255, 255, 0.03);
  border-radius: 10%;
  margin-bottom: 4px;
  font-size: 12px;
}

.clipboard-menu .clipboard-item:hover {
  background-color: rgba(255, 255, 255, 0.08);
  border: 1px solid #11111b;
}

/* Image Item */
.clipboard-menu .image-item {
  /* Styles for image items in the list */
}

/* Image List Info (shown below image in list) */
.clipboard-menu .image-list-info {
  font-size: 10px;
  color: #ffffff;
  padding-left: 4px;
}

/* Scroll Area */
.clipboard-menu .scroll-area {
  background: transparent;
}

/* Delete Button */
.clipboard-menu .delete-button {
  background: #cb3b42;
}
.clipboard-menu .delete-button:hover {
  background-color: #cc6a6f;
}
```
