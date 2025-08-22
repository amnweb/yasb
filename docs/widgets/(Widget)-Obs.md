# OBS Widget Options

ObsWidget is a custom widget that integrates with OBS (Open Broadcaster Software) via WebSocket to display and control recording status.

| Option           | Type     | Default                        | Description                                                                 |
|------------------|----------|--------------------------------|-----------------------------------------------------------------------------|
| `connection`          | dict   | `{host: "192.168.1.5", port: 4455, password: "123456"}`                     | Connection info for OBS WebSocket Server  |
| `icons`      | dict   | `{recording: "\ueba7", stopped: "\ueba5", paused: "\ueba7"}`       | The alternative format string for the label. Useful for displaying additional notification details. |
| `hide_when_not_recording`| boolean  | `true`                          | Hide widget when OBS and recording are not running. |
| `blinking_icon`          | boolean   | `true`                           | Blink icons when recording is active. |

## Example Configuration

```yaml
obs:
  type: "yasb.obs.ObsWidget"
  options:  
    connection:
      host: "192.168.1.5"
      port: 4455
      password: "123456"
    icons:
      recording: "\ueba7"
      stopped: "\ueba5"
      paused: "\ueba7"
    hide_when_not_recording: true
    blinking_icon: true
```
## Description of Options

- **connection:** Connection info for OBS WebSocket Server. Go to Tools -> WebSocket Server Settings in OBS to enable the WebSocket server.
- **icons:**  Icons for different recording states.
- **hide_when_not_recording:** Hide widget when OBS and recording are not running.
- **blinking_icon:** Blink icons when recording is active.

## Example Style
```css
.obs-widget  {
    padding: 0 5px;
}
.obs-widget .recording {
    font-size: 18px;
    color: #ff3b3b;
}
.obs-widget .paused {
    font-size: 18px;
    color: #bfc93b;
}
.obs-widget .stopped {
    font-size: 18px;
    color: #756e70;
}
```