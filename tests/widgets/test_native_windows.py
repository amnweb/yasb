import ast
import inspect
import textwrap
from pathlib import Path

import pytest

from tests.support.source import REPO_ROOT, all_subclasses, core_modules, defined_in_core, import_core_modules

_WHY = (
    "winId() on a widget inside the bar makes Qt turn it, and every sibling, into a native window "
    "(see 18283d81). Use get_widget_monitor_hwnd(self) for the monitor, or self.window().winId() "
    "for the bar's handle."
)


def _bar_widget_classes() -> list[type]:
    import_core_modules()
    from core.widgets.base import BaseWidget

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
    offenders = []
    for cls in _bar_widget_classes():
        lines, start = inspect.getsourcelines(cls)
        tree = ast.parse(textwrap.dedent("".join(lines)))
        path = Path(inspect.getsourcefile(cls)).relative_to(REPO_ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_winid_on_self(node):
                offenders.append(f"{path}:{start + node.lineno - 1}: {ast.unparse(node)} in {cls.__qualname__}")
    if offenders:
        pytest.fail(_WHY + "\n  " + "\n  ".join(offenders), pytrace=False)


def test_winid_is_never_called_unbound():
    offenders = []
    for module in core_modules():
        for node in ast.walk(module.tree()):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "winId"
                and node.args
            ):
                offenders.append(f"{module.rel}:{node.lineno}: {ast.unparse(node)}")
    if offenders:
        message = f"QWidget.winId(widget) is the same call as widget.winId(). {_WHY}\n  " + "\n  ".join(offenders)
        pytest.fail(message, pytrace=False)


@pytest.fixture
def bar(qapp):
    from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

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


def _native_children(window) -> list[str]:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QWidget

    return [
        child.objectName()
        for child in window.findChildren(QWidget)
        if child.testAttribute(Qt.WidgetAttribute.WA_NativeWindow)
    ]


def test_get_widget_monitor_hwnd_keeps_the_bar_children_alien(bar):
    from PyQt6.QtWidgets import QLabel

    from core.utils.win32.utils import get_monitor_hwnd, get_widget_monitor_hwnd

    child = bar.findChild(QLabel, "child")
    monitor = get_widget_monitor_hwnd(child)

    assert _native_children(bar) == [], _WHY
    assert monitor == get_monitor_hwnd(int(bar.winId()))


def test_winid_on_a_child_still_makes_it_native(bar):
    from PyQt6.QtWidgets import QLabel

    bar.findChild(QLabel, "child").winId()

    assert "child" in _native_children(bar), "Qt no longer nativises on winId(); the rules above may be obsolete"
