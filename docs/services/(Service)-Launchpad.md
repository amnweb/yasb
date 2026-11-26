# Launchpad

`import Yasb`

Apps from Start's All apps list (without documents, web links, consoles and uninstallers) in your own order, with
groups and hidden apps. Functions to start an app, run it as administrator, open its folder and uninstall it.

The order is shared by every launchpad and saved in `%LOCALAPPDATA%\YASB\launchpad.json`. The first time, apps are
sorted A to Z. Newly installed apps are added at the end, uninstalled apps are removed.

Two types:

- [LaunchpadApps](#launchpadapps): the one a widget creates.
- [LaunchpadLayout](#launchpadlayout): the order, available as `layout`. Its rows are apps and groups.

## LaunchpadApps

### Properties

#### apps : list `read-only`

All apps, A to Z. Each is an object:

- `id` : string, app id in Windows. Used by `launch()`, `actions()` and `run()`, and held by the rows of `layout`.
- `name` : string, app name, as Start shows it.
- `kind` : string, `store` for Microsoft Store apps, otherwise `desktop`.
- `target` : string, program or file a desktop app starts.
- `arguments` : string, arguments a desktop app starts with.
- `icon` : string, image URL of the icon. It ends with `/` and a number, replace that number with `iconRevision`,
  as `icon.replace(/\/\d+$/, "/" + iconRevision)`, so the icon reloads once it is ready.

#### layout : LaunchpadLayout `read-only`

Apps and groups in your order. See [LaunchpadLayout](#launchpadlayout).

#### loading : bool `read-only`

`true` until Start's apps are read the first time.

#### iconRevision : int `read-only`

Increases as icons finish loading. See `icon` in `apps`.

### Functions

#### launch(id: string)

Starts the app, as Start does.

#### actions(id: string) : list&lt;string&gt;

Actions `run()` can do for the app: `run_as_admin`, `open_file_location` and `uninstall` for desktop apps that
start a program, only `uninstall` for others.

#### run(id: string, action: string)

Runs one of the app's `actions()`: `run_as_admin` starts it as administrator, `open_file_location` opens its
folder in Explorer with the file selected, `uninstall` opens Windows' Installed apps settings. Other actions are
ignored.

#### takeFocus(window: Window)

Gives a YASB window (such as a popup) the foreground and keyboard focus. Needed when a popup opened from a hotkey
must accept typing.

## LaunchpadLayout

The launchpad order, available as `layout` of LaunchpadApps. Use it as the `model` of a `Repeater` or `GridView`.
Each row is an app or a group. Hidden apps have no row. Every function below saves the order, except `move()`,
which `commit()` saves.

### Row fields

#### group : bool

`true` when the row is a group.

#### appId : string

Id of the row's app (an `id` from `apps`). `""` for a group.

#### name : string

Group name. `""` for an app.

#### apps : list&lt;string&gt;

Ids of the group's apps, in order. Empty for an app.

### Properties

#### count : int `read-only`

Number of rows. `0` until the apps are read the first time.

#### hidden : list&lt;string&gt; `read-only`

Ids of installed apps the user hid, in the order they were hidden.

### Functions

All functions take rows by their number in the current order, from 0.

#### move(source: int, before: int)

Moves the row at `source` before the row at `before`, or to the end for `count`. Doesn't save, because it runs at
every step of a drag, call `commit()` when the drag ends.

#### commit()

Saves the order.

#### group(source: int, target: int) : int

Drops the app at `source` on `target`. On an app, the two become a new group named `New group`. On a group, the
app joins it. Returns the group's row, or `-1` when nothing changed (for example when `source` is a group).

#### takeOut(row: int, id: string, before: int) : int

Takes the app out of the group at `row` and places it before the row at `before`. A group left with one app becomes
that app. Returns the app's row, or `-1` when it wasn't in the group.

#### moveInGroup(row: int, id: string, before: int)

Moves the app inside the group at `row` before the app at `before`, or to the end for the group's size.

#### groupApps(ids: list&lt;string&gt;) : int

Makes a new group named `New group` from these apps, taken from wherever they are, in the place of the first one.
Returns its row, or `-1` when fewer than two of them are in the grid.

#### ungroup(row: int)

Replaces the group at `row` with its apps.

#### renameGroup(row: int, name: string)

Renames the group at `row`. An empty `name` sets `New group`.

#### hide(ids: list&lt;string&gt;)

Removes these apps from the grid and their groups, and adds them to `hidden`.

#### unhide(ids: list&lt;string&gt;)

Puts these hidden apps back, at the end of the grid.

#### rowOf(id: string) : int

Row of the app when it isn't in a group. `-1` otherwise.

#### appAt(row: int) : string

Id of the app at `row`. `""` for a group.

#### isGroup(row: int) : bool

`true` when the row is a group.

#### nameOf(row: int) : string

Name of the group at `row`. `""` for an app.

#### appsOf(row: int) : list&lt;string&gt;

Ids of the group's apps at `row`. Empty for an app.

## Used by

YASB's own Launchpad widget, listed in [Widgets](./Widgets).
