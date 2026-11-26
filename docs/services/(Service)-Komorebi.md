# Komorebi

`import Yasb`

[komorebi](https://github.com/LGUG2Z/komorebi) workspaces on the bar's monitor (with layout and window icons), and
whether komorebi is paused, with functions to switch workspaces. Updates on komorebi's events. All
KomorebiWorkspacesModel objects share one subscription. While komorebi isn't running, `connected` is `false` and
`workspaces` is empty.

## KomorebiWorkspacesModel

### Properties

#### screenName : string

Name of the screen the widget is on. Set it to `bar.screenName`. Empty means the primary screen.

Default: `""`

#### appIcons : object

Which workspaces list their windows' icons in `icons`. All keys are optional:

- `enabledActive` : bool, the workspace shown on the monitor. Default `false`.
- `enabledPopulated` : bool, the other workspaces. Default `false`.
- `maxIcons` : int, maximum icons per workspace. `0` means no limit. Default `0`.
- `hideFloating` : bool, skip floating windows. Default `false`.
- `hideDuplicates` : bool, one icon per app. Default `false`.

Default: `{}`

#### connected : bool `read-only`

`true` when komorebi is running and YASB receives its events.

#### monitorIndex : int `read-only`

komorebi's number for the bar's monitor, from 0. `-1` when komorebi doesn't manage it.

#### floatOverride : bool `read-only`

`true` when komorebi's float override is on (new windows float).

#### paused : bool `read-only`

`true` when komorebi is paused.

#### workspaces : list `read-only`

Workspaces on the bar's monitor, in komorebi's order. Each is an object:

- `index` : int, workspace number, from 0. Used by `activateWorkspace()`.
- `name` : string, workspace name. `""` when komorebi gives none.
- `active` : bool, `true` when shown on the monitor.
- `focused` : bool, `true` when `active` and the monitor has komorebi's focus.
- `populated` : bool, `true` when it has windows.
- `windowCount` : int, number of windows, including floating ones.
- `layout` : string, komorebi's layout name, such as `BSP` or `VerticalStack`, or `Custom`.
- `layer` : string, `Tiling` or `Floating`.
- `tile` : bool, `false` while the workspace doesn't tile.
- `monocle` : bool, `true` when it has a monocle container.
- `maximized` : bool, `true` when it has a maximized window.
- `icons` : list, window icons as chosen by `appIcons`, each `{hwnd, title, source}`: window handle, title, and
  image URL of the icon.

### Functions

#### activateWorkspace(index: int)

Shows the workspace with this index on the bar's monitor. When called many times quickly (for example while
scrolling), only the last request waits its turn.

#### switchWorkspace(delta: int)

`delta` above 0 (scroll up): previous workspace. Below 0: next workspace. Wraps around.

## Used by

YASB's own Komorebi workspaces widget, listed in [Widgets](./Widgets).
