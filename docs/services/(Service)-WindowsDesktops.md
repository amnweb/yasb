# Virtual desktops

`import Yasb`

Windows' virtual desktops, the one in view and those with windows open, with functions to switch, create, rename and
remove them, move and pin windows, and set their wallpapers. Updates when Windows reports a change. All VirtualDesktops
objects share one connection to Windows, which reconnects after Explorer restarts.

## VirtualDesktops

### Properties

#### desktops : list `read-only`

The desktops, in Task View's order. Each is an object:

- `number` : int, its place, from 1. Used by the functions.
- `name` : string, its name. `""` until it is renamed, and always on Windows builds before 19041.
- `populated` : bool, `true` when it has a window of its own that Windows shows in its switchers. Windows on every
  desktop don't count.

Empty until Explorer first responds.

#### current : int `read-only`

`number` of the desktop in view. `0` while Explorer isn't answering.

#### wallpaperSupported : bool `read-only`

`true` when each desktop can have its own wallpaper, on Windows 11.

#### hasWindow : bool `read-only`

`true` when a window was found by the last `readForeground()`.

#### windowPinned : bool `read-only`

`true` when the window `readForeground()` found is on every desktop.

#### appPinned : bool `read-only`

`true` when the app of the window `readForeground()` found is on every desktop.

### Functions

#### readForeground()

Remembers the foreground window, for menu entries that act on it after the menu has taken focus. The desktop, the
taskbar, YASB's own windows and windows Windows leaves out of its switchers aren't found.

#### switchTo(number: int)

Switches to this desktop.

#### step(offset: int)

Switches by `offset` desktops, such as `1` or `-1`, wrapping around at either end.

#### create()

Adds a desktop.

#### remove(number: int)

Removes this desktop, or the one in view for `0`. Its windows move to the first other desktop in Task View's
order. Ignored while there is only one desktop.

#### rename(number: int, name: string)

Renames this desktop. Does nothing on Windows builds before 19041.

#### moveWindowTo(number: int)

Moves the window `readForeground()` found to this desktop.

#### moveFrontWindowTo(number: int)

Moves the current foreground window to this desktop, for hotkeys and clicks that open no menu.

#### toggleWindowPin()

Puts the window `readForeground()` found on every desktop, or back on one.

#### toggleAppPin()

Puts every window of that window's app on every desktop, or back on one.

#### setWallpaper(number: int, image: url)

Sets the wallpaper of this desktop to the local file `image`. Only while `wallpaperSupported`.

#### setWallpaperAll(image: url)

Sets the wallpaper of every desktop to the local file `image`. Only while `wallpaperSupported`.

VirtualDesktops has no signals.

## Used by

YASB's own Virtual desktops widget, listed in [Widgets](./Widgets).
