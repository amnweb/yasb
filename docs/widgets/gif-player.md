# GIF Player Widget Configuration

An ultra-low resource animated GIF player widget with interactive gallery picker, multi-monitor synchronization, and automatic aspect-ratio scaling.

Uses PyQt6's native `QMovie` rendering engine (&lt; 0.05% CPU, 0% GPU).

## Options

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `id` | string | `""` | Unique identifier to synchronize active GIF state across multiple monitors. |
| `gif_folder` | string | `""` | Path to folder containing `.gif` files to display in the popup picker. Defaults to `~/.config/yasb/icons/gifs`. |
| `gif_path` | string | `""` | Path to default/initial `.gif` file to play. |
| `folder_icon` | string | `""` | Optional path to an `.ico` or `.png` icon for the "Open Folder" grid tile. |
| `icon_size` | integer | `22` | Height in pixels for the GIF on the status bar (width scales proportionally). |
| `speed_percent` | integer | `100` | Playback speed percentage (100 = 1x, 200 = 2x, 50 = 0.5x). |
| `tooltip` | boolean | `true` | Whether to show a tooltip when hovering over the GIF. |
| `tooltip_text` | string | `"{name}"` | Format template for tooltip text. Supports `{name}`, `{width}`, and `{height}`. |
| `class_name` | string | `"gif-widget"` | CSS class name for styling the widget. |
| `popup` | dict | See below | Configuration for the GIF picker popup window. |
| `callbacks` | dict | See below | Callbacks for mouse click events. |

### Popup Options (`popup`)

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `blur` | boolean | `true` | Enables background blur effect behind the popup window. |
| `round_corners` | boolean | `true` | Enables rounded window corners. |
| `round_corners_type` | string | `"normal"` | Corner radius style (`"normal"` or `"small"`). |
| `border_color` | string | `"None"` | Window border color (`"None"`, `"System"`, or hex color). |
| `alignment` | string | `"center"` | Alignment relative to the widget icon (`"left"`, `"center"`, `"right"`). |
| `direction` | string | `"down"` | Direction to open popup (`"down"` or `"up"`). |
| `icons_per_row` | integer | `4` | Number of columns in the GIF picker grid. |
| `offset_top` | integer | `6` | Top offset in pixels between the bar and popup. |
| `offset_left` | integer | `0` | Horizontal offset in pixels. |

### Callbacks Options (`callbacks`)

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `on_left` | string | `"do_nothing"` | Action on left mouse click (`"do_nothing"`, `"toggle_popup"`, `"toggle_animation"`). |
| `on_middle` | string | `"do_nothing"` | Action on middle mouse click. |
| `on_right` | string | `"toggle_popup"` | Action on right mouse click (`"toggle_popup"`, `"toggle_animation"`, etc.). |

---

## Example Configuration

Add the widget definition to your `config.yaml`:

```yaml
widgets:
  gif_icon:
    type: "yasb.gif_player.GifPlayerWidget"
    options:
      id: "primary_gif"
      gif_folder: "C:/Users/Kat/.config/yasb/icons/gifs"
      gif_path: "C:/Users/Kat/.config/yasb/icons/gifs/RainbowPls.gif"
      folder_icon: "C:/Users/Kat/.config/yasb/icons/Explorer.ico"
      icon_size: 22
      speed_percent: 100
      tooltip: true
      tooltip_text: "{name}"
      popup:
        blur: true
        round_corners: true
        round_corners_type: normal
        border_color: None
        alignment: center
        direction: down
        icons_per_row: 4
        offset_top: 6
        offset_left: 0
      callbacks:
        on_left: do_nothing
        on_middle: do_nothing
        on_right: toggle_popup
```

Then add `gif_icon` to any bar's widget list (`left`, `center`, or `right`):

```yaml
bars:
  primary-bar:
    widgets:
      center:
        - clock
        - gif_icon
```

---

## Styling

Add custom styling rules to `styles.css`:

```css
/* Status bar widget container */
.gif-widget {
    font-family: var(--system-font);
    padding: 0px 6px;
    margin: 4px 0px;
    border-radius: 4px;
    transition: background-color 0.1s ease;
}

.gif-widget:hover {
    background-color: var(--yasb-white-alpha-08);
}

.gif-widget .gif-icon {
    padding: 0px;
    margin: 0px;
    border: none;
}

/* GIF Picker Grid Popup */
.gif-popup {
    font-family: var(--system-font);
    background-color: var(--yasb-popup-bg);
    border: 1px solid var(--yasb-bar-border);
    border-radius: 8px;
    padding: 6px;
}

.gif-popup .button {
    background-color: var(--yasb-white-alpha-03);
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 2px;
    min-width: 40px;
    min-height: 40px;
    max-width: 40px;
    max-height: 40px;
    margin: 0px;
}

.gif-popup .button:hover {
    background-color: var(--yasb-white-alpha-10);
    border: 1px solid var(--yasb-white-alpha-20);
}

.gif-popup .button.active {
    background-color: var(--yasb-white-alpha-15);
    border: 1px solid var(--yasb-accent);
}

.gif-popup .button.folder-tile {
    background-color: var(--yasb-white-alpha-04);
    border: 1px dashed var(--yasb-bar-border);
}

.gif-popup .button.folder-tile:hover {
    background-color: var(--yasb-white-alpha-10);
    border: 1px solid var(--yasb-accent);
}

.gif-popup .button .folder-icon {
    font-family: var(--icons-font);
    font-size: 18px;
    color: var(--yasb-icon-fg);
}
```
