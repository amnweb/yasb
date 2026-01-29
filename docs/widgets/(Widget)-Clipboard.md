# Clipboard Widget for YASB

A powerful, persistent clipboard manager for Windows. This widget maintains a history of recent clipboard items (text and images), and allows you to "Pin" items so they are never lost. If you want to you can even enable persistance for all clipboard items, not just the pinned ones.

## Features
- **History Persistence (Toggleable)**: Option to save history across restarts via a toggle button (Floppy icon). If disabled, history remains in memory only.
- **Image Support**: Full support for copying and previewing images directly in the history list.
- **Pinning**: Pin important items to keep them at the top. Pinned items are always persisted.
- **Management**: Clear entire history or delete individual items using the delete button (recycle bin icon).
- **Search**: Built-in search bar with a persistent clear 'X' button.
- **Dynamic Resizing**: The bar widget grows and shrinks based on the current clipboard content.

## Options

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `type` | `string` | `yasb.clipboard.ClipboardWidget` | The widget class identifier. |
| `label` | `string` | `<span>\udb80\udd4d</span> {clipboard}` | Primary label format. Supports `{clipboard}` token. |
| `label_alt` | `string` | `{clipboard}` | Alternative label format (swapped on right-click). |
| `max_length` | `integer` | `30` | Max characters to display in the bar before truncation. |
| `max_history` | `integer` | `50` | Maximum number of history items to store. |
| `data_path` | `string` | `~/.config/yasb/clipboard.json` | Location where history data is stored. |
| `class_name` | `string` | `""` | Additional CSS class for the widget container. |
| `menu` | `dict` | (See Schema) | Configuration for the popup menu (blur, corners, alignment). |
| `icons` | `dict` | (See Schema) | Custom icons for clipboard, pin, unpin, clear, etc. |

## Icons Configuration defaults

| Key | Default | Description |
| :--- | :--- | :--- |
| `clipboard` | `\udb80\udd4d` | Widget icon. |
| `pin` | `\udb81\udc03` | Pin button icon. |
| `unpin` | `\udb82\udd31` | Unpin button icon. |
| `clear` | `\uf1f8` | Clear/Delete icon. |
| `persistent` | `\udb80\udd93` | Persistence ON icon. |
| `temporary` | `\udb85\ude43` | Persistence OFF icon. |
| `search_clear` | `\uf00d` | Search clear 'X' icon. |

## Callbacks

| Function | Description |
| :--- | :--- |
| `toggle_menu` | Opens or closes the clipboard history popup. |
| `toggle_label` | Switches display between `label` and `label_alt`. |
| `clear_history` | Wipes all recent clips (Preserves Pinned/Starred items). |
| `do_nothing` | No action. |

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
.clipboard-widget .icon {
    color: var(--mauve);
    font-size: 16px;
}

.clipboard-widget .label {
    padding: 0 4px;
}

/* Clipboard Menu Popup */
.clipboard-menu {
    background-color: var(--bg-color1);
    border-radius: 8px;
    border: 1px solid var(--bg-color2);
    min-width: 320px;
    max-width: 400px;
    max-height: 450px;
}

.clipboard-menu .search-input {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
    color: var(--text1);
    font-family: 'Segoe UI';
}

.clipboard-menu .search-input:focus {
    border: 1px solid var(--blue);
    background-color: rgba(255, 255, 255, 0.08);
}

/* Search clear button inside wrapper */
.clipboard-menu .search-wrapper .search-clear-button {
    background-color: transparent;
    border: none;
    color: var(--text4);
    border-radius: 50%;
}
.clipboard-menu .search-wrapper .search-clear-button:hover {
    background-color: rgba(255, 255, 255, 0.1);
    color: var(--red);
}

.clipboard-menu .clear-button {
    background-color: rgba(243, 139, 168, 0.15);
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
    color: var(--red);
    font-size: 12px;
    font-family: 'Segoe UI';
    font-weight: 600;
}

.clipboard-menu .clear-button:hover {
    background-color: rgba(243, 139, 168, 0.25);
}

.clipboard-menu .section-header {
    font-size: 10px;
    font-weight: 700;
    color: var(--blue);
    padding: 8px 12px 4px 12px;
    font-family: 'Segoe UI';
    letter-spacing: 0.5px;
}

.clipboard-menu .clipboard-item {
    background-color: transparent;
    border-radius: 6px;
    margin: 2px 6px;
}

.clipboard-menu .clipboard-item:hover {
    background-color: rgba(255, 255, 255, 0.08);
}

.clipboard-menu .item-text {
    font-size: 12px;
    color: var(--text1);
    font-family: 'Segoe UI';
}

.clipboard-menu .pin-button,
.clipboard-menu .pin-button-active {
    background-color: transparent;
    border: none;
    font-size: 14px;
    color: var(--text4);
    padding: 4px 8px;
    border-radius: 4px;
}

.clipboard-menu .pin-button:hover {
    background-color: rgba(255, 255, 255, 0.1);
    color: var(--yellow);
}

.clipboard-menu .pin-button-active {
    color: var(--yellow);
}

.clipboard-menu .pin-button-active:hover {
    background-color: rgba(255, 255, 255, 0.1);
}

.clipboard-menu .empty-list {
    color: var(--text4);
    font-size: 12px;
    font-family: 'Segoe UI';
    padding: 20px;
}

.clipboard-menu .scroll-area {
    background-color: transparent;
    border: none;
}

/* Delete button for individual items */
.clipboard-menu .delete-button {
    background-color: transparent;
    border: none;
    font-size: 14px;
    color: var(--text4);
    padding: 4px 8px;
    border-radius: 4px;
}

.clipboard-menu .delete-button:hover {
    background-color: rgba(243, 139, 168, 0.15);
    color: var(--red);
}

/* Persistence toggle button */
.clipboard-menu .persistence-button,
.clipboard-menu .persistence-button-active {
    background-color: transparent;
    border-radius: 6px;
    border: none;
    font-size: 16px;
    margin-left: 4px;
}

.clipboard-menu .persistence-button {
    color: var(--text4);
}

.clipboard-menu .persistence-button:hover {
    background-color: rgba(255, 255, 255, 0.1);
    color: var(--mauve);
}

.clipboard-menu .persistence-button-active {
    color: var(--mauve);
}

.clipboard-menu .persistence-button-active:hover {
    background-color: rgba(255, 255, 255, 0.15);
}
```
