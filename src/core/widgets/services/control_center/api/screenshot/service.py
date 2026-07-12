import logging

from core.widgets.services.control_center.api.screenshot.capture import capture_screens
from core.widgets.services.control_center.api.screenshot.overlay import Overlay


class ScreenshotService:
    _overlay: Overlay | None = None

    @classmethod
    def start(cls) -> None:
        if cls._overlay is not None:
            try:
                cls._overlay.close()
            except Exception:
                pass
            cls._overlay = None

        try:
            freezes = capture_screens()
            if not freezes:
                logging.error("Screenshot capture failed")
                return
            overlay = Overlay(freezes)
            cls._overlay = overlay

            def _clear(_obj=None, _ov=overlay):
                if cls._overlay is _ov:
                    cls._overlay = None

            overlay.destroyed.connect(_clear)
            overlay.show()
            overlay.activateWindow()
            overlay.raise_()
        except Exception:
            logging.exception("Screenshot failed to start")
            cls._overlay = None
