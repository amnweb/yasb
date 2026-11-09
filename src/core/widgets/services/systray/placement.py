"""Persistent, per-monitor insertion of existing tray icons between bar widgets."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

from PyQt6.QtCore import QEvent, QMimeData, QObject, QPoint, Qt
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QRubberBand, QWidget

logger = logging.getLogger(__name__)
REGIONS = ("left", "center", "right")


def icon_key(icon):
    data = icon.data
    if data.guid:
        return "icon:guid:" + str(data.guid)
    return "icon:exe:" + data.exe_path.casefold() + ":" + str(data.uID)


class TrayPlacement(QObject):
    def __init__(self, bar, regions, widgets, path):
        super().__init__(bar)
        self.bar = bar
        self.frame = getattr(bar, "bar_frame", None) or bar._bar_frame
        self.regions = regions
        self.path = Path(path)
        self.owners = [
            w for group in widgets.values() for w in group if hasattr(w, "pinned_layout") and hasattr(w, "icons")
        ]
        self.tray_targets = [target for owner in self.owners for target in (owner.pinned_widget, owner.unpinned_widget)]
        self.tray_targets.extend(
            owner._systray_popup.grid_widget for owner in self.owners if owner.config.show_in_popup
        )
        self.widgets = {w: "widget:" + w.widget_name for group in widgets.values() for w in group if w.widget_name}
        self.slots = {}
        self.order = {r: [self.widgets[w] for w in widgets.get(r, []) if w in self.widgets] for r in REGIONS}
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(saved, dict) or any(not isinstance(saved.get(r), list) for r in REGIONS):
                raise ValueError("Invalid tray placement file")
            seen = set()
            for region in REGIONS:
                tokens = saved[region]
                if any(not isinstance(t, str) or not t.startswith(("widget:", "icon:")) or t in seen for t in tokens):
                    raise ValueError("Invalid or duplicate tray placement anchor")
                if len(tokens) != len(set(tokens)):
                    raise ValueError("Duplicate tray placement anchor")
                seen.update(tokens)
            self.order = {r: saved[r] for r in REGIONS}
        except FileNotFoundError:
            pass
        except OSError, ValueError, TypeError:
            logger.exception("Cannot load tray positions; using the existing tray")
        for region, group in widgets.items():
            for widget in group:
                token = self.widgets.get(widget)
                if token and not any(token in tokens for tokens in self.order.values()):
                    self.order[region].append(token)
        self._pressed = None
        self._suppress_release = False
        self.marker = QRubberBand(QRubberBand.Shape.Line, bar)
        for owner in self.owners:
            owner._tray_placement = self
        for widget in [bar, self.frame, *bar.findChildren(QWidget)]:
            if widget in self.widgets or widget is bar or widget is self.frame or widget in regions.values():
                widget.setAcceptDrops(True)
            widget.installEventFilter(self)
        self._arrange()
        for owner in self.owners:
            for icon in owner.icons:
                self.restore_icon(icon)

    def _save(self, order):
        temporary = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(order, indent=2), encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError:
            logger.exception("Cannot save tray positions; placement left unchanged")
            return False
        self.order = order
        return True

    def restore_icon(self, icon):
        if getattr(icon, "_tray_owner", None) not in self.owners or icon.data is None:
            return
        key = icon_key(icon)
        if not any(key in tokens for tokens in self.order.values()):
            return
        if key not in self.slots:
            slot = QFrame(self.bar)
            slot.setProperty("class", "systray tray-icon-slot")
            slot.setAcceptDrops(True)
            slot.installEventFilter(self)
            layout = QHBoxLayout(slot)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            self.slots[key] = slot
        slot = self.slots[key]
        if icon.parentWidget() is slot:
            icon.show()
            return
        slot.layout().addWidget(icon)
        icon.is_pinned = True
        icon.show()
        self._arrange()
        slot.show()

    def _arrange(self):
        for region, container in self.regions.items():
            layout = container.layout()
            tokens = self.order[region]
            for position in range(len(tokens) - 1, -1, -1):
                key = tokens[position]
                slot = self.slots.get(key)
                if slot is None:
                    slot = next((w for w, token in self.widgets.items() if token == key), None)
                if slot is None:
                    continue
                was_hidden = slot.isHidden()
                for other in self.regions.values():
                    other.layout().removeWidget(slot)
                anchor = None
                for token in tokens[position + 1 :]:
                    candidate = self.slots.get(token)
                    if candidate is None:
                        candidate = next(
                            (w for w, name in self.widgets.items() if name == token and layout.indexOf(w) >= 0), None
                        )
                    if candidate is not None and layout.indexOf(candidate) >= 0:
                        anchor = candidate
                        break
                if anchor is not None:
                    index = layout.indexOf(anchor)
                else:
                    preceding = [i for i in range(layout.count()) if layout.itemAt(i).widget() is not None]
                    index = preceding[-1] + 1 if preceding else (1 if region != "left" and layout.count() else 0)
                layout.insertWidget(index, slot)
                if slot in self.widgets and hasattr(slot, "parent_layout_type"):
                    slot.parent_layout_type = region
                slot.setVisible(not was_hidden if slot in self.widgets else True)

    def forget(self, icon):
        key = icon_key(icon)
        order = {r: [t for t in tokens if t != key] for r, tokens in self.order.items()}
        if order == self.order:
            return True
        if not self._save(order):
            return False
        self.remove_icon(icon)
        return True

    def remove_icon(self, icon):
        slot = self.slots.pop(icon_key(icon), None)
        if slot is not None:
            slot.layout().removeWidget(icon)
            for region in self.regions.values():
                region.layout().removeWidget(slot)
            slot.hide()
            slot.deleteLater()

    def place(self, icon, region, before=None):
        if region not in REGIONS or getattr(icon, "_tray_owner", None) not in self.owners:
            return False
        key = icon_key(icon)
        if before == key:
            return True
        order = {r: [t for t in tokens if t != key] for r, tokens in self.order.items()}
        tokens = order[region]
        if before is not None and before not in tokens:
            tokens.append(before)
        tokens.insert(tokens.index(before) if before is not None else len(tokens), key)
        if not self._save(order):
            return False
        owner = icon._tray_owner
        owner.pinned_layout.removeWidget(icon)
        owner.unpinned_layout.removeWidget(icon)
        self.restore_icon(icon)
        self._arrange()
        if owner.config.show_in_popup:
            owner._relayout_popup_grid()
        owner.update_pinned_widget_visibility()
        return True

    def place_widget(self, widget, region, before=None):
        if widget not in self.widgets or region not in REGIONS:
            return False
        key = self.widgets[widget]
        if before == key:
            return True
        order = {r: [t for t in tokens if t != key] for r, tokens in self.order.items()}
        tokens = order[region]
        if before is not None and before not in tokens:
            tokens.append(before)
        tokens.insert(tokens.index(before) if before is not None else len(tokens), key)
        if not self._save(order):
            return False
        self._arrange()
        return True

    def _widget_source(self, watched):
        while isinstance(watched, QWidget) and watched is not self.bar:
            if getattr(watched, "_tray_owner", None) is not None:
                return None  # Actual tray icons retain their own drag/click implementation.
            if watched in self.widgets:
                return watched
            watched = watched.parentWidget()
        return None

    def _target(self, global_pos, source):
        local = self.bar.mapFromGlobal(global_pos)
        region = min(
            REGIONS, key=lambda r: abs(self.regions[r].mapTo(self.bar, self.regions[r].rect().center()).x() - local.x())
        )
        for r, container in self.regions.items():
            if container.rect().contains(container.mapFromGlobal(global_pos)):
                region = r
                break
        layout = self.regions[region].layout()
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if widget is None:
                continue
            token = self.widgets.get(widget) or next((k for k, slot in self.slots.items() if slot is widget), None)
            if token == (self.widgets[source] if source in self.widgets else icon_key(source)):
                continue
            if token and global_pos.x() < widget.mapToGlobal(widget.rect().center()).x():
                return region, token, widget.mapTo(self.bar, QPoint(0, 0)).x()
        container = self.regions[region]
        return region, None, container.mapTo(self.bar, QPoint(container.width() - 2, 0)).x()

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._suppress_release = False
            source = self._widget_source(watched)
            if source is not None:
                self._pressed = (source, event.globalPosition().toPoint())
        elif kind == QEvent.Type.MouseButtonRelease:
            self._pressed = None
            if self._suppress_release:
                self._suppress_release = False
                return True
        elif kind == QEvent.Type.MouseMove and self._pressed and event.buttons() & Qt.MouseButton.LeftButton:
            source, start = self._pressed
            if (event.globalPosition().toPoint() - start).manhattanLength() >= QApplication.startDragDistance():
                self._pressed = None
                self._suppress_release = True
                drag = QDrag(source)
                mime = QMimeData()
                mime.setData("application/x-yasb-widget", self.widgets[source].encode())
                drag.setMimeData(mime)
                drag.setPixmap(source.grab())
                try:
                    drag.exec(Qt.DropAction.MoveAction)
                finally:
                    self.marker.hide()
                    if hasattr(watched, "setDown"):
                        watched.setDown(False)
                return True
        if kind == QEvent.Type.DragLeave:
            self.marker.hide()
            return False
        if kind not in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
            return False
        source = event.source()
        owner = getattr(source, "_tray_owner", None)
        widget_drag = source in self.widgets
        if owner is None and not widget_drag:
            if event.mimeData().hasFormat("application/x-yasb-widget"):
                event.ignore()
                return True
            return False
        if not widget_drag and owner not in self.owners:
            event.ignore()
            return True
        if not widget_drag and watched in self.tray_targets:
            self.marker.hide()
            return False
        try:
            region, before, x = self._target(watched.mapToGlobal(event.position().toPoint()), source)
            if kind == QEvent.Type.Drop:
                self.marker.hide()
                place = self.place_widget if widget_drag else self.place
                if place(source, region, before):
                    event.setDropAction(Qt.DropAction.MoveAction)
                    event.accept()
                else:
                    event.ignore()
            else:
                self.marker.setGeometry(x, 2, 2, max(1, self.bar.height() - 4))
                self.marker.show()
                event.setDropAction(Qt.DropAction.MoveAction)
                event.accept()
        except Exception:
            self.marker.hide()
            logger.exception("Tray drop failed")
            event.ignore()
        return True


def attach_tray_placement(bar, widgets):
    if not any(widgets.values()):
        return
    from core.utils.system import app_data_path

    screen = bar.screen()
    identity = "|".join((bar._bar_name, screen.manufacturer(), screen.name(), screen.serialNumber()))
    filename = "tray_positions_" + hashlib.sha256(identity.encode()).hexdigest()[:20] + ".json"
    frame = getattr(bar, "bar_frame", None) or bar._bar_frame
    regions = {r: frame.layout().itemAtPosition(0, i).widget() for i, r in enumerate(REGIONS)}
    try:
        path = app_data_path(filename)
    except OSError:
        logger.exception("Cannot access tray positions; using the existing tray")
        return
    bar._tray_placement = TrayPlacement(bar, regions, widgets, path)
