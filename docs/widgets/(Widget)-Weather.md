# Weather Widget Options
| Option          | Type    | Default                                                                 | Description                                                                 |
|-----------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`         | string  | `'<span>{icon}</span> {temp}'`                                        | The format string for the weather label. You can use placeholders like `{temp}`, `{icon}`, etc. |
| `label_alt`     | string  | `'{location}: Min {min_temp}, Max {max_temp}, Humidity {humidity}'` | The alternative format string for the weather label. Useful for displaying additional weather details. |
| `update_interval` | integer | `3600`                                                                 | The interval in seconds to update the weather data. Must be between 60 and 36000000. |
| `hide_decimal`  | boolean | `False`                                                                 | Whether to hide the decimal part of the temperature. |
| `location`      | string  | `'London'`                                                              | The location for which to fetch the weather data. |
| `show_alerts`   | boolean | `False`                                                                 | Whether to show weather alerts. |
| `units`         | string  | `'metric'`                                                              | The units for the weather data. Can be `'metric'` or `'imperial'`. |
| `api_key`       | string  | `'0'`                                                                   | The API key for accessing the weather service. |
| `icons`         | dict    | `{ 'sunnyDay': '\ue30d', 'clearNight': '\ue32b', 'cloudyDay': '\ue312', 'cloudyNight': '\ue311', 'rainyDay': '\udb81\ude7e', 'rainyNight': '\udb81\ude7e', 'snowyIcyDay': '\udb81\udd98', 'snowyIcyNight': '\udb81\udd98', 'blizzardDay': '\uebaa', 'default': '\uebaa' }` | A dictionary of icons for different weather conditions. |
| `callbacks`     | dict    | `{ 'on_left': 'do_nothing', 'on_middle': 'do_nothing', 'on_right': 'do_nothing' }` | Callbacks for mouse events on the weather widget. |
| `weather_card`  | dict    | `{ blur': True, 'round_corners': True, 'round_corners_type': 'normal', 'border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0, 'icon_size': 64 }` | Configuration for the weather card popup display. Controls visibility, appearance, and positioning. |
| `animation`         | dict    | `{'enabled': True, 'type': 'fadeInOut', 'duration': 200}`               | Animation settings for the widget.                                          |
| `container_padding`  | dict | `{'top': 0, 'left': 0, 'bottom': 0, 'right': 0}`      | Explicitly set padding inside widget container. |
| `container_shadow`   | dict   | `None`                  | Container shadow options.                       |
| `label_shadow`         | dict   | `None`                  | Label shadow options.                 |

## Example Configuration

```yaml
weather:
  type: "yasb.weather.WeatherWidget"
  options:
    label: "<span>{icon}</span> {temp}"
    label_alt: "{location}: Min {min_temp}, Max {max_temp}, Humidity {humidity}"
    api_key: "3bf4cf9a7c3f40d6b31174128242807" # Get your free API key from https://www.weatherapi.com/
    show_alerts: true
    update_interval: 600 # Update interval in seconds, Min 600 seconds
    hide_decimal: true
    units: "metric" # Can be 'metric' or 'imperial'
    location: "Los Angeles, CA, USA" # You can use "USA Los Angeles 90006" {COUNTRY CITY ZIP_CODE}, or just city.
    callbacks:
      on_left: "toggle_card"
      on_middle: "do_nothing"
      on_right: "toggle_label"
    icons:
      sunnyDay: "\ue30d"
      clearNight: "\ue32b"
      cloudyDay: "\ue312"
      cloudyNight: "\ue311"
      rainyDay: "\ue308"
      rainyNight: "\ue333"
      snowyIcyDay: "\ue30a"
      snowyIcyNight: "\ue335"
      blizzardDay: "\udb83\udf36"
      blizzardNight: "\udb83\udf36"
      foggyDay: "\ue303"
      foggyNight: "\ue346"
      thunderstormDay: "\ue30f"
      thunderstormNight: "\ue338"
      default: "\uebaa"
    weather_card:
      blur: True
      round_corners: True
      round_corners_type: "normal"
      border_color: "System"
      alignment: "right"
      direction: "down"
      icon_size: 64
    label_shadow:
      enabled: true
      color: "black"
      radius: 3
      offset: [ 1, 1 ]
```

## Description of Options

- **label:** The format string for the weather label. You can use placeholders like `{temp}`, `{min_temp}`, `{max_temp}`, `{feelslike}`, `{location}`, `{humidity}`, `{icon}`, `{conditions}`, `{wind}`, `{wind_dir}`, `{wind_degree}`, `{pressure}`, `{precip}`, `{uv}`, `{vis}`, `{cloud}`.
- **label_alt:** The alternative format string for the weather label. Useful for displaying additional weather details.
- **update_interval:** The interval in seconds to update the weather data. Must be between 60 and 36000000.
- **hide_decimal:** Whether to hide the decimal part of the temperature.
- **location:** The location for which to fetch the weather data. You can use example "USA Los Angeles 90006" {COUNTRY CITY ZIP_CODE}, or just city. Location can be set to `env`, this means you have to set `YASB_WEATHER_LOCATION` in environment variable or you can set it directly in the configuration file.
- **api_key:** The API key for accessing the weather service. You can get free API key `weatherapi.com`. API key can be set to `env`, this means you have to set `YASB_WEATHER_API_KEY` in environment variable or you can set it directly in the configuration file.
- **show_alerts:** Whether to show weather alerts.
- **units:** The units for the weather data. Can be `'metric'` or `'imperial'`.
- **icons:** A dictionary of icons for different weather conditions `sunnyDay`, `sunnyNight`, `clearDay`, `clearNight`, `cloudyDay`, `cloudyNight`, `rainyDay`, `rainyNight`, `snowyIcyDay`, `snowyIcyNight`, `blizzard`, `default`.
- **weather_card:** Configuration for the weather card popup display. Controls visibility, appearance, and positioning.
  - **blur:** Enable blur effect for the weather card.
  - **round_corners:** Enable round corners for weather card.
  - **round_corners_type:** Border type for weather card can be `normal` and `small`. Default is `normal`.
  - **border_color:** Border color for weather card can be `None`, `System` or `Hex Color` `"#ff0000"`.
  - **alignment:** Alignment of the weather card. Possible values are `left`, `center`, and `right`.
  - **direction:** Direction of the weather card. Possible values are `up` and `down`.
  - **offset_top:** Offset from the top of the widget in pixels.
  - **offset_left:** Offset from the left of the widget in pixels.
  - **icon_size:** Size of the weather icon in pixels.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.
- **animation:** A dictionary specifying the animation settings for the widget. It contains three keys: `enabled`, `type`, and `duration`. The `type` can be `fadeInOut` and the `duration` is the animation duration in milliseconds.
- **container_padding**: Explicitly set padding inside widget container. Use this option to set padding inside the widget container. You can set padding for top, left, bottom and right sides of the widget container.
- **container_shadow:** Container shadow options.
- **label_shadow:** Label shadow options.

## Example Style
```css
.weather-widget {}
.weather-widget .widget-container {}
.weather-widget .label {}
.weather-widget .label.alt {}
.weather-widget .icon {}

/* Individual weather icons */
.weather-widget .icon.sunnyDay {}
.weather-widget .icon.clearNight {}
.weather-widget .icon.cloudyDay {}
.weather-widget .icon.cloudyNight {}
.weather-widget .icon.rainyDay {}
.weather-widget .icon.rainyNight {}
.weather-widget .icon.snowyIcyDay {}
.weather-widget .icon.snowyIcyNight {}
.weather-widget .icon.blizzardDay {}
.weather-widget .icon.blizzardNight {}
.weather-widget .icon.foggyDay {}
.weather-widget .icon.foggyNight {}
.weather-widget .icon.thunderstormDay {}
.weather-widget .icon.thunderstormNight {}
.weather-widget .icon.default {}

/* Weather card style */
.weather-card {
    background-color: rgba(17, 17, 27, 0.5);
}
.weather-card-today {
    border: 1px solid #282936;
    border-radius: 8px;
    background-color:  rgba(17, 17, 27, 0.2);
}
.weather-card-today .label {
    font-size: 12px;
}
.weather-card-today .label.location {
    font-size: 24px;
    font-weight: 700;
}
.weather-card-today .label.alert {
    font-size: 12px;
    font-weight: 700;
    background-color: rgba(247, 199, 42, 0.05);
    border: 1px solid rgba(247, 209, 42, 0.1);
    color: rgba(196, 181, 162, 0.85);
    border-radius: 6px;
    padding: 5px 0;
}
.weather-card-day {
    border: 1px solid #45475a;
    border-radius: 8px;
    background-color:  rgba(17, 17, 27, 0.2);
}
.weather-card-day .label {
    font-size: 12px;
}
```

## Preview of the weather card
![Weather YASB Widget](assets/955689587-g4ejd6c7-22ab-6cde-9822-34789abcdef.png)
