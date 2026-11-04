import logging
import math
import time
from datetime import date, datetime
from typing import Any, ClassVar, cast

from PyQt6.QtCore import QDateTime, QLocale, QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtNetwork import QNetworkAccessManager

from core.utils.qml import qml_property
from core.widgets.services.weather import location as places
from core.widgets.services.weather.api import (
    CURRENT_FIELDS,
    DAILY_FIELDS,
    HOURLY_FIELDS,
    UNIT_NAMES,
    fold,
    forecast_url,
    get_json,
    in_region,
    search_url,
)
from core.widgets.services.weather.conditions import RAIN_CODES, SNOW_CODES, condition

MIN_INTERVAL_MS = 60000
MAX_INTERVAL_MS = 86400000
# Open-Meteo leaves most of a 15th and 16th day empty
MAX_DAYS = 14
RETRY_MS = 15000
SEARCH_DELAY_MS = 300
# Open-Meteo needs two letters; the region after a comma narrows its answers, so many are asked for
MIN_LETTERS = 2
SEARCH_COUNT = 100
MAX_RESULTS = 20
UNITS = ("metric", "imperial")
TIME_FORMATS = ("24h", "12h")
# Settings that change what Open-Meteo is asked for and how often, so changing them joins another feed
FEED_SETTINGS = {"locationId", "units", "forecastDays", "updateInterval"}
# The label placeholders, each "--" until there is a forecast
PLACEHOLDERS = (
    "temp",
    "feelslike",
    "min_temp",
    "max_temp",
    "humidity",
    "pressure",
    "precipitation",
    "precipitation_probability",
    "rain_chance",
    "snow_chance",
    "wind",
    "wind_dir",
    "cloud",
    "uv",
    "location",
    "condition_text",
    "is_day",
    "sunrise",
    "sunset",
)

# Location id, units, forecast days and update interval
type FeedKey = tuple[str, str, int, int]


def at(series: dict[str, Any], name: str, index: int) -> Any:
    values = series.get(name)
    if not isinstance(values, list) or not 0 <= index < len(cast(list[Any], values)):
        return None
    return cast(list[Any], values)[index]


def fields(series: dict[str, Any], names: dict[str, str], index: int | None = None) -> dict[str, Any]:
    """Open-Meteo's values by the forecast's names for them; with an index, those of one hour or day."""
    return {name: series.get(field) if index is None else at(series, field, index) for name, field in names.items()}


def whole(value: float) -> int:
    """Rounded half up, as QML's Math.round() rounds."""
    return math.floor(value + 0.5)


def measure(value: Any, suffix: str) -> str:
    return "--" if value is None else f"{value}{suffix}"


def percent(value: float | None) -> str:
    return "--" if value is None else f"{whole(value)}%"


def temperature(value: float | None, units: str, hide_decimal: bool) -> str:
    if value is None:
        return "--"
    return f"{whole(value) if hide_decimal else value}{'°F' if units == 'imperial' else '°C'}"


def clock(moment: str | None, time_format: str) -> str:
    """An ISO time such as 2026-11-03T06:41, as 06:41 or 6:41 AM."""
    try:
        parsed = datetime.fromisoformat(moment or "")
    except ValueError:
        return "--"
    return parsed.strftime("%I:%M %p").lstrip("0") if time_format == "12h" else parsed.strftime("%H:%M")


def forecast_days(data: dict[str, Any]) -> int:
    daily = data.get("daily")
    times = cast(dict[str, Any], daily).get("time") if isinstance(daily, dict) else None
    return len(cast(list[Any], times)) if isinstance(times, list) else 0


def covers(data: dict[str, Any]) -> bool:
    """Whether a forecast has every value YASB asks for, which one cached by an older YASB may not."""
    for part, names in (("current", CURRENT_FIELDS), ("hourly", HOURLY_FIELDS), ("daily", DAILY_FIELDS)):
        series = data.get(part)
        if not isinstance(series, dict) or any(field not in series for field in names.values()):
            return False
    return True


def forecast_units(data: dict[str, Any]) -> dict[str, str]:
    """The unit of each value by the forecast's name for it, such as {temperature: "°C", windSpeed: "km/h"}."""
    units: dict[str, str] = {}
    for part, names in (("daily", DAILY_FIELDS), ("hourly", HOURLY_FIELDS), ("current", CURRENT_FIELDS)):
        given = data.get(f"{part}_units")
        if not isinstance(given, dict):
            continue
        given = cast(dict[str, Any], given)
        for name, field in names.items():
            if field in given:
                units[name] = UNIT_NAMES.get(str(given[field]), str(given[field]))
    return units


def empty_model(place: dict[str, Any] | None) -> dict[str, Any]:
    values = dict.fromkeys(PLACEHOLDERS, "--")
    if place is not None:
        values["location"] = place["name"]
    return {
        "values": values,
        "condition": "default",
        "current": {},
        "days": [],
        "hours": [],
        "upcoming": [],
        "unitLabels": {},
    }


def forecast_model(data: dict[str, Any], settings: dict[str, Any], place: dict[str, Any]) -> dict[str, Any]:
    """Everything Open-Meteo sent, by the forecast's names, with the text the settings shape and the label values."""
    units, time_format = settings["units"], settings["timeFormat"]
    dates: list[str] = data["daily"]["time"][: settings["forecastDays"]]
    times: list[str] = data["hourly"]["time"]
    now = f"{data['current']['time'][:13]}:00"
    unit_of = forecast_units(data)

    def temp(value: float | None) -> str:
        return temperature(value, units, settings["hideDecimal"])

    current: dict[str, Any] = {"time": data["current"]["time"], **fields(data["current"], CURRENT_FIELDS)}
    current["isDay"] = current["isDay"] != 0
    current["condition"], current["text"] = condition(current["weatherCode"], current["isDay"])
    current["temperatureText"] = temp(current["temperature"])
    current["feelsLikeText"] = temp(current["feelsLike"])

    hours: list[dict[str, Any]] = []
    for index, moment in enumerate(times):
        hour: dict[str, Any] = {"time": moment, **fields(data["hourly"], HOURLY_FIELDS, index)}
        hour["isDay"] = hour["isDay"] != 0
        hour["condition"], hour["text"] = condition(hour["weatherCode"], hour["isDay"])
        # A chance of precipitation is a chance of rain or of snow by the weather that hour
        chance = hour["precipitationChance"] or 0
        hour.update(
            timeText=clock(moment, time_format),
            now=moment == now,
            temperatureText=temp(hour["temperature"]),
            feelsLikeText=temp(hour["feelsLike"]),
            rainChance=chance if hour["weatherCode"] in RAIN_CODES else 0,
            snowChance=chance if hour["weatherCode"] in SNOW_CODES else 0,
        )
        hours.append(hour)

    days: list[dict[str, Any]] = []
    for index, day in enumerate(dates):
        entry: dict[str, Any] = {"date": day, **fields(data["daily"], DAILY_FIELDS, index)}
        entry["condition"], entry["text"] = condition(entry["weatherCode"], True)
        entry.update(
            # 0 for Sunday, as Qt.locale().dayName() counts
            weekday=date.fromisoformat(day).isoweekday() % 7,
            highText=temp(entry["high"]),
            lowText=temp(entry["low"]),
            feelsLikeHighText=temp(entry["feelsLikeHigh"]),
            feelsLikeLowText=temp(entry["feelsLikeLow"]),
            sunriseText=clock(entry["sunrise"], time_format),
            sunsetText=clock(entry["sunset"], time_format),
        )
        days.append(entry)

    by_day = [[hour for hour in hours if hour["time"].startswith(day)] for day in dates]
    start = next((index for index, hour in enumerate(hours) if hour["time"] >= now), len(hours))
    # Today's chance of rain or snow, from the hours it rains or snows
    rain_chance = max((hour["precipitationChance"] or 0 for hour in by_day[0] if (hour["rain"] or 0) > 0), default=0)
    snow_chance = max(
        (hour["precipitationChance"] or 0 for hour in by_day[0] if (hour["snowfall"] or 0) > 0), default=0
    )

    def amount(value: float | None, name: str) -> str:
        return measure(value, f" {unit_of[name]}" if unit_of.get(name) else "")

    today = days[0]
    values = {
        "temp": current["temperatureText"],
        "feelslike": current["feelsLikeText"],
        "min_temp": today["lowText"],
        "max_temp": today["highText"],
        "humidity": percent(current["humidity"]),
        "pressure": amount(current["pressure"], "pressure"),
        "precipitation": amount(current["precipitation"], "precipitation"),
        "precipitation_probability": percent(today["precipitationChance"]),
        "rain_chance": percent(rain_chance),
        "snow_chance": percent(snow_chance),
        "wind": amount(current["windSpeed"], "windSpeed"),
        "wind_dir": measure(current["windDirection"], "°"),
        "cloud": percent(current["cloudCover"]),
        "uv": measure(today["uvIndex"], ""),
        "location": place["name"],
        "condition_text": current["text"],
        "is_day": "Day" if current["isDay"] else "Night",
        "sunrise": today["sunriseText"],
        "sunset": today["sunsetText"],
    }

    return {
        "values": values,
        "condition": current["condition"],
        "current": current,
        "days": days,
        "hours": by_day,
        "upcoming": hours[start : start + 24],
        "unitLabels": unit_of,
    }


class ForecastFeed(QObject):
    """One place's forecast in some units, fetched on its own schedule for every widget that shows it."""

    changed = pyqtSignal()

    _feeds: ClassVar[dict[FeedKey, ForecastFeed]] = {}

    def __init__(self, key: FeedKey) -> None:
        super().__init__()
        self.key = key
        self.location_id, self.units, self.days, self.interval = key
        self.location = places.load_location(self.location_id)
        self.data: dict[str, Any] | None = None
        # When data was fetched, in ms since the epoch
        self.fetched_at = 0
        self.loading = False
        self.error = ""
        self._users = 0
        self._request = 0
        self._network = QNetworkAccessManager(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.fetch)
        if self.location is None:
            return
        cached, fetched_at, units = places.load_weather_cache(self.location_id)
        if cached is not None and units == self.units and forecast_days(cached) >= self.days and covers(cached):
            self.data, self.fetched_at = cached, fetched_at
        # The first fetch waits for the bar, and for the cached forecast to be due
        age = int(time.time() * 1000) - self.fetched_at
        self._timer.start(max(0, min(self.interval - age, self.interval)))

    @classmethod
    def join(cls, key: FeedKey, user: QObject) -> ForecastFeed:
        feed = cls._feeds.get(key)
        if feed is None:
            feed = cls._feeds[key] = cls(key)
        feed._users += 1
        user.destroyed.connect(feed._user_destroyed)
        return feed

    def leave(self, user: QObject) -> None:
        user.destroyed.disconnect(self._user_destroyed)
        self._user_destroyed()

    def _user_destroyed(self) -> None:
        self._users -= 1
        if self._users > 0:
            return
        if type(self)._feeds.get(self.key) is self:
            del type(self)._feeds[self.key]
        # An answer still on its way is dropped
        self._request += 1
        self._timer.stop()
        self.deleteLater()

    @classmethod
    def move(cls, location_id: str, place: dict[str, Any] | None) -> None:
        """Saves the place for the location id, or forgets it for None, in every widget that shows the id.

        A new place is fetched at once; the same place again keeps its forecast.
        """
        before = places.load_location(location_id)
        if place is None:
            places.delete_location(location_id)
        else:
            places.save_location(location_id, place)
        location = places.load_location(location_id)
        moved = location is None or before is None or any(before[f] != location[f] for f in places.COORDINATES)
        for feed in list(cls._feeds.values()):
            if feed.location_id != location_id:
                continue
            feed.location = location
            if moved:
                # An answer for the old place is dropped
                feed._request += 1
                feed._timer.stop()
                feed.data, feed.fetched_at, feed.loading, feed.error = None, 0, False, ""
            feed.changed.emit()
            if moved:
                feed.fetch()

    @pyqtSlot()
    def fetch(self) -> None:
        if self.location is None:
            return
        self._timer.stop()
        self._request += 1
        request = self._request
        self.loading = True
        self.changed.emit()
        url = forecast_url(self.location["latitude"], self.location["longitude"], self.units, self.days)
        get_json(self._network, url, lambda data, error: self._receive(request, data, error))

    def _receive(self, request: int, data: Any, error: str) -> None:
        if request != self._request:
            return
        forecast = cast(dict[str, Any], data) if isinstance(data, dict) else {}
        if not error and not all(isinstance(forecast.get(part), dict) for part in ("current", "daily", "hourly")):
            error = "Open-Meteo sent an incomplete forecast."
        if error:
            # The last forecast stays until one comes
            self._timer.start(RETRY_MS)
        else:
            self.data, self.fetched_at = forecast, int(time.time() * 1000)
            places.save_weather_cache(self.location_id, forecast, self.units)
            self._timer.start(self.interval)
        self.loading, self.error = False, error
        self.changed.emit()


def _setting(kind: type | str, name: str, notify: pyqtSignal) -> pyqtProperty[Any]:
    def get(forecast: WeatherForecast) -> Any:
        return forecast.setting(name)

    def set_value(forecast: WeatherForecast, value: Any) -> None:
        forecast.change_setting(name, value)

    return pyqtProperty(kind, get, set_value, notify=notify)


class WeatherForecast(QObject):
    """Open-Meteo's forecast for one widget, from the feed it shares with every widget asking for the same."""

    settingsChanged = pyqtSignal()
    forecastChanged = pyqtSignal()
    stateChanged = pyqtSignal()
    searchChanged = pyqtSignal()

    # Widgets with the same id show the same saved place; give a widget its own id for another place
    locationId = _setting(str, "locationId", settingsChanged)
    # metric or imperial
    units = _setting(str, "units", settingsChanged)
    forecastDays = _setting(int, "forecastDays", settingsChanged)
    updateInterval = _setting(int, "updateInterval", settingsChanged)
    hideDecimal = _setting(bool, "hideDecimal", settingsChanged)
    # 24h or 12h
    timeFormat = _setting(str, "timeFormat", settingsChanged)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings: dict[str, Any] = {
            "locationId": "weather",
            "units": "metric",
            "forecastDays": 7,
            "updateInterval": 3600000,
            "hideDecimal": False,
            "timeFormat": "24h",
        }
        self._feed: ForecastFeed | None = None
        self._model = empty_model(None)
        self._location: dict[str, Any] = {}
        self._loading = False
        self._error = ""
        self._updated = 0
        self._query = ""
        self._search_results: list[dict[str, Any]] = []
        self._searching = False
        self._search_error = ""
        self._search_request = 0
        self._network: QNetworkAccessManager | None = None

        # Open-Meteo is searched once typing pauses
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DELAY_MS)
        self._search_timer.timeout.connect(self._send_search)

        # QML sets the settings after creating the object, so the feed is joined once they are in
        self._join_timer = QTimer(self)
        self._join_timer.setSingleShot(True)
        self._join_timer.setInterval(0)
        self._join_timer.timeout.connect(self._join)
        self._join_timer.start()

    def setting(self, name: str) -> Any:
        return self._settings[name]

    def change_setting(self, name: str, value: Any) -> None:
        if name == "units" and value not in UNITS:
            value = "metric"
        elif name == "timeFormat" and value not in TIME_FORMATS:
            value = "24h"
        elif name == "forecastDays":
            value = max(1, min(value, MAX_DAYS))
        elif name == "updateInterval":
            value = max(MIN_INTERVAL_MS, min(value, MAX_INTERVAL_MS))
        if value == self._settings[name]:
            return
        self._settings[name] = value
        self.settingsChanged.emit()
        if name in FEED_SETTINGS:
            self._join_timer.start()
        else:
            self._publish()

    @qml_property(bool, notify=stateChanged)
    def hasLocation(self) -> bool:
        return bool(self._location)

    # The saved place: {name, region, latitude, longitude, country, admin1, admin2, admin3, timezone}; empty
    # without one, when a widget shows a way to choose it
    @qml_property("QVariantMap", notify=stateChanged)
    def location(self) -> dict[str, Any]:
        return self._location

    @qml_property(bool, notify=stateChanged)
    def loading(self) -> bool:
        return self._loading

    @qml_property(str, notify=stateChanged)
    def error(self) -> str:
        return self._error

    # When the forecast shown was fetched; invalid without one
    @qml_property(QDateTime, notify=stateChanged)
    def updated(self) -> QDateTime:
        return QDateTime.fromMSecsSinceEpoch(self._updated) if self._updated else QDateTime()

    @qml_property(bool, notify=forecastChanged)
    def ready(self) -> bool:
        return bool(self._model["days"])

    # The label placeholders as text, such as {temp: "21°C"}
    @qml_property("QVariantMap", notify=forecastChanged)
    def values(self) -> dict[str, str]:
        return self._model["values"]

    # The picture for now, such as sunnyDay or rainyNight; default without a forecast
    @qml_property(str, notify=forecastChanged)
    def condition(self) -> str:
        return self._model["condition"]

    # The weather now: every current value Open-Meteo sends, by the names in CURRENT_FIELDS, with time, condition,
    # text, temperatureText and feelsLikeText; empty without a forecast
    @qml_property("QVariantMap", notify=forecastChanged)
    def current(self) -> dict[str, Any]:
        return self._model["current"]

    # Each day, today first: every daily value by the names in DAILY_FIELDS, with date, weekday, condition, text and
    # highText, lowText, feelsLikeHighText, feelsLikeLowText, sunriseText and sunsetText
    @qml_property("QVariantList", notify=forecastChanged)
    def days(self) -> list[dict[str, Any]]:
        return self._model["days"]

    # The hours of each day: every hourly value by the names in HOURLY_FIELDS, with time, timeText, now, condition,
    # text, temperatureText, feelsLikeText, rainChance and snowChance
    @qml_property("QVariantList", notify=forecastChanged)
    def hours(self) -> list[list[dict[str, Any]]]:
        return self._model["hours"]

    # The next 24 hours, from the one under way, as in hours
    @qml_property("QVariantList", notify=forecastChanged)
    def upcoming(self) -> list[dict[str, Any]]:
        return self._model["upcoming"]

    # The unit of each value by its name, such as {temperature: "°C", windSpeed: "km/h", precipitation: "mm"}
    @qml_property("QVariantMap", notify=forecastChanged)
    def unitLabels(self) -> dict[str, str]:
        return self._model["unitLabels"]

    # The places the last search found, each a place for setLocation(), as in location
    @qml_property("QVariantList", notify=searchChanged)
    def searchResults(self) -> list[dict[str, Any]]:
        return self._search_results

    @qml_property(bool, notify=searchChanged)
    def searching(self) -> bool:
        return self._searching

    @qml_property(str, notify=searchChanged)
    def searchError(self) -> str:
        return self._search_error

    def _join(self) -> None:
        settings = self._settings
        key: FeedKey = (
            settings["locationId"],
            settings["units"],
            settings["forecastDays"],
            settings["updateInterval"],
        )
        if self._feed is not None and self._feed.key == key:
            return
        if self._feed is not None:
            self._feed.changed.disconnect(self._publish)
            self._feed.leave(self)
        self._feed = ForecastFeed.join(key, self)
        self._feed.changed.connect(self._publish)
        self._publish()

    def _publish(self) -> None:
        feed = self._feed
        place = feed.location if feed is not None else None
        model = empty_model(place)
        error = feed.error if feed is not None else ""
        if feed is not None and feed.data is not None and place is not None:
            try:
                model = forecast_model(feed.data, self._settings, place)
            except AttributeError, IndexError, KeyError, TypeError, ValueError:
                logging.exception("Could not read the Open-Meteo forecast")
                error = error or "Could not read the forecast Open-Meteo sent."
        if model != self._model:
            self._model = model
            self.forecastChanged.emit()
        location = places.place_row(place) if place is not None else {}
        loading = feed is not None and feed.loading
        updated = feed.fetched_at if feed is not None and feed.data is not None else 0
        if (location, loading, error, updated) != (self._location, self._loading, self._error, self._updated):
            self._location, self._loading, self._error, self._updated = location, loading, error, updated
            self.stateChanged.emit()

    @pyqtSlot()
    def refresh(self) -> None:
        if self._feed is not None:
            self._feed.fetch()

    # Shows a place here and in every widget with this location id: one of searchResults, or a widget's own such as
    # ({ name: "Zagreb", latitude: 45.81, longitude: 15.98 }); the same place again keeps its forecast
    @pyqtSlot("QVariantMap")
    def setLocation(self, place: dict[str, Any]) -> None:
        if places.has_coordinates(place):
            ForecastFeed.move(self._settings["locationId"], place)

    # Forgets the place here and in every widget with this location id
    @pyqtSlot()
    def clearLocation(self) -> None:
        ForecastFeed.move(self._settings["locationId"], None)

    # Searches for places once typing pauses: a name, narrowed by a region after a comma as in "Paris, Texas"
    @pyqtSlot(str)
    def search(self, text: str) -> None:
        self._query = text.strip()
        # Answers to what was typed before are dropped
        self._search_request += 1
        if len(self._query.partition(",")[0].strip()) < MIN_LETTERS:
            self._search_timer.stop()
            self._set_search([], False, "")
            return
        self._set_search(self._search_results, True, "")
        self._search_timer.start()

    def _send_search(self) -> None:
        if self._network is None:
            self._network = QNetworkAccessManager(self)
        request = self._search_request
        name, _, region = self._query.partition(",")
        folded = fold(region.strip())
        language = QLocale.system().name().partition("_")[0].lower() or "en"
        get_json(
            self._network,
            search_url(name.strip(), SEARCH_COUNT, language),
            lambda data, error: self._receive_search(request, folded, data, error),
        )

    def _receive_search(self, request: int, region: str, data: Any, error: str) -> None:
        if request != self._search_request:
            return
        results: Any = cast(dict[str, Any], data).get("results") if isinstance(data, dict) else None
        found: list[dict[str, Any]] = []
        for item in cast(list[Any], results) if isinstance(results, list) else []:
            place = cast(dict[str, Any], item) if isinstance(item, dict) else {}
            if places.has_coordinates(place) and in_region(place, region):
                found.append(places.place_row(place))
        self._set_search(found[:MAX_RESULTS], False, error)

    def _set_search(self, results: list[dict[str, Any]], searching: bool, error: str) -> None:
        if (results, searching, error) != (self._search_results, self._searching, self._search_error):
            self._search_results, self._searching, self._search_error = results, searching, error
            self.searchChanged.emit()
