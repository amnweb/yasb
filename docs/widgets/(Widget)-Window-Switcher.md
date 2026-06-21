# Window Switcher Widget

The Window Switcher is a fast, lightweight popup widget designed to let you easily cycle through and focus your currently open applications. It acts as a highly customizable, mouse-and-keyboard friendly alternative to the built-in Windows Alt-Tab menu.

## Options

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| label | string | `"\uf2d0"` | The icon or text displayed on the status bar. |
| label_alt | string | `""` | The alternate label. |
| icon_size | int | `48` | The size of the application icons. |
| max_visible_apps | int | `5` | The maximum number of apps to show before enabling scrolling. |
| show_title | boolean | `true` | Whether to display the focused app's title below the icons. |
| callbacks | object | See [Callbacks](#callbacks) | Defines widget interaction actions. |
| popup | object | See [Popup](#popup) | Defines popup styling and positioning. |
| keybindings | list | `[]` | Global hotkeys to trigger the popup. |

### Callbacks
| Option | Type | Default | Action |
| --- | --- | --- | --- |
| on_left | string | `"toggle_window_switcher"` | Toggles the window switcher. |
| on_middle | string | `"do_nothing"` | Optional action. |
| on_right | string | `"do_nothing"` | Optional action. |

### Popup
Contains the styling parameters for the window switcher interface.
| Name | Type | Default | Description |
| --- | --- | --- | --- |
| blur | boolean | `true` | Apply blur to the popup background. |
| round_corners | boolean | `true` | Apply rounded corners to the popup. |
| round_corners_type | string | `"normal"` | The type of rounded corners (`normal` or `small`). |
| border_color | string | `"System"` | Border color. |
| dark_mode | boolean | `true` | Apply dark mode to the popup. |

## Keyboard Navigation
When the popup is open, you can use the keyboard to navigate:
- **Left**: Move to the previous window.
- **Right**: Move to the next window.
- **Enter/Space**: Select and switch to the currently focused window.
- **Delete**: Close the selected window application.
- **Escape**: Close the window switcher without changing focus.

## Usage
Add the widget configuration to your `config.yaml`:

```yaml
widgets:
  window_switcher:
    type: "yasb.window_switcher.WindowSwitcherWidget"
    options:
      label: "<span>\uf2d2</span>"
      icon_size: 48
      max_visible_apps: 5
      show_title: true
      keybindings:
        - keys: "alt+w"
          action: "toggle_window_switcher"
          screen: "cursor"
```

### Keybindings Options

| Option   | Type   | Description                                                                                                            |
| -------- | ------ | ---------------------------------------------------------------------------------------------------------------------- |
| `keys`   | string | A keyboard shortcut sequence (e.g. `"alt+w"`).                                                                         |
| `action` | string | The widget action to trigger (`"toggle_window_switcher"`).                                                             |
| `screen` | string | Screen mode to pop up on (`"active"`, `"cursor"`, `"primary"`). Default is `"active"`.                                 |

> **Note:**
> **Layout & Quality Notes:**
> - **Icon Blurriness:** If you set `icon_size` to a very large value (e.g., `80` or `128`), some application icons might appear blurry or pixelated. This is because many applications do not embed high-resolution icons in their `.exe` files (often maxing out at `64x64`). The widget extracts the absolute highest quality icon natively available, but if the app doesn't provide a large one, the image must be stretched.
> - **Dynamic Screen Width:** The widget is fully screen-aware. To prevent the popup from bleeding off your monitor when using huge icons or a high `max_visible_apps` limit, the popup will dynamically cap its maximum width to **90% of your screen** and allow you to smoothly scroll through the remaining icons.
 
## CSS Example
Because this is a really simple widget, all of the styling classes used by the widget and its components are included in this example below. You can use this as a starting point for styling the window switcher overlay in your `styles.css`.

```css
.window-switcher-widget {}
.window-switcher-widget .label {}
.window-switcher-widget .icon {
    font-family: "JetBrainsMono NFP"
}

/* Styling for the popup container */
.window-switcher-popup {
    background-color: rgba(18, 19, 20, 0.4);
    padding: 10px;
}
/* Styling for each window item */
.window-switcher-popup .item {
    background-color: rgba(255, 255, 255, 0);
    border-radius: 8px;
    margin: 5px;
    padding: 10px;
    cursor: pointer;
    border: 1px solid transparent
}
/* Hover or keyboard-focus effect */
.window-switcher-popup .item:hover,
.window-switcher-popup .item.active {
    background-color: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(255, 255, 255, 0.07);
}
/* Window title text styling */
.window-switcher-popup .title {
    padding: 10px 10px 5px 10px;
    color: #ffffff;
    font-size: 12px;
    font-weight: 600;
    margin-top: 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.158);
}
```

## Preview of the Widget
![Window Switcher YASB Widget](assets/503816492-e4a9f2c1-b8d3-4567-9012-aefb3c84d9f6.png)