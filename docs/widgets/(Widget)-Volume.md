# Volume Widget Options
| Option       | Type   | Default                                                                 | Description                                                                 |
|--------------|--------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`      | string | `'{volume[percent]}%'`                                                  | The format string for the volume label. You can use placeholders like `{volume[percent]}` to dynamically insert volume information. |
| `label_alt`  | string | `'{volume[percent]}%'`                                                  | The alternative format string for the volume label. Useful for displaying additional volume details. |
| `tooltip`  | boolean  | `True`        | Whether to show the tooltip on hover. |
| `volume_icons` | list  | `['\ueee8', '\uf026', '\uf027', '\uf027', '\uf028']`                    | A list of icons representing different volume levels. The icons are used based on the current volume percentage. |
| `callbacks`  | dict   | `{'on_middle': 'do_nothing', 'on_right': 'do_nothing'}`                  | Callbacks for mouse events on the volume widget. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container. |

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
    callbacks:
      on_right: "exec cmd.exe /c start ms-settings:sound"
```

## Description of Options

- **label**: The format string for the volume label. You can use placeholders like `{volume[percent]}` to dynamically insert volume information.
- **label_alt**: The alternative format string for the volume label. Useful for displaying additional volume details.
- **tooltip**: Whether to show the tooltip on hover.
- **volume_icons**: A list of icons representing different volume levels. The icons are used based on the current volume percentage.
- **callbacks**: A dictionary specifying the callbacks for mouse events. The keys are `on_middle` and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.

## Example Style
```css
.volume-widget {}
.volume-widget .widget-container {}
.volume-widget .label {}
.volume-widget .icon {}
```