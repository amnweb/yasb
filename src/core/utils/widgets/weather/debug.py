import math
import random
from datetime import datetime, timedelta

from PyQt6.QtCore import QPointF

from core.utils.widgets.weather.widgets import HourlyData


def generate_debug_data(
    start_time: datetime | None = None, orig_data: list[HourlyData] | None = None
) -> list[HourlyData]:
    """
    Generates a believable list of HourlyData for debugging purposes.
    Generates 48 hours of data starting from midnight of the current day (or provided start_time).
    """
    if start_time is None:
        start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    data: list[HourlyData] = []

    # Base parameters for "believable" weather
    base_temp = 20
    temp_variation = 5

    for i in range(48):
        current_time = start_time + timedelta(hours=i)

        # Temperature curve (sinusoidal)
        hour_angle = (current_time.hour - 4) * (2 * math.pi / 24)
        temp_offset = math.sin(hour_angle) * temp_variation
        temp = int(base_temp + temp_offset + random.uniform(-1, 1))

        # Wind (random but somewhat consistent)
        wind = round(random.uniform(5.0, 20.0), 1)

        # Precipitation chances
        chance_of_rain = 0
        chance_of_snow = 0

        # 1. Intersection/Overlap Block (Hours 7-11)
        # Both rain and snow are present here (e.g., sleet/mixed conditions)
        if 7 <= i <= 11:
            chance_of_rain = random.randint(30, 60)
            chance_of_snow = random.randint(30, 60)

        # 2. Pure Rain Block (Hours 2-6)
        # Precedes the overlap
        elif 2 <= i < 7:
            chance_of_rain = random.randint(80, 100)
            chance_of_snow = 0

        # 3. Pure Snow Block (Hours 12-16)
        # Follows the overlap
        elif 12 <= i <= 16:
            chance_of_rain = 0
            chance_of_snow = random.randint(80, 100)

        # 4. Scattered/Random logic for the rest of the timeline
        else:
            precip_roll = random.random()
            if precip_roll < 0.2:
                intensity = random.randint(10, 100)
                if temp < 5:
                    chance_of_snow = intensity
                else:
                    chance_of_rain = intensity

        humidity = random.randint(40, 100)

        # Get original icon from orig_data (we don't generate icons here)
        icon_url = ""
        if orig_data:
            try:
                icon_url = orig_data[i].icon_url
            except IndexError:
                icon_url = ""

        hourly_item = HourlyData(
            temp=temp,
            wind=wind,
            icon_url=icon_url,
            time=current_time,
            chance_of_rain=chance_of_rain,
            chance_of_snow=chance_of_snow,
            humidity=humidity,
            graph_point=QPointF(),
        )
        data.append(hourly_item)

    return data
