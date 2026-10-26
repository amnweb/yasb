from typing import Any

import pytest
from pydantic import ValidationError
from PyQt6.QtCore import QRect

from core.bar.geometry import bar_geometry, bar_length
from core.validation.bar import BarConfig

SCREEN = QRect(1920, 0, 1920, 1080)
MARGIN = {"top": 4, "left": 8, "bottom": 4, "right": 8}


def config(**values: Any) -> BarConfig:
    return BarConfig.model_validate(values)


@pytest.mark.parametrize(
    ("length", "content", "expected"),
    [(600, 0, 600), ("50%", 0, 960), ("100%", 0, 1904), ("auto", 300, 300), ("auto", 5000, 1904), (5000, 0, 1904)],
    ids=["pixels", "percent", "full", "auto", "auto-clamped", "pixels-clamped"],
)
def test_bar_length_stays_inside_the_margins(length: int | str, content: int, expected: int):
    assert bar_length(config(length=length, margin=MARGIN), SCREEN, content) == expected


def test_a_vertical_bar_length_runs_down_the_screen():
    assert bar_length(config(edge="left", length="100%", margin=MARGIN), SCREEN, 0) == 1072


@pytest.mark.parametrize(("align", "x"), [("left", 1928), ("center", 2580), ("right", 3232)])
def test_bar_aligns_between_the_margins(align: str, x: int):
    assert bar_geometry(config(align=align, margin=MARGIN), SCREEN, 600).x() == x


@pytest.mark.parametrize(
    ("edge", "expected"),
    [
        ("top", (2580, 4, 600, 30)),
        ("bottom", (2580, 1046, 600, 30)),
        ("left", (1928, 240, 30, 600)),
        ("right", (3802, 240, 30, 600)),
    ],
)
def test_bar_sits_on_its_edge_inside_the_margin(edge: str, expected: tuple[int, int, int, int]):
    align = "center"
    geometry = bar_geometry(config(edge=edge, align=align, thickness=30, margin=MARGIN), SCREEN, 600)
    assert geometry.getRect() == expected


@pytest.mark.parametrize(("edge", "align"), [("left", "right"), ("top", "bottom")])
def test_align_must_follow_the_bar_direction(edge: str, align: str):
    with pytest.raises(ValidationError, match="Align must be"):
        config(edge=edge, align=align)
