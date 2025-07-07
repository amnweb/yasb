# Microphone Widget Configuration

| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`           | string  | `'{icon}'`                        | The format string for the microphone widget. Displays icon or level. |
| `label_alt`       | string  | `'{icon} {level}'`        | The alternative format string for the microphone widget. Displays icon or level. |
| `mute_text` | string  | `'mute'` | Text used by `{level}` to indicate muted volume |
| `tooltip`  | boolean  | `True`        | Whether to show the tooltip on hover. |
| `scroll_step`     | int     | `2`                  | The step size for volume adjustment when scrolling. The value is in percentage points (0-100). |
| `icons`       | dict    | `{'normal', 'muted'` | Icons for microphone widget |
| `callbacks`       | dict    | `{'on_left': 'toggle_mute', 'on_middle': 'toggle_label', 'on_right': 'do_nothing'}` | Callbacks for mouse events on the memory widget. |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.                            |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |
| `mic_menu` | dict | `{'blur': True, 'round_corners': True, 'round_corners_type': 'normal', 'border_color': 'system', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0}` | Menu settings for the widget. |

## Example Configuration

```yaml
microphone:
  type: "yasb.microphone.MicrophoneWidget"
  options:
    label: "<span>{icon}</span>"
    label_alt: "<span>{icon}</span> {level}"
    mute_text: "mute"
    icons:
      normal: "\uf130"
      muted: "\uf131"
    mic_menu:
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "system"
      alignment: "right"
      direction: "down"
    callbacks:
      on_left: "toggle_mic_menu"
      on_middle: "toggle_label"
      on_right: "toggle_mute"
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
- **scroll_step:** The step size for volume adjustment when scrolling. The value is in percentage points (0-100).
- **icons:** A dictionary specifying the icons for the microphone widget. The keys are `normal` and `muted`, and the values are the unicode characters for the icons.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.
- **mic_menu:** A dictionary specifying the menu settings for the widget. It contains the following keys:
  - **blur:** Enable blur effect for the menu.
  - **round_corners:** Enable round corners for the menu (this option is not supported on Windows 10).
  - **round_corners_type:** Set the type of round corners for the menu (normal, small) (this option is not supported on Windows 10).
  - **border_color:** Set the border color for the menu (this option is not supported on Windows 10). Available options are `"system"`, `HEX` or None.
  - **alignment:** Set the alignment of the menu (left, right).
  - **direction:** Set the direction of the menu (up, down).
  - **offset_top:** Set the top offset of the menu.
  - **offset_left:** Set the left offset of the menu.

## Example Style
```css
.microphone-widget {}
.microphone-widget .widget-container {}
.microphone-widget .label {}
.microphone-widget .label.alt {}
.microphone-widget .icon {}
.microphone-widget .label.muted {}
.microphone-widget .icon.muted {}
.microphone-slider {
    border: none;
}
.microphone-slider::groove {}
.microphone-slider::handle{} 
.microphone-menu {
    background-color:rgba(17, 17, 27, 0.4); 
}
```