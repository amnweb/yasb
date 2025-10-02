# Notifications Widget Configuration

| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`           | string  | `"{count} new notifications"`                        | The format string for the notifications widget.     |
| `label_alt`       | string  | `"{count} new notifications"`        | The alternative format string for the notifications widget. |
| `class_name`      | string  | `""`                                                                                  | Additional CSS class name for the widget.                                    |
| `tooltip`  | boolean  | `true`        | Whether to show the tooltip on hover. |
| `icons`          | dict    | `{'new': '\udb80\udc9e', 'default': '\udb80\udc9a'}`               | Icons for different notification states.                                    |
| `hide_empty`       | boolean  | `false`  | Whether to hide the widget when there are no notifications. |
| `callbacks`       | dict    | `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}` | Callbacks for mouse events on the notifications widget. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |

## Example Configuration

```yaml
  notifications:
    type: "yasb.notifications.NotificationsWidget"
    options:
      label: "<span>\uf476</span> {count}"
      label_alt: "{count} notifications"
      hide_empty: true
      tooltip: false
      callbacks:
        on_left: "toggle_notification"
        on_right: "do_nothing"
        on_middle: "toggle_label"
      label_shadow:
        enabled: true
        color: "black"
        radius: 3
        offset: [ 1, 1 ]
```

## Description of Options

- **label:** The format string for the notifications widget. The string can contain the `{count}` placeholder which will be replaced with the number of notifications and the `{icon}` placeholder which will be replaced with the icon representing the notification state.
- **label_alt:** The alternative format string for the notifications widget. The string can contain the `{count}` placeholder which will be replaced with the number of notifications and the `{icon}` placeholder which will be replaced with the icon representing the notification state.
- **class_name:** Additional CSS class name for the widget. This allows for custom styling.
- **tooltip:** Whether to show the tooltip on hover.
- **icons:** A dictionary specifying the icons for different notification states. It contains two keys: `new` and `default`. The values are the icons to be used for new notifications and the default state, respectively.
- **hide_empty:** Whether to hide the widget when there are no notifications.
- **callbacks:** Callbacks for mouse events on the notifications widget. The following callbacks are available:
  - `on_left`: Callback for left-click event.
  - `on_middle`: Callback for middle-click event.
  - `on_right`: Callback for right-click event.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.

## Available Callbacks

- **toggle_notification:** Toggles the notification panel.
- **toggle_label:** Toggles the label between the default and alternative format.
- **do_nothing:** A placeholder callback that does nothing.
- **clear_notifications:** Clears all notifications.

## Example Style
```css
.notification-widget {
    padding: 0 0px 0 4px;
}
.notification-widget.your_class {} /* If you are using class_name option */
.notification-widget .widget-container {
	background-color:rgba(17, 17, 27, 0.75);
	margin: 3px 0 3px 0;
	border-radius: 12px;
    border: 1px solid #45475a;
}
.notification-widget .icon {
    font-size: 12px;
}
.notification-widget .icon.new-notification {
    color: #89b4fa;
}
.notification-widget .label.new-notification {
    color: #89b4fa;
}
```