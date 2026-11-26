# OBS

`import Yasb`

OBS Studio's recording, streaming, virtual camera, studio mode and program scene, with functions to toggle them.
Connects to OBS's WebSocket server (obs-websocket 5). While OBS isn't running, YASB retries every 5 seconds and the
data is empty. All ObsStudio objects with the same host, port and password share one connection.

## ObsStudio

### Properties

#### host : string

Host of OBS's WebSocket server.

Default: `"localhost"`

#### port : int

Port of OBS's WebSocket server.

Default: `4455`

#### password : string

Password of OBS's WebSocket server. Empty when its authentication is off.

Default: `""`

#### connected : bool `read-only`

`true` once OBS has accepted the connection.

#### error : string `read-only`

`"OBS refused the password."` when the password is wrong, otherwise `""`.

#### recording : object `read-only`

- `active` : bool, `true` while recording.
- `paused` : bool, `true` while the recording is paused.
- `duration` : int, milliseconds recorded.

#### streaming : object `read-only`

- `active` : bool, `true` while streaming.
- `reconnecting` : bool, `true` while the stream reconnects.
- `duration` : int, milliseconds streamed.
- `congestion` : real, from 0 to 1.
- `skippedFrames` : int, frames skipped.
- `totalFrames` : int, frames sent.

`recording` is read again every second while recording, and `streaming` while streaming.

#### virtualCam : bool `read-only`

`true` while the virtual camera is on.

#### studioMode : bool `read-only`

`true` while studio mode is on.

#### scene : string `read-only`

Name of the program scene.

### Functions

All of them are ignored while `connected` is `false`.

#### toggleRecord()

Starts or stops recording.

#### toggleRecordPause()

Pauses or resumes the recording.

#### toggleStream()

Starts or stops streaming.

#### toggleVirtualCam()

Turns the virtual camera on or off.

#### toggleStudioMode()

Turns studio mode on or off.

ObsStudio has no signals.

## Used by

YASB's own OBS widget, listed in [Widgets](./Widgets).
