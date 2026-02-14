# Clipboard Widget for YASB

A lightweight clipboard manager for YASB that integrates directly with the native Windows Clipboard History (Win + V). This widget provides real-time access to your system's clip buffer without the need for heavy local storage or complex background monitoring.

**Note for Users:** This widget requires the `winrt` Python package. If not installed, the widget will display an error message.
`pip install winrt-Windows.ApplicationModel.DataTransfer winrt-Windows.Foundation`

## Features
- **Native Windows Sync**: Syncs in real-time with your official Windows Clipboard History.
- **Search**: Built-in real-time search bar to filter through your text-based history.
- **History**: View your Clipboard history and delete a single history item or your entire history.
- **Image Support**: Full support for previewing and re-copying images directly from the history list.
- **Long text preview**: Hover over a copied long piece of text to display complete text preview.
- **Feedback**: Visual feedback when content is copied.

## Options

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `type` | `string` | `yasb.clipboard.ClipboardWidget` | The widget class identifier. |
| `label` | `string` | `<span>\udb80\udd4d</span>` | Primary label format. |
| `label_alt` | `string` | `CLIPBOARD` | Alternative label format (swapped on right-click). |
| `max_length` | `integer` | `30` | Max characters to display in the bar before truncation. |
| `max_history` | `integer` | `50` | Maximum number of history items to fetch from Windows. |
| `class_name` | `string` | `""` | Additional CSS class for the widget container. |
| `copied_feedback` | `string` | `\uf00c` | Feedback message when copying. |
| `menu` | `dict` | (See Schema) | Configuration for the popup menu (blur, corners, alignment). |
| `icons` | `dict` | (See Schema) | Custom icons for clipboard actions. |

## Icons Configuration Defaults

| Key | Default | Description |
| :--- | :--- | :--- |
| `clear_icon` | `\uf1f8` | Clear all history icon. |
| `delete_icon` | `\uf1f8` | Delete item icon. |

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
      max_length: 25
      menu:
        blur: false
        round_corners: false
        alignment: "right"
        direction: "down"
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
    color: #89b4fa;
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
    background-color: rgba(243, 139, 168, 0.1);
    color: #f38ba8;
    border-radius: 6px;
    padding: 5px;
    margin-bottom: 8px;
    font-weight: bold;
    font-size: 11px;
}

.clipboard-menu .clear-button:hover {
    background-color: rgba(243, 139, 168, 0.2);
}

/* Clipboard Items */
.clipboard-menu .clipboard-item {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 8px;
    margin-bottom: 4px;
    text-align: left;
    color: #cdd6f4;
    font-size: 12px;
}

.clipboard-menu .clipboard-item:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid #11111b;
}

/* Delete Button */
.clipboard-menu .delete-button {
    background: rgba(243, 139, 168, 0.1);
}
.clipboard-menu .delete-button:hover {
    background-color: rgba(243, 139, 168, 0.2);
}
```
