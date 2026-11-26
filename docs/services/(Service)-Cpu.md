# CPU

`import Yasb`

CPU usage (total and per core), CPU frequency, and core count, updated every `updateInterval`.

All CpuMonitor objects share one reader, so the `updateInterval` set last applies to all of them.

## CpuMonitor

### Properties

#### updateInterval : int

Milliseconds between two readings, from 1000 to 60000.

Default: `1000`

#### data : object `read-only`

The processor, after the last reading:

- `percent` : object, how busy it is, from 0 to 100, rounded to one decimal:
  - `total` : real, the whole processor.
  - `core` : list&lt;real&gt;, each logical core, in order.
- `freq` : object, how fast it runs, in MHz:
  - `current` : real, its speed now. It isn't capped at `max`.
  - `max` : real, its base speed.
  - `min` : real, always `0`.
- `cores` : object, how many cores it has:
  - `physical` : int, the physical cores.
  - `total` : int, the logical cores, as many as `percent.core` has.

Until the first reading, the usage and the speeds are `0`, and both core counts `1`.

CpuMonitor has no functions or signals.

## Used by

YASB's own CPU widget, listed in [Widgets](./Widgets).
