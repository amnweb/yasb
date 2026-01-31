# Clipboard Widget for YASB

A lightweight, modern clipboard manager for YASB that integrates directly with the native Windows Clipboard History (Win + V). This widget provides real-time access to your system's clip buffer without the need for heavy local storage or complex background monitoring.

**Note for Users:** This widget requires the following Python packages to interact with Windows APIs:
`pip install winrt-Windows.ApplicationModel.DataTransfer winrt-Windows.Foundation`

## Features
- **Native Windows Sync**: Syncs in real-time with your official Windows Clipboard History.
- **Search**: Built-in real-time search bar to filter through your text-based history.
- **Image Support**: Full support for previewing and re-copying images directly from the history list.
- **Long text preview**: Hover over a copied long piece of text to display complete text preview.
- **Zero-SDK Footprint**: Uses modular WinRT bindings to keep the installation under 10MB.

## Options

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `type` | `string` | `yasb.clipboard.ClipboardWidget` | The widget class identifier. |
| `label` | `string` | `<span>\udb80\udd4d</span> {clipboard}` | Primary label format. Supports `{clipboard}` token. |
| `label_alt` | `string` | `{clipboard}` | Alternative label format (swapped on right-click). |
| `max_length` | `integer` | `30` | Max characters to display in the bar before truncation. |
| `max_history` | `integer` | `50` | Maximum number of history items to fetch from Windows. |
| `class_name` | `string` | `""` | Additional CSS class for the widget container. |
| `menu` | `dict` | (See Schema) | Configuration for the popup menu (blur, corners, alignment). |
| `icons` | `dict` | (See Schema) | Custom icons for clipboard, clear, and search. |

## Icons Configuration Defaults

| Key | Default | Description |
| :--- | :--- | :--- |
| `clipboard` | `\udb80\udd4d` | Main widget icon used on the bar and in the "Copied!" flash. |
| `clear` | `\uf1f8` | Global clear icon (Clears the system's unpinned history). |
| `search_clear` | `\uf00d` | Icon used for general UI elements. |

## Callbacks

| Function | Description |
| :--- | :--- |
| `toggle_menu` | Opens/closes the clipboard history popup (Scheduled asynchronously). |
| `toggle_label` | Switches display between `label` and `label_alt` on the bar. |
| `do_nothing` | No action. |

---


## Configuration Example

```yaml
  clipboard:
    type: "yasb.clipboard.ClipboardWidget"
    options:
      label: "<span>\udb80\udd4d</span> {clipboard}"
      label_alt: "<span>CLIPBOARD:</span> {clipboard}"
      max_length: 25
      menu:
        blur: false
        round_corners: false
        alignment: "right"
        direction: "down"
      callbacks:
        on_left: "toggle_menu"
        on_middle: "do_nothing"
        on_right: "toggle_label"
```

## Styling

### Example CSS

```css
.clipboard-widget {
    font-family: "JetBrainsMono Nerd Font", "Segoe UI Variable";
}
/* Widget on the bar */
.clipboard-widget .label {
    padding: 0 6px;
    color: var(--mauve);
}

/* Main Popup Container */
.clipboard-menu {
    background-color: var(--bg-color1);
    border: 1px solid var(--bg-color2);
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
    color: var(--text1);
    font-size: 13px;
}

.clipboard-menu .search-input:focus {
    border: 1px solid var(--blue);
}

/* Global Clear Button */
.clipboard-menu .clear-button {
    background-color: rgba(243, 139, 168, 0.1);
    color: var(--red);
    border-radius: 6px;
    padding: 5px;
    margin-bottom: 8px;
    font-weight: bold;
    font-size: 11px;
}

.clipboard-menu .clear-button:hover {
    background-color: rgba(243, 139, 168, 0.2);
}

/* Scroll Area Styling */
.clipboard-menu .scroll-area {
    background: transparent;
    border: none;
}

/* Individual Clipboard Items (Buttons) */
.clipboard-menu .clipboard-item {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 8px;
    margin-bottom: 4px;
    text-align: left;
    color: var(--text1);
    font-size: 12px;
}

.clipboard-menu .clipboard-item:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid var(--bg-color2);
}

/* Image Item Specifics (if needed) */
.clipboard-menu .clipboard-item [icon] {
    margin-right: 8px;
}

/* Scrollbar Styling (Optional but looks better) */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 4px;
}

QScrollBar::handle:vertical {
    background: var(--bg-color2);
    border-radius: 2px;
}

/* Styling for the temporary 'Copied!' flash */
.clipboard-widget .label {
    transition: all 0.2s ease-in-out;
}
```
