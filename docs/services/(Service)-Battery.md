# Battery

`import Yasb`

Battery charge, charging state and time left, plus rate, voltage, capacity, temperature, cycle count and health
where the battery reports them. Updated every `updateInterval`.

## BatteryMonitor

### Properties

#### updateInterval : int

Milliseconds between readings, 1000 to 60000.

Default: `5000`

#### available : bool `read-only`

`true` when the PC has a battery. Without one, `data` holds zeros and nulls.

#### data : object `read-only`

- `percent` : int, charge, 0 to 100.
- `charging` : bool, `true` while charging.
- `pluggedIn` : bool, `true` while on power.
- `timeRemaining` : int, time left in seconds. `-1` when Windows has no estimate. `-2` when there is no estimate
  and the PC is on power.
- `timeUnknown` : bool, `true` when `timeRemaining` is `-1`.
- `timeUnlimited` : bool, `true` when `timeRemaining` is `-2`.
- `timeText` : string, time left as `H:MM:SS`, such as `"1:42:10"`. `""` without an estimate.
- `timeNatural` : string, time left in words. `""` without an estimate.
- `rate` : real, charge or discharge rate, in W.
- `voltage` : real, voltage, in V.
- `capacity` : int, current capacity, as the battery reports it.
- `fullCapacity` : int, capacity when full, same unit.
- `designedCapacity` : int, capacity when new, same unit.
- `temperature` : real, temperature in °C, one decimal.
- `cycleCount` : int, number of charge cycles.
- `health` : real, `fullCapacity` as a percent of `designedCapacity`, one decimal.
- `chemistry` : string, battery chemistry, as the battery reports it.

Keys from `rate` down are `null` when the battery doesn't report them.

### Functions

#### refresh()

Reads the battery now.

## Used by

YASB's own Battery widget, listed in [Widgets](./Widgets).
