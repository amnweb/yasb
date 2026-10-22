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
| `max_count`       | integer  | `0`  | The highest number shown on the bar, above which the count is written as `9+`. `0` shows the count as it is. |
| `menu`       | dict  | `{'blur': True, 'round_corners': True, 'round_corners_type': 'normal', 'border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0, 'width': 380, 'max_height': 400, 'max_notifications': 30, 'show_app_icons': True, 'app_icon_size': 36, 'section_icon_size': 16, 'show_site_icons': False, 'show_images': True, 'image_max_height': 180, 'group_by_app': True, 'show_dnd_toggle': True, 'show_notification_center': True}`  | Menu settings for the notification popup. |
| `keybindings`     | list    | `[]` | Optional hotkeys. See [Keybindings](./Keybindings). |
| `callbacks`       | dict    | [See below](#available-callbacks) | Callbacks for mouse events on the notifications widget. |

## Example Configuration

```yaml
  notifications:
    type: "yasb.notifications.NotificationsWidget"
    options:
      label: "<span>\udb80\udc9e</span> {count}"
      label_alt: "{count} notifications"
      hide_empty: true
      max_count: 9
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
        app_icon_size: 36
        section_icon_size: 16
        show_site_icons: false
        show_images: true
        image_max_height: 180
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
- **max_count:** The highest number written on the bar. Above it the count is shown capped, so `max_count: 9` writes `9+` for anything past nine, which keeps a long count from widening the bar. `0`, the default, always shows the real number. The tooltip and the menu header show the real number either way.
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
  - **show_app_icons:** Whether to show the icon of the app that sent the notification, or the app logo the toast supplies in its place. It also covers the icon next to a section header, where Windows has one for the sender.
  - **app_icon_size:** The size of that icon in pixels, between 8 and 64. A stylesheet cannot change it: Qt draws the icon at the size it was built at.
  - **section_icon_size:** The size in pixels of the icon next to a section header, between 8 and 64. Only senders Windows keeps an icon for have one, which in practice means websites; an app is headed by its name alone.
  - **show_site_icons:** Whether a notification from a website shows the site's icon in the item itself when it brings no picture of its own. Off by default, which leaves such an item without an icon the way the Notification Center shows it, with the text taking the space: the icon of the browser it came through is never used, since it is not what sent the notification. The site's icon heads its section either way.
  - **show_images:** Whether to show the images a notification carries: the app logo it can put in place of the app icon, the hero image above it and any inline images below the text.
  - **image_max_height:** The maximum height of a hero or inline image in pixels. Images are scaled to fit the menu width and this height, and are never enlarged.
  - **group_by_app:** Whether to group notifications under a header per sender, the way the Notification Center groups them. A browser is filed one sender per website, so a page's notifications are headed by the page rather than by the browser.
  - **show_dnd_toggle:** Whether to show the Do Not Disturb toggle in the menu header. The toggle is hidden automatically if Windows Focus Assist cannot be reached.
  - **show_notification_center:** Whether to show the footer link that opens the Windows Notification Center.
- **keybindings:** A list of global hotkeys for this widget. See [Keybindings](./Keybindings).
- **callbacks:** Mouse event callbacks. See [Callbacks](#available-callbacks).

> [!NOTE]
> Clicking a notification does what clicking it in the Notification Center does: the app it came from is given that particular notification, so a screenshot notification opens the screenshot and a website notification opens the page behind it. An activated notification is removed, the same way Windows removes it. An app that registered no way of being handed a notification is only brought to the foreground and keeps it. Removing a notification here, by clicking it or by dismissing it, also removes it from the Windows Notification Center.

> [!NOTE]
> `{count}` on the bar counts the notifications the menu lists, so the two always agree. Windows publishes a count of its own for the shell, but it is not one to write on a bar: a notification activated from the Notification Center is taken out of the list without being taken out of that count, which then stays too high until something else resets it. It is used for one case only, when the permission below has been turned off and there is no list to count.
>
> The list itself has one limit of its own: Windows hands out at most twenty notifications per app, so an app that has sent more than that keeps notifications in the Notification Center that neither the menu nor the count can see.

> [!IMPORTANT]
> Reading notifications requires the global **Let apps access my notifications** switch under Settings > Privacy & security > Notifications. Windows does not track this permission per app for apps installed outside the Store, so YASB has no entry of its own there. When the switch is off the menu says so and links to that page, while the count on the bar keeps working.

> [!NOTE]
> Notification images are read from the toast Windows stored locally, since the notification listener only hands out the text of a notification. Messaging apps usually send the sender's picture as an `http(s)` address rather than a file; Windows downloads those itself and notes where it put them, and that note is what YASB reads. YASB never requests an image over the network, so a picture Windows did not keep is not shown, and neither is one a notification points at on a network share.
>
> The file a notification points at usually belongs to the app that sent it and is deleted as soon as the toast has been drawn, long before the notification leaves the Notification Center. YASB copies each picture to `%LOCALAPPDATA%\YASB\notification_images` the first time it sees it so the menu goes on showing what Windows shows, and deletes a copy once its notification is gone.

## Available Callbacks

The `callbacks` option maps mouse buttons (`on_left`, `on_middle`, `on_right`) to actions. All keys are optional, the values shown are the defaults.

```yaml
callbacks:
  on_left: "toggle_menu"
  on_middle: "do_nothing"
  on_right: "do_nothing"
```

Available actions:

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
/* The notification list. Leave it transparent for the menu background to show through */
.notification-menu .contents {
    background-color: transparent;
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
/* The image a toast can show in place of the app icon */
.notification-menu .item .icon.app-logo {
    margin-right: 10px;
}
.notification-menu .item .hero {
    margin-bottom: 8px;
}
.notification-menu .item .inline-image {
    margin-top: 8px;
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
