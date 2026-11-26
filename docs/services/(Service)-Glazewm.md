# GlazeWM

`import Yasb`

[GlazeWM](https://github.com/glzr-io/glazewm) workspaces (with window icons), tiling direction and binding modes,
with functions to switch them. Connects to GlazeWM's IPC server. While GlazeWM isn't running, YASB retries every 4
seconds and the data is empty. Objects of the same type that use the same server share one connection.

Three types, all with `serverUri` and `connected`:

- [GlazewmWorkspaceList](#glazewmworkspacelist): workspaces.
- [GlazewmTiling](#glazewmtiling): tiling direction.
- [GlazewmBindingModes](#glazewmbindingmodes): active binding mode.

## Common to all three

### Properties

#### serverUri : string

GlazeWM's IPC server.

Default: `"ws://localhost:6123"`

#### connected : bool `read-only`

`true` when GlazeWM is running and YASB is connected.

## GlazewmWorkspaceList

### Properties

#### screenName : string

Name of the screen the widget is on. Set it to `bar.screenName`. Empty means the primary screen.

Default: `""`

#### monitorExclusive : bool

When `true`, `workspaces` holds only the workspaces of `screenName`'s monitor. When `false`, all monitors.

Default: `true`

#### appIcons : object

Which workspaces list their windows' icons in `icons`. All keys are optional:

- `enabledPopulated` : bool, workspaces with windows. Default `false`.
- `enabledActive` : bool, the workspace shown on the screen. Default `false`.
- `enabledFocused` : bool, the focused workspace. If not set, `enabledActive` is used.
- `maxIcons` : int, maximum icons per workspace. `0` means no limit. Default `0`.
- `hideFloating` : bool, skip floating windows. Default `false`.
- `hideDuplicates` : bool, one icon per app. Default `false`.

Default: `{}`

#### workspaces : list `read-only`

Workspaces, sorted by name (numbers in numeric order). Each is an object:

- `name` : string, workspace name. Used by `activateWorkspace()`.
- `displayName` : string, display name. `""` when GlazeWM gives none.
- `focused` : bool, `true` for the focused workspace.
- `displayed` : bool, `true` when shown on its monitor.
- `windowCount` : int, number of windows.
- `status` : string, `empty` or `populated`, prefixed with `focused_` for the focused workspace, or `active_` for
  the one shown on the screen with `monitorExclusive`. For example `focused_populated`.
- `icons` : list, window icons as chosen by `appIcons`, each `{hwnd, title, source}`: window handle, title, and
  image URL of the icon.

### Functions

#### activateWorkspace(name: string)

Focuses the workspace with this name.

#### switchWorkspace(direction: int)

`direction` above 0 (scroll up): previous workspace. Below 0: next workspace. Among GlazeWM's active workspaces, on
`screenName`'s monitor with `monitorExclusive`, or on all monitors without it.

## GlazewmTiling

### Properties

#### direction : string `read-only`

Tiling direction of the focused container: `horizontal` or `vertical`. `""` while not `connected`.

### Functions

#### toggleTilingDirection()

Switches the focused container between horizontal and vertical.

## GlazewmBindingModes

### Properties

#### name : string `read-only`

Name of the active binding mode. `""` when none is active or while not `connected`.

#### displayName : string `read-only`

Display name, or `name` when GlazeWM gives none.

#### active : bool `read-only`

`true` when a binding mode is active.

### Functions

#### enableBindingMode(name: string)

Turns on the binding mode with this name.

#### disableBindingMode()

Turns off the active binding mode.

## Used by

YASB's own GlazeWM workspaces widget uses GlazewmWorkspaceList, listed in [Widgets](./Widgets). No YASB widget
uses GlazewmTiling or GlazewmBindingModes.
