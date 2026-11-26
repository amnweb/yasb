# Recycle bin

`import Yasb`

How many items the Recycle Bin holds and their size, with functions to open and empty it. Updates when the bin
changes on a fixed drive, at most every half second. All RecycleBin objects share one watch.

## RecycleBin

### Properties

#### itemCount : int `read-only`

Items in the Recycle Bin. `0` until the first reading.

#### sizeBytes : int `read-only`

Size of the items, in bytes. `0` until the first reading.

### Functions

#### open()

Opens the Recycle Bin in File Explorer.

#### empty()

Empties the Recycle Bin, without a sound. Windows asks to confirm and shows its progress. Ignored while the bin is
being emptied.

RecycleBin has no signals.

## Used by

No YASB widget creates it. The [Taskbar](./(Service)-Taskbar) service shares its watch while the Recycle Bin is
pinned.
