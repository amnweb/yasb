# Microphone Widget Configuration

| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`           | string  | `'{icon}'`                        | The format string for the microphone widget. Displays icon or level. |
| `label_alt`       | string  | `'{icon} {level}'`        | The alternative format string for the microphone widget. Displays icon or level. |
| `class_name`      | string  | `""`                                                                                  | Additional CSS class name for the widget.                                    |
| `mute_text` | string  | `'mute'` | Text used by `{level}` to indicate muted volume |
| `tooltip`  | boolean  | `true`        | Whether to show the tooltip on hover. |
| `scroll_step`     | int     | `2`                  | The step size for volume adjustment when scrolling. The value is in percentage points (0-100). |
| `icons`       | dict    | `{'normal': '\uf130', 'muted': '\uf131'}` | Icons for microphone widget |
| `callbacks`       | dict    | `{'on_left': 'toggle_mute', 'on_middle': 'toggle_label', 'on_right': 'do_nothing'}` | Callbacks for mouse events on the memory widget. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |
| `mic_menu` | dict | `{'blur': True, 'round_corners': True, 'round_corners_type': 'normal', 'border_color': 'system', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0}` | Menu settings for the widget. |
| `progress_bar`       | dict    | `{'enabled': False, 'position': 'left', 'size': 14, 'thickness': 2, 'color': '#57948a', animation: True}` | Progress bar settings.    |


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
- **class_name:** Additional CSS class name for the widget. This allows for custom styling.
- **tooltip:** Whether to show the tooltip on hover.
- **scroll_step:** The step size for volume adjustment when scrolling. The value is in percentage points (0-100).
- **icons:** A dictionary specifying the icons for the microphone widget. The keys are `normal` and `muted`, and the values are the unicode characters for the icons.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
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
- **progress_bar**: A dictionary containing settings for the progress bar. It includes:
  - **enabled**: Whether the progress bar is enabled.
  - **position**: The position of the progress bar, either "left" or "right".
  - **size**: The size of the progress bar.
  - **thickness**: The thickness of the progress bar.
  - **color**: The color of the progress bar. Color can be single color or gradient. For example, `color: "#57948a"` or `color: ["#57948a", "#ff0000"]"` for a gradient.
  - **background_color**: The background color of the progress bar.
  - **animation**: Whether to enable smooth change of the progress bar value.

## Available Styles
```css
.microphone-widget {}
.microphone-widget.your_class {} /* If you are using class_name option */
.microphone-widget .widget-container {}
.microphone-widget .label {}
.microphone-widget .label.alt {}
.microphone-widget .icon {}
.microphone-widget .label.muted {} /* Applied when microphone is muted */
.microphone-widget .icon.muted {} /* Applied when microphone is muted */
.microphone-widget .label.no-device {} /* Applied when no microphone device is connected */
.microphone-widget .icon.no-device {} /* Applied when no microphone device is connected */
/* Microphone progress bar styles if enabled */
.microphone-widget .progress-circle {} 
/* Microphone menu styles */
.microphone-widget .microphone-menu {}
/* System microphone volume */
.microphone-menu .system-volume-container .volume-slider {}
.microphone-menu .system-volume-container .volume-slider::groove {}
.microphone-menu .system-volume-container .volume-slider::handle{}
/* Device list styles (if multiple microphones) */
.microphone-menu .microphone-container .device {}
.microphone-menu .microphone-container .device.selected {}
.microphone-menu .microphone-container .device:hover {}
```

## Example Styles
```css
.microphone-widget .icon {
    color: #ff6b6b;
    margin: 0 2px 0 0;
}
.microphone-menu {
    background-color: rgba(17, 17, 27, 0.4); 
    min-width: 300px;
}
/* System microphone volume */
.microphone-menu .system-volume-container .volume-slider {
    border: none;
}
/* Device list styles */
.microphone-menu .microphone-container .device {
    background-color: transparent;
    border: none;
    padding: 6px 8px 6px 4px;
    margin: 2px 0;
    font-size: 12px;
    border-radius: 4px;
}
.microphone-menu .microphone-container .device.selected {
    background-color: rgba(255, 255, 255, 0.085);
}
.microphone-menu .microphone-container .device:hover {
    background-color: rgba(255, 255, 255, 0.06);
}
```