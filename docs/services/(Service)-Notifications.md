# Notifications

`import Yasb`

Notifications in Windows' notification center, their count, and do not disturb, with functions to open, dismiss
and clear them. Updates when the notification center changes. All NotificationCenter objects share one listener.

## NotificationCenter

### Properties

#### count : int `read-only`

How many notifications Windows counts in its notification center. On Windows 10, its unread count. It can include
notifications that `notifications` can't read. `0` until Windows reports it.

#### notifications : list `read-only`

The notifications in the notification center, newest first. Each is an object:

- `id` : int, the notification's id. Used by `dismiss()` and `activate()`.
- `appId` : string, the sending app's id in Windows. `""` when Windows can't name the sender.
- `appName` : string, the sending app's name. `""` when Windows can't name the sender.
- `title` : string, the notification's first line of text. `""` when it has no text YASB can read.
- `body` : string, its other lines of text, one per line.
- `attribution` : string, the notification's attribution text. `""` when none.
- `time` : real, in milliseconds since 1970: the time the notification gives itself, or when Windows created it.
- `icon` : string, URL of the sending app's icon. `""` when `appId` is `""`.
- `logo` : string, file URL of the notification's own logo. `""` when none.
- `logoCircle` : bool, `true` when `logo` is meant to be cropped to a circle.
- `hero` : string, file URL of the notification's hero image. `""` when none.
- `image` : string, file URL of the notification's inline image. `""` when none.

Images are local files only: a web image when Windows saved a copy to show the notification, never a file on a
network share. An image that isn't on this PC is `""`.

A plain list, not a model: every change replaces the whole list. Only toast notifications are listed.

#### allowed : bool `read-only`

`false` when notification access for apps is turned off in Windows' privacy settings. `notifications` is empty
then.

#### doNotDisturb : bool `read-only`

`true` when Windows' do not disturb is on, in any mode.

#### doNotDisturbAvailable : bool `read-only`

`true` once YASB has read the do not disturb status. Read right after the NotificationCenter is created, then
whenever it changes in Windows.

### Functions

#### refresh()

Reads the notifications again.

#### clearAll()

Removes every notification from the notification center.

#### clearApp(appId: string)

Removes the notifications of the app with this `appId`. `""` removes those whose sender Windows can't name.

#### dismiss(id: int)

Removes this notification from the notification center.

#### activate(id: int)

Does what clicking the notification does: opens its link, or hands it to its app. If the app can't handle it, or the
notification has no launch arguments, the app's window is brought to the front, or the app is started. Once handled, the
notification is removed. Ignored for an `id` not in `notifications`.

#### setDoNotDisturb(enabled: bool)

Turns do not disturb on in its priority only mode, or turns it off. For the other modes, see
[Do not disturb](./(Service)-Dnd).

#### openNotificationCenter()

Opens Windows' notification center.

NotificationCenter has no signals.

## Used by

YASB's own Notifications widget, listed in [Widgets](./Widgets).
