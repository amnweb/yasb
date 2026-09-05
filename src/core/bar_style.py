import math

from PyQt6.QtCore import QEvent, QRect, QRectF, Qt, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen, QTransform
from PyQt6.QtWidgets import QFrame, QWidget

RESTYLE_EVENTS = frozenset({QEvent.Type.Polish, QEvent.Type.StyleChange})


class BarFrame(QFrame):
    """Bar surface for style "bar"."""

    def __init__(self, parent: QFrame | None = None):
        super().__init__(parent)
        # Windows passes clicks through fully transparent pixels, so we need to prevent this
        # This layer is alpha 1 invisible, but takes clicks.
        # So now background-color can be fully transparent in css.
        self._click_floor = QFrame(self)
        self._click_floor.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._click_floor.setAutoFillBackground(True)
        palette = self._click_floor.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 1))
        self._click_floor.setPalette(palette)

    def click_rect(self) -> QRect:
        """The area of the frame that takes mouse clicks."""
        return self.rect()

    def _resize_click_floor(self) -> None:
        self._click_floor.setGeometry(self.click_rect())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_click_floor()


class AdaptiveBarFrame(BarFrame):
    """Bar surface for style "adaptive": a rail along the outer edge, each widget group its own
    island by default. Islands and the edge curves are both optional, so this can also render
    as a plain full-width bar with just its outer corners rounded."""

    def __init__(self, parent: QWidget, position: str = "top", exclude: list[str] | None = None):
        super().__init__(parent)
        self._position = position
        self._exclude = frozenset(exclude or ())
        self._rail_height = 4
        self._island_radius = 16
        self._group_padding = 8
        self._islands_enabled = True
        self._edge_radius = 0
        self._edge_curves = False
        self._border_width = 0
        self._border_color = QColor(0, 0, 0, 0)
        self._islands: tuple[tuple[int, int], ...] = ()
        self._shape = QPainterPath()
        self._gaps = QPainterPath()

    @pyqtProperty(int)
    def railheight(self) -> int:
        return self._rail_height

    @railheight.setter
    def railheight(self, value: int) -> None:
        self._rail_height = max(0, int(value))
        self._update_shape(force=True)

    @pyqtProperty(int)
    def islandradius(self) -> int:
        return self._island_radius

    @islandradius.setter
    def islandradius(self, value: int) -> None:
        self._island_radius = max(0, int(value))
        self._update_shape(force=True)

    @pyqtProperty(int)
    def grouppadding(self) -> int:
        return self._group_padding

    @grouppadding.setter
    def grouppadding(self, value: int) -> None:
        self._group_padding = max(0, int(value))
        self._update_shape(force=True)

    @pyqtProperty(bool)
    def islands(self) -> bool:
        return self._islands_enabled

    @islands.setter
    def islands(self, value: bool) -> None:
        if value == self._islands_enabled:
            return
        self._islands_enabled = value
        self._update_shape(force=True)

    @pyqtProperty(int)
    def edgeradius(self) -> int:
        return self._edge_radius

    @edgeradius.setter
    def edgeradius(self, value: int) -> None:
        value = max(0, int(value))
        if value == self._edge_radius:
            return
        self._edge_radius = value
        self._reserve_edge_space()
        window = self.window()
        if hasattr(window, "position_bar"):
            window.position_bar()
        self._update_shape(force=True)

    @pyqtProperty(int)
    def borderwidth(self) -> int:
        return self._border_width

    @borderwidth.setter
    def borderwidth(self, value: int) -> None:
        self._border_width = max(0, int(value))
        self.update()

    @pyqtProperty(QColor)
    def bordercolor(self) -> QColor:
        return self._border_color

    @bordercolor.setter
    def bordercolor(self, value: QColor) -> None:
        self._border_color = QColor(value)
        self.update()

    @property
    def edge_overhang(self) -> int:
        """How far the frame reaches past the bar, zero unless the bar allowed the edge curves."""
        return self._edge_radius if self._edge_curves else 0

    def use_edge_curves(self, allowed: bool) -> int:
        """Told by the bar whether the edge curves apply; returns the height they need.

        Only the bar knows the width it is about to take, so it decides. Deciding here
        would let the frame reserve space the window was never given.
        """
        allowed = allowed and self._edge_radius > 0
        if allowed != self._edge_curves:
            self._edge_curves = allowed
            self._reserve_edge_space()
            self._update_shape(force=True)
        return self.edge_overhang

    def click_rect(self) -> QRect:
        """The area of the frame that takes mouse clicks, minus the edge curve overhang."""
        overhang = self.edge_overhang
        top = overhang if self._position == "bottom" else 0
        return QRect(0, top, self.width(), self.height() - overhang)

    def setLayout(self, layout) -> None:
        super().setLayout(layout)
        self._reserve_edge_space()

    def _reserve_edge_space(self) -> None:
        """Keep the widgets out of the strip the edge curves are drawn in."""
        layout = self.layout()
        if layout is None:
            return
        overhang = self.edge_overhang
        above = overhang if self._position == "bottom" else 0
        below = 0 if self._position == "bottom" else overhang
        if layout.contentsMargins().top() != above or layout.contentsMargins().bottom() != below:
            layout.setContentsMargins(0, above, 0, below)

    def event(self, event: QEvent) -> bool:
        # super() first, so the layout has run before we measure it
        handled = super().event(event)
        kind = event.type()

        if kind == QEvent.Type.LayoutRequest:
            self._update_shape()
        elif kind in RESTYLE_EVENTS:
            self._update_shape(force=True)

        return handled

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_shape(force=True)

    def paintEvent(self, event) -> None:
        """Cut the gaps out of the background Qt has already painted across the frame."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setClipPath(self._gaps)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(QRectF(0.0, 0.0, float(self.width()), self._frame_bottom()), Qt.GlobalColor.transparent)

        if self._border_width > 0 and self._border_color.alpha() > 0:
            # Stroking the gaps leaves the frame's own edges bare clipped to the shape at
            # twice the width so only the half inside the bar lands
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setClipPath(self._shape)
            painter.setPen(QPen(self._border_color, self._border_width * 2))
            painter.drawPath(self._gaps)

    def _frame_bottom(self) -> float:
        """The frame's bottom, out to a whole device pixel. On fractional scaling the last
        row is a fraction of one, and cutting only part of it leaves a line under the bar."""
        if not self.edge_overhang:  # nothing is cut below the bar, so nothing to round out to
            return float(self.height())
        ratio = self.devicePixelRatioF()
        return math.ceil(self.height() * ratio) / ratio if ratio > 0 else float(self.height())

    def _update_shape(self, force: bool = False) -> None:
        islands = self._island_spans()
        if not force and islands == self._islands:
            return

        changed = self.rect() if force else self._changed_area(self._islands, islands)
        self._islands = islands
        self._shape = self._build_shape(islands)

        frame = QPainterPath()
        frame.addRect(QRectF(0.0, 0.0, float(self.width()), self._frame_bottom()))
        self._gaps = frame.subtracted(self._shape)
        self.update(changed)

    def _changed_area(self, before: tuple, after: tuple) -> QRect:
        """The part of the bar the shape moved in, so a one pixel step does not repaint
        a whole bar and every child in it."""
        if len(before) != len(after):
            return self.rect()

        edges = [x for old, new in zip(before, after) if old != new for x in (*old, *new)]
        if not edges:
            return self.rect()

        margin = self._island_radius + 2
        return QRect(min(edges) - margin, 0, max(edges) - min(edges) + 2 * margin, self.height())

    def _island_spans(self) -> tuple[tuple[int, int], ...]:
        """Horizontal spans covered by each widget group, padded, clamped and merged.

        The containers are stretching grid cells a third of the bar wide, so their geometry
        says nothing about where the widgets are, only their content defines an island.
        An excluded widget ends the run it sits in, so one group can give two islands.
        """
        layout = self.layout()
        if layout is None:
            return ()

        width = self.width()
        if not self._islands_enabled:
            return ((0, width),) if width > 0 else ()

        padding = self._group_padding
        spans: list[tuple[int, int]] = []
        skipped: list[int] = []

        for index in range(layout.count()):
            container = layout.itemAt(index).widget()
            if container is None:
                continue

            # The container's own layout may not have positioned its widgets yet on the
            # first paint, so force it now instead of reading stale, pre-layout geometry
            if container.layout() is not None:
                container.layout().activate()

            children = container.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)
            run = None
            for child in sorted(children, key=lambda child: child.x()):
                if child.isHidden() or child.width() <= 0:
                    continue
                start = container.x() + child.x()
                end = start + child.width()
                if getattr(child, "widget_name", None) in self._exclude:
                    skipped.extend((start, end))
                    if run:
                        spans.append((run[0] - padding, run[1] + padding))
                        run = None
                elif run:
                    run[1] = end
                else:
                    run = [start, end]

            if run:
                spans.append((run[0] - padding, run[1] + padding))

        merged: list[list[int]] = []
        for start, end in sorted(spans):
            start = max(0, start)
            end = min(width, end)
            if end <= start:
                continue
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])

        if merged:
            # An excluded widget against an edge must not be snapped over
            if merged[0][0] <= self._island_radius and (not skipped or min(skipped) >= merged[0][0]):
                merged[0][0] = 0
            if merged[-1][1] >= width - self._island_radius and (not skipped or max(skipped) <= merged[-1][1]):
                merged[-1][1] = width

        return tuple((start, end) for start, end in merged)

    def _build_shape(self, islands: tuple[tuple[int, int], ...]) -> QPainterPath:
        width = float(self.width())
        # The frame is taller than the bar by edgeradius, that strip holds the edge curves
        bottom = self._frame_bottom()
        height = float(self.height() - self.edge_overhang)
        overhang = bottom - height
        rail = min(float(self._rail_height), height)

        full_rect = QPainterPath()
        full_rect.addRect(0.0, 0.0, width, height)

        if width <= 0 or height <= rail or not islands:
            return full_rect

        # Both curves share the island's side, so together they cannot exceed its height
        radius = min(float(self._island_radius), max(0.0, (height - rail) / 2))

        path = QPainterPath()
        path.moveTo(0.0, 0.0)
        path.lineTo(width, 0.0)

        last = len(islands) - 1
        for index in range(last, -1, -1):
            x0 = float(islands[index][0])
            x1 = float(islands[index][1])
            corner = min(radius, (x1 - x0) / 2)

            if x1 >= width:
                if overhang > 0.0:
                    path.lineTo(width, height + overhang)
                    path.arcTo(QRectF(width - 2 * overhang, height, 2 * overhang, 2 * overhang), 0.0, 90.0)
                else:
                    path.lineTo(width, height)
            else:
                if index == last:
                    path.lineTo(width, rail)
                next_start = float(islands[index + 1][0]) if index < last else width
                fillet = min(radius, (next_start - x1) / 2)
                path.lineTo(x1 + fillet, rail)
                if fillet > 0.0:
                    path.arcTo(QRectF(x1, rail, 2 * fillet, 2 * fillet), 90.0, 90.0)
                path.lineTo(x1, height - corner)
                if corner > 0.0:
                    path.arcTo(QRectF(x1 - 2 * corner, height - 2 * corner, 2 * corner, 2 * corner), 0.0, -90.0)

            if x0 <= 0.0:  # closeSubpath draws this side
                if overhang > 0.0:
                    path.lineTo(overhang, height)
                    path.arcTo(QRectF(0.0, height, 2 * overhang, 2 * overhang), 90.0, 90.0)
                else:
                    path.lineTo(0.0, height)
            else:
                path.lineTo(x0 + corner, height)
                if corner > 0.0:
                    path.arcTo(QRectF(x0, height - 2 * corner, 2 * corner, 2 * corner), 270.0, -90.0)
                previous_end = float(islands[index - 1][1]) if index > 0 else 0.0
                fillet = min(radius, (x0 - previous_end) / 2)
                path.lineTo(x0, rail + fillet)
                if fillet > 0.0:
                    path.arcTo(QRectF(x0 - 2 * fillet, rail, 2 * fillet, 2 * fillet), 0.0, 90.0)
                if index == 0:
                    path.lineTo(0.0, rail)

        path.closeSubpath()

        if self._position == "bottom":
            path = QTransform().translate(0.0, height + overhang).scale(1.0, -1.0).map(path)

        return path
