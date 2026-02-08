# Power Menu Widget

| Option              | Type    | Default     | Description                                                                 |
|---------------------|---------|-------------|-----------------------------------------------------------------------------|
| `label`             | string  | `"power"`   | The label for the power menu widget.                                        |
| `uptime`            | boolean | `true`      | Whether to display the system uptime.                                       |
| `show_user`         | boolean | `true`      | Whether to display the user profile info.                                   |
| `blur`              | boolean | `false`     | Whether to blur the button background. (fullscreen mode only)               |
| `blur_background`   | boolean | `true`      | Whether to blur the overlay background. (fullscreen mode only)              |
| `animation_duration`| integer | `200`       | The duration of the animation in milliseconds. Must be between 0 and 2000. (fullscreen mode only) |
| `button_row`        | integer | `3`         | The number of buttons in a row. Must be between 1 and 6. (fullscreen mode only) |
| `menu_style`        | string  | `"fullscreen"` | The menu display style: `"fullscreen"` for full-screen overlay or `"popup"` for compact popup anchored to the bar button. |
| `popup`             | dict    | see below   | Popup appearance/position options. Only used when `menu_style` is `"popup"`. |
| `buttons`           | dict    | `{}`        | A dictionary defining the buttons and their properties.                     |
| `container_shadow`  | dict    | `None`      | Container shadow options.                                                   |
| `label_shadow`      | dict    | `None`      | Label shadow options.                                                       |

### Popup Options (when `menu_style: "popup"`)

| Option              | Type    | Default     | Description                                                                 |
|---------------------|---------|-------------|-----------------------------------------------------------------------------|
| `blur`              | boolean | `true`      | Whether to apply blur effect to the popup.                                  |
| `round_corners`     | boolean | `true`      | Whether to round the popup corners.                                         |
| `round_corners_type`| string  | `"normal"`  | Type of round corners (`"normal"` or `"small"`).                            |
| `border_color`      | string  | `"System"`  | Border color of the popup.                                                  |
| `alignment`         | string  | `"right"`   | Popup alignment relative to the widget: `"left"`, `"right"`, or `"center"`. |
| `direction`         | string  | `"up"`      | Popup direction: `"up"` or `"down"`.                                        |
| `offset_top`        | integer | `6`         | Vertical offset in pixels.                                                  |
| `offset_left`       | integer | `0`         | Horizontal offset in pixels.                                                |

## Available Buttons

Each button is defined as a key-value pair where the key is the action name and the value is a list of `[icon, label]`.

| Button Key        | Required | Description                                                         |
|-------------------|----------|---------------------------------------------------------------------|
| `shutdown`        | Yes      | Performs a hybrid shutdown (`shutdown /s /hybrid /t 0`).            |
| `restart`         | Yes      | Restarts the system (`shutdown /r /t 0`).                           |
| `cancel`          | Yes      | Closes the power menu popup.                                        |
| `lock`            | No       | Locks the workstation.                                              |
| `signout`         | No       | Signs out the current user (`shutdown /l`).                         |
| `sleep`           | No       | Puts the system to sleep.                                           |
| `hibernate`       | No       | Hibernates the system (`shutdown /h`).                              |
| `force_shutdown`  | No       | Forces shutdown, closing all apps without saving (`shutdown /s /f /t 0`). |
| `force_restart`   | No       | Forces restart, closing all apps without saving (`shutdown /r /f /t 0`).  |

## Example Configuration

```yaml
power_menu:
  type: "yasb.power_menu.PowerMenuWidget"
  options:
    label: "\uf011"
    uptime: true
    show_user: true
    blur: false
    blur_background: true
    animation_duration: 120 # Milliseconds
    button_row: 3 # Number of buttons in a row, min 1 max 6
    buttons:
      restart: ["\uead2", "Restart"]
      shutdown: ["\uf011", "Shut Down"]
      signout: ["\udb80\udf43", "Sign out"]
      hibernate: ["\uf28e", "Hibernate"]
      lock: ["\uea75", "Lock"]
      cancel: ["\udb81\udf3a", "Cancel"]
    label_shadow:
      enabled: false
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Example Configuration (Compact Popup)

```yaml
power_menu:
  type: "yasb.power_menu.PowerMenuWidget"
  options:
    label: "\uf011"
    uptime: true
    show_user: true
    menu_style: "popup"
    popup:
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "System"
      alignment: "right"
      direction: "down"
      offset_top: 6
      offset_left: 0
    buttons:
      lock: ["\uea75", "Lock"]
      signout: ["\udb80\udf43", "Sign out"]
      sleep: ["\u23fe", "Sleep"]
      hibernate: ["\uf28e", "Hibernate"]
      restart: ["\uead2", "Restart"]
      shutdown: ["\uf011", "Shut Down"]
      cancel: ["", "Cancel"]
```

## Description of Options
- **label:** The label for the power menu widget.
- **uptime:** Whether to display the system uptime. (fullscreen mode only)
- **show_user:** Whether to display the user profile info above the buttons.
- **blur:** Whether to blur the button background. (fullscreen mode only)
- **blur_background:** Whether to blur the overlay background. (fullscreen mode only)
- **animation_duration:** The duration of the animation in milliseconds. Must be between 0 and 2000. (fullscreen mode only)
- **button_row:** The number of buttons in a row. Must be between 1 and 6. (fullscreen mode only)
- **menu_style:** The menu display style. `"fullscreen"` shows a centered dialog with full-screen overlay (default behavior). `"popup"` shows a compact dropdown popup anchored to the bar button.
- **popup:** Popup configuration (blur, round_corners, alignment, direction, offsets). Only used when `menu_style` is `"popup"`.
- **buttons:** A dictionary defining the buttons and their properties. Possible properties are: `lock`, `signout`, `sleep`, `shutdown`, `restart`, `hibernate`, `cancel`, `force_shutdown`, `force_restart`. Note: `cancel` button is not shown in popup mode since the popup auto-closes on outside click.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.

## Callbacks (Hotkey Only)
This widget does not expose mouse callback configuration, but it does register a hotkey callback:

| Callback | Description |
|----------|-------------|
| `toggle_power_menu` | Toggle the power menu overlay and popup window. |

## Example keybinding:

```yaml
power_menu:
    type: "yasb.power_menu.PowerMenuWidget"
    options:
        keybindings:
            - keys: "win+p"
                action: "toggle_power_menu"
```

## Available Styles

### Fullscreen Mode
```css
.power-menu-overlay {}
.power-menu-overlay .uptime {}
.power-menu-widget .label { /*icon on the bar*/ }
.power-menu-popup {}
.power-menu-popup .profile-info {}
.power-menu-popup .profile-info .profile-avatar {}
.power-menu-popup .profile-info .profile-username {}
.power-menu-popup .profile-info .profile-account-type {}
.power-menu-popup .buttons {}
.power-menu-popup .button {}
.power-menu-popup .button.hover {}
.power-menu-popup .button .label {}
.power-menu-popup .button .icon {}
/* Styles for specific buttons */
.power-menu-popup .button.cancel {}
.power-menu-popup .button.shutdown {}
.power-menu-popup .button.restart {}
.power-menu-popup .button.signout {}
.power-menu-popup .button.hibernate {}
.power-menu-popup .button.sleep {}
.power-menu-popup .button.lock {}
.power-menu-popup .button.force-shutdown {}
.power-menu-popup .button.force-restart {}
```

### Compact Popup Mode
```css
.power-menu-compact {}
.power-menu-compact .profile-info {}
.power-menu-compact .profile-info .profile-avatar {}
.power-menu-compact .profile-info .profile-username {}
.power-menu-compact .profile-info .profile-account-type {}
.power-menu-compact .profile-info .profile-email {}
.power-menu-compact .profile-info .manage-accounts {}
.power-menu-compact .buttons {} /* Container for the buttons */
.power-menu-compact .button {}
.power-menu-compact .button.hover {}
.power-menu-compact .button .icon {}
.power-menu-compact .button .label {}
/* Styles for specific buttons */
.power-menu-compact .button.shutdown {}
.power-menu-compact .button.restart {}
.power-menu-compact .button.signout {}
.power-menu-compact .button.hibernate {}
.power-menu-compact .button.sleep {}
.power-menu-compact .button.lock {}
.power-menu-compact .button.force-shutdown {}
.power-menu-compact .button.force-restart {}
```

## Example Styles

### Fullscreen Mode
```css
.power-menu-widget .label {
    color: #f38ba8;
    font-size: 13px;
}
.power-menu-popup {
    background-color: rgba(255, 255, 255, 0.04);
    padding: 32px;
}
.power-menu-popup .button {
    padding: 0;
    min-width: 140px;
    max-width: 140px;
    min-height: 80px;
    border-radius: 12px;
    background-color: #ffffff11;
    border: 8px solid rgba(255, 255, 255, 0)
}
.power-menu-popup .button.hover {
    background-color: #0969b8;
    border: 8px solid #0969b8;
}
.power-menu-popup .button .label {
    font-size: 13px;
    font-weight: 600;
    font-family: 'Segoe UI';
    color: #a9a9ac;
}
.power-menu-popup .button .icon {
    font-size: 32px;
    color: rgba(255, 255, 255, 0.4)
}
.power-menu-popup .button.hover .label,
.power-menu-popup .button.hover .icon {
    color: #ffffff
}
.power-menu-popup .profile-info {
    padding: 0 0 16px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    background-color: transparent;
    margin-bottom: 16px;
}
.power-menu-popup .profile-info .profile-username {
    font-size: 24px;
    font-weight: 600;
    color: #cdd6f4;
    margin-top: 0;
    font-family: 'Segoe UI';
}
.power-menu-popup .profile-info .profile-account-type {
    font-size: 13px;
    color: #cdd6f493;
    margin-top: 4px;
    font-family: 'Segoe UI'
}
.power-menu-overlay {
    background-color: rgba(0, 0, 0, 0.15);
}
.power-menu-overlay .uptime {
    font-size: 16px;
    margin-bottom: 20px;
    color: #9ea2b4;
    font-weight: 600;
}
```

### Compact Popup Mode
```css
.power-menu-widget .label {
    color: #f38ba8;
    font-size: 13px;
}
.power-menu-compact {
    min-width: 260px;
    background-color: rgba(55, 58, 65, 0.6);
}
.power-menu-compact .profile-info {
    padding: 12px 0 24px 0;
}
 
.power-menu-compact .profile-info .profile-username {
    font-size: 16px;
    font-weight: 600;
    color: #e0e3ee;
    font-family: 'Segoe UI';
    margin-top: 4px;
}
.power-menu-compact .profile-info .profile-account-type {
    font-size: 12px;
    color: #ffffff;
    font-weight: 600;
    margin-top: 8px;
    font-family: 'Segoe UI';
    background-color: #0f68dd;
    padding: 2px 6px;
    border-radius: 6px;
}
.power-menu-compact .profile-info .profile-email {
    font-size: 13px;
    color: rgba(205, 214, 244, 0.6);
    margin-top: 2px;
    font-family: 'Segoe UI';
}
.power-menu-compact .manage-accounts {
    font-size: 12px;
    background-color: rgba(255, 255, 255, 0.08);
    font-family: 'Segoe UI';
    font-weight: 600;
    padding: 2px 8px;
    margin-top: 16px;
    border-radius: 6px; 
    border: 1px solid rgba(255, 255, 255, 0.1);
}
.power-menu-compact .manage-accounts:hover {
    background-color: rgba(255, 255, 255, 0.15);
}
.power-menu-compact .buttons {
    background-color: rgba(255, 255, 255, 0.05);
    margin: 0 12px 12px 12px;
    border-radius: 8px;
}
.power-menu-compact .button {
    padding: 8px 16px;
    background-color: transparent;
    border: none;
    border-radius: 0;
}
.power-menu-compact .button.hover {
    background-color: rgba(255, 255, 255, 0.1);
}
.power-menu-compact .button.lock.hover {
    border-top-right-radius: 8px;
    border-top-left-radius: 8px;
}
.power-menu-compact .button.shutdown.hover {
    border-bottom-right-radius: 8px;
    border-bottom-left-radius: 8px;
}
.power-menu-compact .button .icon {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.4);
    padding-right: 10px;
    min-width: 20px;
}
.power-menu-compact .button .label {
    font-size: 13px;
    font-weight: 500;
    font-family: "Segoe UI";
    color: #bebec0;
}
.power-menu-compact .icon.hover,
.power-menu-compact .label.hover {
    color: #ffffff;
}
```