# Github Widget Options

| Option           | Type     | Default                        | Description                                                                 |
|------------------|----------|--------------------------------|-----------------------------------------------------------------------------|
| `label`          | string   | `'{icon}'`                     | The format string for the label. You can use placeholders like `{icon}` to dynamically insert icon information. |
| `label_alt`      | string   | `'{data} Notifications'`       | The alternative format string for the label. Useful for displaying additional notification details. |
| `tooltip`  | boolean  | `True`        | Whether to show the tooltip on hover. |
| `update_interval`| integer  | `600`                          | The interval in seconds to update the notifications. Must be between 60 and 3600. |
| `token`          | string   | `""`                           | The GitHub personal access token. |
| `max_notification`| integer | `20`                           | The maximum number of notifications to display in the menu. |
| `only_unread`    | boolean  | `False`                        | Whether to show only unread notifications. |
| `max_field_size` | integer  | `100`                          | The maximum number of characters in the title before truncation. |
| `menu_width`     | integer  | `400`                          | The width of the menu in pixels. |
| `menu_height`    | integer  | `400`                          | The height of the menu in pixels. |
| `menu_offset`    | integer  | `240`                          | The offset of the menu in pixels. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container. |

## Example Configuration

```yaml
github:
  type: "yasb.github.GithubWidget"
  options:
    label: "<span>\ueba1</span>"
    label_alt: "Notifications {data}" # {data} return number of unread notification
    token: ghp_xxxxxxxxxxx # GitHub Personal access tokens (classic) https://github.com/settings/tokens
    max_notification: 20 # Max number of notification displaying in menu max: 50
    only_unread: false # Show only unread or all notifications; 
    max_field_size: 54 # Max characters in title before truncation.
    menu_width: 400 
    menu_height: 400 
    menu_offset: 240 
    update_interval: 300 # Check for new notification in seconds
```
## Description of Options

- **label:** The format string for the label. You can use placeholders like `{icon}` to dynamically insert icon information.
- **label_alt:** The alternative format string for the label. Useful for displaying additional notification details.
- **tooltip:** Whether to show the tooltip on hover.
- **update_interval:** The interval in seconds to update the notifications. Must be between 60 and 3600.
- **token:** The GitHub personal access token. GitHub Personal access tokens (classic) https://github.com/settings/tokens you can set `token: env`, this means you have to set YASB_GITHUB_TOKEN in environment variable.
- **max_notification:** The maximum number of notifications to display in the menu, max 50.
- **only_unread:** Whether to show only unread notifications.
- **max_field_size:** The maximum number of characters in the title before truncation.
- **menu_width:** The width of the menu in pixels.
- **menu_height:** The height of the menu in pixels.
- **menu_offset:** The offset of the menu in pixels.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.

## Example Style
```css
.github-widget {}
.github-widget .widget-container {}
.github-widget .widget-container .label {}
```