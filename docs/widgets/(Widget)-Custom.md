# Custom Widget Configuration

| Option          | Type    | Default                                                                 | Description                                                                 |
|-----------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`         | string  | `"{data}"`                                | The format string for data |
| `label_alt`     | string  | `"{data[city]} {data[region]}, {data[country]}"`    | Example of label alt. |
| `label_max_length`          | int     | `None`                                                                     | The maximum length of the label. |
| `class_name`    | string  | `"custom-info-widget"`                                                      | The CSS class name for the widget. |
| `exec_options`  | dict    | `{'run_cmd': 'curl.exe https://ipinfo.io', 'run_interval': 120000, 'return_format': 'json', 'hide_empty: false'}` | Execution options for custom widget. |
| `callbacks`     | dict    | `{'on_left': 'toggle_label', 'on_middle': 'exec cmd /c ncpa.cpl', 'on_right': 'exec cmd /c start https://ipinfo.io/{data[ip]} '}` | Callbacks for mouse events on the IP info widget. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container. |

## Example Configuration to get IP Address

```yaml
ip_info:
  type: "yasb.custom.CustomWidget"
  options:
    label: "<span>\udb81\udd9f</span> {data[ip]}"
    label_alt: "<span>\uf450</span> {data[city]} {data[region]}, {data[country]}"
    class_name: "ip-info-widget"
    exec_options:
      run_cmd: "curl.exe https://ipinfo.io"
      run_interval: 120000  # every 5 minutes
      return_format: "json"
      hide_empty: false
    callbacks:
      on_left: "toggle_label"
      on_middle: "exec cmd /c ncpa.cpl" # open network settings
      on_right: "exec cmd /c start https://ipinfo.io/{data[ip]} " # open ipinfo in browser
```

## Example Configuration to get Nvidia Temp.

```yaml
nvidia_temp:
  type: "yasb.custom.CustomWidget"
  options:
    label: "{data}<span>\udb81\udd04</span>"
    label_alt: "{data}"
    class_name: "system-widget"
    exec_options:
      run_cmd: "powershell nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader"
      run_interval: 10000 # run every 10 sec
      return_format: "string"
      hide_empty: false
```

## Description of Options

- **label**: The format string.
- **label_alt**: The alternative format string.
- **label_max_length**: The maximum length of the label. Minimum value is 1. Default is `None`.
- **class_name**: The CSS class name for the widget.
- **exec_options**: A dictionary specifying the execution options. The keys are `run_cmd`, `run_interval`, `return_format`, `hide_empty`. `return_format` can be `json` or `string`. If you run custom function which result empty data, you can set `hide_empty` to `true` to hide the widget.
- **callbacks**: A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.

## Example Style
```css
.custom-widget {}
.custom-widget .widget-container {}
.custom-widget .widget-container .label {}
.custom-widget .widget-container .label.alt {}
.custom-widget .widget-container .icon {}
```