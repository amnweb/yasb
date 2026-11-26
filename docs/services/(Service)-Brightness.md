# Brightness

`import Yasb`

Brightness of your screens and contrast of external monitors, read and set. Laptop screens are controlled through
Windows, external monitors through DDC/CI. Screens YASB can't control are not listed.

Laptop screens update as soon as Windows changes them. External monitors are read every `pollInterval`, because
their own buttons don't tell Windows. All DisplayBrightness objects share one reader.

## DisplayBrightness

### Properties

#### window : Window

The window whose screen `brightness` refers to. Use your widget's window: `root.Window.window`, where `root` is the
id of your widget's root item. `Window.window` alone doesn't work here, because DisplayBrightness isn't an item.
Without a window, `brightness` is `-1`.

Default: `null`

#### pollInterval : int

Seconds between readings of external monitors. `0` reads them only at start and on `refresh()`. The first
DisplayBrightness created sets it for all of them.

Default: `60`

#### brightness : int `read-only`

Brightness of the bar's screen, 0 to 100. `-1` when unknown or when YASB can't control that screen.

#### available : bool `read-only`

`true` when `brightness` is known, so `setBrightness()` works.

#### monitor : int `read-only`

The bar's screen, as the `monitor` field of its row in `displays`. `0` without a window.

#### displays : list `read-only`

All screens YASB can control, one row each. See [Row fields](#row-fields).

### Functions

#### setBrightness(value: int)

Sets the brightness of the bar's screen, 0 to 100. Ignored while `available` is `false`.

#### setDisplayBrightness(monitor: int, value: int)

Sets the brightness of one screen, 0 to 100. `monitor` is the `monitor` field of its row in `displays`.

#### setDisplayContrast(monitor: int, value: int)

Sets the contrast of one screen, 0 to 100. Screens with `contrast` `-1` have none.

#### refresh()

Reads the external monitors now.

#### isNight(start: string, end: string) : bool

`true` when the current time is between `start` and `end`, both `"hh:mm"`, such as `isNight("20:00", "07:00")`.
The range can cross midnight. Returns `false` for a time not written as `hh:mm`.

### Row fields

Fields of each row in `displays`, as `required property` in a delegate. Values update in place, so a slider being
dragged isn't rebuilt.

#### monitor : int

Windows' number for the screen. Used by `setDisplayBrightness()` and `setDisplayContrast()`. Always take it from
the row, don't store it.

#### name : string

Screen name as the monitor reports it, or `Monitor 1`, `Monitor 2` and so on when it reports none.

#### subtitle : string

Screen number, such as `Monitor 2`, followed by ` · ` and the connection type when Windows gives one.

#### brightness : int

Brightness, 0 to 100. `-1` when unknown.

#### contrast : int

Contrast, 0 to 100. `-1` when the screen has none.

`displays` also has `count`, the number of screens.

## Used by

YASB's own Brightness widget, listed in [Widgets](./Widgets).
