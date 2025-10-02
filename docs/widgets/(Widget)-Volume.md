# Volume Widget Options
| Option       | Type   | Default                                                                 | Description                                                                 |
|--------------|--------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`      | string | `'{volume[percent]}%'`                                                  | The format string for the volume label. You can use placeholders like `{volume[percent]}` to dynamically insert volume information. |
| `label_alt`  | string | `'{volume[percent]}%'`                                                  | The alternative format string for the volume label. Useful for displaying additional volume details. |
| `class_name`      | string | `""`                                                                                  | Additional CSS class name for the widget.                                    |
| `scroll_step`     | int     | `2`                  | The step size for volume adjustment when scrolling. The value is in percentage points (0-100). |
| `slider_beep`   | boolean | `true`              | Whether to play a sound when the volume slider is released. |
| `mute_text` | string  | `'mute'` | Text used by `{level}` to indicate muted volume |
| `tooltip`  | boolean  | `true`        | Whether to show the tooltip on hover. |
| `volume_icons` | list  | `['\ueee8', '\uf026', '\uf027', '\uf027', '\uf028']`                    | A list of icons representing different volume levels. The icons are used based on the current volume percentage. |
| `callbacks`  | dict   | `{'on_left': 'toggle_volume_menu', 'on_middle': 'do_nothing', 'on_right': 'toggle_mute'}`                  | Callbacks for mouse events on the volume widget. |
| `audio_menu` | dict | `{'blur': True, 'round_corners': True, 'round_corners_type': 'normal', 'border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0}` | Menu settings for the widget. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |
| `progress_bar`       | dict    | `{'enabled': false, 'position': 'left', 'size': 14, 'thickness': 2, 'color': '#57948a', 'animation': true, 'center_label': ''}` | Progress bar settings.    |


## Example Configuration

```yaml
volume:
  type: "yasb.volume.VolumeWidget"
  options:
    label: "<span>{icon}</span> {level}"
    label_alt: "{volume}"
    volume_icons:
      - "\ueee8"  # Icon for muted
      - "\uf026"  # Icon for 0-10% volume
      - "\uf027"  # Icon for 11-30% volume
      - "\uf027"  # Icon for 31-60% volume
      - "\uf028"  # Icon for 61-100% volume
    audio_menu:
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "system"
      alignment: "right"
      direction: "down"
    callbacks:
      on_left: "toggle_volume_menu"
      on_right: "toggle_mute"
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Description of Options

- **label**: The format string for the volume label. You can use placeholders like `{volume[percent]}` to dynamically insert volume information.
- **label_alt**: The alternative format string for the volume label. Useful for displaying additional volume details.
- **class_name**: Additional CSS class name for the widget. This allows for custom styling.
- **mute_text**: The text for `{level}` to display when the volume is muted. Default: "mute".
- **tooltip**: Whether to show the tooltip on hover.
- **scroll_step**: The step size for volume adjustment when scrolling. The value is in percentage points (0-100).
- **slider_beep**: Whether to play a sound when the volume slider is released.
- **volume_icons**: A list of icons representing different volume levels. The icons are used based on the current volume percentage.
- **audio_menu**: A dictionary specifying the menu settings for the widget. It contains the following keys:
  - **blur**: Enable blur effect for the menu.
  - **round_corners**: Enable round corners for the menu (this option is not supported on Windows 10).
  - **round_corners_type**: Set the type of round corners for the menu (normal, small) (this option is not supported on Windows 10).
  - **border_color**: Set the border color for the menu (this option is not supported on Windows 10).
  - **alignment**: Set the alignment of the menu (left, right).
  - **direction**: Set the direction of the menu (up, down).
  - **offset_top**: Set the top offset of the menu.
  - **offset_left**: Set the left offset of the menu.
- **callbacks**: A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.
- **progress_bar**: A dictionary containing settings for the progress bar. It includes:
  - **enabled**: Whether the progress bar is enabled.
  - **position**: The position of the progress bar, either "left" or "right".
  - **size**: The size of the progress bar.
  - **thickness**: The thickness of the progress bar.
  - **color**: The color of the progress bar. Color can be single color or gradient. For example, `color: "#57948a"` or `color: ["#57948a", "#ff0000"]` for a gradient.
  - **background_color**: The background color of the progress bar.
  - **animation**: Whether to enable smooth change of the progress bar value.
  - **center_label**: The label that will be centered inside the progress bar (can be styled using `.progress-circle`)

## Example Style
```css
.volume-widget {}
.volume-widget.your_class {} /* If you are using class_name option */
.volume-widget .widget-container {}
.volume-widget .label {}
.volume-widget .label.alt {}
.volume-widget .icon {}
.volume-widget .label.muted {}
.volume-widget .icon.muted {}
/* Volume progress bar styles if enabled */
.volume-widget .progress-circle {} 
```

## Style for the Audio Menu
```css
.volume-slider {
    border: none;
}
.volume-slider::groove {}
.volume-slider::handle{} 
.audio-menu {
    background-color:rgba(17, 17, 27, 0.4); 
}
.audio-container .device {
    background-color:transparent;
    border: none;
    padding:6px 8px 6px 4px;
    margin: 2px 0;
    font-size: 12px;
    border-radius: 4px;
}
.audio-container .device.selected {
    background-color: rgba(255, 255, 255, 0.085);
}
.audio-container .device:hover {
    background-color: rgba(255, 255, 255, 0.06);
}
```

## Preview of the Widget
![Volume Widget](assets/119849t2-ty6f89d1-as5e-9982-t6d7ddbdda70.png)
