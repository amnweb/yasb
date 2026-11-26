# System tray

`import Yasb`

Tray icons of running apps (the icons next to the clock), split in two lists: pinned on the bar, and the rest
(usually shown in a popup). The order the user drags them into is saved per screen. All SystrayModel objects read
the same tray.

## SystrayModel

### Properties

#### screenName : string

Name of the screen the widget is on. Each screen keeps its own icon order, so set it to `bar.screenName`. Empty
means the primary screen.

Default: `""`

#### showBattery : bool

When `true`, Windows' own battery icon is included.

Default: `false`

#### showVolume : bool

When `true`, Windows' own volume icon is included.

Default: `false`

#### showNetwork : bool

When `true`, Windows' own network icon is included.

Default: `false`

#### hideIcons : list&lt;string&gt;

Apps whose icons are never shown, by program name without `.exe`, any case, such as `["discord", "OneDrive"]`.

Default: `[]`

#### useHook : bool

`true`: read the tray through YASB's hook in Explorer. `false`: through the legacy tray window. The legacy window
is also used where the hook can't run, such as under emulation. The first SystrayModel created decides for all
bars, changing it later has no effect until YASB restarts.

Default: `true`

#### pinnedIcons : list `read-only`

Icons pinned on the bar, in the user's order. See [Row fields](#row-fields).

#### unpinnedIcons : list `read-only`

The other icons, in the user's order. See [Row fields](#row-fields).

#### menuOpen : bool `read-only`

`true` while an app shows its menu after a click on one of `unpinnedIcons`. A popup showing those icons should stay
open while this is `true`, or the menu closes with it. Turns `false` when the menu closes, another window comes to
the front, or no menu appeared within two seconds.

Icons hidden by their app, or without an image yet, are in neither list.

### Functions

#### click(iconId: int, button: int)

Clicks the icon like the Windows tray does. `iconId` is the `iconId` field of its row. `button` is
`Qt.LeftButton`, `Qt.RightButton` or `Qt.MiddleButton`.

#### doubleClick(iconId: int)

Double-clicks the icon with the left button.

#### togglePinned(iconId: int)

Moves the icon from `pinnedIcons` to the end of `unpinnedIcons`, or back. Saves the order.

#### moveIcon(iconId: int, pinned: bool, index: int)

Moves the icon to `pinnedIcons` (`pinned` is `true`) or `unpinnedIcons`, before the icon at `index` in that list,
or to its end for `-1`. When the icon stays in the same list, `index` counts it too. Saves the order.

#### refresh()

Asks every app to add its icons again, for example after Explorer restarted.

### Row fields

Fields of each row in `pinnedIcons` and `unpinnedIcons`, as `required property` in a delegate. Rows update in
place, so a drag isn't interrupted.

#### iconId : int

Icon id. Used by the functions.

#### tip : string

Tooltip, or the app's program name when it has none.

#### source : string

Image URL of the icon. Changes when the app changes its icon. An `Image` delegate can't declare
`required property string source`, because `Image` has its own `source`: declare `required property var model`
and use `model.source`.

Both lists also have `count`, the number of icons.

## Used by

YASB's own System tray widget, listed in [Widgets](./Widgets).
