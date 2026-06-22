# Custom Widget Configuration

A blank canvas for whatever data you want to put on your bar. You give it a command or script to run, and it displays the output - perfect for showing your IP address, GPU temperature, stock prices, or anything else you can fetch from a terminal command. Works with plain text or JSON.

| Option          | Type    | Default                                                                 | Description                                                                 |
|-----------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`         | string  | `"{data}"`                                | The format string for data |
| `label_alt`     | string  | `"{data}"`    | Example of label alt. |
| `label_max_length`          | int     | `None`                                                                     | The maximum length of the label. |
| `label_placeholder` | string  | `"Loading..."`                                                          | Placeholder text when data is not available. |
| `tooltip`       | boolean | `false`                                                                | Whether to show the tooltip on hover. |
| `tooltip_label` | string  | `None`                                                                 | Custom format string for the tooltip. If not specified, shows raw data. |
| `class_name`    | string  | `"custom-widget"`                                                      | The CSS class name for the widget. |
| `exec_options`  | dict    | `{'run_cmd': None, 'run_once': false, 'run_interval': 120000, 'return_format': 'json', 'hide_empty': false, 'use_shell': true, 'encoding': None}` | Execution options for custom widget. |
| `callbacks`     | dict    | `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}` | Callbacks for mouse events. |

## Example Configuration to get IP Address

```yaml
ip_info:
  type: "yasb.custom.CustomWidget"
  options:
    label: "<span>\udb81\udd9f</span> {data[ip]}"
    label_alt: "<span>\uf450</span> {data[city]} {data[region]}, {data[country]}"
    class_name: "ip-info-widget"
    tooltip: true
    tooltip_label: "IP: {data[ip]}\nCity: {data[city]}\nRegion: {data[region]}\nCountry: {data[country]}"
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

## Example Configuration to weather data

```yaml
nvidia_temp:
  type: "yasb.custom.CustomWidget"
  options:
    label: "London {data[current][temperature_2m]}{data[current_units][temperature_2m]}"
    class_name: "custom-widget"
    exec_options:
      run_cmd: "curl.exe http://api.open-meteo.com/v1/forecast?latitude=51.5074&longitude=-0.1278&current=temperature_2m&timezone=auto"
      run_interval: 1800000 # run every 30 min
      return_format: "json"
      hide_empty: false
      use_shell: false
```

## Description of Options

- **label**: The format string.
- **label_alt**: The alternative format string.
- **label_placeholder**: Placeholder text when data is not available. Default is `"Loading..."`.
- **label_max_length**: The maximum length of the label. Minimum value is 1. Default is `None`.
- **tooltip**: Whether to show the tooltip on hover. Default is `false`.
- **tooltip_label**: Custom format string for the tooltip. Use `{data}` to reference the command output data. If not specified, shows the raw data representation (JSON for dict, string for other types).
- **class_name**: The CSS class name for the widget.
- **exec_options**: A dictionary specifying the execution options. The keys are:
  - **run_cmd**: The command or executable path to run. Default is `None`.
  - **run_once**: (boolean) If set to `true`, the command runs only once on startup and the repeat interval timer is disabled. Default is `false`.
  - **run_interval**: The repeat execution interval in milliseconds. Default is `120000` (2 minutes).
  - **return_format**: The format expected from the command output, either `"json"` or `"string"`. Default is `"json"`.
  - **hide_empty**: (boolean) If true, the widget hides itself when the output is empty or parsing fails. Default is `false`.
  - **use_shell**: (boolean) Whether to run the command inside a system shell. Default is `true`.
  - **encoding**: (string) Custom character encoding to decode the output (e.g., `utf-8`, `cp1252`). Default is `None`.
- **callbacks**: A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.

## Example Style
```css
.custom-widget {}
.custom-widget .widget-container {}
.custom-widget .widget-container .label {}
.custom-widget .widget-container .label.alt {}
.custom-widget .widget-container .icon {}
```
