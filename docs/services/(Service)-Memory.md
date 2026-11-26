# Memory

`import Yasb`

RAM in use and free, cached memory, and the page file, updated every `updateInterval`.

All MemoryMonitor objects share one reader, so the `updateInterval` set last applies to all of them.

## MemoryMonitor

### Properties

#### updateInterval : int

Milliseconds between readings, 1000 to 60000.

Default: `5000`

#### data : object `read-only`

All sizes in bytes.

- `virtual` : object, installed RAM:
  - `total` : int, total.
  - `used` : int, in use.
  - `available` : int, free for apps, including cached memory.
  - `free` : int, same as `available`.
  - `percent` : real, `used` as a percent of `total`, one decimal.
- `swap` : object, page file:
  - `total` : int, size.
  - `used` : int, in use.
  - `free` : int, free.
  - `percent` : real, `used` as a percent of `total`, one decimal.
- `cached_bytes` : int, cached memory, as Task Manager shows under Cached.

Before the first reading, all values are `0`.

No functions or signals.

## Used by

YASB's own Memory widget, listed in [Widgets](./Widgets).
