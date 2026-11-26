# Microphone

`import Yasb`

Default microphone, its level and mute state, and all connected microphones, with functions to change them.
Updates when anything changes in Windows. All AudioInput objects share one connection to Windows audio.

## AudioInput

### Properties

#### available : bool `read-only`

`true` when Windows has a default microphone. Without one, `volume` is `0` and the functions do nothing.

#### deviceName : string `read-only`

Name of the default microphone.

#### devices : list `read-only`

All connected microphones. Each is an object:

- `id` : string, device id. Used by `setDevice()`.
- `name` : string, device name.
- `current` : bool, `true` for the default microphone.

#### volume : int `read-only`

Level of the default microphone, 0 to 100.

#### muted : bool `read-only`

`true` when the default microphone is muted.

### Functions

#### setVolume(value: int)

Sets the level, 0 to 100. `0` also mutes, above `0` unmutes.

#### setMuted(muted: bool)

Mutes or unmutes.

#### toggleMute()

Switches between muted and unmuted.

#### setDevice(id: string)

Makes this microphone Windows' default device. Windows' default communications device doesn't change.

## Used by

YASB's own Microphone widget, listed in [Widgets](./Widgets).
