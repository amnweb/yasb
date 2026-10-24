# Notifications Widget Configuration

Displays the number of Windows notifications in your status bar. Clicking it opens a menu with the notifications Windows holds, grouped by app, and you can set it to auto-hide when you have no new notifications.

| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`           | string  | `"{count} new notifications"`                        | The format string for the notifications widget.     |
| `label_alt`       | string  | `"{count} new notifications"`        | The alternative format string for the notifications widget. |
| `class_name`      | string  | `""`                                                                                  | Additional CSS class name for the widget.                                    |
| `tooltip`  | boolean  | `true`        | Whether to show tooltips. |
| `icons`           | dict    | [See below](#icons-options) | Icons for different notification states. |
| `hide_empty`       | boolean  | `false`  | Whether to hide the widget when there are no notifications. |
| `menu`            | dict    | [See below](#menu-options) | Settings for the notification menu. |
| `keybindings`     | list    | `[]` | Optional hotkeys. See [Keybindings](./Keybindings). |
| `callbacks`       | dict    | [See below](#available-callbacks) | Callbacks for mouse events on the notifications widget. |

## Example Configuration

```yaml
  notifications:
    type: "yasb.notifications.NotificationsWidget"
    options:
      label: "<span>\uf476</span> {count}"
      label_alt: "{count} notifications"
      hide_empty: true
      tooltip: false
      menu:
        blur: true
        round_corners: true
        round_corners_type: "normal"
        border_color: "System"
        alignment: "right"
        direction: "down"
        offset_top: 6
        offset_left: 0
        app_icon_size: 16
      callbacks:
        on_left: "toggle_menu"
        on_right: "toggle_notification"
        on_middle: "toggle_label"
```

## Menu Options

The `menu` option accepts the following keys. All keys are optional, the values shown are the defaults.

```yaml
menu:
  blur: true
  round_corners: true
  round_corners_type: "normal"
  border_color: "System"
  alignment: "right"
  direction: "down"
  offset_top: 6
  offset_left: 0
  app_icon_size: 16
```

## Icons Options

The `icons` option accepts the following keys. All keys are optional, the values shown are the defaults.

```yaml
icons:
  new: "\udb80\udc9e"
  default: "\udb80\udc9a"
  dnd_on: "\udb80\udc9b"
  dnd_off: "\udb80\udc9a"
  dismiss: "\uf00d"
```

## Description of Options

- **label:** The format string for the notifications widget. The string can contain the `{count}` placeholder which will be replaced with the number of notifications (`9+` above nine) and the `{icon}` placeholder which will be replaced with the icon representing the notification state.
- **label_alt:** The alternative format string for the notifications widget. The string can contain the `{count}` placeholder which will be replaced with the number of notifications (`9+` above nine) and the `{icon}` placeholder which will be replaced with the icon representing the notification state.
- **class_name:** Additional CSS class name for the widget. This allows for custom styling.
- **tooltip:** Whether to show tooltips.
- **icons:** A dictionary specifying the icons used by the widget:
  - `new`: shown when there is at least one notification.
  - `default`: shown when there are no notifications, and in the empty menu.
  - `dnd_on` / `dnd_off`: the Do Not Disturb button in the menu header, while it is on or off.
  - `dismiss`: the button that removes a single notification.
- **hide_empty:** Whether to hide the widget when there are no notifications.
- **menu:** Settings for the notification menu. Its size is set in CSS, see [Menu Style](#menu-style).
  - **blur:** Whether to apply a blur effect to the menu.
  - **round_corners:** Whether the menu has rounded corners.
  - **round_corners_type:** The type of rounded corners, `normal` or `small`.
  - **border_color:** The border color of the menu, `None`, `System` or a hex color.
  - **alignment:** The alignment of the menu, `left`, `center` or `right`.
  - **direction:** Whether the menu opens `down` or `up`.
  - **offset_top:** Vertical offset of the menu in pixels.
  - **offset_left:** Horizontal offset of the menu in pixels.
  - **app_icon_size:** Size of the app icon next to each app name in the menu, in pixels.
- **keybindings:** A list of global hotkeys for this widget. See [Keybindings](./Keybindings).
- **callbacks:** Mouse event callbacks. See [Callbacks](#available-callbacks).

Clicking a notification hands it to its app: a link opens, and an app that registered for its notifications (Chrome and most desktop apps) opens what the notification is about. An app that registered nothing is brought to the front or started. Either way the notification is removed, as it is in the Notification Center.

> [!WARNING]
> Some apps only react to a click that Windows itself delivers. Firefox, for example, ignores a click from this menu on a notification it showed while it is still running: nothing opens, and the notification is removed. The Notification Center can reach these apps through a part of Windows that other programs can't use, so open such notifications from there. If Firefox was closed after the notification arrived, clicking it in this menu works.

> [!NOTE]
> The menu needs the **Let apps access your notifications** switch under Settings > Privacy & security > Notifications. When it is off the menu says so and links to that page, while the count on the bar keeps working.

## Available Callbacks

The `callbacks` option maps mouse buttons (`on_left`, `on_middle`, `on_right`) to actions. All keys are optional, the values shown are the defaults.

```yaml
callbacks:
  on_left: "toggle_menu"
  on_middle: "do_nothing"
  on_right: "do_nothing"
```

Available actions:

- **toggle_menu:** Toggles the notification menu.
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
```

## Menu Style
```css
.notification-menu {} /* The menu, set its size here */
.notification-menu .header {}
.notification-menu .header .title {}
.notification-menu .header .dnd {} /* Do Not Disturb button, .dnd.active while it is on */
.notification-menu .header .clear-all {}
.notification-menu .contents {}
.notification-menu .contents .section {} /* All notifications of one app */
.notification-menu .contents .section-header {}
.notification-menu .contents .section-header .icon {}
.notification-menu .contents .section-header .name {}
.notification-menu .contents .section-header .clear-app {} /* Clears this app's notifications, shown while the header is hovered */
.notification-menu .contents .item {}
.notification-menu .contents .item .hero {} /* Large picture above the text, in the 364:180 shape Windows uses */
.notification-menu .contents .item .avatar {} /* Contact photo or logo, 48x48 */
.notification-menu .contents .item .title {}
.notification-menu .contents .item .time {}
.notification-menu .contents .item .dismiss {} /* Replaces the time while hovered */
.notification-menu .contents .item .body {} /* A max-height cuts long text after whole lines */
.notification-menu .contents .item .attribution {} /* Who sent it, for example "via www.youtube.com" */
.notification-menu .contents .item .image {} /* Picture below the text */
.notification-menu .contents .more {} /* "N more" and "Show less" */
.notification-menu .contents .empty {}
.notification-menu .contents .empty .icon {}
.notification-menu .contents .empty .text {}
.notification-menu .contents .empty .link {}
.notification-menu .footer {}
.notification-menu .footer .label {}
```

## Example Menu Style
```css
.notification-menu {
    background-color: rgb(44, 44, 44);
    min-width: 400px;
    max-width: 400px;
    min-height: 640px;
    max-height: 640px;
}
.notification-menu .header {
    padding: 12px 12px 8px 16px;
}
.notification-menu .header .title {
    font-family: "Segoe UI";
    font-size: 14px;
    font-weight: 600;
    color: #ffffff;
}
.notification-menu .header .dnd,
.notification-menu .header .clear-all {
    color: #ffffff;
    padding: 4px 10px;
    margin-left: 4px;
    border-radius: 6px;
    background-color: rgba(255, 255, 255, 0.05);
}
.notification-menu .header .dnd {
    font-family: "JetBrainsMono NFP";
    font-size: 14px;
    padding: 6px 8px;
}
.notification-menu .header .clear-all {
    font-family: "Segoe UI";
    font-size: 12px;
}
.notification-menu .header .dnd.active {
    color: #4cc2ff;
}
.notification-menu .header .dnd:hover,
.notification-menu .header .clear-all:hover {
    background-color: rgba(255, 255, 255, 0.06);
}
.notification-menu .contents .section {
    margin: 0 12px 12px 12px;
}
.notification-menu .contents .section-header {
    padding: 4px 4px 8px 4px;
}
.notification-menu .contents .section-header .icon {
    margin-right: 8px;
}
.notification-menu .contents .section-header .name {
    font-family: "Segoe UI";
    font-size: 12px;
    color: rgba(255, 255, 255, 0.79);
}
.notification-menu .contents .section-header .clear-app,
.notification-menu .contents .item .dismiss {
    font-family: "JetBrainsMono NFP";
    font-size: 10px;
    color: rgba(255, 255, 255, 0.79);
    padding: 4px;
    border-radius: 4px;
}
.notification-menu .contents .section-header .clear-app:hover,
.notification-menu .contents .item .dismiss:hover {
    background-color: rgba(255, 255, 255, 0.08);
}
.notification-menu .contents .item {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 4px;
}
.notification-menu .contents .item:hover {
    background-color: rgba(255, 255, 255, 0.08);
}
.notification-menu .contents .item .hero {
    margin-bottom: 12px;
}
.notification-menu .contents .item .avatar {
    margin-right: 12px;
}
.notification-menu .contents .item .title {
    font-family: "Segoe UI";
    font-size: 14px;
    font-weight: 600;
    color: #ffffff;
}
.notification-menu .contents .item .time {
    font-family: "Segoe UI";
    font-size: 12px;
    color: rgba(255, 255, 255, 0.54);
    margin-left: 8px;
}
.notification-menu .contents .item .dismiss {
    margin-left: 8px;
}
.notification-menu .contents .item .body {
    font-family: "Segoe UI";
    font-size: 14px;
    color: rgba(255, 255, 255, 0.79);
    margin-top: 2px;
    max-height: 57px;
}
.notification-menu .contents .item .attribution {
    font-family: "Segoe UI";
    font-size: 12px;
    color: rgba(255, 255, 255, 0.54);
    margin-top: 2px;
}
.notification-menu .contents .item .image {
    margin-top: 12px;
}
.notification-menu .contents .more {
    font-family: "Segoe UI";
    font-size: 12px;
    color: #4cc2ff;
    padding: 4px 4px 0 4px;
}
.notification-menu .contents .more:hover {
    color: #40ace2;
}
.notification-menu .contents .empty {
    padding: 48px 0;
}
.notification-menu .contents .empty .icon {
    font-family: "JetBrainsMono NFP";
    font-size: 40px;
    color: rgba(255, 255, 255, 0.54);
}
.notification-menu .contents .empty .text {
    font-family: "Segoe UI";
    font-size: 14px;
    color: rgba(255, 255, 255, 0.79);
    margin-top: 12px;
}
.notification-menu .contents .empty .link {
    font-family: "Segoe UI";
    font-size: 12px;
    color: #4cc2ff;
    margin-top: 8px;
}
.notification-menu .footer {
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding: 10px 16px;
}
.notification-menu .footer .label {
    font-family: "Segoe UI";
    font-size: 12px;
    color: #4cc2ff;
}
.notification-menu .footer .label:hover {
    color: #40ace2;
}
```

## Preview of the Widget
![Notifications YASB Widget](assets/d4e1f893-a2b6-43fc-9c71-3b5a82ef4d0b.png)
