# Power mode

`import Yasb`

Windows' power mode when plugged in and on battery, with a function to change it. Read when first used and on
`refresh()`, changes made in Windows Settings show only after `refresh()`.

PowerModes is a singleton: use it by its name, without creating it.

## PowerModes

### Properties

#### modes : list `read-only`

The three power modes, each an object:

- `id` : string, `efficiency`, `balanced` or `performance`.
- `name` : string, `Best power efficiency`, `Balanced` or `Best performance`.

#### acModeId : string `read-only`

`id` of the mode when plugged in. `""` when it is none of the three, or not `supported`.

#### dcModeId : string `read-only`

`id` of the mode on battery. `""` when it is none of the three, or not `supported`.

#### supported : bool `read-only`

`true` when Windows has power modes and the active power plan is a Balanced one.

#### loading : bool `read-only`

`true` while the modes are read or changed.

#### error : string `read-only`

Last error, `""` when none. Cleared when the next read or change starts.

- `Invalid power mode or power source.`: `setMode()` got a value it doesn't know.
- `Windows did not apply the requested power mode.`: Windows kept another mode.
- `Could not change the power mode.`, sometimes followed by Windows' reason: the change failed.
- `Could not read Windows power modes.` or `Windows did not return an active power plan.`: reading failed.

### Functions

#### refresh()

Reads the modes again. Ignored while `loading`.

#### setMode(modeId: string, source: string)

Sets the mode with this `id` for `source`: `ac` (plugged in) or `dc` (on battery). Ignored while `loading`, or
while not `supported`.

PowerModes has no signals.

## Used by

No YASB widget uses it.
