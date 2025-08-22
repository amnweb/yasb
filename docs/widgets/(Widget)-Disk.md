# Disk Widget Configuration
| Option            | Type    | Default                                                                 | Description                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`           | string  | `'{volume_label} {space[used][percent]}'`                        | The format string for the disk widget. |
| `label_alt`       | string  | `'{volume_label} {space[used][gb]} / {space[total][gb]}'`        | The alternative format string for the disk widget. |
| `class_name`      | string  | `""`                                                                                  | Additional CSS class name for the widget.                                    |
| `volume_label`       | string  | `'C'`        | Partition which you want to show in the bar |
| `decimal_display` | integer | `1`                                                                  | The number of decimal places to show, default 1 (min 0 max 3) |
| `update_interval` | integer | `60`                                                                  | The interval in seconds to update the disk widget. Must be between 0 and 3600. |
| `group_label` | dict | `{'volume_labels': ["C"], 'show_label_name': true, 'blur': true, 'round_corners': true, 'round_corners_type': 'normal','border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0}` | Group labels for multiple disks. This will show the labels of multiple disks in a popup window. |
| `callbacks`       | dict    | `{'on_left': 'do_nothing', 'on_middle': 'do_nothing', 'on_right': "exec explorer C:\\"}` | Callbacks for mouse events. |
| `disk_thresholds` | dict  | `{'low': 25, 'medium': 50, 'high': 90}`                                 | Thresholds for Disk usage levels. |
| `animation`         | dict    | `{'enabled': true, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |
| `progress_bar`       | dict    | `{'enabled': false, 'position': 'left', 'size': 14, 'thickness': 2, 'color': '#57948a', 'animation': false}` | Progress bar settings.    |

## Example Configuration

```yaml
disk:
  type: "yasb.disk.DiskWidget"
  options:
      label: "{volume_label} {space[used][percent]}"
      label_alt: "{volume_label} {space[used][gb]} / {space[total][gb]}"
      volume_label: "C"
      update_interval: 60
      group_label:
        volume_labels: ["C", "D", "E", "F"]
        show_label_name: true
        blur: True
        round_corners: True
        round_corners_type: "small"
        border_color: "System"
        alignment: "right"
        direction: "down"
      callbacks:
        on_left: "toggle_group"
        on_middle: "toggle_label"
        on_right: "exec explorer C:\\" # Open disk C in file explorer
      label_shadow:
        enabled: true
        color: "black"
        radius: 3
        offset: [ 1, 1 ]
      disk_thresholds:
          low: 25
          medium: 50
          high: 90
```

## Description of Options

- **label:** The format string for the disk widget. Displays free space in percent.
- **label_alt:** The alternative format string for the disk widget.
- **class_name:** Additional CSS class name for the widget. This allows for custom styling.
- **volume_label:** Partition/volume which you want to show in the bar.
- **decimal_display:** The number of decimal places to show, default 1 (min 0 max 3).
- **update_interval:** The interval in seconds to update the disk widget. Must be between 0 and 3600.
- **disk_thresholds:** A dictionary specifying the thresholds for disk usage levels. The keys are `low`, `medium`, and `high`, and the values are the percentage thresholds.
- **group_label:** Group labels for multiple disks. This will show the labels of multiple disks in a popup window.
  - **volume_labels:** List of volume labels to show in the group label.
  - **show_label_name:** Show the label name in the group label.
  - **blur:** Enable blur effect for the group label.
  - **round_corners:** Enable round corners for group label.
  - **round_corners_type:** Border type for group label can be `normal` and `small`. Default is `normal`.
  - **border_color:** Border color for group label can be `None`, `System` or `Hex Color` `"#ff0000"`.
  - **alignment:** Alignment of the group label. Possible values are `left`, `center`, and `right`.
  - **direction:** Direction of the group label. Possible values are `up` and `down`.
  - **offset_top:** Offset from the top of the screen.
  - **offset_left:** Offset from the left of the screen.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.
- **progress_bar**: A dictionary containing settings for the progress bar. It includes:
  - **enabled**: Whether the progress bar is enabled.
  - **position**: The position of the progress bar, either "left" or "right".
  - **size**: The size of the progress bar.
  - **thickness**: The thickness of the progress bar.
  - **color**: The color of the progress bar. Color can be single color or gradient. For example, `color: "#57948a"` or `color: ["#57948a", "#ff0000"]"` for a gradient.
  - **background_color**: The background color of the progress bar.
  - **animation**: Whether to enable smooth change of the progress bar value.

## Widget Style
```css
.disk-widget {}
.disk-widget.your_class {} /* If you are using class_name option */
.disk-widget .widget-container {}
.disk-widget .widget-container .label {}
.disk-widget .widget-container .label.alt {}
.disk-widget .widget-container .icon {}
/* Group label style */
.disk-group {}
.disk-group-row {}
.disk-group-label {}
.disk-group-label-size {}
.disk-group-label-bar {}
.disk-group-label-bar::chunk {}

/* Disk progress bar styles if enabled */
.disk-widget .progress-circle {} 
```

## Example Style for Group Label
```css
.disk-group {
    background-color:rgba(17, 17, 27, 0.75);
}
.disk-group-row {
    min-width: 220px;
    max-width: 220px;
    max-height: 40px;
    margin: 0;
    padding: 0;
    border-radius: 6px;
    border: 1px solid rgba(128, 128, 128, 0);
}
.disk-group-row:hover {
    background-color:rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1)
}
.disk-group-label-bar{
    max-height:8px;
    border:0px solid rgba(128, 128, 128, 0);
    background-color: rgba(137, 180, 250, 0.1);
    border-radius: 4px
}
.disk-group-label-bar::chunk{
    background-color: rgba(137, 180, 250, 0.3);
    border-radius: 4px
}
.disk-group-label {
    font-size: 10px
}
.disk-group-label-size {
    font-size: 10px;
    color: #585b70
}
```

## Example Settings for Group Label and show menu
```yaml
  disk:
    type: "yasb.disk.DiskWidget"
    options:
        label: "<span>\uf473</span>"
        label_alt: "<span>\uf473</span>"
        group_label:
          volume_labels: ["C", "D", "E", "F"]
          show_label_name: true 
          blur: True
          round_corners: True
          round_corners_type: "normal"
          border_color: "System"
          alignment: "right"
          direction: "down"
          distance: 6
        callbacks:
          on_left: "toggle_group"
```

## Style for Group Label and show menu
```css
.disk-widget {
    padding: 0 6px 0 6px;
}
.disk-group {
    background-color:rgba(17, 17, 27, 0.4); 
}
.disk-group-row {
    min-width: 220px;
    max-width: 220px;
    max-height: 40px;
    margin: 0;
    padding: 0;
    border-radius: 6px;
    border: 1px solid rgba(128, 128, 128, 0);
}
.disk-group-row:hover {
    background-color:rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
}
.disk-group-label-bar{
    max-height:8px;
    border:0px solid rgba(128, 128, 128, 0);
    background-color: rgba(137, 180, 250, 0.1);
    border-radius: 4px;
}
.disk-group-label-bar::chunk{
    background-color: rgba(61, 135, 255, 0.3);
    border-radius: 4px;
}
.disk-group-label {
    font-size: 10px;
}
.disk-group-label-size {
    font-size: 10px;
    color: #666879;
}
```

## Preview of example above
![GitHub YASB Widget](assets/758425162-b61ef748-4280-0884-dc5f59c2ba8d.png)