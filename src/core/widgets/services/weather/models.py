"""Pydantic models for weatherapi.com API response validation."""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_percent(v: object) -> object:
    """
    Strip trailing '%' or '°' so '0.0%' can be parsed as a float.
    Probably we don't need this but who knows, maybe some API fields can come with a percent sign.
    """
    if isinstance(v, str):
        v = re.sub(r"[%°]+$", "", v.strip())
    return v


class _WeatherBase(BaseModel):
    model_config = ConfigDict(extra="allow")


class Condition(_WeatherBase):
    text: str = "Unknown"
    icon: str = ""
    code: int = 0


class Current(_WeatherBase):
    temp_c: float = 0.0
    temp_f: float = 0.0
    is_day: int = 1
    condition: Condition = Condition()
    wind_mph: float = 0.0
    wind_kph: float = 0.0
    wind_degree: float = 0.0
    wind_dir: str = ""
    pressure_mb: float = 0.0
    pressure_in: float = 0.0
    precip_mm: float = 0.0
    precip_in: float = 0.0
    humidity: float = 0.0
    cloud: float = 0.0
    feelslike_c: float = 0.0
    feelslike_f: float = 0.0
    vis_km: float = 0.0
    vis_miles: float = 0.0
    uv: float = 0.0

    @field_validator("humidity", "cloud", mode="before")
    @classmethod
    def _clean_percent(cls, v: object) -> object:
        return _strip_percent(v)


class Location(_WeatherBase):
    name: str = "Unknown"
    region: str = ""
    country: str = ""
    tz_id: str = ""
    localtime: str = ""


class ForecastDay(_WeatherBase):
    maxtemp_c: float = 0.0
    maxtemp_f: float = 0.0
    mintemp_c: float = 0.0
    mintemp_f: float = 0.0
    daily_chance_of_rain: float = 0.0
    daily_chance_of_snow: float = 0.0
    condition: Condition = Condition()

    @field_validator("daily_chance_of_rain", "daily_chance_of_snow", mode="before")
    @classmethod
    def _clean_percent(cls, v: object) -> object:
        return _strip_percent(v)


class HourForecast(_WeatherBase):
    time: str = ""
    temp_c: float = 0.0
    temp_f: float = 0.0
    wind_kph: float = 0.0
    wind_mph: float = 0.0
    humidity: float = 0.0
    chance_of_rain: float = 0.0
    chance_of_snow: float = 0.0
    condition: Condition = Condition()

    @field_validator("chance_of_rain", "chance_of_snow", "humidity", mode="before")
    @classmethod
    def _clean_percent(cls, v: object) -> object:
        return _strip_percent(v)


class ForecastDayEntry(_WeatherBase):
    date: str = ""
    day: ForecastDay = ForecastDay()
    hour: list[HourForecast] = Field(default_factory=list)


class Forecast(_WeatherBase):
    forecastday: list[ForecastDayEntry] = Field(default_factory=list)


class Alert(_WeatherBase):
    headline: str | None = None
    desc: str | None = None
    expires: str | None = None


class Alerts(_WeatherBase):
    alert: list[Alert] = Field(default_factory=list)


class WeatherApiResponse(_WeatherBase):
    location: Location = Location()
    current: Current = Current()
    forecast: Forecast = Forecast()
    alerts: Alerts = Alerts()
