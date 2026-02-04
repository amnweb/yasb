# OBS Widget Options

ObsWidget is a custom widget that integrates with OBS (Open Broadcaster Software) via WebSocket to display and control recording status, virtual camera, and studio mode.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `connection` | dict | `{host: "localhost", port: 4455, password: ""}` | Connection info for OBS WebSocket Server |
| `icons` | dict | See below | Icons for recording states, virtual camera, and studio mode |
| `hide_when_not_recording` | boolean | `false` | Hide widget when not recording |
| `blinking_icon` | boolean | `true` | Blink record icon when recording is active |
| `show_record_time` | boolean | `false` | Show recording duration |
| `show_virtual_cam` | boolean | `false` | Show virtual camera status button |
| `show_studio_mode` | boolean | `false` | Show studio mode status button |
| `tooltip` | boolean | `true` | Enable or disable tooltips for buttons |


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
    hide_when_not_recording: false
    blinking_icon: true
    show_record_time: true
    show_virtual_cam: true
    show_studio_mode: true
    tooltip: true
```

## Description of Options

- **connection:** Connection info for OBS WebSocket Server. Go to Tools -> WebSocket Server Settings in OBS to enable the WebSocket server.
- **icons:** Icons for different states:
  - `recording`, `stopped`, `paused` - Record button states
  - `virtual_cam_on`, `virtual_cam_off` - Virtual camera button states
  - `studio_mode_on`, `studio_mode_off` - Studio mode button states
- **hide_when_not_recording:** Hide the entire widget when not recording.
- **blinking_icon:** Blink the record icon when recording is active (opacity toggles between 0.6 and 1.0).
- **show_record_time:** Display recording duration next to the record button.
- **show_virtual_cam:** Show a clickable button for virtual camera status.
- **show_studio_mode:** Show a clickable button for studio mode status.
- **tooltip:** Enable or disable tooltips on hover for all buttons.

## Click Behavior

Each button in the widget responds to left click:

| Button | Left Click Action |
|--------|-------------------|
| Record button | Toggle recording (start/stop) |
| Virtual camera button | Toggle virtual camera on/off |
| Studio mode button | Toggle studio mode on/off |

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
    margin: 0 8px;
}
/* Record button states (icon class) */
.obs-widget .icon.record.recording {
    font-size: 18px;
    color: #ff3b3b;
}
.obs-widget .icon.record.paused {
    font-size: 18px;
    color: #bfc93b;
}
.obs-widget .icon.record.stopped {
    font-size: 18px;
    color: #756e70;
}

/* Record time label (label class) */
.obs-widget .label.record-time {
    font-size: 12px;
    font-family: "Segoe UI";
    color: #ffffff;
}

/* Virtual camera button (icon class) */
.obs-widget .icon.virtual-cam.on {
    font-size: 18px;
    color: #c4ff3b;
}
.obs-widget .icon.virtual-cam.off {
    font-size: 18px;
    color: #756e70;
}

/* Studio mode button (icon class) */
.obs-widget .icon.studio-mode.on {
    font-size: 18px;
    color: #3ba0ff;
}
.obs-widget .icon.studio-mode.off {
    font-size: 18px;
    color: #756e70;
}
```