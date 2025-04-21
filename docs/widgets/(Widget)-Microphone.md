# Microphone Widget Configuration

| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`           | string  | `'{icon}'`                        | The format string for the microphone widget. Displays icon or level. |
| `label_alt`       | string  | `'{icon} {level}%'`        | The alternative format string for the microphone widget. Displays icon or level. |
| `tooltip`  | boolean  | `True`        | Whether to show the tooltip on hover. |
| `icons`       | dict    | `{'normal', 'muted'` | Icons for microphone widget |
| `callbacks`       | dict    | `{'on_left': 'toggle_mute', 'on_middle': 'toggle_label', 'on_right': 'do_nothing'}` | Callbacks for mouse events on the memory widget. |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.                            |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |

## Example Configuration

```yaml
microphone:
  type: "yasb.microphone.MicrophoneWidget"
  options:
    label: "<span>{icon}</span>"
    label_alt: "<span>{icon}</span> {level}%"
    icons:
      normal: "\uf130"
      muted: "\uf131"
    callbacks:
      on_left: "toggle_mute"
      on_middle: "toggle_label"
      on_right: "exec cmd.exe /c start ms-settings:sound"
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Description of Options

- **label:** The format string for the microphone widget. Displays the microphone icon or level.
- **label_alt:** The alternative format string for the microphone widget. Displays the microphone icon or level.
- **tooltip:** Whether to show the tooltip on hover.
- **icons:** A dictionary specifying the icons for the microphone widget. The keys are `normal` and `muted`, and the values are the unicode characters for the icons.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.

## Example Style
```css
.microphone-widget {}
.microphone-widget .widget-container {}
.microphone-widget .label {}
.microphone-widget .label.alt {}
.microphone-widget .icon {}
```