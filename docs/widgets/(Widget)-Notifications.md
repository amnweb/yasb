# Notifications Widget Configuration

Displays the number of unread Windows notifications in your status bar. Clicking it opens a YASB notification menu that lists the notifications currently in the Action Center, and you can set it to auto-hide when you have no new notifications.

| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`           | string  | `"{count} new notifications"`                        | The format string for the notifications widget.     |
| `label_alt`       | string  | `"{count} new notifications"`        | The alternative format string for the notifications widget. |
| `class_name`      | string  | `""`                                                                                  | Additional CSS class name for the widget.                                    |
| `tooltip`  | boolean  | `true`        | Whether to show the tooltip on hover. |
| `icons`          | dict    | `{'new': '\udb80\udc9e', 'default': '\udb80\udc9a', 'dnd_on': '\udb80\udc9b', 'dnd_off': '\udb80\udc9a', 'dismiss': '\uf00d'}`               | Icons for different notification states.                                    |
| `hide_empty`       | boolean  | `false`  | Whether to hide the widget when there are no notifications. |
| `menu`       | dict  | `{'blur': True, 'round_corners': True, 'round_corners_type': 'normal', 'border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0, 'width': 380, 'max_height': 400, 'max_notifications': 30, 'show_app_icons': True, 'group_by_app': True, 'show_dnd_toggle': True, 'show_notification_center': True}`  | Menu settings for the notification popup. |
| `callbacks`       | dict    | `{'on_left': 'toggle_menu', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}` | Callbacks for mouse events on the notifications widget. |

## Example Configuration

```yaml
  notifications:
    type: "yasb.notifications.NotificationsWidget"
    options:
      label: "<span>\udb80\udc9e</span> {count}"
      label_alt: "{count} notifications"
      hide_empty: true
      tooltip: false
      menu:
        blur: true
        round_corners: true
        alignment: "right"
        direction: "down"
        width: 380
        max_height: 400
        group_by_app: true
        show_app_icons: true
      callbacks:
        on_left: "toggle_menu"
        on_right: "toggle_notification"
        on_middle: "toggle_label"
```

## Description of Options

- **label:** The format string for the notifications widget. The string can contain the `{count}` placeholder which will be replaced with the number of notifications and the `{icon}` placeholder which will be replaced with the icon representing the notification state.
- **label_alt:** The alternative format string for the notifications widget. The string can contain the `{count}` placeholder which will be replaced with the number of notifications and the `{icon}` placeholder which will be replaced with the icon representing the notification state.
- **class_name:** Additional CSS class name for the widget. This allows for custom styling.
- **tooltip:** Whether to show the tooltip on hover.
- **icons:** A dictionary specifying the icons used by the widget:
  - `new`: shown when there is at least one notification.
  - `default`: shown when there are no notifications, and as the empty-state icon inside the menu.
  - `dnd_on` / `dnd_off`: the Do Not Disturb toggle in the menu header. `dnd_on` is shown while Do Not Disturb is active (a crossed-out bell), `dnd_off` while notifications are allowed.
  - `dismiss`: the button that removes a single notification.
- **hide_empty:** Whether to hide the widget when there are no notifications.
- **menu:** Menu settings for the notification popup.
  - **blur:** Whether to apply a blur effect to the menu.
  - **round_corners:** Whether the menu should have rounded corners.
  - **round_corners_type:** The type of rounded corners, `normal` or `small`.
  - **border_color:** The border color of the menu, `None`, `System` or a hex color.
  - **alignment:** The alignment of the menu, `left`, `center` or `right`.
  - **direction:** Whether the menu opens `down` or `up`.
  - **offset_top:** Vertical offset of the menu in pixels.
  - **offset_left:** Horizontal offset of the menu in pixels.
  - **width:** The width of the menu in pixels. Notification text is elided to fit.
  - **max_height:** The maximum height of the scrollable notification list in pixels.
  - **max_notifications:** The maximum number of notifications shown in the menu.
  - **show_app_icons:** Whether to show the icon of the app that sent the notification.
  - **group_by_app:** Whether to group notifications under a header per app.
  - **show_dnd_toggle:** Whether to show the Do Not Disturb toggle in the menu header. The toggle is hidden automatically if Windows Focus Assist cannot be reached.
  - **show_notification_center:** Whether to show the footer link that opens the Windows Notification Center.
- **callbacks:** Callbacks for mouse events on the notifications widget. The following callbacks are available:
  - `on_left`: Callback for left-click event.
  - `on_middle`: Callback for middle-click event.
  - `on_right`: Callback for right-click event.

> [!NOTE]
> Clicking a notification brings the sending app to the foreground. Only the dismiss button removes it, and removing a notification here also removes it from the Windows Notification Center.

> [!NOTE]
> `{count}` on the bar is the number Windows itself reports, which is not always the number of entries in the Action Center, so the bar and the menu can differ by one or two. Clearing removes the notifications one by one and the menu then shows whatever is left, since Windows can refuse to remove an individual notification.

> [!IMPORTANT]
> Reading notifications requires the global **Let apps access my notifications** switch under Settings > Privacy & security > Notifications. Windows does not track this permission per app for apps installed outside the Store, so YASB has no entry of its own there. When the switch is off the menu says so and links to that page, while the count on the bar keeps working.

## Available Callbacks

- **toggle_menu:** Toggles the YASB notification menu.
- **toggle_notification:** Toggles the Windows Notification Center.
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

/* Notification menu */
.notification-menu {
    background-color: rgba(17, 17, 27, 0.9);
}
.notification-menu .header {
    border-bottom: 1px solid #45475a;
    padding: 10px 14px;
}
.notification-menu .header .label {
    font-size: 13px;
    font-weight: 700;
    color: #cdd6f4;
}
.notification-menu .header .label.clear-all {
    font-size: 11px;
    font-weight: 600;
    color: #9399b2;
    padding: 2px 6px;
    border-radius: 4px;
}
.notification-menu .header .label.clear-all:hover {
    color: #f38ba8;
}
.notification-menu .header .dnd-button {
    font-size: 14px;
    color: #9399b2;
    padding: 2px 8px;
    border-radius: 4px;
}
.notification-menu .header .dnd-button.active {
    color: #89b4fa;
}
.notification-menu .section-header {
    font-size: 11px;
    font-weight: 700;
    color: #89b4fa;
    padding: 8px 6px 4px 6px;
}
.notification-menu .section-header.other {
    color: #9399b2;
}
.notification-menu .empty-icon {
    font-size: 64px;
    color: #45475a;
    padding: 24px 0 8px 0;
}
.notification-menu .empty-text {
    font-size: 13px;
    font-weight: 600;
    color: #9399b2;
    padding-bottom: 24px;
}
.notification-menu .empty-action {
    font-size: 12px;
    font-weight: 600;
    color: #89b4fa;
    padding-bottom: 24px;
}
.notification-menu .item {
    background-color: rgba(30, 30, 46, 0.6);
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 10px;
    margin: 2px 4px;
}
.notification-menu .item:hover {
    border-color: #89b4fa;
}
.notification-menu .item .icon {
    margin-right: 10px;
}
.notification-menu .item .title {
    font-size: 13px;
    font-weight: 700;
    color: #cdd6f4;
}
.notification-menu .item .body {
    font-size: 12px;
    color: #bac2de;
    margin-top: 2px;
}
.notification-menu .item .description {
    font-size: 11px;
    color: #9399b2;
    margin-top: 3px;
}
.notification-menu .item .dismiss {
    font-size: 12px;
    color: #9399b2;
    min-width: 22px;
    max-width: 22px;
    min-height: 22px;
    max-height: 22px;
    margin-left: 8px;
    border-radius: 4px;
}
.notification-menu .item .dismiss:hover {
    color: #f38ba8;
}
.notification-menu .footer {
    border-top: 1px solid #45475a;
    padding: 8px 14px;
}
.notification-menu .footer .label {
    font-size: 11px;
    font-weight: 600;
    color: #9399b2;
}
.notification-menu .footer .label:hover {
    color: #89b4fa;
}
```

## Preview of the Widget
![Notifications YASB Widget](assets/notifications-widget.png)
