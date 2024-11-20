# Traffic Widget Options

| Option          | Type    | Default                                                                 | Description                                                                 |
|-----------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`         | string  | `'\ueb01 \ueab4 {download_speed} - \ueab7 {upload_speed}'`                | The format string for the traffic widget. Displays download and upload speeds. |
| `label_alt`     | string  | `'Download {download_speed} - Upload {upload_speed}'`                | The alternative format string for the traffic widget. Displays upload and download speeds. |
| `update_interval` | integer | `1000`                                                                 | The interval in milliseconds to update the traffic data. Must be between 0 and 60000. |
| `callbacks`     | dict    | `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}` | Callbacks for mouse events on the traffic widget. |

## Example Configuration

```yaml
traffic:
  type: "yasb.traffic.TrafficWidget"
  options:
    label: "\ueb01 \ueab4 {download_speed} | \ueab7 {upload_speed}"
    label_alt: "Download {download_speed} | Upload {upload_speed}"
    update_interval: 1000
    callbacks:
      on_left: 'toggle_label'
      on_right: 'exec cmd /c Taskmgr'
```

## Description of Options

- **label:** The format string for the traffic widget. Displays download and upload speeds.
- **label_alt:** The alternative format string for the traffic widget. Displays upload and download speeds.
- **update_interval:** The interval in milliseconds to update the traffic data. Must be between 0 and 60000.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.


## Example Style
```css
.traffic-widget {}
.traffic-widget .widget-container {}
.traffic-widget .label {}
.traffic-widget .label.alt {}
.traffic-widget .icon {}
```