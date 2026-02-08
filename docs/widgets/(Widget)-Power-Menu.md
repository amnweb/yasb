# Power Menu Widget

| Option              | Type    | Default     | Description                                                                 |
|---------------------|---------|-------------|-----------------------------------------------------------------------------|
| `label`             | string  | `"power"`   | The label for the power menu widget.                                        |
| `uptime`            | boolean | `true`      | Whether to display the system uptime.                                       |
| `show_user`         | boolean | `true`      | Whether to display the user profile info.                                   |
| `blur`              | boolean | `false`     | Whether to blur the button background.                                      |
| `blur_background`   | boolean | `true`      | Whether to blur the overlay background.                                     |
| `animation_duration`| integer | `200`       | The duration of the animation in milliseconds. Must be between 0 and 2000.  |
| `button_row`        | integer | `3`         | The number of buttons in a row. Must be between 1 and 6.                    |
| `buttons`           | dict    | `{}`        | A dictionary defining the buttons and their properties.                     |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |

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

## Description of Options
- **label:** The label for the power menu widget.
- **uptime:** Whether to display the system uptime.
- **show_user:** Whether to display the user profile info above the buttons.
- **blur:** Whether to blur the button background.
- **blur_background:** Whether to blur the overlay background.
- **animation_duration:** The duration of the animation in milliseconds. Must be between 0 and 2000.
- **button_row:** The number of buttons in a row. Must be between 1 and 6.
- **buttons:** A dictionary defining the buttons and their properties. Possible properties are: `lock`, `signout`, `sleep`, `shutdown`, `restart`, `hibernate`, `cancel`, `force_shutdown`, `force_restart`.
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

## Example Styles
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
.power-menu-popup .profile-info .profile-avatar {

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