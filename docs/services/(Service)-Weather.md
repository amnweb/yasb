# Weather

`import Yasb`

The weather now, by hour and by day, for a place you choose, from Open-Meteo, with a search for places. Fetched
every `updateInterval`, the last forecast is kept and shows at once when YASB starts, if it has the same units and
enough days. All WeatherForecast objects
with the same `locationId`, `units`, `forecastDays` and `updateInterval` share one fetch.

The place and its last forecast are saved by location id in `%LOCALAPPDATA%\YASB\weather.json`.

## WeatherForecast

### Properties

#### locationId : string

The saved place to show. WeatherForecast objects with the same id show the same place, give one another id for
another place.

Default: `"weather"`

#### units : string

`metric` (°C, km/h, mm) or `imperial` (°F, mph, inches). Any other value is taken as `metric`.

Default: `"metric"`

#### forecastDays : int

Days to forecast, today included, from 1 to 14.

Default: `7`

#### updateInterval : int

Milliseconds between two fetches, from 60000 to 86400000. After a failed fetch, the next try is 15 seconds later.

Default: `3600000`

#### hideDecimal : bool

When `true`, the temperature texts are rounded to whole degrees.

Default: `false`

#### timeFormat : string

How the time texts are written: `24h` (`06:41`) or `12h` (`6:41 AM`). Any other value is taken as `24h`.

Default: `"24h"`

#### hasLocation : bool `read-only`

`true` when a place is saved for `locationId`.

#### location : object `read-only`

The saved place, empty without one:

- `name` : string, the place's name.
- `region` : string, where it lies, its regions and country joined with commas.
- `latitude` and `longitude` : real, where it is.
- `country` : string, its country.
- `admin1`, `admin2` and `admin3` : string, its regions, as Open-Meteo gives them. `""` when it has none.
- `timezone` : string, its time zone.

#### loading : bool `read-only`

`true` while the forecast is fetched.

#### error : string `read-only`

What went wrong in the last fetch, `""` when nothing. The last forecast stays shown.

- `Open-Meteo: <reason>`, or `Open-Meteo returned HTTP <code>.`: Open-Meteo refused.
- `Could not connect to Open-Meteo.`
- `Open-Meteo sent an answer YASB could not read.`, `Open-Meteo sent an incomplete forecast.` or
  `Could not read the forecast Open-Meteo sent.`

#### updated : date `read-only`

When the forecast shown was fetched. Invalid without one.

#### ready : bool `read-only`

`true` once there is a forecast.

#### values : object `read-only`

Texts of the weather now and today, each `"--"` until there is a forecast:

- `temp` and `feelslike`: the temperature now, and how it feels.
- `min_temp` and `max_temp`: today's low and high.
- `humidity`, `cloud`: humidity and cloud cover now, in %.
- `pressure`, `precipitation`, `wind`: the pressure, precipitation and wind speed now, with their units.
- `wind_dir`: the wind's direction now, in degrees.
- `precipitation_probability`: today's highest chance of precipitation, in %.
- `rain_chance` and `snow_chance`: today's highest chance of precipitation in the hours it rains, or snows.
- `uv`: today's highest UV index.
- `location`: the place's name, also before there is a forecast.
- `condition_text`: the weather now, such as `Partly cloudy`.
- `is_day`: `Day` or `Night`.
- `sunrise` and `sunset`: today's, as `timeFormat` writes them.

#### condition : string `read-only`

The picture for the weather now: a kind of weather followed by `Day` or `Night`, such as `rainyNight`. The kinds are
`sunny`, `cloudy`, `foggy`, `drizzle`, `rainy`, `snowy` and `thunderstorm`, a clear night is `clearNight`.
`default` without a forecast, or for a weather code YASB doesn't know.

#### current : object `read-only`

The weather now, empty without a forecast. See [Forecast values](#forecast-values) for its values, it also has:

- `time` : string, the time of the reading, such as `2026-11-03T06:45`.
- `isDay` : bool, `true` in daylight.
- `condition` : string, the picture, as in `condition`.
- `text` : string, the weather, such as `Slight rain`.
- `temperatureText` and `feelsLikeText` : string, the temperatures as text.

#### days : list `read-only`

Each day, today first, as an object with the daily values (see [Forecast values](#forecast-values)) and:

- `date` : string, such as `2026-11-03`.
- `weekday` : int, 0 for Sunday to 6 for Saturday.
- `condition` : string, the day's picture, always a `Day` one.
- `text` : string, the day's weather.
- `highText`, `lowText`, `feelsLikeHighText` and `feelsLikeLowText` : string, the temperatures as text.
- `sunriseText` and `sunsetText` : string, as `timeFormat` writes them.

#### hours : list `read-only`

For each of `days`, the list of its hours, each an object with the hourly values (see
[Forecast values](#forecast-values)) and:

- `time` : string, the hour, such as `2026-11-03T14:00`.
- `timeText` : string, as `timeFormat` writes it.
- `now` : bool, `true` for the hour under way.
- `isDay` : bool, `true` in daylight.
- `condition` : string, the hour's picture.
- `text` : string, the hour's weather.
- `temperatureText` and `feelsLikeText` : string, the temperatures as text.
- `rainChance` and `snowChance` : int, the chance of precipitation when that hour's weather is rain, or snow,
  otherwise `0`.

#### upcoming : list `read-only`

The next 24 hours, from the one under way, as in `hours`.

#### unitLabels : object `read-only`

The unit of each value, by its name, such as `{temperature: "°C", windSpeed: "km/h", precipitation: "mm"}`.

#### searchResults : list `read-only`

The places the last `search()` found, up to 20, each as in `location`.

#### searching : bool `read-only`

`true` while a search is under way.

#### searchError : string `read-only`

What went wrong in the last search, `""` when nothing.

### Forecast values

Open-Meteo's values in `current`, `days` and `hours`, by these names. Each has its unit in `unitLabels`, and is
`null` when Open-Meteo has none.

Now (`current`): `temperature`, `feelsLike`, `humidity`, `precipitation`, `rain`, `showers`, `snowfall`,
`weatherCode`, `cloudCover`, `pressure` (at sea level), `windSpeed`, `windDirection` and `windGusts`.

Each hour (`hours`, `upcoming`): the same, and `dewPoint`, `precipitationChance`, `visibility` and `uvIndex`.

Each day (`days`): `weatherCode`, `high`, `low`, `feelsLikeHigh`, `feelsLikeLow`, `sunrise` and `sunset` (local
times), `daylight`, `uvIndex` (the highest), `precipitation`, `rain`, `showers`, `snowfall` (the day's totals),
`precipitationHours`, `precipitationChance` (the highest), `windSpeed` and `windGusts` (the highest) and
`windDirection` (the main one).

`weatherCode` is the WMO weather code Open-Meteo gives.

### Functions

#### refresh()

Fetches the forecast now.

#### setLocation(place: object)

Saves this place for `locationId`, for every WeatherForecast with that id: one of `searchResults`, or one of your
own with a `name`, a `latitude` and a `longitude`. Ignored without a numeric `latitude` and `longitude`. A new
place is fetched at once, the same place again keeps its forecast.

#### clearLocation()

Forgets the place of `locationId`, for every WeatherForecast with that id.

#### search(text: string)

Searches for places once typing pauses: a name, narrowed by a region or country after a comma, as in
`Paris, Texas`. The region matches the start of a place's regions, country or country code, in any case and
without accents. Under 2 letters before the comma clears `searchResults`. Names come in Windows' language.

WeatherForecast has no signals.

## Used by

YASB's own Weather widget, listed in [Widgets](./Widgets).
