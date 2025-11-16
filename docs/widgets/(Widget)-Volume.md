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
| `audio_menu` | dict | [See below](#audio-menu-options)  | Menu settings for the widget. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |
| `progress_bar`       | dict    | `{'enabled': false, 'position': 'left', 'size': 14, 'thickness': 2, 'color': '#57948a', 'animation': true}` | Progress bar settings.    |


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
## Audio Menu Options
```yaml
    audio_menu:
      blur: true # Enable blur effect for the menu
      round_corners: true # Enable round corners for the menu (not supported on Windows 10)
      round_corners_type: "normal" # Set the type of round corners for the menu (normal, small) (not supported on Windows 10)
      border_color: "system" # Set the border color for the menu, "system", Hex color or None
      alignment: "right" # Set the alignment of the menu (left, right, center)
      direction: "down" # Set the direction of the menu (up, down)
      offset_top: 6 # Set the top offset of the menu
      offset_left: 0 # Set the left offset of the menu
      show_apps: true # Whether to show the list of applications with audio sessions
      show_app_labels: false # Whether to show application labels in the audio menu
      show_app_icons: true # Whether to show application icons in the audio menu
      show_apps_expanded: false # Whether application volumes are expanded by default when opening the menu
      app_icons: # Icons for the toggle button to expand/collapse application volumes
        toggle_down: "\uf078" # Icon for btn collapsed state
        toggle_up: "\uf077" # Icon for btn expanded state
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
  - **show_apps**: Whether to show the list of applications with audio sessions.
  - **show_app_labels**: Whether to show application labels in the audio menu.
  - **show_app_icons**: Whether to show application icons in the audio menu.
  - **show_apps_expanded**: Whether application volumes are expanded by default when opening the menu. When set to `true`, the application volume sliders will be visible immediately when the menu opens. When set to `false` (default), they remain collapsed until the toggle button is clicked.
  - **app_icons**: A dictionary specifying icons for the toggle button to expand/collapse application volumes. It contains the following keys:
    - **toggle_down**: Icon for the button in the collapsed state.
    - **toggle_up**: Icon for the button in the expanded state.
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

## Available Styles
```css
.volume-widget {}
.volume-widget.your_class {} /* If you are using class_name option */
.volume-widget .widget-container {}
.volume-widget .label {}
.volume-widget .label.alt {}
.volume-widget .icon {}
.volume-widget .label.muted {} /* Applied when audio is muted */
.volume-widget .icon.muted {} /* Applied when audio is muted */
.volume-widget .label.no-device {} /* Applied when no audio device is connected */
.volume-widget .icon.no-device {} /* Applied when no audio device is connected */
/* Volume progress bar styles if enabled */
.volume-widget .progress-circle {} 
/* Audio menu styles */
.volume-widget .audio-menu {}
/* System volume */
.audio-menu .system-volume-container .volume-slider {}
.audio-menu .system-volume-container .volume-slider::groove {}
.audio-menu .system-volume-container .volume-slider::handle{}
/* Device list styles */
.audio-menu .audio-container .device {}
.audio-menu .audio-container .device.selected {}
.audio-menu .audio-container .device:hover {}
/* Toggle button for application volumes (if is enabled) */
.audio-menu .toggle-apps {}
.audio-menu .toggle-apps.expanded {}
.audio-menu .toggle-apps:hover {}
/* Container for application volumes (if is enabled) */
.audio-menu .apps-container {} /* Individual application volume container */
.audio-menu .apps-container .app-volume {} /* Individual application volume container */
.audio-menu .apps-container .app-volume:hover {}
.audio-menu .apps-container .app-volume .app-label {} /* Application label */
.audio-menu .apps-container .app-volume .app-icon-container .app-icon {} /* Application icon */
.audio-menu .apps-container .app-volume .app-slider {} /* Application volume slider */  
```

## Example Styles
```css
.volume-widget .icon {
	color: #74b0ff;;
	margin:0 2px 0 0;
}
.audio-menu {
    background-color:rgba(17, 17, 27, 0.4); 
    min-width: 300px;
}
/* System volume */
.audio-menu .system-volume-container .volume-slider {
    border: none;
}
/* Device list styles */
.audio-menu .audio-container .device {
    background-color:transparent;
    border: none;
    padding:6px 8px 6px 4px;
    margin: 2px 0;
    font-size: 12px;
    border-radius: 4px;
}
.audio-menu .audio-container .device.selected {
    background-color: rgba(255, 255, 255, 0.085);
   
}
.audio-menu .audio-container .device:hover {
    background-color: rgba(255, 255, 255, 0.06);
}
/* Toggle button for application volumes (if is enabled) */
.audio-menu .toggle-apps {
    background-color: transparent;
    border: none;
    padding: 0;
    margin: 0;
    min-height: 24px;
    min-width: 24px;
    border-radius: 4px;
}
.audio-menu .toggle-apps.expanded {
    background-color: rgba(255, 255, 255, 0.1);
}
.audio-menu .toggle-apps:hover {
    background-color: rgba(255, 255, 255, 0.15);
    
}
/* Container for application volumes (if is enabled) */
.audio-menu .apps-container {
    padding: 8px;
    margin-top:20px;
    border-radius: 8px;
    background-color:rgba(255, 255, 255, 0.062)
}
.audio-menu .apps-container .app-volume .app-icon-container {
    min-width: 40px;
    min-height: 40px;
    max-width: 40px;
    max-height: 40px;
    border-radius: 6px;
    margin-right: 8px;
}
.audio-menu .apps-container .app-volume .app-slider {
    min-height: 40px;
    max-height: 40px;
}
.audio-menu .apps-container .app-volume .app-icon-container:hover {
    background-color: rgba(255, 255, 255, 0.1);
}
```

## Preview of the Widget
![Volume Widget](assets/119849t2-ty6f89d1-as5e-9982-t6d7ddbdda70.png)
