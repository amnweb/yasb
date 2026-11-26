# Audio visualizer

`import Yasb`

The level of each frequency band in the sound an output device plays, from bass to highs, updated many times a second,
for drawing a visualizer. It also reports whether sound is playing.

Changing any setting except `running` restarts the analysis. All AudioLevels objects that listen to the same
device share one capture.

## AudioLevels

### Properties

#### source : string

Output device to listen to. `"auto"` is the Windows default device. Otherwise the device's full name exactly as
Windows shows it, such as `"Speakers (Realtek(R) Audio)"`. While that device isn't active, the default device is
used.

Default: `"auto"`

#### bands : int

Number of bands, 2 to 128. With `stereo`, they are split between the left and right channel.

Default: `24`

#### stereo : bool

When `true`, the left and right channel get their own bands.

Default: `false`

#### monoChannel : string

What the bands show without `stereo`: `average` (both channels), `left` or `right`.

Default: `"average"`

#### reverse : bool

Reverses the band order. See `levels`.

Default: `false`

#### sensitivity : int

How high the bands go, 0 to 100. With `autoGain`: how hard the loudest bands push to the top. Without it: `50` is
the sound as it is, `100` is twice that.

Default: `50`

#### smoothness : int

0 to 100. Higher is smoother and slower.

Default: `55`

#### autoGain : bool

When `true`, quiet and loud music reach the same height.

Default: `true`

#### freqMin : int

Lowest frequency, in Hz. At least 20.

Default: `50`

#### freqMax : int

Highest frequency, in Hz. At most 24000.

Default: `12000`

#### framerate : int

Maximum updates of `levels` per second, 1 to 240.

Default: `60`

#### idleAfter : int

Milliseconds of silence before `playing` turns `false`. At least 100.

Default: `2000`

#### running : bool

Set it to `false` while the visualizer is hidden, for example `running: visible`. The analysis stops and the bands drop
to 0, but `playing` still updates.

Default: `true`

#### levels : list&lt;real&gt; `read-only`

Level of each band, 0 to 1. Falls to 0 when the sound stops. Order, left to right:

- Without `stereo`: bass to highs. With `reverse`: highs to bass.
- With `stereo`: left channel, then right channel, bass of both in the middle. With `reverse`: bass on the outer
  edges.

#### playing : bool `read-only`

`true` while sound plays. Stays `true` for `idleAfter` after the sound stops.

No functions or signals.

## Used by

YASB's own Audio visualizer widget, listed in [Widgets](./Widgets).
