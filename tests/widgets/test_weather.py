# pyright: reportPrivateUsage=false

import copy
import json
import re
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QMetaObject, QObject, Qt, QTimer, QUrl, QUrlQuery
from PyQt6.QtGui import QGuiApplication, QKeyEvent
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError, QQmlProperty
from PyQt6.QtQuick import QQuickItem, QQuickWindow
from PyQt6.QtWidgets import QApplication

from core.qml_types import register_qml_types
from core.utils.system import app_data_path
from core.widget_files import BUILTIN_WIDGETS_DIR
from core.widgets.services.weather import forecast as forecast_module
from core.widgets.services.weather.api import CURRENT_FIELDS, DAILY_FIELDS, HOURLY_FIELDS
from core.widgets.services.weather.conditions import condition
from core.widgets.services.weather.forecast import ForecastFeed, WeatherForecast, forecast_model
from core.widgets.services.weather.location import (
    LOCATION_FILE,
    load_location,
    load_weather_cache,
    save_location,
    save_weather_cache,
)
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait

BERLIN = {
    "name": "Berlin",
    "latitude": 52.52,
    "longitude": 13.41,
    "country": "Germany",
    "admin1": "Land Berlin",
    "timezone": "Europe/Berlin",
}
PLACES = [
    {"name": "Paris", "latitude": 48.85, "longitude": 2.35, "admin1": "Île-de-France", "country": "France"},
    {"name": "Paris", "latitude": 33.66, "longitude": -95.56, "admin1": "Texas", "country": "United States"},
    {"name": "Paris", "latitude": 36.3, "longitude": -88.33, "admin1": "Tennessee", "country": "United States"},
]
SETTINGS = {"units": "metric", "timeFormat": "24h", "hideDecimal": False, "forecastDays": 2}


METRIC_UNITS = {"temperature_2m": "°C", "wind_speed_10m": "km/h", "precipitation": "mm", "pressure_msl": "hPa"}
IMPERIAL_UNITS = {"temperature_2m": "°F", "wind_speed_10m": "mp/h", "precipitation": "inch", "pressure_msl": "hPa"}


def sample(days: int = 2, units: dict[str, str] = METRIC_UNITS) -> dict[str, Any]:
    """Days from 2026-11-03, a Tuesday: rain until 18:00 on the first, then snow, and 14:15 now."""
    dates = [f"2026-11-{3 + day:02d}" for day in range(days)]
    times = [f"{day}T{hour:02d}:00" for day in dates for hour in range(24)]
    codes = [61 if index < 18 else 71 for index in range(len(times))]
    current: dict[str, Any] = dict.fromkeys(CURRENT_FIELDS.values(), 0)
    current.update(
        time="2026-11-03T14:15",
        temperature_2m=12.4,
        apparent_temperature=10.6,
        is_day=1,
        weather_code=61,
        relative_humidity_2m=81,
        pressure_msl=1012.3,
        precipitation=0.4,
        wind_speed_10m=14.2,
        wind_direction_10m=250,
        wind_gusts_10m=31.0,
        cloud_cover=90,
    )
    daily: dict[str, Any] = {field: [0] * days for field in DAILY_FIELDS.values()}
    daily.update(
        time=dates,
        weather_code=[61, 3, 0, 95, 3, 71, 0][:days],
        temperature_2m_max=[13.6, 11.0, 9.5, 8.0, 7.0, 4.0, 6.0][:days],
        temperature_2m_min=[7.2, 5.5, 3.1, 2.0, 1.0, -1.0, 0.0][:days],
        precipitation_probability_max=[70, 10, 0, 40, 0, 60, 0][:days],
        sunrise=[f"{day}T07:01" for day in dates],
        sunset=[f"{day}T16:40" for day in dates],
        uv_index_max=[1.9, 2.2, 2.5, 1.0, 1.5, 0.8, 2.0][:days],
    )
    count = len(times)
    hourly: dict[str, Any] = {field: [0] * count for field in HOURLY_FIELDS.values()}
    hourly.update(
        time=times,
        temperature_2m=[float(index % 24) for index in range(count)],
        weather_code=codes,
        precipitation_probability=[40 if index < 12 else 60 for index in range(count)],
        rain=[0.3 if code == 61 else 0 for code in codes],
        snowfall=[0.2 if code == 71 else 0 for code in codes],
        is_day=[1 if 7 <= index % 24 < 17 else 0 for index in range(count)],
        relative_humidity_2m=[80] * count,
        wind_speed_10m=[10.5] * count,
    )
    return {
        "current": current,
        "current_units": units,
        "daily": daily,
        "daily_units": {"temperature_2m_max": units["temperature_2m"], "precipitation_sum": units["precipitation"]},
        "hourly": hourly,
        "hourly_units": units,
    }


def until(condition: Callable[[], Any]) -> None:
    for _ in range(200):
        if condition():
            return
        wait(10)
    assert condition()


class WeatherApi:
    """Stands in for the Open-Meteo API, so the tests never reach the network."""

    def __init__(self) -> None:
        self.forecast = sample()
        self.places = PLACES
        self.error = ""
        self.asked: list[QUrl] = []

    def get_json(self, _network: Any, url: QUrl, done: Callable[[Any, str], None]) -> None:
        self.asked.append(url)
        data = {"results": self.places} if url.host().startswith("geocoding") else self.forecast
        answer = (None, self.error) if self.error else (copy.deepcopy(data), "")
        QTimer.singleShot(0, lambda: done(*answer))

    def forecasts(self) -> list[QUrlQuery]:
        return [QUrlQuery(url) for url in self.asked if not url.host().startswith("geocoding")]

    def searches(self) -> list[str]:
        return [QUrlQuery(url).queryItemValue("name") for url in self.asked if url.host().startswith("geocoding")]


@pytest.fixture
def api(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> WeatherApi:
    api = WeatherApi()
    monkeypatch.setattr(forecast_module, "get_json", api.get_json)
    monkeypatch.setattr(forecast_module, "SEARCH_DELAY_MS", 20)
    monkeypatch.setattr(ForecastFeed, "_feeds", {})
    app_data_path(LOCATION_FILE).unlink(missing_ok=True)
    return api


def weather(**settings: Any) -> WeatherForecast:
    forecast = WeatherForecast()
    for name, value in settings.items():
        forecast.setProperty(name, value)
    return forecast


def test_every_value_asked_for_reaches_qml():
    model = forecast_model(sample(), SETTINGS, BERLIN)
    assert set(CURRENT_FIELDS) <= set(model["current"])
    assert all(set(DAILY_FIELDS) <= set(day) for day in model["days"])
    assert all(set(HOURLY_FIELDS) <= set(hour) for day in model["hours"] for hour in day)
    assert model["current"]["windGusts"] == 31.0 and model["current"]["isDay"] is True


def test_a_forecast_gives_label_values_and_text_beside_each_number():
    model = forecast_model(sample(), SETTINGS, BERLIN)
    values = model["values"]
    assert (values["temp"], values["feelslike"], values["min_temp"], values["max_temp"]) == (
        "12.4°C",
        "10.6°C",
        "7.2°C",
        "13.6°C",
    )
    assert (values["humidity"], values["wind"], values["cloud"], values["uv"]) == ("81%", "14.2 km/h", "90%", "1.9")
    assert (values["pressure"], values["precipitation"]) == ("1012.3 hPa", "0.4 mm")
    assert (values["sunrise"], values["sunset"], values["location"]) == ("07:01", "16:40", "Berlin")
    # Rain falls until 18:00 at 40 and 60 percent, then snow at 60 percent
    assert (values["rain_chance"], values["snow_chance"]) == ("60%", "60%")
    current = model["current"]
    assert (current["temperature"], current["temperatureText"]) == (12.4, "12.4°C")
    assert (model["condition"], current["condition"], current["text"]) == ("rainyDay", "rainyDay", "Slight rain")
    today, tomorrow = model["days"]
    assert (today["date"], today["weekday"], today["condition"]) == ("2026-11-03", 2, "rainyDay")
    assert (today["high"], today["highText"], today["low"], today["lowText"]) == (13.6, "13.6°C", 7.2, "7.2°C")
    assert (today["sunrise"], today["sunriseText"], today["precipitationChance"]) == ("2026-11-03T07:01", "07:01", 70)
    assert (tomorrow["weekday"], tomorrow["condition"]) == (3, "cloudyDay")
    assert model["unitLabels"]["temperature"] == "°C" and model["unitLabels"]["windSpeed"] == "km/h"


def test_hours_come_by_day_and_from_now():
    model = forecast_model(sample(), SETTINGS, BERLIN)
    today, tomorrow = model["hours"]
    assert [hour["timeText"] for hour in (today[0], today[-1], tomorrow[0])] == ["00:00", "23:00", "00:00"]
    assert [hour["timeText"] for hour in today if hour["now"]] == ["14:00"]
    upcoming = model["upcoming"]
    assert len(upcoming) == 24 and upcoming[0]["now"] and upcoming[0]["time"] == "2026-11-03T14:00"
    assert upcoming[-1]["time"] == "2026-11-04T13:00"
    # A chance of precipitation counts as rain or snow by the weather that hour
    rainy, snowy = upcoming[0], upcoming[4]
    assert (rainy["rainChance"], rainy["snowChance"], snowy["rainChance"], snowy["snowChance"]) == (60, 0, 0, 60)
    assert (rainy["condition"], snowy["condition"], snowy["isDay"]) == ("rainyDay", "snowyNight", False)
    assert (rainy["temperature"], rainy["temperatureText"]) == (14.0, "14.0°C")


def test_imperial_whole_degrees_and_a_12_hour_clock():
    data = sample(units=IMPERIAL_UNITS)
    data["current"].update(is_day=0, weather_code=0, temperature_2m=12.5)
    model = forecast_model(data, {**SETTINGS, "units": "imperial", "hideDecimal": True, "timeFormat": "12h"}, BERLIN)
    values = model["values"]
    # Half a degree rounds up, as the popup rounds
    assert (values["temp"], values["wind"], values["precipitation"], values["is_day"]) == (
        "13°F",
        "14.2 mph",
        "0.4 in",
        "Night",
    )
    assert (values["sunrise"], values["sunset"]) == ("7:01 AM", "4:40 PM")
    assert model["condition"] == "clearNight"
    assert model["upcoming"][0]["timeText"] == "2:00 PM"
    assert (model["unitLabels"]["windSpeed"], model["unitLabels"]["precipitation"]) == ("mph", "in")


def test_weather_codes_name_their_picture():
    assert condition(0, True) == ("sunnyDay", "Clear sky")
    assert condition(0, False) == ("clearNight", "Clear sky")
    assert condition(81, False) == ("rainyNight", "Moderate rain showers")
    assert condition(42, True) == ("default", "Unknown")
    assert condition(None, True) == ("default", "Unknown")


def test_without_a_saved_place_nothing_is_fetched(api: WeatherApi):
    forecast = weather()
    wait(20)
    assert not forecast.property("hasLocation") and not forecast.property("ready")
    assert set(forecast.property("values").values()) == {"--"}
    assert not forecast.property("updated").isValid()
    assert api.asked == []


def test_a_picked_place_is_fetched_once_for_every_widget_with_its_id(api: WeatherApi):
    first, second, elsewhere = weather(), weather(), weather(locationId="work")
    wait(20)
    first.setLocation({**BERLIN, "population": 3426354})
    until(lambda: first.property("ready") and second.property("ready"))
    location = second.property("location")
    assert (location["name"], location["region"], location["latitude"]) == ("Berlin", "Land Berlin, Germany", 52.52)
    assert second.property("values")["temp"] == "12.4°C"
    assert not elsewhere.property("hasLocation")
    assert len(api.forecasts()) == 1
    query = api.forecasts()[0]
    assert (query.queryItemValue("latitude"), query.queryItemValue("forecast_days")) == ("52.52", "7")
    saved = load_location("weather")
    assert saved is not None and saved["name"] == "Berlin" and "population" not in saved
    assert load_weather_cache("weather")[2] == "metric"


def test_a_fresh_cached_forecast_is_shown_and_fetched_only_when_due(api: WeatherApi):
    save_location("weather", BERLIN)
    save_weather_cache("weather", sample(days=7), "metric")
    forecast = weather()
    until(lambda: forecast.property("ready"))
    wait(20)
    assert api.asked == []
    assert forecast.property("updated").toMSecsSinceEpoch() == load_weather_cache("weather")[1]
    # A forecast in other units, or for fewer days, is fetched again
    imperial = weather(units="imperial", forecastDays=10)
    until(lambda: imperial.property("ready"))
    assert [query.queryItemValue("temperature_unit") for query in api.forecasts()] == ["fahrenheit"]


def test_a_cache_from_an_older_yasb_is_fetched_again(api: WeatherApi):
    save_location("weather", BERLIN)
    cached = sample(days=7)
    del cached["hourly"]["dew_point_2m"]
    save_weather_cache("weather", cached, "metric")
    forecast = weather()
    until(lambda: len(api.forecasts()) == 1)
    until(lambda: forecast.property("ready"))


def test_an_old_cached_forecast_is_fetched_again(api: WeatherApi):
    save_location("weather", BERLIN)
    save_weather_cache("weather", sample(days=7), "metric")
    path = app_data_path(LOCATION_FILE)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["weather"]["last_updated_ms"] = int(time.time() * 1000) - 3600001
    path.write_text(json.dumps(data), encoding="utf-8")
    forecast = weather()
    until(lambda: len(api.forecasts()) == 1)
    assert forecast.property("ready")


def test_a_failed_fetch_keeps_the_last_forecast_and_tries_again(api: WeatherApi, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(forecast_module, "RETRY_MS", 50)
    save_location("weather", BERLIN)
    forecast = weather()
    until(lambda: forecast.property("ready"))
    updated = forecast.property("updated").toMSecsSinceEpoch()
    api.error = "Could not connect to Open-Meteo."
    forecast.refresh()
    until(lambda: forecast.property("error") == api.error)
    assert forecast.property("ready") and not forecast.property("loading")
    assert forecast.property("updated").toMSecsSinceEpoch() == updated
    api.error = ""
    until(lambda: forecast.property("error") == "")
    assert len(api.forecasts()) == 3
    assert forecast.property("updated").toMSecsSinceEpoch() > updated


def test_an_incomplete_forecast_is_an_error(api: WeatherApi):
    api.forecast = {"current": {}, "daily": {}}
    save_location("weather", BERLIN)
    forecast = weather()
    until(lambda: forecast.property("error") != "")
    assert not forecast.property("ready")


def test_how_values_read_changes_without_fetching_and_units_fetch_again(api: WeatherApi):
    save_location("weather", BERLIN)
    forecast = weather()
    until(lambda: forecast.property("ready"))
    forecast.setProperty("hideDecimal", True)
    forecast.setProperty("timeFormat", "12h")
    assert (forecast.property("values")["temp"], forecast.property("values")["sunrise"]) == ("12°C", "7:01 AM")
    wait(20)
    assert len(api.forecasts()) == 1
    forecast.setProperty("units", "imperial")
    until(lambda: len(api.forecasts()) == 2)
    assert api.forecasts()[1].queryItemValue("wind_speed_unit") == "mph"


def test_settings_stay_in_range():
    forecast = WeatherForecast()
    for name, value, kept in (
        ("forecastDays", 30, 14),
        ("forecastDays", 0, 1),
        ("updateInterval", 10, 60000),
        ("units", "kelvin", "metric"),
        ("timeFormat", "36h", "24h"),
    ):
        forecast.setProperty(name, value)
        assert forecast.property(name) == kept


def test_the_feed_goes_with_the_last_widget_that_shows_it(api: WeatherApi):
    first, second = weather(), weather()
    wait(20)
    assert len(ForecastFeed._feeds) == 1
    sip.delete(first)
    assert len(ForecastFeed._feeds) == 1
    sip.delete(second)
    assert ForecastFeed._feeds == {}


def test_a_widget_can_set_its_own_place_and_setting_it_again_keeps_the_forecast(api: WeatherApi):
    forecast = weather()
    wait(20)
    forecast.setLocation({"name": "Berlin", "latitude": 52.52, "longitude": 13.41})
    until(lambda: forecast.property("ready"))
    forecast.setLocation({"name": "Berlin Mitte", "latitude": 52.52, "longitude": 13.41})
    wait(20)
    assert len(api.forecasts()) == 1
    assert forecast.property("location")["name"] == "Berlin Mitte" and forecast.property("ready")
    forecast.setLocation(PLACES[0])
    until(lambda: len(api.forecasts()) == 2)


def test_clearing_the_place_clears_every_widget_with_its_id(api: WeatherApi):
    save_location("weather", BERLIN)
    first, second = weather(), weather()
    until(lambda: second.property("ready"))
    first.clearLocation()
    assert not second.property("hasLocation") and not second.property("ready")
    assert load_location("weather") is None


def test_search_waits_for_typing_and_narrows_by_the_region_after_a_comma(api: WeatherApi):
    forecast = weather()
    forecast.search("P")
    assert not forecast.property("searching")
    forecast.search("Par")
    forecast.search("Paris, ten")
    assert forecast.property("searching")
    until(lambda: not forecast.property("searching"))
    assert api.searches() == ["Paris"]
    assert [(place["name"], place["region"]) for place in forecast.property("searchResults")] == [
        ("Paris", "Tennessee, United States")
    ]
    forecast.search("Paris")
    until(lambda: len(forecast.property("searchResults")) == 3)
    forecast.search("")
    assert forecast.property("searchResults") == []


def test_the_answer_to_earlier_text_is_dropped(api: WeatherApi):
    forecast = weather()
    forecast.search("Paris")
    until(lambda: len(api.searches()) == 1)
    forecast.search("P")
    wait(20)
    assert forecast.property("searchResults") == [] and not forecast.property("searching")


def test_a_place_found_by_search_is_the_one_shown(api: WeatherApi):
    forecast = weather()
    forecast.search("Paris, Texas")
    until(lambda: len(forecast.property("searchResults")) == 1)
    forecast.setLocation(forecast.property("searchResults")[0])
    until(lambda: forecast.property("ready"))
    assert forecast.property("location")["admin1"] == "Texas"


@pytest.fixture
def widget(api: WeatherApi) -> Iterator[tuple[QQuickItem, list[str]]]:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect_warnings(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect_warnings)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Weather" / "Weather.qml")))
    item = component.create()
    assert isinstance(item, QQuickItem), [error.toString() for error in component.errors()]
    host = QQuickWindow()
    host.resize(200, 36)
    item.setParentItem(host.contentItem())
    host.show()
    try:
        yield item, warnings
    finally:
        item.setParentItem(None)
        item.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        host.close()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)


def test_the_bar_label_fills_its_placeholders(widget: tuple[QQuickItem, list[str]]):
    item, warnings = widget
    item.setProperty("label", "{temp} in {location}, {unknown}")
    label = find_item(item, "label")
    assert label is not None
    until(lambda: label.property("text") == "Set location")
    forecast = item.findChild(WeatherForecast)
    assert forecast is not None
    forecast.setLocation(BERLIN)
    until(lambda: label.property("text") == "12.4°C in Berlin, {unknown}")
    assert not warnings


def test_the_popup_searches_without_a_place_then_shows_the_forecast(
    api: WeatherApi, widget: tuple[QQuickItem, list[str]]
):
    item, warnings = widget
    wait(20)
    QMetaObject.invokeMethod(item, "togglePopup")
    popup = item.findChild(QObject, "popup")
    assert popup is not None
    window = QQmlProperty.read(popup, "window")
    until(lambda: window.isVisible())
    content = window.contentItem()
    search, field = find_item(content, "search"), find_item(content, "field")
    assert search is not None and field is not None and search.isVisible()
    field.setProperty("text", "Paris, Texas")
    forecast = item.findChild(WeatherForecast)
    assert forecast is not None
    until(lambda: len(forecast.property("searchResults")) == 1)
    # Return picks the first place found
    until(lambda: field.hasActiveFocus())
    key = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    QGuiApplication.sendEvent(window, key)
    until(lambda: (forecast := find_item(content, "forecast")) is not None and forecast.isVisible())
    assert not search.isVisible()
    days = find_item(content, "days")
    assert days is not None and days.property("count") == 2
    temperature = find_item(content, "temperature")
    assert temperature is not None and temperature.property("text") == "12.4°"
    updated = find_item(content, "updated")
    assert updated is not None and updated.isVisible()
    assert re.fullmatch(r"Updated \d\d:\d\d", updated.property("text"))
    saved = load_location("weather")
    assert saved is not None and saved["admin1"] == "Texas"
    assert not warnings


def test_the_popup_stays_on_a_screen_shorter_than_it(api: WeatherApi, widget: tuple[QQuickItem, list[str]]):
    item, warnings = widget
    api.forecast = sample(days=7)
    save_location("weather", BERLIN)
    forecast = item.findChild(WeatherForecast)
    assert forecast is not None
    until(lambda: forecast.property("ready"))
    QMetaObject.invokeMethod(item, "togglePopup")
    popup = item.findChild(QObject, "popup")
    assert popup is not None
    window = QQmlProperty.read(popup, "window")
    until(lambda: window.isVisible())
    screen = QGuiApplication.primaryScreen()
    assert screen is not None
    area = screen.availableGeometry()
    top, height = QQmlProperty.read(popup, "y"), QQmlProperty.read(popup, "height")
    # The test screen is 600 high, less than the popup would take for a week
    assert area.top() <= top and top + height <= area.bottom()
    days = find_item(window.contentItem(), "days")
    assert days is not None and days.property("count") == 7
    assert not warnings
