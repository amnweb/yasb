# Do not disturb

`import Yasb`

Windows Do not disturb (Focus Assist) status, with functions to change it. Updates when the status changes in
Windows, from Settings, the notification center or YASB.

## DoNotDisturb

### Properties

#### status : string `read-only`

Current mode: `disabled` (off), `priority` (priority notifications only) or `alarms` (alarms only). `unknown`
until YASB has read it, or if Windows doesn't support Do not disturb.

#### available : bool `read-only`

`true` when `status` is known. The functions do nothing while this is `false`.

#### active : bool `read-only`

`true` when Do not disturb is on (`priority` or `alarms`).

### Functions

#### setStatus(mode: string)

Sets the mode: `disabled`, `priority` or `alarms`. Any other value is ignored.

#### toggle(mode: string)

If Do not disturb is off, turns it on with `mode` (`priority` or `alarms`). If it is on, turns it off.

#### cycle()

Switches to the next mode: `disabled` → `priority` → `alarms` → `disabled`.

## Used by

YASB's own Do not disturb widget, listed in [Widgets](./Widgets).
