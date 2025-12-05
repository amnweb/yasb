import math
import random
from dataclasses import dataclass, field
from enum import StrEnum, auto
from itertools import groupby
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject, QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

from core.utils.widgets.weather.utils import create_path_from_points, find_point_and_percent

if TYPE_CHECKING:
    from core.utils.widgets.weather.widgets import HourlyData


class Effect(StrEnum):
    RAIN = auto()
    SNOW = auto()


@dataclass
class Section:
    """A section of the path used to spawn particles"""

    path: QPainterPath
    closed_path: QPainterPath
    x_min: float
    x_max: float
    effect: Effect
    spawn_rate: float = 1.0
    # Density map is used to control the density of particle spawns in a section
    density_map: list[float] = field(default_factory=lambda: [1.0])
    clr: QColor = field(default_factory=lambda: QColor(0, 0, 0, 0))


@dataclass
class RainDrop:
    """State of a single drop"""

    x: float
    y: float
    speed: float | int
    length: float | int

    def __post_init__(self):
        self.y -= self.speed  # Offset to compensate for the first frame


@dataclass
class SnowFlake:
    """State of a single flake"""

    x: float
    y: float
    speed: float = 0
    size: float = 0
    wobble_speed: float = 0
    wobble_range: float = 0
    phase: float = 0

    def __post_init__(self):
        self.speed = random.uniform(0.4, 1.8)
        self.size = random.uniform(2.0, 4.0)
        self.wobble_speed = random.uniform(0.02, 0.05)
        self.wobble_range = random.uniform(0.5, 0.8)
        self.phase = random.uniform(0, 2 * math.pi)


class WeatherAnimationManager(QObject):
    def __init__(
        self,
        parent: QWidget,
        config: dict[str, Any],
    ):
        super().__init__(parent=parent)
        self.config = config
        self.anim_config = self.config["weather_animation"]
        self.parent_widget = parent

        self.rain_colors = QColor("white"), QColor("black")
        self.snow_colors = QColor("white"), QColor("black")

        self.drops: list[RainDrop] = []
        self.flakes: list[SnowFlake] = []

        self.animation_frame = 0

        self.source_path = QPainterPath()
        self.hourly_data: list[HourlyData] = []

        self.sections: list[Section] = []

        if self.anim_config["enabled"]:
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._update_animation_state)
            self.timer.start(16)

    def update_data(
        self,
        hourly_data: list[HourlyData],
        path: QPainterPath,
        data_type: str,
        colors: dict[str, tuple[QColor, QColor]],
    ):
        self.source_path = path
        self.hourly_data = hourly_data
        self.data_type = data_type
        self.rain_colors = colors["rain"]
        self.snow_colors = colors["snow"]
        self._calculate_static_data()

    def _calculate_static_data(self):
        """
        Calculate the sections and fill path based on the current data.
        Should be only updated when data changes
        """
        if not self.hourly_data:
            return
        self.sections = []

        enabled_effects = self._get_enabled_effects()

        weather_types = [
            ("chance_of_rain", Effect.RAIN),
            ("chance_of_snow", Effect.SNOW),
        ]

        for attr, effect_type in weather_types:
            if effect_type in enabled_effects:
                self._process_weather_type(attr, effect_type, enabled_effects)

    def _get_enabled_effects(self) -> list[Effect]:
        enabled_effects: list[Effect] = []
        if self.data_type == "rain":
            enabled_effects.append(Effect.RAIN)
        elif self.data_type == "snow":
            enabled_effects.append(Effect.SNOW)
        elif self.data_type == "temperature":
            if self.anim_config["temp_line_animation_style"] == "rain":
                enabled_effects.append(Effect.RAIN)
            elif self.anim_config["temp_line_animation_style"] == "snow":
                enabled_effects.append(Effect.SNOW)
            elif self.anim_config["temp_line_animation_style"] == "both":
                enabled_effects.append(Effect.RAIN)
                enabled_effects.append(Effect.SNOW)
            # none
        return enabled_effects

    def _process_weather_type(self, attr: str, effect_type: Effect, enabled_effects: list[Effect]):
        """Process weather type (rain/snow) for each bucket"""

        def group_key(x: tuple[int, HourlyData]):
            # Group snow and rain together if snow_overrides_rain is disabled
            if not self.anim_config["snow_overrides_rain"]:
                return getattr(x[1], attr) > 0
            # Otherwise if we are processing rain and snow is also enabled, we only want rain if there is NO snow
            if effect_type == Effect.RAIN and Effect.SNOW in enabled_effects:
                return getattr(x[1], attr) > 0 and x[1].chance_of_snow == 0
            return getattr(x[1], attr) > 0

        groups = groupby(enumerate(self.hourly_data), key=group_key)
        for is_active, group in groups:
            if not is_active:
                continue

            bucket = list(group)
            if self.anim_config["scale_with_chance"]:
                density_map = [
                    p[1].chance_of_rain / 100.0 if effect_type == Effect.RAIN else p[1].chance_of_snow / 100.0
                    for p in bucket
                ]
            else:
                density_map = [1.0] * len(bucket)

            spawn_x_min, spawn_x_max = self._calculate_section_bounds(bucket, effect_type)

            section_start, r_start = find_point_and_percent(self.source_path, spawn_x_min)
            section_end, r_end = find_point_and_percent(self.source_path, spawn_x_max)

            # Sample points between r_start and r_end to get the curve section
            section_points = [section_start]
            n = 8 * len(bucket)
            for i in range(n):
                r = r_start + (r_end - r_start) * i / n
                section_points.append(self.source_path.pointAtPercent(r))
            section_points.append(section_end)

            # Create section path and closed path
            if len(section_points) > 0:
                section_path = create_path_from_points(section_points)
                closed_section_path = QPainterPath(section_path)
                closed_section_path.lineTo(closed_section_path.pointAtPercent(1.0).x(), self.parent_widget.height())
                closed_section_path.lineTo(closed_section_path.pointAtPercent(0.0).x(), self.parent_widget.height())
                closed_section_path.closeSubpath()
                spawn_rate = (
                    3.0 * self.anim_config["rain_effect_intensity"]
                    if effect_type == Effect.RAIN
                    else 0.4 * self.anim_config["snow_effect_intensity"]
                )
                self.sections.append(
                    Section(
                        section_path,
                        closed_section_path,
                        spawn_x_min,
                        spawn_x_max,
                        effect_type,
                        spawn_rate=spawn_rate,
                        density_map=density_map,
                        # clr=QColor.fromHsvF(random.random(), 1.0, 0.5), # for debugging sections
                    )
                )

    def _calculate_section_bounds(
        self,
        bucket: list[tuple[int, HourlyData]],
        effect_type: Effect,
    ) -> tuple[float, float]:
        # Helper to check effective weather type at an index
        def get_effective_type(idx: int):
            d = self.hourly_data[idx]
            if d.chance_of_snow > 0:
                return Effect.SNOW
            if d.chance_of_rain > 0:
                return Effect.RAIN
            return None

        # Calculate start point
        start_idx = bucket[0][0]
        prev_idx = start_idx - 1
        if prev_idx < 0:
            spawn_x_min = self.hourly_data[start_idx].graph_point.x()
        else:
            prev_type = get_effective_type(prev_idx)
            # If neighbor has a different weather effect (and neither is None/Clear), split at midpoint
            if prev_type is not None and prev_type != effect_type:
                spawn_x_min = (
                    self.hourly_data[prev_idx].graph_point.x() + self.hourly_data[start_idx].graph_point.x()
                ) / 2
            else:
                spawn_x_min = self.hourly_data[prev_idx].graph_point.x()

        # Calculate end point
        end_idx = bucket[-1][0]
        next_idx = end_idx + 1
        if next_idx >= len(self.hourly_data):
            spawn_x_max = self.hourly_data[end_idx].graph_point.x()
        else:
            next_type = get_effective_type(next_idx)
            # If neighbor has a different weather effect (and neither is None/Clear), split at midpoint
            if next_type is not None and next_type != effect_type:
                spawn_x_max = (
                    self.hourly_data[end_idx].graph_point.x() + self.hourly_data[next_idx].graph_point.x()
                ) / 2
            else:
                spawn_x_max = self.hourly_data[next_idx].graph_point.x()

        return spawn_x_min, spawn_x_max

    def _update_animation_state(self):
        """Logic to update positions and handle physics"""
        if not self.hourly_data:
            return
        self.animation_frame += 1

        # Generate particles for each section
        for section in self.sections:
            n_bins = len(section.density_map)
            particles_to_spawn = section.spawn_rate * n_bins + random.random()
            if particles_to_spawn > 0 and section.density_map and sum(section.density_map) > 0:
                bin_indices = random.choices(range(n_bins), weights=section.density_map, k=int(particles_to_spawn))
                bin_width = 1.0 / n_bins
                for bin_idx in bin_indices:
                    r_min = bin_idx * bin_width
                    r_max = (bin_idx + 1) * bin_width
                    r = random.uniform(r_min, r_max)
                    point = section.path.pointAtPercent(r)
                    x = point.x()
                    y = point.y()
                    if section.effect == Effect.RAIN:
                        speed = random.randint(5, 12)
                        length = random.randint(10, 20)
                        self.drops.append(RainDrop(x, y, speed, length))
                    else:
                        self.flakes.append(SnowFlake(x, y))

        # Update drops
        active_drops: list[RainDrop] = []
        for drop in self.drops:
            drop.y += drop.speed
            if drop.y < self.parent_widget.height() + drop.length:
                active_drops.append(drop)
        self.drops = active_drops

        # Update flakes
        active_flakes: list[SnowFlake] = []
        for flake in self.flakes:
            flake.y += flake.speed

            # Formula: x += sin(time * speed + unique_phase) * range
            wobble = math.sin(self.animation_frame * flake.wobble_speed + flake.phase) * flake.wobble_range
            flake.x += wobble

            if flake.y < self.parent_widget.height() + 10:
                active_flakes.append(flake)
        self.flakes = active_flakes

        self.parent_widget.update()

    def paint_animation(self, painter: QPainter, parent_clip_path: QPainterPath):
        """Draw all the computed elements"""
        # DEBUG: Draw the path sections
        # painter.save()
        # for section in self.sections:
        #     painter.setPen(QPen(section.clr, 8.0))
        #     painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        #     painter.drawPath(section.path)
        # painter.restore()
        # Draw Rain
        painter.save()
        if self.drops:
            combined_clip_path_rain = QPainterPath()
            for section in self.sections:
                if section.effect == Effect.RAIN:
                    painter.setPen(QPen(Qt.PenStyle.NoPen))
                    painter.setBrush(QBrush(self.rain_colors[1]))
                    painter.drawPath(section.closed_path)
                    combined_clip_path_rain.addPath(section.closed_path)
            combined_clip_path_rain = combined_clip_path_rain.intersected(parent_clip_path)
            painter.setClipPath(combined_clip_path_rain)

            painter.setPen(QPen(self.rain_colors[0], 1.0))
            for drop in self.drops:
                p1 = QPointF(drop.x, drop.y)
                p2 = QPointF(drop.x, drop.y + drop.length)
                painter.drawLine(p1, p2)
        painter.restore()

        painter.save()
        # Draw Snow
        if self.flakes:
            combined_clip_path_snow = QPainterPath()
            for section in self.sections:
                if section.effect == Effect.SNOW:
                    painter.setPen(QPen(Qt.PenStyle.NoPen))
                    painter.setBrush(QBrush(self.snow_colors[1]))
                    painter.drawPath(section.closed_path)
                    combined_clip_path_snow.addPath(section.closed_path)
            combined_clip_path_snow = combined_clip_path_snow.intersected(parent_clip_path)
            painter.setClipPath(combined_clip_path_snow)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self.snow_colors[0]))
            for flake in self.flakes:
                painter.drawEllipse(QRectF(flake.x, flake.y, flake.size, flake.size))
        painter.restore()
