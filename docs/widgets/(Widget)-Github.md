# Github Widget Options

| Option              | Type    | Default                                                                                                                                                                         | Description                                                                                                     |
|---------------------|---------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| `label`             | string  | `'{icon}'`                                                                                                                                                                      | The format string for the label. You can use placeholders like `{icon}` to dynamically insert icon information. |
| `label_alt`         | string  | `'{data} Notifications'`                                                                                                                                                        | The alternative format string for the label. Useful for displaying additional notification details.             |
| `tooltip`           | boolean | `True`                                                                                                                                                                          | Whether to show the tooltip on hover.                                                                           |
| `update_interval`   | integer | `600`                                                                                                                                                                           | The interval in seconds to update the notifications. Must be between 60 and 3600.                               |
| `token`             | string  | `""`                                                                                                                                                                            | The GitHub personal access token.                                                                               |
| `max_notification`  | integer | `20`                                                                                                                                                                            | The maximum number of notifications to display in the menu.                                                     |
| `notification_dot`  | dict    | `{'enabled': True, 'corner': 'bottom_left', 'color': 'red', 'margin': [1, 1]}`                                                                                                  | A dictionary specifying the notification dot settings for the widget.                                           |
| `only_unread`       | boolean | `False`                                                                                                                                                                         | Whether to show only unread notifications.                                                                      |
| `max_field_size`    | integer | `100`                                                                                                                                                                           | The maximum number of characters in the title before truncation.                                                |
| `menu`              | dict    | `{'blur': True, 'round_corners': True, 'round_corners_type': 'normal', 'border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0}` | Menu settings for the widget.                                                                                   |
| `icons`             | dict    | `{'issue': '\uf41b', 'pull_request': '\uea64', 'release': '\uea84', 'discussion': '\uf442', 'default': '\uea84', 'github_logo': '\uea84'}`                                      | Icons for different types of notifications in the menu.                                                         |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`                                                                                                                       | Animation settings for the widget.                                                                              |
| `container_padding` | dict    | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`                                                                                                                                | Explicitly set padding inside widget container.                                                                 |
| `container_shadow`  | dict    | `None`                                                                                                                                                                          | Container shadow options.                                                                                       |
| `label_shadow`      | dict    | `None`                                                                                                                                                                          | Label shadow options.                                                                                           |

```yaml
github:
  type: "yasb.github.GithubWidget"
  options:
    label: "<span>\ueba1</span>"
    label_alt: "Notifications {data}" # {data} return number of unread notification
    token: ghp_xxxxxxxxxxx # GitHub Personal access tokens (classic) https://github.com/settings/tokens
    max_notification: 20 # Max number of notification displaying in menu max: 50
    notification_dot:
      enabled: True
      corner: "bottom_left" # Can be "top_left", "top_right", "bottom_left", "bottom_right"
      color: "red" # Can be hex color or string
      margin: [ 1, 1 ] # x and y margin for the dot
    only_unread: false # Show only unread or all notifications; 
    max_field_size: 54 # Max characters in title before truncation.
    update_interval: 300 # Check for new notification in seconds
    menu:
      blur: True # Enable blur effect for the menu
      round_corners: True # Enable round corners for the menu (this option is not supported on Windows 10)
      round_corners_type: "normal" # Set the type of round corners for the menu (normal, small) (this option is not supported on Windows 10)
      border_color: "System" # Set the border color for the menu (this option is not supported on Windows 10)
      alignment: "right"
      direction: "down"
    label_shadow:
      enabled: True
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```
## Description of Options

- **label:** The format string for the label. You can use placeholders like `{icon}` to dynamically insert icon information.
- **label_alt:** The alternative format string for the label. Useful for displaying additional notification details.
- **tooltip:** Whether to show the tooltip on hover.
- **update_interval:** The interval in seconds to update the notifications. Must be between 60 and 3600.
- **token:** The GitHub personal access token. GitHub Personal access tokens (classic) https://github.com/settings/tokens you can set `token: env`, this means you have to set YASB_GITHUB_TOKEN in environment variable.
- **max_notification:** The maximum number of notifications to display in the menu, max 50.
- **notification_dot:** A dictionary specifying the notification dot settings for the widget. This will show a dot on the icon (enclosed with the <span> tag).
  - **enabled:** Enable notification dot.
  - **corner:** Set the corner where the dot should appear.
  - **color:** Set the color of the notification dot. Can be hex or string color.
  - **margin:** Set the x, y margin for the notification dot.
- **only_unread:** Whether to show only unread notifications.
- **max_field_size:** The maximum number of characters in the title before truncation.
- **menu:** A dictionary specifying the menu settings for the widget. It contains the following keys:
  - **blur:** Enable blur effect for the menu.
  - **round_corners:** Enable round corners for the menu (this option is not supported on Windows 10).
  - **round_corners_type:** Set the type of round corners for the menu (normal, small) (this option is not supported on Windows 10).
  - **border_color:** Set the border color for the menu (this option is not supported on Windows 10).
  - **alignment:** Set the alignment of the menu (left, right).
  - **direction:** Set the direction of the menu (up, down).
  - **offset_top:** Set the offset from the top of the screen.
  - **offset_left:** Set the offset from the left of the screen.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.

## Widget Style
```css
.github-widget {}
.github-widget .widget-container {}
.github-widget .widget-container .label {}
 /* Popup menu*/
.github-menu {}
.github-menu .header {}
.github-menu .footer {}
.github-menu .contents {}
.github-menu .contents .item {}
.github-menu .contents .item.new {} /* New notification */
.github-menu .contents .item .title {}
.github-menu .contents .item .description {}
.github-menu .contents .item .icon {}
```

## Example Style for the Widget and Menu
```css
.github-menu    {
    background-color:  rgba(17, 17, 27, 0.2);
    max-height: 500px;
    min-height: 500px;
    min-width: 420px;
}
.github-menu .header {
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    font-size: 15px;
    font-weight: 400;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    padding: 8px;
    color: white;
    background-color: rgba(17, 17, 27, 0.75);
}
.github-menu .footer {
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    font-size: 12px;
    padding: 4px 8px 6px 8px;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: #9399b2;
    background-color: rgba(17, 17, 27, 0.75);
}
.github-menu .contents {
    background-color:  rgba(17, 17, 27, 0.2);
}
.github-menu .contents .item {
    min-height: 40px;
    padding: 6px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.075);
}
.github-menu .contents .item:hover {
    background-color: rgba(255, 255, 255, 0.05);
    border-bottom: 1px solid rgba(255, 255, 255, 0);
}
.github-menu .contents .item .title,
.github-menu .contents .item .description {
    color: #9399b2;
    font-family: Segoe UI;
}
.github-menu .contents .item .title {
    font-size: 14px;
    font-weight: 600; 
}
.github-menu .contents .item .description {
    font-size: 12px;
    font-weight: 500
}
.github-menu .contents .item.new .title,
.github-menu .contents .item.new .description {
    color: #ffffff
}
.github-menu .contents .item .icon {
    font-size: 16px;
    padding-right: 0;
    padding-left: 8px;
    padding-right: 4px;
    color: #9399b2;
}
.github-menu .contents .item.new .icon {
    color: #3fb950;
}
```

## Preview of the Widget
![GitHub YASB Widget](assets/576054922-dc651bd1-dedc-5786-c62a7ebdca70.png)
