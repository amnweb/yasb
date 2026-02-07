# OBS Widget Options

ObsWidget is a custom widget that integrates with OBS (Open Broadcaster Software) via WebSocket to display and control recording, streaming, virtual camera, studio mode, current scene name, and live stream statistics.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `connection` | dict | `{host: "localhost", port: 4455, password: ""}` | Connection info for OBS WebSocket Server |
| `icons` | dict | See below | Icons for recording states, virtual camera, studio mode, and streaming |
| `hide_when_not_recording` | boolean | `false` | Hide widget when not recording |
| `blinking_icon` | boolean | `true` | Blink record/stream icon when active |
| `show_record_time` | boolean | `false` | Show recording duration |
| `show_virtual_cam` | boolean | `false` | Show virtual camera status button |
| `show_studio_mode` | boolean | `false` | Show studio mode status button |
| `show_stream` | boolean | `false` | Show stream status button |
| `show_stream_time` | boolean | `false` | Show streaming duration |
| `show_scene_name` | boolean | `false` | Show current OBS program scene name |
| `show_stream_stats` | boolean | `false` | Show stream bitrate (kbps) and dropped frames while streaming |
| `tooltip` | boolean | `true` | Enable or disable tooltips for buttons |
| `container_padding` | dict | `{top: 0, left: 0, bottom: 0, right: 0}` | Padding around the widget container |


## Example Configuration

```yaml
obs:
  type: "yasb.obs.ObsWidget"
  options:
    connection:
      host: "localhost"
      port: 4455
      password: "your_password"
    icons:
      recording: "\ueba7"
      stopped: "\ueba7"
      paused: "\ueba7"
      virtual_cam_on: "\udb81\udda0"
      virtual_cam_off: "\udb81\udda0"
      studio_mode_on: "\udb84\uddd8"
      studio_mode_off: "\udb84\uddd8"
      streaming: "\udb82\udd02"
      streaming_stopped: "\udb82\udd02"
    hide_when_not_recording: false
    blinking_icon: true
    show_record_time: true
    show_virtual_cam: true
    show_studio_mode: true
    show_stream: true
    show_stream_time: true
    show_scene_name: true
    show_stream_stats: true
    tooltip: true
```

## Description of Options

- **connection:** Connection info for OBS WebSocket Server. Go to Tools -> WebSocket Server Settings in OBS to enable the WebSocket server.
- **icons:** Icons for different states:
  - `recording`, `stopped`, `paused` - Record button states
  - `virtual_cam_on`, `virtual_cam_off` - Virtual camera button states
  - `studio_mode_on`, `studio_mode_off` - Studio mode button states
  - `streaming`, `streaming_stopped` - Stream button states
- **hide_when_not_recording:** Hide the entire widget when not recording.
- **blinking_icon:** Blink the record/stream icon when active (opacity toggles between 0.6 and 1.0).
- **show_record_time:** Display recording duration next to the record button.
- **show_virtual_cam:** Show a clickable button for virtual camera status.
- **show_studio_mode:** Show a clickable button for studio mode status.
- **show_stream:** Show a clickable button for stream status.
- **show_stream_time:** Display streaming duration next to the stream button.
- **show_scene_name:** Display the current OBS program scene name. Updates automatically when the scene changes.
- **show_stream_stats:** Display stream bitrate (kbps) and dropped frames count (e.g. `3500 kbps 5/2400 dropped`) while streaming. Updates every second.
- **tooltip:** Enable or disable tooltips on hover for all buttons.

## Click Behavior

Each button in the widget responds to left click:

| Button | Left Click Action |
|--------|-------------------|
| Record button | Toggle recording (start/stop) |
| Virtual camera button | Toggle virtual camera on/off |
| Studio mode button | Toggle studio mode on/off |
| Stream button | Toggle stream on/off |

## Callbacks (Hotkey Only)

Callbacks are available only via keybindings and cannot be assigned to mouse clicks on the widget.

| Callback | Description |
|----------|-------------|
| `toggle_record` | Toggle recording on/off |
| `start_record` | Start recording |
| `stop_record` | Stop recording |
| `pause_record` | Pause recording |
| `resume_record` | Resume recording |
| `toggle_record_pause` | Toggle pause/resume |
| `toggle_virtual_cam` | Toggle virtual camera |
| `toggle_studio_mode` | Toggle studio mode |
| `toggle_stream` | Toggle stream on/off |
| `start_stream` | Start streaming |
| `stop_stream` | Stop streaming |

### Keybinding Example

```yaml
obs:
  type: "yasb.obs.ObsWidget"
  options:
    # ... other options
    keybindings:
      - keys: "ctrl+shift+r"
        action: "toggle_record"
      - keys: "ctrl+shift+p"
        action: "toggle_record_pause"
      - keys: "ctrl+shift+v"
        action: "toggle_virtual_cam"
      - keys: "ctrl+shift+b"
        action: "toggle_stream"
```

## Example Style

```css
.obs-widget {
    padding: 0 5px;
}
.obs-widget .widget-container {
    /* Container for all buttons */
}
/* Icon styles (all icons) */
.obs-widget .icon {
    min-width: 20px;
    max-width: 20px;
    font-size: 14px;
    min-height: 24px;
}
/* Record button states (icon class) */
.obs-widget .icon.record.recording {
    color: #ff3b3b;
}
.obs-widget .icon.record.paused {
    color: #bfc93b;
}
.obs-widget .icon.record.stopped {
    color: #90939c;
}

/* Record time label (label class) */
.obs-widget .label.record-time {
    font-size: 12px;
    font-family: "Segoe UI";
    color: #ffffff;
}

/* Virtual camera button (icon class) */
.obs-widget .icon.virtual-cam.on {
    color: #c4ff3b;
}
.obs-widget .icon.virtual-cam.off {
    color: #90939c;
}

/* Studio mode button (icon class) */
.obs-widget .icon.studio-mode.on {
    color: #3ba0ff;
}
.obs-widget .icon.studio-mode.off {
    color: #90939c;
}

/* Stream button (icon class) */
.obs-widget .icon.stream.on {
    color: #ff3b3b;
}
.obs-widget .icon.stream.off {
    color: #90939c;
}
.obs-widget .icon.stream.starting {
    color: #ffaa3b;
}
.obs-widget .icon.stream.stopping {
    color: #ffaa3b;
}

/* Stream time label (label class) */
.obs-widget .label.stream-time {
    font-size: 12px;
    font-family: "Segoe UI";
    color: #ffffff;
}

/* Scene name label (label class) */
.obs-widget .label.scene-name {
    font-size: 12px;
    font-family: "Segoe UI";
    color: #c4ff3b;
}

/* Stream stats label (label class) */
.obs-widget .label.stream-stats {
    font-size: 12px;
    font-family: "Segoe UI";
    color: #aaaaaa;
}
```