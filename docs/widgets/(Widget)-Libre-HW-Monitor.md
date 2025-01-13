# Libre Hardware Monitor Widget Configuration

| Option                   | Type    | Default                                                                                        | Description                                                                                                                                  |
|--------------------------|---------|------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| `label`                  | string  | `"<span>\udb82\udcae </span> {info[value]}{info[unit]}"`                                       | The primary label format.                                                                                                                    |
| `label_alt`              | string  | `"<span>\uf4bc </span>{info[histogram]} {info[value]} ({info[min]}/{info[max]}) {info[unit]}"` | Histograms. The alternative label format.                                                                                                    |
| `sensor_id`              | string  | `"/amdcpu/0/load/0"`                                                                           | Libre Hardware Monitor SensorId from http://localhost:8085/data.json                                                                         |
| `class_name`             | string  | `"libre-monitor-widget"`                                                                       | CSS class name for styling of different widget instances.                                                                                    |
| `update_interval`        | integer | `1000`                                                                                         | The interval in milliseconds to update the widget.                                                                                           |
| `precision`              | integer | `2`                                                                                            | Floating point precision of the info[value].                                                                                                 |
| `history_size`           | integer | `60`                                                                                           | The size of the min/max history.                                                                                                             |
| `histogram_num_columns`  | integer | `10`                                                                                           | The number of columns in the histogram.                                                                                                      |
| `histogram_fixed_min`    | integer | `None`                                                                                         | Histogram minimum value. If None - set as history minimum value.                                                                             |
| `histogram_fixed_max`    | integer | `None`                                                                                         | Histogram maximum value. If None - set as history maximum value.                                                                             |
| `sensor_id_error_label`  | string  | `N/A`                                                                                          | The label shown when the sensor id is invalid or the sensor does not exist/disabled.                                                         |
| `connection_error_label` | string  | `Connection error...`                                                                          | The label shown when YASB can't connect to the Libre Hardware Monitor Web server. Either the server is not running or the IP/port is wrong.  |
| `auth_error_label`       | string  | `Auth Failed...`                                                                               | The label shown when there is a username/password issue while connecting to LHM Web server if the authentication is enabled in LHM settings. |
| `server_host`            | string  | `"localhost"`                                                                                  | Libre Hardware Monitor server host.                                                                                                          |
| `server_port`            | integer | `8085`                                                                                         | Libre Hardware Monitor server port.                                                                                                          |
| `server_username`        | string  | `""`                                                                                           | Libre Hardware Monitor username. Only needed if auth is enabled.                                                                             |
| `server_password`        | string  | `""`                                                                                           | Libre Hardware Monitor password. Only needed if auth is enabled.                                                                             |
| `histogram_icons`        | list    | `['\u2581', '\u2581', '\u2582', '\u2583', '\u2584', '\u2585', '\u2586', '\u2587', '\u2588']`   | Icons representing CPU usage histograms.                                                                                                     |
| `callbacks`              | dict    | `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}`             | Callback functions for different mouse button actions.                                                                                       |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container.                            |
## Example Configuration (GPU Temperature)

```yaml
  libre_gpu:
    type: "yasb.libre_monitor.LibreHardwareMonitorWidget"
    options:
      label: "<span>\udb82\udcae </span> {info[value]}{info[unit]}"
      label_alt: "<span>\uf437 </span>{info[histogram]} {info[value]} ({info[min]}/{info[max]}) {info[unit]}"
      sensor_id: "/gpu-nvidia/0/temperature/0"
      update_interval: 1000
      precision: 2
      histogram_num_columns: 10
      class_name: "libre-monitor-widget"

      history_size: 60
      histogram_icons:
        - '\u2581' # 0%
        - '\u2581' # 10%
        - '\u2582' # 20%
        - '\u2583' # 30%
        - '\u2584' # 40%
        - '\u2585' # 50%
        - '\u2586' # 60%
        - '\u2587' # 70%
        - '\u2588' # 80%+

      # histogram_fixed_min: 0.0
      # histogram_fixed_max: 100.0

      # server_host: "localhost"
      # server_port: 8085
      # server_username: "admin"
      # server_password: "password"

      callbacks:
        on_left: "toggle_label"
        on_middle: "do_nothing"
        on_right: "do_nothing"
```
## Set up instructions
1. Install Libre Hardware Monitor https://github.com/LibreHardwareMonitor/LibreHardwareMonitor
2. Run Libre Hardware Monitor.
3. Start the Remote Web Server (Options -> Remote Web Server -> Run).
4. Find the required SensorId in the http://localhost:8085/data.json.
5. Update the widget configuration with the required SensorId.

**Note**: Libre Hardware Monitor and its web server must be running in the background for the widget to work. Autostart is recommended.

## Description of Options

- **label**: The format string for the Libre Monitor label. You can use placeholders like `{info[value]} {info[unit]}` to dynamically insert required information.
- **label_alt**: The alternative format string for the Libre Monitor label. Useful for displaying additional details like histogram `{info[histogram]}` or min/max values `{info[min]} {info[max]}`.
- **class_name**: Custom CSS class name for the widget instance. Useful when having multiple widgets with different styling.
- **sensor_id**: The sensor ID of the Libre Hardware Monitor server. All the SensorIds can be found in the http://localhost:8085/data.json when the server is running (Options->Remote Web Server->Run).
- **update_interval**: The interval in milliseconds at which the widget updates its information. Limited by the Libre Hardware Monitor update interval.
- **precision**: Floating point precision of the `{info[value]}`.
- **history_size**: The size of the min/max history. The history is reset when the widget/yasb is reloaded.
- **histogram_fixed_min**: Set the fixed minimum value of the histogram. Actual sensor min value from the history is not changed. If not set manually it will be set as history minimum value.
- **histogram_fixed_max**: Set the fixed maximum value of the histogram. Actual sensor max value from the history is not changed. If not set manually it will be set as history maximum value.
- **histogram_icons**: A list of icons representing different values of the histogram.
- **histogram_num_columns**: The number of columns to display in the histogram.
- **sensor_id_error_label**: The label shown when the sensor id is invalid or the sensor does not exist/disabled.
- **connection_error_label**: The label shown when YASB can't connect to the Libre Hardware Monitor Web server. Either the server is not running or the IP/port is wrong.
- **auth_error_label**: The label shown when there is a username/password issue while connecting to LHM Web server if the authentication is enabled in LHM settings.
- **server_host**: The host of the Libre Hardware Monitor server.
- **server_port**: The port of the Libre Hardware Monitor server.
- **server_username**: The username of the Libre Hardware Monitor server. Required if auth is enabled.
- **server_password**: The password of the Libre Hardware Monitor server. Required if auth is enabled.
- **callbacks**: A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.

## Example Style
```css
.libre-monitor-widget {}
.libre-monitor-widget .widget-container {}
.libre-monitor-widget .widget-container .label {}
.libre-monitor-widget .widget-container .label.alt {}
.libre-monitor-widget .widget-container .icon {}
```
