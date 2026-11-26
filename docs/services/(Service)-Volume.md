# Volume

`import Yasb`

Default output device, its volume and mute state, all output devices, and the apps playing sound, with functions to
change them. Updates when the volume or devices change in Windows. `apps` updates on `refreshApps()`. All AudioOutput
objects share one connection to Windows audio.

## AudioOutput

### Properties

#### available : bool `read-only`

`true` when Windows has a default output device. Without one, `volume` is `0`, `apps` stays empty, and
`setVolume()` and `setMuted()` do nothing.

#### deviceName : string `read-only`

Name of the default output device.

#### devices : list `read-only`

All active output devices. Each is an object:

- `id` : string, device id. Used by `setDevice()`.
- `name` : string, device name.
- `current` : bool, `true` for the default output device.

#### volume : int `read-only`

Volume of the default output device, 0 to 100.

#### muted : bool `read-only`

`true` when the default output device is muted.

#### apps : list `read-only`

The apps with an audio session on the default output device, one per process and session group, as of the last
`refreshApps()`, sorted by name. Empty until then. Each is an object:

- `key` : int, used by `setAppVolume()` and `setAppMuted()`. Valid until the next `refreshApps()`.
- `pid` : int, the app's process id.
- `name` : string, the app's name, or a cleaned-up version of its process name.
- `process` : string, the process name, such as `chrome.exe`.
- `appId` : string, the app's id in Windows. `""` when it has none.
- `volume` : int, the app's volume, 0 to 100.
- `muted` : bool, `true` when the app is muted.
- `icon` : string, image URL of the app's icon.

Some system processes, such as `audiodg.exe` and `svchost.exe`, are left out.

### Functions

#### setVolume(value: int)

Sets the volume, 0 to 100.

#### setMuted(muted: bool)

Mutes or unmutes.

#### toggleMute()

Switches between muted and unmuted.

#### setDevice(id: string)

Makes this output device Windows' default device. Windows' default communications device doesn't change.

#### refreshApps()

Reads `apps` again. Also runs automatically when the default output device changes, once `apps` has been read.

#### setAppVolume(key: int, value: int)

Sets the app's volume, 0 to 100. `apps` isn't sent again, so a slider being dragged isn't rebuilt.

#### setAppMuted(key: int, muted: bool)

Mutes or unmutes the app.

#### beep()

Plays Windows' beep, as `MessageBeep(0)` does.

AudioOutput has no signals.

## Used by

YASB's own Volume and Media widgets, listed in [Widgets](./Widgets).
