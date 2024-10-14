# Weather Widget Options
| Option          | Type    | Default                                                                 | Description                                                                 |
|-----------------|---------|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `label`         | string  | `'<span>{icon}</span> {temp_c}'`                                        | The format string for the weather label. You can use placeholders like `{temp_c}`, `{icon}`, etc. |
| `label_alt`     | string  | `'{location}: Min {min_temp_c}, Max {max_temp_c}, Humidity {humidity}'` | The alternative format string for the weather label. Useful for displaying additional weather details. |
| `update_interval` | integer | `3600`                                                                 | The interval in seconds to update the weather data. Must be between 60 and 36000000. |
| `hide_decimal`  | boolean | `False`                                                                 | Whether to hide the decimal part of the temperature. |
| `location`      | string  | `'London'`                                                              | The location for which to fetch the weather data. |
| `api_key`       | string  | `'0'`                                                                   | The API key for accessing the weather service. |
| `icons`         | dict    | `{ 'sunnyDay': '\ue30d', 'clearNight': '\ue32b', 'cloudyDay': '\ue312', 'cloudyNight': '\ue311', 'rainyDay': '\udb81\ude7e', 'rainyNight': '\udb81\ude7e', 'snowyIcyDay': '\udb81\udd98', 'snowyIcyNight': '\udb81\udd98', 'blizzard': '\uebaa', 'default': '\uebaa' }` | A dictionary of icons for different weather conditions. |
| `callbacks`     | dict    | `{ 'on_left': 'do_nothing', 'on_middle': 'do_nothing', 'on_right': 'do_nothing' }` | Callbacks for mouse events on the weather widget. |

## Example Configuration

```yaml
weather:
  type: "yasb.weather.WeatherWidget"
  options:
    label: '<span>{icon}</span> {temp_c}'
    label_alt: '{location}: Min {min_temp_c}, Max {max_temp_c}, Humidity {humidity}'
    api_key: '209841561465465461' # Get your free API key from https://www.weatherapi.com/
    update_interval: 600 # Update interval in seconds, Min 600 seconds
    hide_decimal: true
    location: 'Los Angeles, CA, USA' # You can use "USA Los Angeles 90006" {COUNTRY CITY ZIP_CODE}, or just city.
    callbacks:
      on_left: "toggle_label"
    icons: 
      sunnyDay: "\ue30d"
      clearNight: "\ue32b"
      cloudyDay: "\udb81\udd99"
      cloudyNight: "\ue311"
      rainyDay: "\udb81\ude7e"
      rainyNight: "\udb81\ude7e"
      snowyIcyDay: "\udb81\udd98"
      snowyIcyNight: "\udb81\udd98"
      blizzard: "\uebaa"
      default: "\uebaa"
```

## Description of Options

- **label:** The format string for the weather label. You can use placeholders like `{temp_c}`, `{min_temp_c}`, `{max_temp_c}`, `{temp_f}`, `{min_temp_f}`, `{max_temp_f}`, `{location}`, `{humidity}`, `{icon}`, `{conditions}`.
- **label_alt:** The alternative format string for the weather label. Useful for displaying additional weather details.
- **update_interval:** The interval in seconds to update the weather data. Must be between 60 and 36000000.
- **hide_decimal:** Whether to hide the decimal part of the temperature.
- **location:** The location for which to fetch the weather data. You can use example "USA Los Angeles 90006" {COUNTRY CITY ZIP_CODE}, or just city.
- **api_key:** The API key for accessing the weather service. You can get free API key `weatherapi.com`
- **icons:** A dictionary of icons for different weather conditions `sunnyDay`, `sunnyNight`, `clearDay`, `clearNight`, `cloudyDay`, `cloudyNight`, `rainyDay`, `rainyNight`, `snowyIcyDay`, `snowyIcyNight`, `blizzard`, `default`.
- **callbacks:** A dictionary specifying the callbacks for mouse events. The keys are `on_left`, `on_middle`, and `on_right`, and the values are the names of the callback functions.

## Example Style
```css
.weather-widget {}
.weather-widget .widget-container {}
.weather-widget .label {}
.weather-widget .label.alt {}
.weather-widget .icon {}
.weather-widget .icon.cloudyDay {}
.weather-widget .icon.cloudyNight {} 
.weather-widget .icon.rainyDay {} 
.weather-widget .icon.rainyNight {} 
.weather-widget .icon.snowyIcyDay {} 
.weather-widget .icon.snowyIcyNight {} 
.weather-widget .icon.blizzard {} 
.weather-widget .icon.default {}
```

