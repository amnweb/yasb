# Power Menu Widget

| Option              | Type    | Default     | Description                                                                 |
|---------------------|---------|-------------|-----------------------------------------------------------------------------|
| `label`             | string  | `"power"`   | The label for the power menu widget.                                        |
| `uptime`            | boolean | `true`      | Whether to display the system uptime.                                       |
| `blur`              | boolean | `false`     | Whether to blur the button background.                                      |
| `blur_background`   | boolean | `true`      | Whether to blur the overlay background.                                     |
| `animation_duration`| integer | `200`       | The duration of the animation in milliseconds. Must be between 0 and 2000.  |
| `button_row`        | integer | `3`         | The number of buttons in a row. Must be between 1 and 5.                    |
| `buttons`           | dict    | `{}`        | A dictionary defining the buttons and their properties.                     |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |

## Example Configuration

```yaml
power_menu:
  type: "yasb.power_menu.PowerMenuWidget"
  options:
    label: "\uf011"
    uptime: true
    blur: false
    blur_background: true
    animation_duration: 200 # Milliseconds
    button_row: 5 # Number of buttons in a row, min 1 max 5
    buttons:
      lock: ["\uea75", "Lock"]
      sleep: ["\u23fe","Sleep"]
      signout: ["\udb80\udf43", "Sign out"]
      shutdown: ["\uf011", "Shut Down"]
      restart: ["\uead2", "Restart"]
      hibernate: ["\uf28e", "Hibernate"]
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
- **blur:** Whether to blur the button background.
- **blur_background:** Whether to blur the overlay background.
- **animation_duration:** The duration of the animation in milliseconds. Must be between 0 and 2000.
- **button_row:** The number of buttons in a row. Must be between 1 and 5.
- **buttons:** A dictionary defining the buttons and their properties. Possible properties are: `lock`, `signout`, `sleep`, `shutdown`, `restart`, `hibernate`, `cancel`, `force_shutdown`, `force_restart`.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.

## Available Styles
```css
.uptime {}
.power-menu-widget .label { /*icon on the bar*/ }
.power-menu-popup {}
.power-menu-popup .button {}
.power-menu-popup .button.hover {}
.power-menu-popup .button .label {}
.power-menu-popup .button .icon {}
/* A style for a specific button. */
.power-menu-popup .button.cancel {}
.power-menu-popup .button.shutdown {}
.power-menu-popup .button.restart {}
.power-menu-popup .button.signout {}
.power-menu-popup .button.hibernate {}
.power-menu-popup .button.sleep {}
.power-menu-popup .button.force_shutdown {}
.power-menu-popup .button.force_restart {}

```
## Example Styles
```css
.power-menu-widget .label {
    color: #f38ba8;
    font-size: 13px;
}
.power-menu-popup {
    background-color: transparent
}
.power-menu-popup .button {
    padding: 0;
    width: 180px;
    height: 230px;
    border-radius: 8px;
    background-color: #191919;
    border: 4px solid transparent;
    margin: 0px;
}
.power-menu-popup .button.hover {
    background-color: #1d1d1d;
    border: 4px solid #1d1d1d;
}
.power-menu-popup .button .label {
    margin-bottom: 8px;
    font-size: 16px;
    font-weight: 500;
    color: #9399b2
}
.power-menu-popup .button .icon {
    font-size: 64px;
    padding-top: 32px;
    color: #7f849c
}
.power-menu-popup .button.hover .label,
.power-menu-popup .button.hover .icon {
    color: rgba(255, 255, 255, 0.808)
}
.power-menu-popup .button.cancel .icon {
    padding: 0;
    margin: 0;
    max-height: 0;
}
.power-menu-popup .button.cancel .label {
    color:  #f38ba8;
    margin: 0;
}
.power-menu-popup .button.cancel {
    height: 40px;
    border-radius: 4px;
}
.power-menu-popup .button.cancel.hover .label {
    color: rgb(255, 255, 255)
}
.uptime {
    font-size: 14px;
    margin-bottom: 10px;
    color: #7f849c;
    font-weight: 600;
}
```

> [!NOTE]
> Power Menu widget supports toggle visibility using the `toggle-widget powermenu` command in the CLI. More information about the CLI commands can be found in the [CLI documentation](https://github.com/amnweb/yasb/wiki/CLI#toggle-widget-visibility).