# Window switcher

`import Yasb`

Every window that belongs on a taskbar, front to back, with functions to switch to or close one, and a live
picture of any window. Updates when windows open, close or change. It reads the same window tracker as
[Taskbar](./(Service)-Taskbar).

Two types:

- [WindowList](#windowlist): the windows, and switching to them.
- [WindowThumbnail](#windowthumbnail): an item that shows a window, live, by its `hwnd`.

## WindowList

### Properties

#### windows : list `read-only`

The windows, front to back, those on other virtual desktops too. Each is an object:

- `hwnd` : int, the window's handle. Used by the functions.
- `appId` : string, the app's id, as in [Taskbar](./(Service)-Taskbar).
- `title` : string, the window's title.
- `icon` : string, image URL of the window's icon.
- `process` : string, the process name, such as `notepad.exe`.
- `className` : string, the window's class name.
- `active` : bool, `true` when it is the window in front.
- `flashing` : bool, `true` while it asks for attention.
- `minimized` : bool, `true` when minimized.
- `cloaked` : bool, `true` when cloaked, such as on another virtual desktop.
- `canMinimize` : bool, `true` when it can be minimized.

A plain list, not a model: every change replaces it.

### Functions

#### inFront(hwnd: int) : bool

`true` when this window, or a window it owns such as a dialog, is the one in front.

#### switchTo(hwnd: int)

Brings the window and the window that owns it to the front, restoring them when minimized. The keyboard focus goes
to the dialog it last showed, if any. Done just after the call, so a popup asking for it can start to close first.

#### close(hwnd: int)

Asks the window that owns this one, or the window itself, to close, as its close button does. When that window
hangs, it is sent a close message instead, and as a last resort Windows is asked to end the task.

#### keyboardModifiers() : int

The modifier keys held down now, as `Qt.KeyboardModifier` flags.

#### takeFocus(window: Window)

Gives `window` the foreground and the keyboard, as a popup opened from a hotkey needs.

WindowList has no signals.

## WindowThumbnail

An Item that shows another window, live, in its place. Windows draws the picture over the QML scene, so nothing
else in the item's place is seen. The item's visibility, opacity and clipping, through all its parents, carry
over. The whole window is drawn at the item's size, size the item from `sourceWidth` and `sourceHeight` to keep
its shape.

### Properties

#### hwnd : int

The window shown. `0` for none.

Default: `0`

#### sourceWidth : int `read-only`

Width of the window shown, in pixels. `0` until it is known.

#### sourceHeight : int `read-only`

Height of the window shown, in pixels. `0` until it is known.

WindowThumbnail has no functions or signals.

## Used by

YASB's own Window switcher widget, listed in [Widgets](./Widgets).
