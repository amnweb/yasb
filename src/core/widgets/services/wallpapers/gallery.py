import logging
import math
from collections import OrderedDict
from functools import partial
from typing import NamedTuple

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QThreadPool,
    QVariantAnimation,
)
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QWidget,
)

from core.bar_helper import GlobalState
from core.utils.win32.utils import apply_qmenu_style
from core.utils.win32.window_actions import force_foreground_focus
from core.widgets.services.wallpapers.images import FolderScanner, ImageLoader
from core.widgets.services.wallpapers.manager import WallpaperManager

FADE_IN_DURATION = 80
FADE_OUT_DURATION = 120

CARD_ANIMATION_DURATION = 320
CARD_ANIMATION_EASING = QEasingCurve.Type.OutCubic

# Windows hit tests a translucent window per pixel, so a fully transparent gap
# is clicked through. One step of alpha catches the click instead.
CLICK_ALPHA = 1

NOTICE_FONT_SIZE = 13
NOTICE_PADDING = 22


def resolve_accent(value: str) -> QColor:
    """The selection colour: a hex from the config, or the Windows accent."""
    if value != "auto":
        return QColor(value)
    try:
        import winrt.windows.ui.viewmanagement as viewmanagement

        colour = viewmanagement.UISettings().get_color_value(viewmanagement.UIColorType.ACCENT)
        return QColor(colour.r, colour.g, colour.b)
    except Exception:
        logging.debug("Windows accent colour unavailable, using white", exc_info=True)
        return QColor(255, 255, 255)


class GalleryWindow(QMainWindow):
    """The window every gallery type is: screen, menu, applying, closing."""

    image_files: list[str]
    is_closing: bool
    _menu_open = False

    def build_frame(self) -> None:
        raise NotImplementedError

    def build_content(self, screen) -> None:
        raise NotImplementedError

    def selected_image(self) -> str | None:
        raise NotImplementedError

    def _on_fade_out_finished(self) -> None:
        raise NotImplementedError

    def initUI(self, parent=None, screen=None) -> None:
        screen = self.setup_window(parent, screen)
        self.build_frame()
        self.setStyleSheet(GlobalState.stylesheet())
        self.build_content(screen)

    def setup_window(self, parent, screen=None):
        if parent and not screen:
            if parent.window() and parent.window().screen():
                screen = parent.window().screen()
            if not screen:
                screen = QApplication.screenAt(parent.mapToGlobal(QPoint(0, 0)))
            if not screen:
                screen = parent.screen()
        if not screen:
            screen = QApplication.primaryScreen()

        try:
            self.dpr = float(screen.devicePixelRatio())
        except Exception:
            self.dpr = 1.0

        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        return screen

    def showEvent(self, event):
        super().showEvent(event)
        force_foreground_focus(int(self.winId()))

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow() and not self.is_closing and not self._menu_open:
                self.fade_out_and_close_gallery()
        super().changeEvent(event)

    def set_wallpaper(self) -> None:
        image_path = self.selected_image()
        if image_path:
            self.apply_wallpaper(image_path, None)

    def show_context_menu_for_image(self, index: int, pos) -> None:
        if index < 0 or index >= len(self.image_files):
            return

        image_path = self.image_files[index]
        menu = QMenu(self)
        apply_qmenu_style(menu)
        menu.setProperty("class", "context-menu")

        action_all = menu.addAction("Set on all screens")
        action_all.triggered.connect(lambda: self.apply_wallpaper(image_path, None))

        monitor_ids = WallpaperManager().get_monitor_ids()
        if len(monitor_ids) > 1:
            menu.addSeparator()
            for position, monitor_id in enumerate(monitor_ids):
                action = menu.addAction(f"Set on screen {position + 1}")
                action.triggered.connect(partial(self.apply_wallpaper, image_path, monitor_id))

        self._menu_open = True
        menu.exec(pos)
        self._menu_open = False
        if not self.is_closing and not self.isActiveWindow():
            self.fade_out_and_close_gallery()

    def apply_wallpaper(self, image_path: str, monitor_id: str | None) -> None:
        self.fade_out_and_close_gallery()
        if monitor_id is None:
            WallpaperManager().set_wallpaper(image_path)
        else:
            WallpaperManager().set_wallpaper(image_path, monitor_id=monitor_id, animate=False)

    def fade_in_gallery(self, parent=None, screen=None) -> None:
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, GalleryWindow) and widget.isVisible():
                widget.fade_out_and_close_gallery()

        self.initUI(parent, screen)
        self.fade_in_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in_animation.setDuration(FADE_IN_DURATION)
        self.fade_in_animation.setStartValue(0)
        self.fade_in_animation.setEndValue(1)
        self.fade_in_animation.start()
        self.show()

    def fade_out_and_close_gallery(self) -> None:
        if self.is_closing:
            return
        self.is_closing = True

        self.fade_out_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out_animation.setDuration(FADE_OUT_DURATION)
        self.fade_out_animation.setStartValue(1)
        self.fade_out_animation.setEndValue(0)
        self.fade_out_animation.finished.connect(self._on_fade_out_finished)
        self.fade_out_animation.start()


class Placement(NamedTuple):
    """Where one card sits, in pixels from the centre of the view."""

    x: float
    scale: float = 1.0
    shear: float = 0.0
    opacity: float = 1.0
    focus: float = 0.0


class CardsView(QWidget):
    def __init__(self, gallery: Cards):
        super().__init__()
        self.gallery = gallery
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.offset = 0.0
        self.index = 0
        self.hovered: int | None = None
        self.hit_areas: list[tuple[int, QPolygonF]] = []

        self.animation = QVariantAnimation(self)
        self.animation.setDuration(CARD_ANIMATION_DURATION)
        self.animation.setEasingCurve(CARD_ANIMATION_EASING)
        self.animation.valueChanged.connect(self._on_animation_value)
        self.animation.finished.connect(self._on_animation_finished)

    @property
    def count(self) -> int:
        return len(self.gallery.image_files)

    def relative_distance(self, index: int) -> float:
        count = self.count
        distance = index - self.offset
        if self.gallery.wraps and count > 1:
            distance = ((distance + count / 2.0) % count) - count / 2.0
        return distance

    def visible_cards(self) -> list[tuple[int, float]]:
        count = self.count
        if count == 0:
            return []

        neighbours = self.gallery.neighbours
        limit = neighbours + 0.5
        centre = int(math.floor(self.offset + 0.5))
        nearest: dict[int, float] = {}

        for step in range(centre - neighbours - 1, centre + neighbours + 2):
            index = step % count
            distance = self.relative_distance(index)
            if abs(distance) > limit:
                continue
            if index not in nearest or abs(distance) < abs(nearest[index]):
                nearest[index] = distance

        cards = list(nearest.items())
        cards.sort(key=lambda card: -abs(card[1]))
        return cards

    def project(self, spot: Placement, inset: float = 0.0) -> QPolygonF:
        card_w, card_h = self.gallery.card_size

        half_w = max(1.0, card_w * spot.scale / 2.0 - inset)
        half_h = max(1.0, card_h * spot.scale / 2.0 - inset)
        centre_x = self.width() / 2.0 + spot.x
        centre_y = self.height() / 2.0
        lean = spot.shear * half_h

        return QPolygonF(
            [
                QPointF(centre_x - half_w + lean, centre_y - half_h),
                QPointF(centre_x + half_w + lean, centre_y - half_h),
                QPointF(centre_x + half_w - lean, centre_y + half_h),
                QPointF(centre_x - half_w - lean, centre_y + half_h),
            ]
        )

    @staticmethod
    def draw_cover(painter: QPainter, pixmap: QPixmap, rect: QRectF):
        """Fill *rect* with *pixmap*, cropping rather than stretching it."""
        size = pixmap.deviceIndependentSize()
        scale = max(rect.width() / size.width(), rect.height() / size.height())
        width, height = size.width() * scale, size.height() * scale
        centre = rect.center()
        target = QRectF(centre.x() - width / 2.0, centre.y() - height / 2.0, width, height)
        painter.drawPixmap(target, pixmap, QRectF(0, 0, pixmap.width(), pixmap.height()))

    def draw_notice(self, message: str, painter: QPainter):
        """A message on its own panel.

        The window is translucent, so the text sits directly on the desktop and
        plain white is unreadable over a light wallpaper. The panel gives it a
        background it controls.
        """
        font = painter.font()
        font.setPointSize(NOTICE_FONT_SIZE)
        painter.setFont(font)

        align = Qt.AlignmentFlag.AlignCenter
        text_area = painter.boundingRect(self.rect(), align, message)
        panel = text_area.adjusted(-NOTICE_PADDING, -NOTICE_PADDING, NOTICE_PADDING, NOTICE_PADDING)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 190))
        painter.drawRoundedRect(panel, 12, 12)

        painter.setPen(QColor(255, 255, 255, 235))
        painter.drawText(self.rect(), align, message)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        gallery = self.gallery
        border = gallery.border
        self.hit_areas = []

        if not gallery.image_files:
            if not gallery.scanning:
                self.draw_notice("No wallpapers found in\n" + "\n".join(gallery.image_paths), painter)
            painter.end()
            return

        if CLICK_ALPHA:
            painter.fillRect(self.rect(), QColor(0, 0, 0, CLICK_ALPHA))

        for index, spot in gallery.layout_cards():
            quad = self.project(spot)
            opacity = spot.opacity
            if opacity <= 0.01:
                continue
            bounds = quad.boundingRect()
            if bounds.right() < 0 or bounds.left() > self.width():
                continue
            if bounds.bottom() < 0 or bounds.top() > self.height():
                continue

            picture = self.project(spot, border) if border else quad
            area = picture.boundingRect()
            focus = spot.focus

            painter.setOpacity(opacity)
            painter.save()
            window = QPainterPath()
            radius = gallery.corner_radius
            if spot.shear or radius <= 0:
                # A leaning card is a parallelogram; a rounded rect cannot follow it.
                window.addPolygon(picture)
                window.closeSubpath()
            else:
                # Same rect and radius as the border, so the two stay concentric.
                window.addRoundedRect(area, radius, radius)
            painter.setClipPath(window)

            pixmap = gallery.pixmap_for(index)
            if pixmap is not None:
                self.draw_cover(painter, pixmap, area)
            else:
                painter.fillRect(area, QColor(255, 255, 255, 18))

            shade = int(255 * gallery.dim * (1.0 - focus))
            if shade:
                painter.fillRect(area, QColor(0, 0, 0, shade))
            painter.restore()

            # Cubed, so a card mid-move barely shows a border and only one looks selected.
            strength = 1.0 if index == self.hovered else focus**3
            if border and strength > 0.01:
                edge = self.project(spot, border / 2.0)
                outline = QPainterPath()
                radius = gallery.corner_radius
                if spot.shear or radius <= 0:
                    # A leaning card is a parallelogram; a rounded rect cannot follow it.
                    outline.addPolygon(edge)
                    outline.closeSubpath()
                else:
                    corner = radius + border / 2.0
                    outline.addRoundedRect(edge.boundingRect(), corner, corner)

                accent = QColor(gallery.accent)
                accent.setAlpha(int(255 * strength))
                pen = QPen(accent)
                pen.setWidthF(border)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(outline)

            self.hit_areas.append((index, quad))

        painter.end()

    def card_at(self, position: QPointF) -> int | None:
        for index, quad in reversed(self.hit_areas):
            if quad.containsPoint(position, Qt.FillRule.OddEvenFill):
                return index
        return None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.gallery.fit_to_view(self.width(), self.height())

    def _on_animation_value(self, value):
        self.offset = float(value)
        self.update()

    def _on_animation_finished(self):
        # The selection was set when the move started; only the offset needs tidying.
        self.offset = self.gallery.normalise_offset(self.offset)
        self.update()

    def go_to(self, index: int, animate: bool = True):
        count = self.count
        if not count:
            return

        self.index = index % count
        target = self.gallery.offset_for(self.index)
        self.gallery.on_focus_changed(self.index)

        self.animation.stop()
        if not animate:
            self.offset = target
            self.update()
            return

        self.animation.setStartValue(self.offset)
        self.animation.setEndValue(target)
        self.animation.start()

    def move_by(self, delta: int):
        count = self.count
        if not count:
            return
        if self.gallery.wraps:
            self.go_to(self.index + delta)
        else:
            self.go_to(max(0, min(count - 1, self.index + delta)))

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            self.move_by(-1 if delta > 0 else 1)
            event.accept()

    def mouseMoveEvent(self, event):
        hovered = self.card_at(event.position())
        if hovered != self.hovered:
            self.hovered = hovered
            self.update()

    def leaveEvent(self, event):
        if self.hovered is not None:
            self.hovered = None
            self.update()

    def mousePressEvent(self, event):
        # Clicking never moves the cards, so a double click acts on what you aimed at.
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        index = self.card_at(event.position())
        if index is not None:
            self.gallery.apply_wallpaper(self.gallery.image_files[index], None)
        event.accept()

    def contextMenuEvent(self, event):
        mouse = event.reason() == event.Reason.Mouse
        index = self.card_at(QPointF(event.pos())) if mouse else self.index
        if index is not None:
            self.gallery.show_context_menu_for_image(index, event.globalPos())


class Cards(GalleryWindow):
    """A gallery that paints its wallpapers instead of making a widget per image."""

    step = 1.0  # gap between neighbouring cards, in card widths
    border = 0  # frame every card gives up, painted only on the selected one
    dim = 0.0  # how far the unselected cards are darkened
    max_scale = 1.0  # largest a card ever gets, so the band can be tall enough

    def place(self, distance: float) -> Placement:
        """Where the card *distance* steps from the selection sits."""
        raise NotImplementedError

    def layout_cards(self) -> list[tuple[int, Placement]]:
        """Every card worth painting, outermost first."""
        cards = []
        for index, distance in self.view.visible_cards():
            spot = self.place(distance)
            cards.append((index, spot._replace(focus=max(0.0, 1.0 - abs(distance)))))
        return cards

    def decode_order(self, index: int) -> float:
        return abs(self.view.relative_distance(index))

    def offset_for(self, index: int) -> float:
        return self.view.offset + self.view.relative_distance(index)

    def normalise_offset(self, offset: float) -> float:
        count = len(self.image_files)
        return offset % count if count and self.wraps else offset

    def __init__(self, image_paths, gallery):
        super().__init__()
        self.image_paths = [image_paths] if isinstance(image_paths, str) else list(image_paths)
        self.image_files: list[str] = []
        self.scanning = True

        width = gallery["image_width"]
        height = width * 9 // 16 if gallery["orientation"] == "landscape" else width * 16 // 9
        self.card_size = (width, height)
        self.corner_radius = gallery["image_corner_radius"]
        self.accent = resolve_accent(gallery["accent_color"])

        self.neighbours = 1
        self.wraps = False
        self.dpr = 1.0
        self.is_closing = False
        self._cache: OrderedDict[int, QPixmap] = OrderedDict()
        self._pending: set[int] = set()
        self._queued: dict[int, ImageLoader] = {}
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(2)

        self.view = CardsView(self)

        # Started here rather than on show, so the walk has a head start on the
        # window being built and the fade-in running.
        scanner = FolderScanner(self.image_paths)
        scanner.signals.finished.connect(self._on_scan_finished)
        self.threadpool.start(scanner)

    def _on_scan_finished(self, files: list[str]):
        self.scanning = False
        if self.is_closing:
            return
        self.image_files = files
        self.fit_to_view(self.view.width(), self.view.height())
        self.view.go_to(0, animate=False)

    def build_frame(self):
        self.setCentralWidget(self.view)

    def build_content(self, screen):
        area = screen.geometry()
        _, card_h = self.card_size
        height = min(area.height(), int(card_h * self.max_scale))
        self.setGeometry(area.x(), area.y() + (area.height() - height) // 2, area.width(), height)
        self.fit_to_view(area.width(), height)
        self.on_focus_changed(0)

    def fit_to_view(self, width: int, height: int):
        card_w, _ = self.card_size
        step = max(1.0, self.step * card_w)
        needed = int(math.ceil(width / (2.0 * step))) + 1
        count = len(self.image_files)
        self.neighbours = max(1, min(needed, max(1, (count - 1) // 2)))
        self.wraps = count > 2 * self.neighbours

    def selected_image(self) -> str | None:
        if not self.image_files:
            return None
        return self.image_files[self.view.index]

    def pixmap_for(self, index: int) -> QPixmap | None:
        pixmap = self._cache.get(index)
        if pixmap is not None:
            self._cache.move_to_end(index)
        return pixmap

    def on_focus_changed(self, index: int):
        if self.image_files:
            self._load_around(index)

    def _load_around(self, index: int):
        count = len(self.image_files)
        if not count:
            return

        radius = self.neighbours + 3
        wanted = {(index + offset) % count for offset in range(-radius, radius + 1)}
        card_w, card_h = self.card_size

        self._requeue(wanted)

        for target in sorted(wanted, key=self.decode_order):
            if target in self._cache or target in self._pending:
                continue
            self._pending.add(target)
            loader = ImageLoader(self.image_files[target], card_w, card_h, target, dpr=self.dpr)
            loader.signals.loaded.connect(self._on_image_loaded)
            loader.setAutoDelete(False)
            self._queued[target] = loader
            self.threadpool.start(loader, self._priority(target))

        limit = 2 * radius + 8
        for cached in [i for i in self._cache if i not in wanted]:
            if len(self._cache) <= limit:
                break
            del self._cache[cached]

    def _priority(self, target: int) -> int:
        """Higher for the cards nearest the selection, so they decode first."""
        count = len(self.image_files)
        distance = abs(target - self.view.index)
        if self.wraps and count:
            distance = min(distance, count - distance)
        return -distance

    def _requeue(self, wanted: set[int]):
        for target, loader in list(self._queued.items()):
            if target in self._cache:
                del self._queued[target]
            elif not self.threadpool.tryTake(loader):
                continue  # already running, too late to reorder it
            elif target in wanted:
                self.threadpool.start(loader, self._priority(target))
            else:
                # Never started, so nothing will arrive to clear it.
                del self._queued[target]
                self._pending.discard(target)

    def _on_image_loaded(self, image_path: str, pixmap: QPixmap, index: int):
        self._pending.discard(index)
        if self.is_closing or index >= len(self.image_files):
            return
        self._cache[index] = pixmap
        if abs(self.view.relative_distance(index)) <= self.neighbours + 0.5:
            self.view.update()

    def page_step(self) -> int:
        """How far Page Up/Down moves: onto the last card actually on screen."""
        card_w, _ = self.card_size
        step = max(1.0, self.step * card_w)
        return max(1, int((self.view.width() / 2 - card_w / 2) // step))

    def keyPressEvent(self, event):
        key = event.key()
        page = self.page_step()

        if key == Qt.Key.Key_Escape:
            self.fade_out_and_close_gallery()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.set_wallpaper()
        elif key == Qt.Key.Key_Left:
            self.view.move_by(-1)
        elif key == Qt.Key.Key_Right:
            self.view.move_by(1)
        elif key == Qt.Key.Key_PageUp:
            self.view.move_by(-page)
        elif key == Qt.Key.Key_PageDown:
            self.view.move_by(page)
        elif key == Qt.Key.Key_Home:
            self.view.go_to(0)
        elif key == Qt.Key.Key_End:
            self.view.go_to(len(self.image_files) - 1)
        else:
            super().keyPressEvent(event)

    def _on_fade_out_finished(self):
        self.view.animation.stop()
        self.threadpool.clear()
        self._cache.clear()
        self.destroy()


class Default(Cards):
    """One row of thumbnails at a fixed size, with a gap between them."""

    gap = 6  # between thumbnails, in pixels
    border = 2
    dim = 0.0

    @property
    def step(self) -> float:
        card_w, _ = self.card_size
        return (card_w + self.gap) / card_w

    def place(self, distance: float) -> Placement:
        card_w, _ = self.card_size
        return Placement(x=distance * self.step * card_w)


class Magnified(Cards):
    """A tight row where the selected card swells and pushes its neighbours aside."""

    gap = 6
    border = 2
    dim = 0.0
    grow = 0.2  # how much bigger the selected card gets
    reach = 1.0  # how many cards away the growth fades out over

    @property
    def max_scale(self) -> float:
        return 1.0 + self.grow

    def scale_at(self, distance: float) -> float:
        return 1.0 + self.grow * max(0.0, 1.0 - abs(distance) / self.reach)

    def layout_cards(self) -> list[tuple[int, Placement]]:
        cards = sorted(self.view.visible_cards(), key=lambda pair: pair[1])
        if not cards:
            return []

        card_w, _ = self.card_size
        widths = [card_w * self.scale_at(distance) for _, distance in cards]

        # Accumulated, so growth pushes the neighbours aside instead of covering
        # them. A closed form of this gets the spacing wrong mid-move.
        centres = [0.0]
        for before, after in zip(widths, widths[1:]):
            centres.append(centres[-1] + (before + after) / 2.0 + self.gap)

        distances = [distance for _, distance in cards]
        anchor = centres[0]
        for position in range(len(distances) - 1):
            if distances[position] <= 0.0 <= distances[position + 1]:
                span = distances[position + 1] - distances[position]
                share = (0.0 - distances[position]) / span if span else 0.0
                anchor = centres[position] + (centres[position + 1] - centres[position]) * share
                break

        placed = [
            (
                index,
                Placement(
                    x=centre - anchor,
                    scale=self.scale_at(distance),
                    focus=max(0.0, 1.0 - abs(distance)),
                ),
            )
            for (index, distance), centre in zip(cards, centres)
        ]
        placed.sort(key=lambda pair: pair[1].focus)
        return placed


class Strip(Cards):
    """Cards tile edge to edge with leaning edges."""

    step = 1.0
    lean = 0.21  # of the card edges, in half card heights
    border = 2
    dim = 0.40

    def place(self, distance: float) -> Placement:
        card_w, _ = self.card_size
        return Placement(x=distance * self.step * card_w, shear=self.lean)


class Slide(Cards):
    """Upright cards; neighbours shrink and fade towards the edges."""

    step = 0.72
    shrink = 0.26  # how much each step away shrinks a card
    fade = 0.28  # how much each step away fades a card

    def place(self, distance: float) -> Placement:
        card_w, _ = self.card_size
        span = abs(distance)
        return Placement(
            x=distance * self.step * card_w,
            scale=1.0 / (1.0 + self.shrink * span),
            opacity=max(0.0, 1.0 - span * self.fade),
        )


TYPES: dict[str, type[GalleryWindow]] = {
    "default": Default,
    "magnified": Magnified,
    "strip": Strip,
    "slide": Slide,
}
