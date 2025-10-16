import logging
from ctypes import byref, wintypes

import win32gui
from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt
from PyQt6.QtGui import QFontMetrics, QPixmap, QRegion
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from core.utils.utilities import refresh_widget_style
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

logger = logging.getLogger(__name__)


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


class PreviewPopup(QFrame):
    """Window preview popup with thumbnail, title and icon."""

    ICON_SIZE = 16
    HEADER_SPACING = 6

    def __init__(self, parent=None, width: int = 240, padding: int = 8, margin: int = 8, animation_duration: int = 300):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._thumb = wintypes.HANDLE(0)
        self._width = width
        self._margin = margin
        self._padding = padding
        self._animation_duration = animation_duration

        # Main content frame
        self._content = QFrame(self)
        self._content.setProperty("class", "taskbar-preview")

        # Header with icon and title
        self._header = QFrame(self._content)
        self._header.setProperty("class", "header")
        self._header_layout = QHBoxLayout(self._header)
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(self.HEADER_SPACING)

        self._icon_label = QLabel(self._header)
        self._icon_label.setFixedSize(self.ICON_SIZE, self.ICON_SIZE)
        self._icon_label.setScaledContents(True)

        self._title_label = QLabel(self._header)
        self._title_label.setProperty("class", "title")

        self._header_layout.addWidget(self._icon_label)
        self._header_layout.addWidget(self._title_label, 1)

        self._fade_anim = PreviewAnimation(self, self._animation_duration)
        self._header_title_full = ""

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

    def _cleanup_thumb(self):
        if self._thumb and self._thumb.value:
            try:
                DwmUnregisterThumbnail(self._thumb)
            except Exception:
                logger.exception("DwmUnregisterThumbnail failed")
            self._thumb = wintypes.HANDLE(0)

    def hideEvent(self, event):
        try:
            self._fade_anim.stop()
        except Exception:
            pass
        self._cleanup_thumb()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._cleanup_thumb()
        super().closeEvent(event)

    def show_for(
        self,
        src_hwnd: int,
        anchor_widget: QWidget,
        title: str | None = None,
        icon: QPixmap | None = None,
    ):
        if not win32gui.IsWindow(src_hwnd):
            return None

        self._src_hwnd = src_hwnd
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

        self._header_title_full = title if title is not None else (win32gui.GetWindowText(src_hwnd) or "")
        self._title_label.setText(self._header_title_full)
        if isinstance(icon, QPixmap) and not icon.isNull():
            dpr = self.get_dpr()
            target = max(1, int(self.ICON_SIZE * dpr))
            phys_pix = icon.scaled(
                target,
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            phys_pix.setDevicePixelRatio(dpr)
            self._icon_label.setPixmap(phys_pix)
        else:
            self._icon_label.clear()

        anchor_center = anchor_widget.mapToGlobal(anchor_widget.rect().center())
        screen_geom = anchor_widget.screen().geometry()
        self._anchor_center_x = anchor_center.x()
        self._anchor_top = anchor_widget.mapToGlobal(anchor_widget.rect().topLeft()).y()
        self._anchor_bottom = anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft()).y()
        self._screen_geom = screen_geom

        # compute and apply final popup geometry, return global rect for thumbnail host
        thumb_global_rect = self._calculate_and_position_popup()
        return thumb_global_rect

    def _calculate_and_position_popup(self):
        """
        Calculate popup size and position based on thumbnail dimensions from DWM.
        Returns the global QRect where the thumbnail host should be placed.
        """
        # Get actual source window dimensions from DWM if possible
        src_w, src_h = self._get_source_dimensions()

        header_h = self._header.sizeHint().height()

        # Treat `self._width` as the desired thumbnail content width.
        available_w = self._width

        # Aspect ratio based max height (16:9 derived from width)
        max_h_aspect = int(self._width * (9 / 16))

        # Compute available popup vertical space near the anchor (above or below)
        space_above = max(0, self._anchor_top - self._screen_geom.top() - self._margin)
        space_below = max(0, self._screen_geom.bottom() - self._anchor_bottom - self._margin)
        max_popup_space = max(space_above, space_below)

        # Available height for thumbnail content is popup space minus header and vertical paddings
        max_h_screen = max(1, max_popup_space - header_h - (2 * self._padding))

        # Final max height is the tighter constraint
        max_h = min(max_h_aspect, max_h_screen)

        # guard against zero dimensions
        if src_w <= 0:
            src_w = 1
        if src_h <= 0:
            src_h = 1

        # compute scale and thumbnail size
        scale = min(available_w / src_w, max_h / src_h)
        thumb_w = max(1, int(src_w * scale))
        thumb_h = max(1, int(src_h * scale))

        # Total popup includes paddings around the thumbnail plus header height.
        total_w = thumb_w + (2 * self._padding)
        total_h = thumb_h + header_h + (2 * self._padding)

        # Enforce minimum popup width for the preview window.
        popup_w = max(total_w, 100)

        # Calculate position relative to anchor and screen
        x = self._anchor_center_x - popup_w // 2
        if self._anchor_top - total_h - self._margin >= self._screen_geom.top():
            y = self._anchor_top - total_h - self._margin
            self._above_anchor = True
        else:
            y = self._anchor_bottom + self._margin
            self._above_anchor = False

        x = max(self._screen_geom.left() + self._margin, min(self._screen_geom.right() - popup_w - self._margin, x))
        y = max(self._screen_geom.top() + self._margin, min(self._screen_geom.bottom() - total_h - self._margin, y))

        self._final_pos = QPoint(x, y)

        # Apply final geometry
        self.setGeometry(x, y, popup_w, total_h)
        self._content.setGeometry(0, 0, popup_w, total_h)
        self._header.setGeometry(self._padding, self._padding, popup_w - (2 * self._padding), header_h)
        self._update_header_elided_title()

        # Center thumbnail horizontally inside the popup. Vertically it is below the header.
        thumb_x_local = (popup_w - thumb_w) // 2
        thumb_y_local = self._padding + header_h
        self._thumb_local_rect = QRect(thumb_x_local, thumb_y_local, thumb_w, thumb_h)
        thumb_global_rect = QRect(x + thumb_x_local, y + thumb_y_local, thumb_w, thumb_h)

        return thumb_global_rect

    def _get_source_dimensions(self):
        """Get source window dimensions, preferably from DWM thumbnail source size."""
        # Try to get dimensions from DWM first (more accurate)
        if hasattr(self, "_thumb") and self._thumb and self._thumb.value:
            try:
                sz = SIZE(0, 0)
                if DwmQueryThumbnailSourceSize(self._thumb, byref(sz)) == 0 and sz.cx > 0 and sz.cy > 0:
                    # DWM reports physical pixels. Convert to logical pixels using devicePixelRatio
                    try:
                        dpr = self.get_dpr()
                        if dpr > 0:
                            return int(sz.cx / dpr), int(sz.cy / dpr)
                    except Exception:
                        pass
                    return sz.cx, sz.cy
            except Exception:
                logger.debug("DwmQueryThumbnailSourceSize failed", exc_info=True)

        # Fallback to window rect
        if hasattr(self, "_src_hwnd"):
            try:
                l, t, r, b = win32gui.GetWindowRect(self._src_hwnd)
                src_w = max(1, r - l)
                src_h = max(1, b - t)
                return src_w, src_h
            except Exception:
                logger.debug("GetWindowRect failed for hwnd %s", getattr(self, "_src_hwnd", None), exc_info=True)

        # Default fallback
        return 800, 600

    def _show_with_animation(self):
        try:
            self._fade_anim.start()
        except Exception:
            # fallback to immediate show
            try:
                self.setWindowOpacity(1.0)
                self.show()
            except Exception:
                pass

    def resizeEvent(self, event):
        self._update_header_elided_title()
        super().resizeEvent(event)

    def _update_header_elided_title(self):
        text = self._header_title_full or ""
        fm = QFontMetrics(self._title_label.font())
        inner_w = self.width() - (2 * self._padding)
        avail = inner_w - self._icon_label.width() - self.HEADER_SPACING
        if avail <= 0:
            self._title_label.setText("")
        else:
            self._title_label.setText(fm.elidedText(text, Qt.TextElideMode.ElideRight, avail))

    def start_animation(self):
        try:
            # If an opacity animation already exists and is running, don't restart
            if getattr(self, "_fade_anim", None) and self._fade_anim.running:
                return
            if not hasattr(self, "_final_pos"):
                return
            self._show_with_animation()
        except Exception:
            pass


class TaskbarThumbnailManager:
    """Encapsulates preview popup & DWM thumbnail host logic for TaskbarWidget."""

    def __init__(self, taskbar_widget, width: int, delay: int, padding: int, margin: int, animation: bool):
        self._taskbar = taskbar_widget
        self.width = width
        self.delay = delay
        self.padding = padding
        self.margin = margin
        self.animation_duration = 200 if animation else 0
        self._preview_popup = None
        self._thumb_host = None
        self._thumb_handle = wintypes.HANDLE(0)
        self._host_fade_anim = None

    def stop(self):
        try:
            if self._preview_popup:
                self._preview_popup.close()
                self._preview_popup.deleteLater()
        except Exception:
            pass
        self._preview_popup = None
        self._unregister_thumbnail()
        try:
            if self._thumb_host:
                try:
                    # stop any host animation
                    if self._host_fade_anim:
                        self._host_fade_anim.stop()
                except Exception:
                    pass
                self._thumb_host.close()
                self._thumb_host.deleteLater()
        except Exception:
            pass
        self._thumb_host = None

    def _ensure_thumb_host(self):
        if self._thumb_host is None:
            host = QWidget(None)
            host.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Tool
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.NoDropShadowWindowHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            host.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            host.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            host.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
            self._thumb_host = host
            try:
                self._host_fade_anim = PreviewAnimation(host, self.animation_duration)
            except Exception:
                self._host_fade_anim = None
        return self._thumb_host

    def _unregister_thumbnail(self):
        if self._thumb_handle and getattr(self._thumb_handle, "value", 0):
            try:
                DwmUnregisterThumbnail(self._thumb_handle)
            except Exception:
                logger.exception("DwmUnregisterThumbnail failed for handle")
            self._thumb_handle = wintypes.HANDLE(0)
            # Clear any reference held by the preview popup to avoid lingering handles
            try:
                if getattr(self, "_preview_popup", None) and getattr(self._preview_popup, "_thumb", None):
                    self._preview_popup._thumb = wintypes.HANDLE(0)
            except Exception:
                pass

    def show_preview_for_hwnd(self, hwnd: int, anchor_widget: QWidget):
        try:
            # Ensure any previous preview is properly closed/deleted to avoid accumulating hidden widgets
            if self._preview_popup:
                try:
                    self._preview_popup.close()
                    self._preview_popup.deleteLater()
                except Exception:
                    pass
                self._preview_popup = None
            if self._thumb_host:
                try:
                    if self._host_fade_anim:
                        self._host_fade_anim.stop()
                except Exception:
                    pass
                try:
                    self._thumb_host.hide()
                    self._thumb_host.deleteLater()
                except Exception:
                    pass
                self._thumb_host = None

            self._preview_popup = PreviewPopup(
                self._taskbar, self.width, self.padding, self.margin, self.animation_duration
            )
            title = icon = None
            data = getattr(self._taskbar, "_window_buttons", {}).get(hwnd)
            if data:
                title, icon = data[0], data[1]

            # Check if window is flashing using existing taskbar logic
            is_flashing = "flashing" in self._taskbar._get_container_class(hwnd)

            # Show popup with initial size calculation
            self._preview_popup.show_for(hwnd, anchor_widget, title=title, icon=icon)

            # Add flashing class to preview content if window is flashing
            if is_flashing and hasattr(self._preview_popup, "_content"):
                try:
                    self._preview_popup._content.setProperty("class", "taskbar-preview flashing")
                    refresh_widget_style(self._preview_popup._content)
                except Exception:
                    pass

            # Set up external thumbnail which may recalculate size with accurate DWM data
            self._show_external_thumbnail(hwnd, self._preview_popup)

            # Start animation after everything is positioned
            self._preview_popup.start_animation()
        except Exception:
            logger.exception("Failed to show preview for hwnd %s", hwnd)
            if self._preview_popup:
                self._preview_popup.close()

    def hide_preview(self):
        try:
            if self._preview_popup:
                try:
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
                except Exception:
                    pass
                self._preview_popup = None
            self._unregister_thumbnail()
            if self._thumb_host:
                try:
                    # stop host fade animation if running
                    if self._host_fade_anim:
                        self._host_fade_anim.stop()
                except Exception:
                    pass
                try:
                    self._thumb_host.hide()
                except Exception:
                    pass
        except Exception:
            logger.exception("Error while hiding preview")

    def _show_external_thumbnail(self, src_hwnd: int, preview_popup: PreviewPopup):  # type: ignore[name-defined]
        if not win32gui.IsWindow(src_hwnd):
            return
        host = self._ensure_thumb_host()
        self._unregister_thumbnail()
        hthumb = wintypes.HANDLE(0)
        if DwmRegisterThumbnail(int(host.winId()), wintypes.HWND(src_hwnd), byref(hthumb)) != 0:
            return
        self._thumb_handle = hthumb

        # Store the thumbnail handle in the preview popup for size calculation
        preview_popup._thumb = hthumb

        # Recalculate with accurate dimensions
        thumb_global_rect = preview_popup._calculate_and_position_popup()
        if thumb_global_rect:
            # Update thumbnail rectangle from recalculated position
            thumb_w = preview_popup._thumb_local_rect.width()
            thumb_h = preview_popup._thumb_local_rect.height()
            # Position the host widget using the thumbnail's local offsets
            thumb_x_local = preview_popup._thumb_local_rect.x()
            thumb_y_local = preview_popup._thumb_local_rect.y()
            if hasattr(preview_popup, "_final_pos"):
                base_left = preview_popup._final_pos.x()
                base_top = preview_popup._final_pos.y()
            else:
                geo = preview_popup.geometry()
                base_left, base_top = geo.left(), geo.top()

            global_left = base_left + thumb_x_local
            global_top = base_top + thumb_y_local
            host.setGeometry(global_left, global_top, thumb_w, thumb_h)

        host.show()

        # Start host fade-in if available
        try:
            if self._host_fade_anim:
                self._host_fade_anim.start()
        except Exception:
            pass

        dpr = preview_popup.get_dpr()
        phys_w = max(1, int(thumb_w * dpr))
        phys_h = max(1, int(thumb_h * dpr))

        # Configure DWM thumbnail properties
        props = DWM_THUMBNAIL_PROPERTIES()
        props.dwFlags = DWM_TNP_RECTDESTINATION | DWM_TNP_VISIBLE | DWM_TNP_OPACITY | DWM_TNP_SOURCECLIENTAREAONLY
        props.rcDestination = RECT(0, 0, phys_w, phys_h)
        props.rcSource = RECT(0, 0, 0, 0)
        props.opacity = 255
        props.fVisible = True
        props.fSourceClientAreaOnly = False
        try:
            DwmUpdateThumbnailProperties(self._thumb_handle, byref(props))
        except Exception:
            logger.exception("DwmUpdateThumbnailProperties failed for handle %s", self._thumb_handle)

        # Set up masking and final positioning
        try:
            preview_popup.raise_()
        except Exception:
            pass
        try:
            full_region = QRegion(0, 0, preview_popup.width(), preview_popup.height())
            # use the thumbnail local offsets for hole region
            hole_region = QRegion(
                preview_popup._thumb_local_rect.x(), preview_popup._thumb_local_rect.y(), thumb_w, thumb_h
            )
            preview_popup.setMask(full_region.subtracted(hole_region))
        except Exception:
            pass
