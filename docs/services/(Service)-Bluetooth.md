# Bluetooth

`import Yasb`

Bluetooth radio state, connected devices, known devices and nearby devices, with functions to scan, connect,
disconnect and turn the radio on or off.

`radioOn` and `connected` always update. `devices` and `nearby` are only populated while `watching` is `true` (for
example while a popup is open). All BluetoothMonitor objects share one connection to Windows Bluetooth, which stays open
while at least one exists.

## BluetoothMonitor

### Properties

#### watching : bool

When `true`, `devices` and `nearby` are kept up to date. Turning it on reads the devices at once. Turning it off
clears `pending` and `busy`.

Default: `false`

#### radioOn : bool `read-only`

`true` when the Bluetooth radio is on.

#### connected : list&lt;string&gt; `read-only`

Names of the paired devices that are connected. Empty while the radio is off.

#### devices : list `read-only`

Devices Windows knows (paired or remembered), connected first. Only while `watching`, empty while the radio is off.
See [Row fields](#row-fields).

#### nearby : list `read-only`

Unpaired devices found by the last `scan()`. Only while `watching`, kept until the next scan. See
[Row fields](#row-fields).

#### busy : bool `read-only`

`true` while a refresh, scan or radio change is running.

#### pending : string `read-only`

Address of the device being connected or disconnected. `""` when none.

#### error : string `read-only`

Last error, such as a failed scan or connection. Cleared after 4 seconds.

### Functions

#### refresh()

Reads the known devices again. `busy` is `true` until done.

#### scan()

Searches for nearby devices for `nearby`. `busy` is `true` until done.

#### setRadio(on: bool)

Turns the radio on or off. Fails while a connection or another radio change is running, and sets `error`.

#### connectDevice(address: string)

Connects the device with this `address` (the `address` field of its row). Ignored while another device is
`pending`.

#### disconnectDevice(address: string)

Disconnects the device with this `address`. Ignored while another device is `pending`.

### Row fields

Fields of each row in `devices` and `nearby`, as `required property` in a delegate. Connected devices first, then
by name. Rows update in place.

#### address : string

Bluetooth address. Used by `connectDevice()` and `disconnectDevice()`.

#### name : string

Device name.

#### kind : string

Device type: `headphones`, `headset`, `speaker`, `phone`, `tablet`, `laptop`, `computer`, `keyboard`, `mouse`,
`controller`, `watch`, `camera` or `generic`.

#### connected : bool

`true` when connected.

#### known : bool

`true` when paired or remembered in Windows.

#### battery : int

Battery level, 0 to 100. `-1` when the device reports none or isn't connected.

#### profiles : list&lt;string&gt;

What a connected device does, such as `audio`, `mic` or `input`. Empty when not connected.

#### canConnect : bool

`true` when YASB can connect and disconnect it.

Both lists also have `count`, the number of devices.

## Used by

YASB's own Bluetooth widget, listed in [Widgets](./Widgets).
