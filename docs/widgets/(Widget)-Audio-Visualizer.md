# Audio Visualizer Widget Configuration

Native audio visualizer for the default output device (WASAPI loopback). No external audio app or process needed.

## How it captures audio

Audio comes from a WASAPI loopback capture on whatever Windows currently has set as the default playback device - the same device shown selected in the Windows volume mixer. This is automatic and dynamic: there is no device picker, and switching outputs (plugging in headphones, disabling a device, changing the default in Windows sound settings) is picked up on its own, with capture rebuilding against the new endpoint.

Because of that, only audio going through the normal Windows shared-mixer path is visible. Anything routed through **ASIO**, or another driver model that bypasses the shared mixer for direct hardware access, never reaches this capture, since that audio doesn't pass through the default device's loopback path at all - a limitation of WASAPI loopback itself, not something specific to this widget. If an app is set to output via ASIO, the visualizer will sit silent for that app's audio while continuing to show anything else still playing through the normal output.

## Shared options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `class_name` | string | `""` | Additional CSS class names for the widget container |
| `style` | string | `"bars"` | Visual style: `"bars"`, `"waves"`, or `"dots"` |
| `height` | integer | `14` | Paint surface height in pixels |
| `smoothness` | integer | `55` | Motion smoothing 0–100 (higher = smoother, slower). Expressed in real time, so the motion looks identical at any `framerate` |
| `sensitivity` | integer | `50` | Amplitude trim 0–100. With `auto_gain` on it sets how hard the peaks push: `50` = loudest bars ride near the top, lower = calmer, higher = into the ceiling. With `auto_gain` off it is a plain multiplier (`50` = 1×, `100` = 2×) |
| `auto_gain` | boolean | `true` | Auto-sensitivity: continuously tracks the level so quiet tracks and loud tracks look the same and bars never pin flat at the top. Turn off to set the level yourself with `sensitivity` |
| `framerate` | integer | `60` | Upper limit on repaints per second. Frames are pushed by the audio stream, so the real rate is also capped by the device period |
| `freq_min` | integer | `50` | Lowest frequency bucket in Hz (20–24000) |
| `freq_max` | integer | `12000` | Highest frequency bucket in Hz (must be greater than `freq_min`) |
| `hide_idle` | boolean | `false` | Collapse the widget once audio stops, freeing its space in the bar. It reappears the moment audio returns |
| `hide_idle_after` | integer | `2000` | How long audio must be absent before collapsing (ms) |
| `channels` | string | `"mono"` | Visual channels: `"stereo"` or `"mono"` |
| `mono_option` | string | `"average"` | Mono input source: `"average"`, `"left"`, or `"right"` (ignored when `channels` is `"stereo"`) |
| `reverse` | boolean | `false` | Flip frequency direction |
| `gradient` | boolean | `true` | Bars/waves: gradient across `colors`. `false` = solid `colors[0]`. Dots always cycle `colors` per column |
| `mirror` | boolean | `false` | Grow from the vertical center instead of the bottom edge, symmetric up and down. Applies to all three styles |
| `colors` | list[string] | see example | Hex color palette |
| `edge_fade` | integer or array | `0` | Edge fade in pixels. Single value, or `[left, right]` |
| `callbacks` | dict | do_nothing | Mouse callbacks: `on_left`, `on_middle`, `on_right` |

## Style blocks

Only the block matching `style` is used; the others are ignored.

### `bars`

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `count` | integer | `24` | Number of bar columns (4–128). With `channels: stereo` the count is split between the two channels. Past roughly 40 the extra bars mostly subdivide the low end rather than add detail (see [Levels](#levels)) |
| `width` | integer | `2` | Bar thickness in pixels |
| `gap` | integer | `4` | Gap between bars in pixels |

### `waves`

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `width` | integer | `80` | Total widget width in pixels. Spectrum point count is derived automatically |

### `dots`

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `count` | integer | `24` | Number of LED columns (4–128) |
| `size` | integer | `2` | Block size in pixels |
| `gap` | integer | `4` | Gap between stacked blocks (also used between columns) |

## Example Configuration

```yaml
  audio_visualizer:
    type: "yasb.audio_visualizer.AudioVisualizerWidget"
    options:
      style: bars
      height: 16
      smoothness: 80
      sensitivity: 50
      auto_gain: true
      framerate: 60
      freq_min: 500
      freq_max: 12000
      hide_idle: true
      hide_idle_after: 2000
      channels: mono
      mono_option: average
      reverse: false
      gradient: true
      mirror: false
      colors:
        - "#8A9AFF"
        - "#8A8AFF"
        - "#C38AFF"
      bars:
        count: 24
        width: 2
        gap: 4
      waves:
        width: 80
      dots:
        count: 24
        size: 2
        gap: 4
```

## Styles

- **bars**: sharp rectangular frequency bars.
- **waves**: same spectrum as bars, connected into a filled outline. With stereo, left and right halves are drawn separately.
- **dots**: LED-style stacked square blocks per column.

## Levels

`auto_gain` (on by default) is an auto-sensitivity loop: it backs off quickly when a band saturates and creeps back up when there is headroom, with a hard ramp on startup so the level settles in under a second. The result is that a quiet track and a loud track look the same, and bars never sit pinned flat at the top.

`sensitivity` rides on top. With `auto_gain` on it sets the target the auto-level aims for: `50` keeps the loudest bars near the top, lower leaves headroom for a calmer look, higher pushes them into the ceiling for a hotter, more clipped look. It does not fight the auto-level, so a quiet track and a loud track still match at the same `sensitivity`. With `auto_gain: false` it becomes the only level control, a plain fixed multiplier (`50` = ×1, `100` = ×2).

The bar heights stay roughly consistent as you change the `count`. More bars means finer frequency resolution, so the tallest bars reach about the same height either way but there are more short bars filling the gaps between peaks.

## Channels

- **`channels: mono`**: one spectrum across the strip, lowest to highest left to right. Use `mono_option` to pick `"average"`, `"left"`, or `"right"` as the input.
- **`channels: stereo`**: mirrors both channels with low frequencies in the center (left half = L, right half = R).
- **`reverse: true`**: flips frequency direction.
  - mono: highest to lowest left to right
  - stereo: bass moves to the outer edges, highs meet in the center

## Style

```css
.audio-visualizer-widget {
    padding: 0;
    margin: 0;
}
.audio-visualizer-widget .widget-container {
    padding: 0;
    margin: 0;
}
```
