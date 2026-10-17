import ast
import inspect
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget

from core.utils.win32.utils import get_monitor_hwnd, get_widget_monitor_hwnd
from core.widgets.base import BaseWidget
from tests.support.source import REPO_ROOT, all_subclasses, defined_in_core, import_core_modules

_WHY = (
    "winId() on a widget inside the bar makes Qt turn it, and every sibling, into a native window. "
    "Use get_widget_monitor_hwnd(self) for the monitor, or self.window().winId() for the bar's handle."
)


def _bar_widget_classes() -> list[type]:
    import_core_modules()
    return sorted(
        (cls for cls in all_subclasses(BaseWidget) if defined_in_core(cls)),
        key=lambda cls: f"{cls.__module__}.{cls.__qualname__}",
    )


def _is_winid_on_self(node: ast.Call) -> bool:
    if not (isinstance(node.func, ast.Attribute) and node.func.attr == "winId"):
        return False
    receiver = node.func.value
    if isinstance(receiver, ast.Name) and receiver.id == "self" and not node.args:
        return True
    return bool(node.args) and isinstance(node.args[0], ast.Name) and node.args[0].id == "self"


def test_bar_widgets_never_call_winid_on_themselves():
    offenders: list[str] = []
    for cls in _bar_widget_classes():
        lines, start = inspect.getsourcelines(cls)
        tree = ast.parse(textwrap.dedent("".join(lines)))
        source = inspect.getsourcefile(cls)
        assert source is not None
        path = Path(source).relative_to(REPO_ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_winid_on_self(node):
                offenders.append(f"{path}:{start + node.lineno - 1}: {ast.unparse(node)} in {cls.__qualname__}")
    if offenders:
        pytest.fail(_WHY + "\n  " + "\n  ".join(offenders), pytrace=False)


@pytest.fixture
def bar(qapp: QApplication) -> Iterator[QWidget]:
    window = QWidget()
    layout = QHBoxLayout(window)
    for name in ("child", "sibling"):
        label = QLabel(name)
        label.setObjectName(name)
        layout.addWidget(label)
    window.show()
    qapp.processEvents()
    yield window
    window.close()
    window.deleteLater()
    qapp.processEvents()


def _native_children(window: QWidget) -> list[str]:
    return [
        child.objectName()
        for child in window.findChildren(QWidget)
        if child.testAttribute(Qt.WidgetAttribute.WA_NativeWindow)
    ]


def test_get_widget_monitor_hwnd_keeps_the_bar_children_alien(bar: QWidget):
    child = bar.findChild(QLabel, "child")
    assert child is not None
    monitor = get_widget_monitor_hwnd(child)

    assert _native_children(bar) == [], _WHY
    assert monitor == get_monitor_hwnd(int(bar.winId()))
