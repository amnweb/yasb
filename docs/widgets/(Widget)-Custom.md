# Custom Widget Configuration

A blank canvas for whatever data you want to put on your bar. You give it a command or script to run, and it displays the output - perfect for showing your IP address, GPU temperature, stock prices, or anything else you can fetch from a terminal command. Works with plain text or JSON.

| Option          | Type    | Default                                                                 | Description                                                                 |
|-----------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`         | string  | Required                                | The format string for data, for example `"{data}"` |
| `label_alt`     | string  | `""`    | The alternative format string. |
| `label_max_length`          | int     | `None`                                                                     | The maximum length of the label. |
| `label_placeholder` | string  | `"Loading..."`                                                          | Placeholder text when data is not available. |
| `tooltip`       | boolean | `false`                                                                | Whether to show the tooltip on hover. |
| `tooltip_label` | string  | `None`                                                                 | Custom format string for the tooltip. If not specified, shows raw data. |
| `class_name`    | string  | Required                                                      | The CSS class name for the widget. |
| `exec_options`  | dict    | [See below](#exec-options) | Execution options for custom widget. |
| `keybindings`   | list    | `[]`                                                                   | Optional hotkeys. See [Keybindings](./Keybindings). |
| `callbacks`     | dict    | [See below](#callbacks) | Callbacks for mouse events. |

## Callbacks

The `callbacks` option maps mouse buttons (`on_left`, `on_middle`, `on_right`) to actions. All keys are optional, the values shown are the defaults.

```yaml
callbacks:
  on_left: "toggle_label"
  on_middle: "do_nothing"
  on_right: "do_nothing"
```

Available actions:

- `toggle_label` - Switch between `label` and `label_alt`.
- `exec_custom` - Run the command from `exec_options` now.
- `do_nothing` - Do nothing.
- `exec <command>` - Run a command, for example `exec cmd.exe /c start ms-settings:network`.

## Exec Options

The `exec_options` option accepts the following keys. All keys are optional, the values shown are the defaults.

```yaml
exec_options:
  run_cmd: null
  run_once: false
  run_interval: 120000
  return_format: "json"
  hide_empty: false
  use_shell: true
  encoding: null
```

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
      run_interval: 120000  # every 2 minutes
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
weather:
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

- **label**: (Required) The format string.
- **label_alt**: The alternative format string. Default is `""`.
- **label_placeholder**: Placeholder text when data is not available. Default is `"Loading..."`.
- **label_max_length**: The maximum length of the label. Minimum value is 1. Default is `None`.
- **tooltip**: Whether to show the tooltip on hover. Default is `false`.
- **tooltip_label**: Custom format string for the tooltip. Use `{data}` to reference the command output data. If not specified, shows the raw data representation (JSON for dict, string for other types).
- **class_name**: (Required) The CSS class name for the widget.
- **exec_options**: A dictionary specifying the execution options. The keys are:
  - **run_cmd**: The command or executable path to run. Put double quotes around a path or argument that contains spaces, for example `run_cmd: '"C:\Program Files\Tool\tool.exe" --json'`. Default is `None`.
  - **run_once**: (boolean) If set to `true`, the command runs only once on startup and the repeat interval timer is disabled. Default is `false`.
  - **run_interval**: The repeat execution interval in milliseconds. Must be `0` or greater. Default is `120000` (2 minutes).
  - **return_format**: The format expected from the command output, either `"json"` or `"string"`. Default is `"json"`.
  - **hide_empty**: (boolean) If true, the widget hides itself when the output is empty or parsing fails. Default is `false`.
  - **use_shell**: (boolean) Whether to run the command inside a system shell. Default is `true`.
  - **encoding**: (string) Custom character encoding to decode the output (e.g., `utf-8`, `cp1252`). Default is `None`.
- **keybindings**: A list of global hotkeys for this widget. See [Keybindings](./Keybindings).
- **callbacks:** Mouse event callbacks. See [Callbacks](#callbacks).

## Example Style
```css
.custom-widget {}
.custom-widget .widget-container {}
.custom-widget .widget-container .label {}
.custom-widget .widget-container .label.alt {}
.custom-widget .widget-container .icon {}
```
