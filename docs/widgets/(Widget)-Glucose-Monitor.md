# Glucose Monitor Widget

Nightscout (also known as CGM in the Cloud) is an open-source cloud application used by people with diabetes and parents of kids with diabetes to visualize, store and share the data from their Continuous Glucose Monitoring sensors in real-time. Once setup, Nightscout acts as a central repository of blood glucose and insulin dosing/treatment data for a single person, allowing you to view the CGM graph and treatment data anywhere using just a web browser connected to the internet.

There are several parts to this system. You need somewhere online to store, process and visualize this data (a Nightscout Site), something to upload CGM data to your Nightscout (an Uploader), and then optionally you can use other devices to access or view this data (one - or more - Follower).

Go to [Nightscout documentation](https://nightscout.github.io/nightscout/new_user/) for the details.

This widget allows you to monitor someone's blood sugar level through [Nightscout CGM remote monitor](https://github.com/nightscout/cgm-remote-monitor) API.


| Option                  | Type   | Default                                                                                                                                                                                                                                        | Description                                                                                                                                            |
|-------------------------|--------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| `label`                 | string | `\ud83e\ude78{sgv}{direction}`                                                                                                                                                                                                                 | The format string for the widget.                                                                                                                      |
| `tooltip`               | string | `({sgv_delta}) {delta_time_in_minutes} min`                                                                                                                                                                                                    | The format string for the tooltip.                                                                                                                     |
| `host`                  | string | `...`                                                                                                                                                                                                                                          | The URL for your [Nightscout CGM remote monitor](https://github.com/nightscout/cgm-remote-monitor).                                                    |
| `secret`                | string | `...`                                                                                                                                                                                                                                          | The secret key for the CGM API.                                                                                                                        |
| `secret_env_name`       | string | `...`                                                                                                                                                                                                                                          | If the secret variable is equals to `env` then widget will try to get secret from the environment variable with a name of the `secret_env_name` value. |
| `direction_icons`       | dict   | `{"double_up": "\u2b06\ufe0f\u2b06\ufe0f", "single_up": "\u2b06\ufe0f", "forty_five_up": "\u2197\ufe0f", "flat": "\u27a1\ufe0f", "forty_five_down": "\u2198\ufe0f", "single_down": "\u2b07\ufe0f", "double_down": "\u2b07\ufe0f\u2b07\ufe0f"}` | Direction icon settings.                                                                                                                               |
| `sgv_measurement_units` | string | `mg/dl`                                                                                                                                                                                                                                        | SGV measurement units can be `mg/dl` or `mmol/l`.                                                                                                      |
| `callbacks`             | dict   | `{"on_left": "open_cgm", "on_middle": "do_nothing", "on_right": "do_nothing"}`                                                                                                                                                                 | Callbacks for mouse events on the glucose monitor widget.                                                                                              |

## Example Configuration

```yaml
  glucose_monitor:
    type: "yasb.glucose_monitor.GlucoseMonitor"
    options:
        label: "\ud83e\ude78{sgv}{direction}"
        tooltip: "({sgv_delta}) {delta_time_in_minutes} min"
        host: "https://your-domain.com"
        secret: "env"
        secret_env_name: "YASB_CGM_YOUR_SECRET_ENV_NAME"
        sgv_measurement_units: "mg/dl"
```

## Description of Options

- **label:** The format string for the widget.
- **tooltip:** The format string for the tooltip
- **host:** The URL for the CGM
- **secret:** The secret key for the CGM API
- **direction_icons:** Direction icon settings
- **sgv_measurement_units:** SGV measurement units can be `mg/dl` or `mmol/l`
- **callbacks:** Callbacks for mouse events on the glucose monitor widget


## Example Style
```css
.cgm-widget {
    padding: 0 4px 0 4px;
}
.cgm-widget .widget-container {
}
.cgm-widget .label {
}
```

## Preview of the Widget
![Glucose Monitor YASB Widget](assets/glucose_monitor_01.png)
