# GPU

`import Yasb`

Graphics card usage and memory, plus temperature and fan on NVIDIA and AMD cards, and power draw on NVIDIA cards.
Updated every `updateInterval`. Usage is the busiest engine of the card, as in Task Manager.

All GpuMonitor objects share one reader, so the `updateInterval` set last applies to all of them.

## GpuMonitor

### Properties

#### gpuIndex : int

Which card, from 0, in the order Windows lists them. Windows' software renderer is not counted.

Default: `0`

#### updateInterval : int

Milliseconds between readings, 2000 to 60000.

Default: `2000`

#### available : bool `read-only`

`true` once the card at `gpuIndex` has been read. Stays `false` if there is no such card.

#### data : object `read-only`

- `index` : int, the `gpuIndex`.
- `name` : string, card name, as Windows gives it.
- `utilization` : real, usage, 0 to 100.
- `mem_total` : int, dedicated memory, in bytes.
- `mem_used` : int, dedicated memory in use, in bytes.
- `mem_free` : int, dedicated memory free, in bytes.
- `mem_shared_total` : int, shared system memory, in bytes.
- `mem_shared_used` : int, shared memory in use, in bytes.
- `temp` : int, temperature, in °C.
- `fan_speed` : int, fan speed, in percent.
- `power_draw` : real, power draw, in W.

`temp` and `fan_speed` are `0` on cards other than NVIDIA and AMD. `power_draw` is `0` on cards other than NVIDIA.
Before the first reading, all values are `0` or `""`.

No functions or signals.

## Used by

YASB's own GPU widget, listed in [Widgets](./Widgets).
