import json
from types import SimpleNamespace
from unittest.mock import patch

from PyQt6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt
from PyQt6.QtGui import QDropEvent, QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QWidget

from core.widgets.services.systray.placement import REGIONS, TrayPlacement, icon_key


def make_bar(path):
    bar = QWidget()
    bar.resize(900, 30)
    bar.bar_frame = bar
    outer = QHBoxLayout(bar)
    regions, widgets = {}, {}
    for name in REGIONS:
        region = QFrame(bar)
        layout = QHBoxLayout(region)
        layout.setContentsMargins(0, 0, 0, 0)
        if name != "left":
            layout.addStretch()
        widget = QPushButton(name, region)
        widget.widget_name = name
        layout.addWidget(widget)
        if name != "right":
            layout.addStretch()
        regions[name], widgets[name] = region, [widget]
        outer.addWidget(region)
    owner = QWidget(bar)
    owner.widget_name = "systray"
    owner.icons = []
    owner.config = SimpleNamespace(show_in_popup=False)
    owner.pinned_widget, owner.unpinned_widget = QWidget(owner), QWidget(owner)
    owner.pinned_layout, owner.unpinned_layout = QHBoxLayout(owner.pinned_widget), QHBoxLayout(owner.unpinned_widget)
    owner.update_pinned_widget_visibility = lambda: None
    regions["right"].layout().addWidget(owner)
    widgets["right"].append(owner)
    bar.owner = owner
    placement = TrayPlacement(bar, regions, widgets, path)
    bar.show()
    return bar, placement


def add_icon(owner, uid=1, guid=None):
    icon = QPushButton("icon", owner)
    icon.data = SimpleNamespace(guid=guid, exe_path="C:/App/app.exe", uID=uid)
    icon._tray_owner = owner
    icon.is_pinned = False
    owner.icons.append(icon)
    owner.unpinned_layout.addWidget(icon)
    return icon


def actual_order(placement, region):
    layout = placement.regions[region].layout()
    return [layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget()]


def test_interleave_reorder_and_restore_after_restart(qapp, tmp_path):
    path = tmp_path / "positions.json"
    bar, placement = make_bar(path)
    one, two = add_icon(bar.owner), add_icon(bar.owner, 2)
    assert icon_key(one) != icon_key(two)
    assert placement.place(one, "center", "widget:center")
    assert placement.place(two, "center", icon_key(one))
    assert actual_order(placement, "center") == [
        placement.slots[icon_key(two)],
        placement.slots[icon_key(one)],
        next(w for w, token in placement.widgets.items() if token == "widget:center"),
    ]
    saved = json.loads(path.read_text())
    other, restored = make_bar(path)
    new_one = add_icon(other.owner)
    restored.restore_icon(new_one)
    assert new_one.parentWidget() is restored.slots[icon_key(one)]
    assert restored.order == saved  # Absent app remains an anchor until it registers again.
    new_two = add_icon(other.owner, 2)
    restored.restore_icon(new_two)
    assert actual_order(restored, "center")[:2] == [restored.slots[icon_key(two)], restored.slots[icon_key(one)]]
    assert restored.place(new_one, "left", "widget:left")
    assert actual_order(restored, "left")[0] is restored.slots[icon_key(one)]
    assert restored.slots[icon_key(one)] not in actual_order(restored, "center")
    assert restored.place(new_two, "left", icon_key(new_one))
    assert actual_order(restored, "left")[:2] == [restored.slots[icon_key(two)], restored.slots[icon_key(one)]]
    bar.close()
    other.close()


def test_failed_save_and_monitor_isolation_leave_icon_unchanged(qapp, tmp_path):
    bar, placement = make_bar(tmp_path / "a.json")
    other, foreign = make_bar(tmp_path / "b.json")
    icon = add_icon(bar.owner)
    assert not foreign.place(icon, "left")
    parent = icon.parentWidget()
    with patch("core.widgets.services.systray.placement.os.replace", side_effect=OSError("read-only")):
        assert not placement.place(icon, "left")
    assert icon.parentWidget() is parent
    assert not placement.slots
    assert not placement.path.exists()
    bar.close()
    other.close()


def test_remove_reappear_return_to_overflow_and_missing_anchor(qapp, tmp_path):
    bar, placement = make_bar(tmp_path / "positions.json")
    icon = add_icon(bar.owner)
    assert placement.place(icon, "left", "widget:removed")
    key = icon_key(icon)
    placement.remove_icon(icon)
    assert key not in placement.slots
    replacement = add_icon(bar.owner)
    placement.restore_icon(replacement)
    assert key in placement.slots
    assert placement.forget(replacement)
    bar.owner.unpinned_layout.addWidget(replacement)
    qapp.processEvents()
    assert replacement.parentWidget() is bar.owner.unpinned_widget
    assert all(key not in tokens for tokens in placement.order.values())
    bar.close()


def test_corrupt_duplicate_state_uses_original_layout(qapp, tmp_path):
    path = tmp_path / "positions.json"
    path.write_text(json.dumps({"left": ["icon:bad", "icon:bad"], "center": [], "right": []}))
    bar, placement = make_bar(path)
    assert placement.order["left"] == ["widget:left"]
    bar.close()


class Drop(QDropEvent):
    def __init__(self, source, position):
        super().__init__(
            QPointF(position),
            Qt.DropAction.MoveAction,
            QMimeData(),
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.icon = source

    def source(self):
        return self.icon


def test_drop_event_snaps_and_foreign_drop_is_rejected(qapp, tmp_path):
    bar, placement = make_bar(tmp_path / "positions.json")
    other, foreign = make_bar(tmp_path / "other.json")
    icon = add_icon(bar.owner)
    qapp.processEvents()
    target = next(w for w, token in placement.widgets.items() if token == "widget:center")
    drop = Drop(icon, target.rect().topLeft())
    assert placement.eventFilter(target, drop)
    assert drop.isAccepted()
    assert placement.order["center"][:2] == [icon_key(icon), "widget:center"]
    denied = Drop(icon, other.rect().center())
    assert foreign.eventFilter(other, denied)
    assert not denied.isAccepted()
    assert not foreign.slots
    assert not placement.eventFilter(bar, QEvent(QEvent.Type.DragLeave))
    assert placement.marker.isHidden()
    bar.close()
    other.close()


def test_widgets_snap_around_icons_and_restore(qapp, tmp_path):
    path = tmp_path / "positions.json"
    bar, placement = make_bar(path)
    clock = next(w for w, token in placement.widgets.items() if token == "widget:center")
    icon = add_icon(bar.owner)
    assert placement.place(icon, "left", "widget:left")
    assert placement.place_widget(clock, "left", icon_key(icon))
    assert actual_order(placement, "left")[:2] == [clock, placement.slots[icon_key(icon)]]
    assert clock not in actual_order(placement, "center")
    other, restored = make_bar(path)
    new_clock = next(w for w, token in restored.widgets.items() if token == "widget:center")
    assert actual_order(restored, "left")[0] is new_clock
    assert not restored.place_widget(clock, "right")
    before = dict(restored.order)
    with patch("core.widgets.services.systray.placement.os.replace", side_effect=OSError("denied")):
        assert not restored.place_widget(new_clock, "right")
    assert restored.order == before
    assert actual_order(restored, "left")[0] is new_clock
    drop = Drop(new_clock, QPoint())
    assert restored.eventFilter(restored.regions["center"], drop) and drop.isAccepted()
    assert new_clock in actual_order(restored, "center")
    bar.close()
    other.close()


def test_widget_click_and_cancelled_drag(qapp, tmp_path):
    bar, placement = make_bar(tmp_path / "positions.json")
    clock = next(w for w, token in placement.widgets.items() if token == "widget:center")
    clicks = []
    clock.clicked.connect(lambda: clicks.append(True))
    QTest.mouseClick(clock, Qt.MouseButton.LeftButton)
    assert clicks == [True]
    QTest.mousePress(clock, Qt.MouseButton.LeftButton)
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(50, 0),
        QPointF(clock.mapToGlobal(QPoint(50, 0))),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    with patch("core.widgets.services.systray.placement.QDrag.exec", return_value=Qt.DropAction.IgnoreAction) as drag:
        assert placement.eventFilter(clock, move)
        drag.assert_called_once()
    QTest.mouseRelease(clock, Qt.MouseButton.LeftButton)
    assert clicks == [True]
    QTest.mouseClick(clock, Qt.MouseButton.LeftButton)
    assert clicks == [True, True]
    assert not placement.path.exists()
    bar.close()


def test_ignored_child_press_keeps_widget_drag_source(qapp, tmp_path):
    bar, placement = make_bar(tmp_path / "positions.json")
    widget = next(w for w, token in placement.widgets.items() if token == "widget:center")
    child = QFrame(widget)
    child.resize(20, 20)
    child.show()
    child.installEventFilter(placement)
    QTest.mousePress(child, Qt.MouseButton.LeftButton)
    assert placement._pressed[0] is widget
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(50, 0),
        QPointF(child.mapToGlobal(QPoint(50, 0))),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    with patch("core.widgets.services.systray.placement.QDrag.exec", return_value=Qt.DropAction.IgnoreAction):
        assert placement.eventFilter(child, move)
    QTest.mouseRelease(child, Qt.MouseButton.LeftButton)
    bar.close()
