import logging
from ctypes import byref, wintypes

import win32gui
from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, QTimer
from PyQt6.QtGui import QCursor, QFontMetrics, QImage, QPixmap, QRegion
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from core.utils.utilities import refresh_widget_style
from core.utils.win32.backdrop import enable_blur
from core.utils.win32.bindings.dwmapi import (
    DwmQueryThumbnailSourceSize,
    DwmRegisterThumbnail,
    DwmUnregisterThumbnail,
    DwmUpdateThumbnailProperties,
)
from core.utils.win32.constants import (
    DWM_TNP_OPACITY,
    DWM_TNP_RECTDESTINATION,
    DWM_TNP_SOURCECLIENTAREAONLY,
    DWM_TNP_VISIBLE,
)
from core.utils.win32.structs import DWM_THUMBNAIL_PROPERTIES, RECT, SIZE
from core.utils.win32.window_actions import close_application
from core.widgets.services.taskbar.peek import activate_live_preview, exclude_from_peek, is_live_preview_available

logger = logging.getLogger("taskbar_thumbnail")


def ceil(count: int, per: int) -> int:
    """How many groups of `per` it takes to hold `count`."""
    return -(-count // per)


class ThumbnailHost(QWidget):
    """Custom widget to host DWM thumbnail and capture mouse clicks."""

    def __init__(self, preview_popup, item, parent=None):
        super().__init__(parent)
        self._preview_popup = preview_popup
        self._item = item
        self._hwnd = item.hwnd
        self.setMouseTracking(True)

    def enterEvent(self, event):
        """Notify preview that mouse entered thumbnail and hover its item."""
        try:
            if self._preview_popup:
                self._preview_popup._cancel_hide()
            self._item.set_hovered(True)
        except RuntimeError:
            pass
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Notify preview that mouse left thumbnail, and drop the item's hover with it."""
        try:
            if self._preview_popup:
                self._preview_popup._schedule_hide()
            self._item.set_hovered(False)
        except RuntimeError:
            pass
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Forward click to preview to bring the hosted window to foreground."""
        if self._preview_popup:
            self._preview_popup.activate_window(self._hwnd)
        else:
            super().mousePressEvent(event)


class PreviewAnimation:
    """Helper class to manage fade-in animation for preview popups."""

    def __init__(self, widget: QWidget, duration: int = 300):
        self._widget = widget
        self._duration = int(duration or 0)
        self._anim: QPropertyAnimation | None = None
        self._running = False

    def start(self):
        if self._running:
            return

        if self._duration <= 0:
            try:
                self._widget.setWindowOpacity(1.0)
                self._widget.show()
            except Exception:
                pass
            return

        try:
            self._widget.setWindowOpacity(0.0)
            self._widget.show()
            self._anim = QPropertyAnimation(self._widget, b"windowOpacity", self._widget)
            self._anim.setDuration(self._duration)
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._running = True

            def _on_finished():
                self._running = False

            self._anim.finished.connect(_on_finished)
            self._anim.start()
        except Exception:
            # fallback to immediate show
            try:
                self._widget.setWindowOpacity(1.0)
                self._widget.show()
            except Exception:
                pass

    def stop(self):
        try:
            if self._anim is not None:
                try:
                    self._anim.stop()
                except Exception:
                    pass
                self._anim = None
            self._running = False
        except Exception:
            pass

    @property
    def running(self) -> bool:
        return bool(self._running)


class PreviewItem(QFrame):
    """One window inside a preview popup, header (icon, title, close) above its thumbnail."""

    ICON_SIZE = 16
    SPACING = 6

    def __init__(self, popup: PreviewPopup, hwnd: int, title: str | None, icon: QPixmap | None, flashing: bool):
        super().__init__(popup._content)
        self.setProperty("class", "preview-item flashing" if flashing else "preview-item")
        self._popup = popup
        self.hwnd = hwnd
        self.title = title if title is not None else (win32gui.GetWindowText(hwnd) or "")
        self.thumb = wintypes.HANDLE(0)
        self.thumb_rect = QRect()

        self.header = QFrame(self)
        self.header.setProperty("class", "header")
        layout = QHBoxLayout(self.header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.SPACING)

        self.icon_label = QLabel(self.header)
        self.icon_label.setFixedSize(self.ICON_SIZE, self.ICON_SIZE)
        self.icon_label.setScaledContents(True)

        self.title_label = QLabel(self.header)
        self.title_label.setProperty("class", "title")

        self.close_button = QLabel(self.header)
        self.close_button.setProperty("class", "close-button")
        self.close_button.setText("\ue8bb")
        self.close_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.mousePressEvent = lambda e: popup.close_window(self.hwnd)

        self._header_width = 0

        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.title_label, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.header_height = self.header.sizeHint().height()
        self.close_button.setVisible(False)

        if isinstance(icon, QPixmap) and not icon.isNull():
            dpr = popup.get_dpr()
            target = max(1, int(self.ICON_SIZE * dpr))
            phys_pix = icon.scaled(
                target,
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            phys_pix.setDevicePixelRatio(dpr)
            self.icon_label.setPixmap(phys_pix)

    def update_elided_title(self, width: int | None = None):
        if width is not None:
            self._header_width = width
        avail = self._header_width - self.icon_label.width() - self.SPACING
        if self.close_button.isVisibleTo(self):
            # Ask for the size, the button has no geometry yet on the hover that reveals it
            close_w = max(self.close_button.sizeHint().width(), self.close_button.minimumWidth())
            avail -= close_w + self.SPACING
        if avail <= 0:
            self.title_label.setText("")
            return
        elided_text = QFontMetrics(self.title_label.font()).elidedText(self.title, Qt.TextElideMode.ElideRight, avail)
        self.title_label.setText(elided_text)

    def natural_width(self) -> int:
        """Width the header needs to show the whole title next to the icon and the close button."""
        close_w = max(self.close_button.sizeHint().width(), self.close_button.minimumWidth())
        title_w = QFontMetrics(self.title_label.font()).horizontalAdvance(self.title)
        return self.icon_label.width() + title_w + close_w + (2 * self.SPACING)

    def round_outer_corners(self, radius: int, at_left: bool, at_right: bool, at_top: bool, at_bottom: bool):
        """Match the popup radius on the corners this item sits on, so a hovered item is not square."""
        corners = []
        if radius > 0:
            for name, touching in (
                ("top-left", at_top and at_left),
                ("top-right", at_top and at_right),
                ("bottom-left", at_bottom and at_left),
                ("bottom-right", at_bottom and at_right),
            ):
                if touching:
                    corners.append(f"border-{name}-radius:{radius}px")
        style = ".preview-item{" + ";".join(corners) + "}" if corners else ""
        if self.styleSheet() != style:
            self.setStyleSheet(style)

    def set_hovered(self, hovered: bool):
        """Drive the :hover state by hand, the thumbnail sits in a masked hole outside this widget."""
        if hovered:
            # Only one window is ever hovered, so a neighbour that missed its own leave lets go here
            for other in self._popup._items:
                if other is not self:
                    other.set_hovered(False)
        if self.underMouse() != hovered:
            self.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, hovered)
            self.update()
        if self.close_button.isVisibleTo(self) != hovered:
            self.close_button.setVisible(hovered)
            self.update_elided_title()
        # Peek follows the whole cell, not just the thumbnail, so the padding around it still counts
        manager = getattr(self._popup, "_thumbnail_manager", None)
        if manager:
            manager.set_peek(self.hwnd, hovered)

    def enterEvent(self, event):
        """Hovering the header counts as hovering the item, same as hovering its thumbnail."""
        self.set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Leaving means not hovered.

        Whatever the pointer moved onto sets the hover itself: crossing to the thumbnail raises
        the host's enter, coming back raises this widget's. Trying to preserve the hover here is
        what stuck the highlight on, because a state kept from a cursor sample can only be undone
        by a later event, and the pointer may never send this widget another one.
        """
        self.set_hovered(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Clicking anywhere on the item focuses its window."""
        self._popup.activate_window(self.hwnd)
        super().mousePressEvent(event)


class PreviewPopup(QFrame):
    """Window preview popup, a row of thumbnails or, once they no longer fit, a list of titles."""

    # The narrowest a cell may get, measured on the cell rather than on the thumbnail inside it:
    # at this width the header still fits its icon, a few characters of title and the close
    # button, the title giving its room back to the button on hover. Below it the windows are
    # listed by title instead. Every part of that is in logical pixels, so a scaled screen keeps
    # the same proportions, but a heavier close button or font in CSS eats into the title.
    MIN_WIDTH = 100
    # How often the backdrop is nudged into resampling while the preview is up
    BACKDROP_REFRESH = 20

    def __init__(
        self,
        parent=None,
        width: int = 240,
        padding: int = 8,
        margin: int = 8,
        animation_duration: int = 300,
        blur: bool = False,
        peek: bool = False,
    ):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._width = width
        self._margin = margin
        self._padding = padding
        self._animation_duration = animation_duration
        self._blur = blur
        self._peek = peek

        # Main content frame
        self._content = QFrame(self)
        self._content.setProperty("class", "taskbar-preview")

        if self._blur:
            enable_blur(self.winId(), DarkMode=False, RoundCorners=True, BorderColor="None")

        self._fade_anim = PreviewAnimation(self, self._animation_duration)
        self._items: list[PreviewItem] = []
        self._thumbnail_manager = None
        self._radius = None

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(300)
        self._hide_timer.timeout.connect(self._do_hide)

        # Backdrop blur fix. Without updating the popup content, we get the same result as the real taskbar,
        # where the blur shows a stale background from the window or wallpaper.
        self._backdrop = QTimer(self)
        self._backdrop.setInterval(self.BACKDROP_REFRESH)
        self._backdrop.timeout.connect(lambda: self._content.update(QRect(0, 0, 1, 1)))
        self._list_mode = False

    def _corner_radius(self) -> int:
        """Measure the styled corner radius: first column of the top row reaching the inside opacity."""
        if self._radius is not None:
            return self._radius

        self._radius = 0
        probe = min(64, self.width() // 2, self.height() // 2)
        if probe > 0:
            image = QImage(probe, probe, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            self._content.render(image, QPoint(), QRegion(0, 0, probe, probe), QWidget.RenderFlag(0))
            # A transparent inside means no background is painted, keep the plain rectangle
            opaque = image.pixelColor(probe - 1, probe - 1).alpha()
            if opaque > 0:
                radius = 0
                while radius < probe and image.pixelColor(radius, 0).alpha() < opaque:
                    radius += 1
                self._radius = 0 if radius >= probe else radius
        return self._radius

    def get_dpr(self) -> float:
        """Return device pixel ratio for this preview (per-screen)."""
        val = getattr(self, "_dpr", None)
        if val is not None:
            return float(val)

        # fall back to the widget's devicePixelRatioF() when available
        try:
            return float(self.devicePixelRatioF())
        except Exception:
            return 1.0

    def showEvent(self, event):
        # Only peek moves what is behind the preview, so without it the backdrop cannot go stale
        if self._blur and self._peek:
            self._backdrop.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._backdrop.stop()
        self._fade_anim.stop()
        self._cancel_hide()
        super().hideEvent(event)

    def show_for(self, entries: list[tuple[int, str | None, QPixmap | None, bool]], anchor_widget: QWidget) -> bool:
        """Build preview item per (hwnd, title, icon) entry and lay the popup out."""
        entries = [entry for entry in entries if win32gui.IsWindow(entry[0])]
        if not entries:
            return False

        # The window the anchor button currently stands for, used to match an already open preview
        self._src_hwnd = getattr(anchor_widget, "_hwnd", entries[0][0])
        self._anchor_widget = anchor_widget

        # Capture device pixel ratio from the anchor's screen so previews on multi-monitor
        # setups use the correct per-screen scaling.
        try:
            # prefer the screen DPR if available
            screen = anchor_widget.screen()
            try:
                self._dpr = float(screen.devicePixelRatio())
            except Exception:
                # fallback to floating DPR if available on the screen; else default to 1.0
                try:
                    self._dpr = float(screen.devicePixelRatioF())
                except Exception:
                    self._dpr = 1.0
        except Exception:
            self._dpr = 1.0

        self._items = [PreviewItem(self, hwnd, title, icon, flashing) for hwnd, title, icon, flashing in entries]

        anchor_center = anchor_widget.mapToGlobal(anchor_widget.rect().center())
        screen_geom = anchor_widget.screen().geometry()
        self._anchor_center_x = anchor_center.x()
        self._anchor_top = anchor_widget.mapToGlobal(anchor_widget.rect().topLeft()).y()
        self._anchor_bottom = anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft()).y()
        self._screen_geom = screen_geom

        # A second row of thumbnails would both span the screen and register that many more live
        # DWM thumbnails at once, so the windows are listed by title from there on instead
        self._list_mode = len(self._items) > self._grid_columns(len(self._items))

        self._calculate_and_position_popup()
        return True

    def _popup_space(self) -> int:
        """Vertical room for the popup, on whichever side of the bar has more of it."""
        above = self._anchor_top - self._screen_geom.top() - self._margin
        below = self._screen_geom.bottom() - self._anchor_bottom - self._margin
        return max(0, above, below)

    def _grid_columns(self, count: int) -> int:
        """How many thumbnails fit side by side once shrunk as far as MIN_WIDTH allows."""
        gap = 2 * self._padding
        available_w = self._screen_geom.width() - (2 * self._margin) - (2 * self._padding)
        return max(1, min(count, (available_w + gap) // (self.MIN_WIDTH + gap)))

    def _place(self, popup_w: int, popup_h: int) -> int:
        """Center the popup on its anchor, above the bar when it fits, and pull it inside the screen.

        Returns the width it was placed with, which is never below MIN_WIDTH.
        """
        popup_w = max(popup_w, self.MIN_WIDTH)

        x = self._anchor_center_x - popup_w // 2
        if self._anchor_top - popup_h - self._margin >= self._screen_geom.top():
            y = self._anchor_top - popup_h - self._margin
        else:
            y = self._anchor_bottom + self._margin

        x = max(self._screen_geom.left() + self._margin, min(self._screen_geom.right() - popup_w - self._margin, x))
        y = max(self._screen_geom.top() + self._margin, min(self._screen_geom.bottom() - popup_h - self._margin, y))

        self._final_pos = QPoint(x, y)
        self.setGeometry(x, y, popup_w, popup_h)
        self._content.setGeometry(0, 0, popup_w, popup_h)
        return popup_w

    def _calculate_and_position_popup(self):
        """
        Size and position the popup from the thumbnail dimensions reported by DWM.
        Every thumbnail is fitted into the same box, the configured width at 16:9, keeping its own
        aspect ratio. A window taller than the box comes out narrower at the same height, a wider
        one comes out shorter at the same width, and each cell then hugs the thumbnail it holds.
        The box gives way as the row fills, so more windows means smaller thumbnails until they
        would pass MIN_WIDTH, which is where the list takes over.
        """
        count = len(self._items)
        if not count:
            return

        if self._list_mode:
            self._layout_as_list()
            return

        header_h = self._items[0].header_height

        # Cells are spaced by two paddings so every item keeps the same padding around its own cell
        gap = 2 * self._padding

        # The box every thumbnail is fitted into, shortened when the screen is too short for it
        available_w = self._screen_geom.width() - (2 * self._margin) - (2 * self._padding)
        box_w = max(self.MIN_WIDTH, min(self._width, (available_w - (count - 1) * gap) // count))
        box_h = max(1, min(int(box_w * 9 / 16), self._popup_space() - header_h - (2 * self._padding)))

        sizes = []
        for item in self._items:
            src_w, src_h = self._source_size(item)
            scale = min(box_w / src_w, box_h / src_h)
            sizes.append((max(1, int(src_w * scale)), max(1, int(src_h * scale))))

        # A cell hugs its own thumbnail, down to the width its header still needs, and the row is
        # as tall as the tallest thumbnail in it
        cells = [max(self.MIN_WIDTH, w) for w, _ in sizes]
        row_w = sum(cells) + (count - 1) * gap
        row_h = max(h for _, h in sizes)
        total_h = header_h + row_h + (2 * self._padding)

        popup_w = self._place(row_w + (2 * self._padding), total_h)

        cell_x = (popup_w - row_w) // 2
        for position, (item, (thumb_w, thumb_h), cell) in enumerate(zip(self._items, sizes, cells)):
            # Items tile the popup, each one padded evenly around its cell, and the outer ones
            # reach the popup edge so hovering a window never leaves a background strip showing
            left = 0 if position == 0 else cell_x - self._padding
            right = popup_w if position == count - 1 else cell_x + cell + self._padding
            item.setGeometry(left, 0, right - left, total_h)
            item.header.setGeometry(cell_x - left, self._padding, cell, header_h)
            item.update_elided_title(cell)
            item.round_outer_corners(self._corner_radius(), left == 0, right == popup_w, True, True)
            item.thumb_rect = QRect(
                cell_x + (cell - thumb_w) // 2,
                self._padding + header_h + (row_h - thumb_h) // 2,
                thumb_w,
                thumb_h,
            )
            cell_x += cell + gap

    def _layout_as_list(self):
        """
        Size and position the popup as a list of windows, one row of icon and title each.
        Rows tile the popup and carry their own padding, so it doubles as the padding around the
        whole list, the same way the grid cells reach its edges.
        """
        count = len(self._items)
        header_h = self._items[0].header_height
        row_h = header_h + (2 * self._padding)

        available_w = self._screen_geom.width() - (2 * self._margin)

        # A list too tall for the screen wraps into further columns rather than running off it
        rows_that_fit = max(1, self._popup_space() // row_h)
        widest_allowed = max(1, available_w // self.MIN_WIDTH)
        columns = max(1, min(ceil(count, rows_that_fit), widest_allowed))
        rows = ceil(count, columns)

        # Columns are as wide as the longest title needs, between one and two thumbnail widths
        wanted_w = max(item.natural_width() for item in self._items) + (2 * self._padding)
        col_w = min(max(wanted_w, self._width), 2 * self._width)
        col_w = max(self.MIN_WIDTH, min(col_w, available_w // columns))

        total_h = rows * row_h
        popup_w = self._place(col_w * columns, total_h)
        col_w = popup_w // columns

        for index, item in enumerate(self._items):
            column, row = divmod(index, rows)
            # The last column takes the width left over, so every row reaches the popup edge
            left = column * col_w
            right = popup_w if column == columns - 1 else left + col_w
            top = row * row_h
            header_w = right - left - (2 * self._padding)
            item.setGeometry(left, top, right - left, row_h)
            item.header.setGeometry(self._padding, self._padding, header_w, header_h)
            item.update_elided_title(header_w)
            item.round_outer_corners(
                self._corner_radius(), left == 0, right == popup_w, top == 0, top + row_h == total_h
            )

    def _source_size(self, item: PreviewItem):
        """Get source window dimensions, preferably from DWM thumbnail source size."""
        # Try to get dimensions from DWM first (more accurate)
        if item.thumb and item.thumb.value:
            try:
                sz = SIZE(0, 0)
                if DwmQueryThumbnailSourceSize(item.thumb, byref(sz)) == 0 and sz.cx > 0 and sz.cy > 0:
                    # DWM reports physical pixels. Convert to logical pixels using devicePixelRatio
                    dpr = self.get_dpr()
                    if dpr > 0:
                        return max(1, int(sz.cx / dpr)), max(1, int(sz.cy / dpr))
                    return sz.cx, sz.cy
            except Exception:
                logger.debug("DwmQueryThumbnailSourceSize failed", exc_info=True)

        # Fallback to window rect
        try:
            l, t, r, b = win32gui.GetWindowRect(item.hwnd)
            return max(1, r - l), max(1, b - t)
        except Exception:
            logger.debug("GetWindowRect failed for hwnd %s", item.hwnd, exc_info=True)

        # Default fallback
        return 800, 600

    def close_window(self, hwnd: int):
        """Close one previewed window, keeping the popup open for the remaining ones."""
        try:
            if win32gui.IsWindow(hwnd):
                close_application(hwnd)
            if not self._thumbnail_manager:
                return
            remaining = [item.hwnd for item in self._items if item.hwnd != hwnd]
            if remaining and getattr(self, "_anchor_widget", None):
                manager, anchor = self._thumbnail_manager, self._anchor_widget
                QTimer.singleShot(0, lambda: manager.show_preview_for_hwnds(remaining, anchor))
            else:
                self._thumbnail_manager.hide_preview()
        except Exception:
            logger.exception("Failed to close window")

    def activate_window(self, hwnd: int):
        """Bring one previewed window to the foreground using the taskbar's method."""
        try:
            if win32gui.IsWindow(hwnd) and self._thumbnail_manager:
                self._thumbnail_manager._taskbar.bring_to_foreground(hwnd)
                self._thumbnail_manager.hide_preview()
        except Exception:
            logger.exception("Failed to bring window to foreground")

    def mousePressEvent(self, event):
        """Handle click on the popup background - activate the window it was opened from."""
        if hasattr(self, "_src_hwnd"):
            self.activate_window(self._src_hwnd)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self._cancel_hide()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._schedule_hide()
        super().leaveEvent(event)

    def _cancel_hide(self):
        """The pointer is on the preview, or on a thumbnail hosted over it."""
        try:
            self._hide_timer.stop()
        except RuntimeError:
            # The timer went with the widget, which is being destroyed
            pass

    def _schedule_hide(self):
        """The pointer left. Hide unless it comes back, or is only crossing to the button."""
        try:
            self._hide_timer.start()
        except RuntimeError:
            pass

    def global_area(self) -> QRect:
        """The popup's rectangle in screen coordinates."""
        return QRect(self.mapToGlobal(QPoint(0, 0)), self.size())

    def keeps_hover(self, cursor_pos: QPoint) -> bool:
        """True while the pointer is over the preview or still crossing the gap to its button."""
        try:
            area = self.global_area()
            if area.contains(cursor_pos):
                return True
            anchor = getattr(self, "_anchor_widget", None)
            if anchor is None:
                return False
            anchor_rect = QRect(anchor.mapToGlobal(QPoint(0, 0)), anchor.size())
            if anchor_rect.contains(cursor_pos):
                return True
            # The gap between the bar and the preview, never the bar row itself, so crossing the
            # gap keeps the preview open while moving along the bar lets it close
            span = area.united(anchor_rect)
            top = min(area.bottom(), anchor_rect.bottom()) + 1
            bottom = max(area.top(), anchor_rect.top()) - 1
            return QRect(span.left(), top, span.width(), bottom - top + 1).contains(cursor_pos)
        except RuntimeError:
            # The button went away with its window, nothing left to keep the preview open for
            return False

    def _do_hide(self):
        """Hide preview."""
        if not self.isVisible():
            return
        if self.keeps_hover(QCursor.pos()):
            self._hide_timer.start()
            return
        if self._thumbnail_manager:
            self._thumbnail_manager.hide_preview()

    def start_animation(self):
        """Fade the popup in, unless it is already fading or was never placed.

        PreviewAnimation falls back to a plain show of its own if the animation cannot run.
        """
        if self._fade_anim.running or not hasattr(self, "_final_pos"):
            return
        self._fade_anim.start()


class TaskbarThumbnailManager:
    """Encapsulates preview popup & DWM thumbnail host logic for TaskbarWidget."""

    # How long the pointer rests on a window before the desktop is faded for it
    PEEK_DELAY = 400

    def __init__(self, taskbar_widget, width: int, padding: int, margin: int, blur: bool = False, peek: bool = False):
        self._taskbar = taskbar_widget
        self.width = width
        self.padding = padding
        self.margin = margin
        self.blur = blur
        self.peek = peek and is_live_preview_available()
        if self.peek:
            activate_live_preview(False)
        self._peeking = 0
        self._peek_pending = 0
        self._peek_on = QTimer(taskbar_widget)
        self._peek_on.setSingleShot(True)
        self._peek_on.setInterval(self.PEEK_DELAY)
        self._peek_on.timeout.connect(self._take_peek)
        # Restoring the desktop is deferred, so moving between thumbnails does not bounce it back
        self._peek_off = QTimer(taskbar_widget)
        self._peek_off.setSingleShot(True)
        self._peek_off.setInterval(60)
        self._peek_off.timeout.connect(lambda: self._apply_peek(0))
        self.animation_duration = 200
        self._preview_popup = None
        self._thumb_hosts = []
        self._host_fade_anims = []

    def stop(self):
        self._release_thumbnails()
        try:
            if self._preview_popup:
                self._preview_popup.close()
                self._preview_popup.deleteLater()
        except Exception:
            pass
        self._preview_popup = None

    def set_peek(self, hwnd: int, hovered: bool = True):
        """Peek at one window, or release the desktop once no thumbnail has taken over."""
        if not self.peek:
            return
        if not hovered:
            if hwnd in (self._peeking, self._peek_pending):
                self._peek_on.stop()
                self._peek_pending = 0
                if hwnd == self._peeking:
                    self._peek_off.start()
        elif self._peeking:
            # The desktop is already faded, so moving to another window switches at once
            self._peek_off.stop()
            self._apply_peek(hwnd)
        elif self._peek_pending != hwnd or not self._peek_on.isActive():
            # An item reports the pointer more than once on arrival, so the wait is timed from the
            # first of those rather than restarted by each
            self._peek_off.stop()
            self._peek_pending = hwnd
            self._peek_on.start()

    def _take_peek(self):
        """Fade the desktop for the window the pointer settled on, if it is still on the preview."""
        hwnd, self._peek_pending = self._peek_pending, 0
        if self._pointer_on_preview():
            self._apply_peek(hwnd)

    def _pointer_on_preview(self) -> bool:
        popup = self._preview_popup
        return popup is not None and popup.isVisible() and popup.global_area().contains(QCursor.pos())

    def _apply_peek(self, hwnd: int):
        """Fade every other window on the desktop to show this one, or restore them when hwnd is 0."""
        if hwnd == self._peeking:
            return
        bar = self._taskbar.window() if self._taskbar else None
        activate_live_preview(bool(hwnd), hwnd, int(bar.winId()) if bar else 0)
        self._peeking = hwnd

    def _keep_out_of_peek(self):
        """Mark our own windows so peek never fades them, once per preview rather than per hover."""
        if not self.peek:
            return
        bar = self._taskbar.window() if self._taskbar else None
        for widget in (bar, self._preview_popup, *self._thumb_hosts):
            if widget is not None:
                exclude_from_peek(widget.winId())

    def _release_thumbnails(self):
        """Unregister every DWM thumbnail and destroy the windows hosting them."""
        # Every teardown path runs through here, so the desktop can never stay faded out
        self._peek_on.stop()
        self._peek_off.stop()
        self._peek_pending = 0
        self._apply_peek(0)
        for anim in self._host_fade_anims:
            try:
                anim.stop()
            except Exception:
                pass
        self._host_fade_anims = []
        for item in getattr(self._preview_popup, "_items", []):
            if item.thumb and item.thumb.value:
                try:
                    DwmUnregisterThumbnail(item.thumb)
                except Exception:
                    logger.exception("DwmUnregisterThumbnail failed for handle")
                item.thumb = wintypes.HANDLE(0)
        for host in self._thumb_hosts:
            try:
                host.hide()
                host.deleteLater()
            except Exception:
                pass
        self._thumb_hosts = []

    def show_preview_for_hwnds(self, hwnds: list[int], anchor_widget: QWidget):
        """Show a single popup holding a live thumbnail for each of the given windows."""
        try:
            # Ensure any previous preview is properly closed/deleted to avoid accumulating hidden widgets
            self._release_thumbnails()
            if self._preview_popup:
                try:
                    self._preview_popup.close()
                    self._preview_popup.deleteLater()
                except Exception:
                    pass
                self._preview_popup = None

            self._preview_popup = PreviewPopup(
                self._taskbar, self.width, self.padding, self.margin, self.animation_duration, self.blur, self.peek
            )
            self._preview_popup._thumbnail_manager = self

            entries = []
            buttons = getattr(self._taskbar, "_window_buttons", {})
            windows = getattr(getattr(self._taskbar, "_task_manager", None), "_windows", {})
            for hwnd in hwnds:
                data = buttons.get(hwnd)
                flashing = bool(getattr(windows.get(hwnd), "is_flashing", False))
                entries.append((hwnd, data[0], data[1], flashing) if data else (hwnd, None, None, flashing))

            # Check if any window is flashing using existing taskbar logic
            is_flashing = any("flashing" in self._taskbar._get_container_class(hwnd) for hwnd in hwnds)

            # Show popup with initial size calculation
            if not self._preview_popup.show_for(entries, anchor_widget):
                self._preview_popup.deleteLater()
                self._preview_popup = None
                return

            # Add flashing class to preview content if a window is flashing
            if is_flashing:
                try:
                    self._preview_popup._content.setProperty("class", "taskbar-preview flashing")
                    refresh_widget_style(self._preview_popup._content)
                except Exception:
                    pass

            if self._preview_popup._list_mode:
                # Nothing to register, the list is laid out and masking would only cut holes in it
                self._keep_out_of_peek()
            else:
                # Set up external thumbnails which recalculate the layout with accurate DWM data
                self._show_external_thumbnails(self._preview_popup)

            # Start animation after everything is positioned
            if self._preview_popup:
                self._preview_popup.start_animation()
                # Showing the popup puts it on top, lift the thumbnails back above it. Their holes
                # in the popup mask are not enough once a blur backdrop covers the whole window.
                for host in self._thumb_hosts:
                    host.raise_()
        except Exception:
            logger.exception("Failed to show preview for hwnds %s", hwnds)
            if self._preview_popup:
                self._preview_popup.close()
                self._preview_popup.deleteLater()
                self._preview_popup = None

    def hide_preview(self):
        try:
            self._release_thumbnails()
            if self._preview_popup:
                try:
                    if self._preview_popup.isVisible():
                        self._preview_popup.clearMask()
                except Exception:
                    pass
                try:
                    self._preview_popup.hide()
                    self._preview_popup.close()
                    self._preview_popup.deleteLater()
                except Exception:
                    pass
                self._preview_popup = None
        except Exception:
            logger.exception("Error while hiding preview")

    def _show_external_thumbnails(self, preview_popup: PreviewPopup):
        """Register a DWM thumbnail per item, then place one host window over each of them."""
        registered = []
        for item in preview_popup._items:
            host = ThumbnailHost(preview_popup, item)
            host.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Tool
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.NoDropShadowWindowHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            host.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            host.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)

            hthumb = wintypes.HANDLE(0)
            if DwmRegisterThumbnail(int(host.winId()), wintypes.HWND(item.hwnd), byref(hthumb)) != 0:
                # Window died between the layout pass and now, drop its slot
                host.deleteLater()
                item.deleteLater()
                continue
            item.thumb = hthumb
            registered.append(item)
            self._thumb_hosts.append(host)

        preview_popup._items = registered
        if not registered:
            self.hide_preview()
            return

        # Recalculate with accurate dimensions now that DWM can report the source sizes
        preview_popup._calculate_and_position_popup()
        base = preview_popup._final_pos
        dpr = preview_popup.get_dpr()
        holes = QRegion()

        for host, item in zip(self._thumb_hosts, registered):
            rect = item.thumb_rect
            host.setGeometry(base.x() + rect.x(), base.y() + rect.y(), rect.width(), rect.height())
            host.show()

            # Start host fade-in
            try:
                anim = PreviewAnimation(host, self.animation_duration)
                self._host_fade_anims.append(anim)
                anim.start()
            except Exception:
                pass

            # Configure DWM thumbnail properties
            props = DWM_THUMBNAIL_PROPERTIES()
            props.dwFlags = DWM_TNP_RECTDESTINATION | DWM_TNP_VISIBLE | DWM_TNP_OPACITY | DWM_TNP_SOURCECLIENTAREAONLY
            props.rcDestination = RECT(0, 0, max(1, int(rect.width() * dpr)), max(1, int(rect.height() * dpr)))
            props.rcSource = RECT(0, 0, 0, 0)
            props.opacity = 255
            props.fVisible = True
            props.fSourceClientAreaOnly = False
            try:
                DwmUpdateThumbnailProperties(item.thumb, byref(props))
            except Exception:
                logger.exception("DwmUpdateThumbnailProperties failed for handle %s", item.thumb)

            holes = holes.united(QRegion(rect))

        # Every host exists now, so peek can be told to leave our windows alone up front
        self._keep_out_of_peek()

        # Set up masking and final positioning
        try:
            preview_popup.raise_()
        except Exception:
            logger.exception("Could not raise the preview, thumbnails may sit behind it")
        try:
            full_region = QRegion(0, 0, preview_popup.width(), preview_popup.height())
            preview_popup.setMask(full_region.subtracted(holes))
        except Exception:
            logger.exception("Could not mask the preview, its background will cover the thumbnails")
