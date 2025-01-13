# Power Menu Widget

| Option              | Type    | Default     | Description                                                                 |
|---------------------|---------|-------------|-----------------------------------------------------------------------------|
| `label`             | string  | `"power"`   | The label for the power menu widget.                                        |
| `uptime`            | boolean | `True`      | Whether to display the system uptime.                                       |
| `blur`              | boolean | `False`     | Whether to blur the button background.                                      |
| `blur_background`   | boolean | `True`      | Whether to blur the overlay background.                                     |
| `animation_duration`| integer | `200`       | The duration of the animation in milliseconds. Must be between 0 and 2000.  |
| `button_row`        | integer | `3`         | The number of buttons in a row. Must be between 1 and 5.                    |
| `buttons`           | dict    | `{}`        | A dictionary defining the buttons and their properties.                     |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container. |
## Example Configuration

```yaml
power_menu:
  type: "yasb.power_menu.PowerMenuWidget"
  options:
    label: "\uf011"
    uptime: True
    blur: False
    blur_background: True
    animation_duration: 300 # Milliseconds
    button_row: 3 # Number of buttons in a row, min 1 max 5
    buttons:
      lock: ["\uea75", "Lock"]
      sleep: ["\u23fe","Sleep"]
      signout: ["\udb80\udf43", "Sign out"]
      shutdown: ["\uf011", "Shut Down"]
      restart: ["\uead2", "Restart"]
      hibernate: ["\uf28e", "Hibernate"]
      cancel: ["\udb81\udf3a", "Cancel"]
```

## Description of Options
- **label:** The label for the power menu widget.
- **uptime:** Whether to display the system uptime.
- **blur:** Whether to blur the button background.
- **blur_background:** Whether to blur the overlay background.
- **animation_duration:** The duration of the animation in milliseconds. Must be between 0 and 2000.
- **button_row:** The number of buttons in a row. Must be between 1 and 5.
- **buttons:** A dictionary defining the buttons and their properties. Possible properties are: `lock`, `signout`, `sleep`, `shutdown`, `restart`, `hibernate`, `cancel`, `force_shutdown`, `force_restart`.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.

## Example Style
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