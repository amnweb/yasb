from typing import Any, cast

from PyQt6.QtCore import QByteArray, QObject, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine

from core.bar.revisions import Revisions
from core.bar.window import BarContext
from core.validation.bar import BarConfig


class BarWindow(QObject):
    """What a bar's BarContext reads from its window."""

    def __init__(self, engine: QQmlEngine, edge: str) -> None:
        super().__init__()
        self.engine = engine
        self.name = "bar"
        self.config = BarConfig.model_validate({"edge": edge})
        self.revisions = Revisions()
        self.target_screen = QGuiApplication.primaryScreen()


def make_bar(engine: QQmlEngine, edge: str = "top") -> QObject:
    """A bar with the default theme, which owns its window. The caller owns the bar."""
    window = BarWindow(engine, edge)
    component = QQmlComponent(engine)
    component.setData(QByteArray(b"import Yasb.Bar\n\nBarBase {}\n"), QUrl("bar.qml"))
    bar = component.createWithInitialProperties({"context": BarContext(cast(Any, window))})
    assert bar is not None, [error.toString() for error in component.errors()]
    window.setParent(bar)
    return bar


def create_with_bar(
    component: QQmlComponent, properties: dict[str | None, Any] | None = None, edge: str = "top"
) -> Any:
    """A widget made as a bar makes it, with its bar, which the widget owns and deletes with itself."""
    engine = component.engine()
    assert engine is not None
    bar = make_bar(engine, edge)
    widget = component.createWithInitialProperties({"bar": bar, **(properties or {})})
    if widget is not None:
        bar.setParent(widget)
    return widget
