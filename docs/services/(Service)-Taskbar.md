# Taskbar

`import Yasb`

Pinned apps and open windows, grouped by app, with functions to start, switch, close and pin them, and a live
picture of any window. Updates when windows open, close or change. All TaskbarApps objects share one window tracker
and one set of pins, saved in `%LOCALAPPDATA%\YASB\taskbar_pinned.json`.

Two types:

- [TaskbarApps](#taskbarapps): the apps and their windows. Its settings choose which windows it shows.
- [WindowThumbnail](#windowthumbnail): an item that shows a window, live, by its `hwnd`.

## TaskbarApps

### Properties

#### screenName : string

Only windows on the screen with this name. `""`, or a name no screen has, for every screen.

Default: `""`

#### onlyVisible : bool

When `true`, leaves out cloaked windows, such as those on other virtual desktops.

Default: `false`

#### strictFiltering : bool

When `true`, leaves out windows that can't be minimized, such as some dialogs.

Default: `true`

#### ignoreClasses : list&lt;string&gt;

Windows to leave out, by their exact class name.

Default: `[]`

#### ignoreProcesses : list&lt;string&gt;

Windows to leave out, by their exact process name.

Default: `[]`

#### ignoreTitles : list&lt;string&gt;

Windows to leave out, by their exact title.

Default: `[]`

#### apps : list `read-only`

The apps in taskbar order: pinned ones first, in their pinned order, then the others as they opened. Each is an
object:

- `id` : string, the app's id: `aumid:<app id>`, `explorer:<folder>`, `path:<exe>` (followed by `|` and its
  arguments for apps told apart by them), or `window:<hwnd>` when the app can't be told.
- `name` : string, the pinned name. `""` when not pinned.
- `pinned` : bool, `true` when pinned.
- `icon` : string, image URL of the app's icon. A pinned Recycle Bin shows whether it is empty.
- `windows` : list&lt;object&gt;, the app's open windows that pass the settings, as they opened:
  - `hwnd` : int, the window's handle. Used by the functions.
  - `appId` : string, the app's `id`.
  - `title` : string, the window's title.
  - `icon` : string, image URL of the window's icon.
  - `process` : string, the process name, such as `notepad.exe`.
  - `className` : string, the window's class name.
  - `active` : bool, `true` when it is the window in front.
  - `flashing` : bool, `true` while it asks for attention.
  - `minimized` : bool, `true` when minimized.
  - `cloaked` : bool, `true` when cloaked, such as on another virtual desktop.
  - `canMinimize` : bool, `true` when it can be minimized.

Windows without a title or a process are left out. A plain list, not a model: every change replaces it.

#### iconRevision : int `read-only`

Goes up as icons finish loading. Icon URLs end with `/` and the number they were made with, one kept from before,
such as in a menu, loads the new icon with this number at its end.

#### peekAvailable : bool `read-only`

`true` when this Windows build can fade the desktop to show one window. See `peek()`.

### Functions

#### activate(hwnd: int)

Acts on the window that owns this one, or the window itself:

- When it is minimized, restores it and brings it to the front, then gives the focus to the dialog it last showed,
  if any.
- When it, or a window it owns, is already in front, minimizes it, if this window can be minimized.
- Otherwise, brings it to the front.

#### focus(hwnd: int)

Restores the window that owns this one, or the window itself, when minimized, and brings the dialog it last showed,
or else that window, to the front with the focus. It never minimizes, as for a file dragged over its button.

#### close(hwnd: int)

Asks the window that owns this one, or the window itself, to close, as its close button does. When that window
hangs, it is sent a close message instead, and as a last resort Windows is asked to end the task.

#### launch(appId: string, arguments: string)

Starts the app with this `id`, with `arguments` after its own. `arguments` can be left out. Ignored for a
`window:` id.

#### pin(appId: string, index: int)

Pins an open app at this place among the pinned apps, or after them for `-1`. `index` can be left out, for `-1`.
Ignored for a `window:` id, or an app with no open window.

#### unpin(appId: string)

Unpins the app.

#### move(appId: string, index: int)

Moves a pinned app to this place among the pinned apps.

#### jumpList(appId: string) : object

What a button's menu offers for the app:

- `name` : string, the pinned name, or else the name Windows shows for the app, found from one of its open
  windows, for File Explorer, the window's title. `""` when the app isn't pinned and has no open window.
- `items` : list&lt;object&gt;, extra items for some apps, each with:
  - `kind` : string, `window` (a new window), `private` (a new private window), `profile` (a Windows Terminal
    profile), `folder` (a folder pinned in File Explorer) or `explorer` (File Explorer).
  - `text` : string, the item's text.
  - `target` and `arguments` : string, to start it with `launch(target, arguments)`.
  - `icon` : string, image URL of its icon, when it has one.
  - `iconText` : string, its icon when it is text, such as an emoji, when it has one.

Items are given for Edge, Chrome, Firefox and Zen (new window, new private window), VS Code (new window), Windows
Terminal (up to 20 profiles) and File Explorer (up to 10 Quick Access folders, and File Explorer). For the Recycle
Bin, `items` has one item of kind `recycleBin`, with `items` and `bytes`, what it holds.

#### peek(hwnd: int, keep: list)

Fades the desktop to show only this window. The windows in `keep`, QML windows such as the preview and the bar,
stay visible, the first is the preview, and the window shows below it. `0` ends peek.

#### emptyRecycleBin()

Empties the Recycle Bin. Windows asks to confirm.

TaskbarApps has no signals.

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

YASB's own Taskbar widget, listed in [Widgets](./Widgets).
