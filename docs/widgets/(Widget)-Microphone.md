# Microphone Widget Configuration

| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`           | string  | `'{icon}'`                        | The format string for the microphone widget. Displays icon or level. |
| `label_alt`       | string  | `'{icon} {level}%'`        | The alternative format string for the microphone widget. Displays icon or level. |
| `icons`       | dict    | `{'normal', 'muted'` | Icons for microphone widget |
| `callbacks`       | dict    | `{'on_left': 'toggle_mute', 'on_middle': 'toggle_label', 'on_right': 'do_nothing'}` | Callbacks for mouse events on the memory widget. |


## Example Configuration

```yaml
microphone:
  type: "yasb.microphone.MicrophoneWidget"
  label: '<span>{icon}</span>'
  label_alt: '<span>{icon}</span> {level}%'
  icons:
    normal: "\uf130"
    muted: "\uf131"
  callbacks:
    on_left: 'toggle_mute'
    on_middle: 'toggle_label'
    on_right: 'exec cmd.exe /c start ms-settings:sound'
```

## Description of Options

- **label:** The format string for the microphone widget. Displays the microphone icon or level.
- **label_alt:** The alternative format string for the microphone widget. Displays the microphone icon or level.
- **icons:** A dictionary specifying the icons for the microphone widget. The keys are `normal` and `muted`, and the values are the unicode characters for the icons.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.


## Example Style
```css
.microphone-widget {}
.microphone-widget .widget-container {}
.microphone-widget .label {}
.microphone-widget .label.alt {}
.microphone-widget .icon {}
```