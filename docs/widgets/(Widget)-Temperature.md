# Temperature Widget

Native CPU/GPU temperature monitoring through Libre Hardware Monitor's local HTTP server.
The widget uses the same stat popup, pin, drag and outside-click behavior as CPU, memory and GPU.

```yaml
temperatures:
  type: yasb.temperature.TemperatureWidget
  options:
    label: "<span>\ue9ca</span>"
    libre_host: 127.0.0.1
    libre_port: 8085
    update_interval: 1000
    history_seconds: 120
    hardware_labels:
      /amdcpu/0: CPU
      /gpu-amd/5: GPU 0
      /gpu-amd/0: GPU 1
    thresholds: {}
    callbacks:
      on_left: toggle_menu
    menu:
      enabled: true
      blur: false
      border_color: "#292929"
      width: 400
      alignment: right
      direction: down
      offset_top: 8
      show_graph: true
      show_graph_grid: false
```

Hardware and sensor identifiers are discovered from `/data.json`. `hardware_labels` optionally
maps Libre's identifiers to the same GPU 0 / GPU 1 names used elsewhere in the bar; adapt the
example to the local machine. Libre's ordering can differ from Windows or the GPU widget.
CPU package/Tctl/Tdie and GPU Core readings are selected first when available. Selecting another
sensor remembers that selection per component. An integrated GPU exposing only VR SoC retains
that sensor name; it is not presented as a GPU Core reading.

| Option | Default | Description |
| --- | --- | --- |
| `label`, `label_alt` | thermometer icon | Native bar labels. |
| `class_name` | `""` | Additional widget CSS class. |
| `libre_host`, `libre_port` | `127.0.0.1`, `8085` | Libre HTTP server. |
| `update_interval` | `1000` | Sampling interval, 1000–60000 milliseconds. |
| `history_seconds` | `120` | Rolling history window, 30–3600 seconds. |
| `hardware_labels` | `{}` | Hardware ID → component label overrides. |
| `thresholds` | `{}` | Sensor ID → `warning` and `critical` thresholds in Celsius. Both are required per entry and warning must be lower than critical. |
| `menu.width` | `400` | Native popup width, 360–800 pixels, clamped to the screen. |
| `menu.enabled`, `menu.show_graph` | `true` | Enable the popup and graph. |
| `menu.show_graph_grid` | `false` | Optional native graph grid. |

Polling occurs on a shared background worker and continues while the popup is closed.
When CPU/GPU fan RPM monitoring is enabled, the same HTTP response also supplies the
cooling readings. Missing fan data clears the current RPM while retaining its sensor identity.
The in-memory history lasts for the running YASB process and is not written to disk.
Current, minimum and maximum are shown in Celsius. Minimum/maximum reflect available samples
within the configured history window. Missing readings display an em dash and produce graph
gaps. The client retries after connection errors, retains sensor identities, and never substitutes
zero for a missing temperature. Valid zero readings remain valid.

The graph reuses the native smooth line renderer, without fill or shadow. Its Celsius range
expands above 100°C when necessary. Optional thresholds change the current reading and graph
stroke to yellow/red; no hardware-independent threshold values are enabled by default.

Styles are scoped under `.temperature-widget` and `.temperature-popup`. Popup classes include
`.header .text`, `.header .pin-btn` (hover/checked/pinned), `.component-button`, `.sensor-button`,
`.hardware-name`, `.status`, `.graph-title`, `.graph-container`, `.temperature-graph`,
and the standard `.stats .stat-item`, `.stat-label` and `.stat-value` classes.
The current reading has `.primary`; configured alerts add `.warning` or `.critical`.
