from PyQt6.QtCore import QEasingCurve, QTimer, QVariantAnimation


class KomorebiAnimation:
    """Centralized, width-only animations for workspace buttons/frames."""

    DEFAULT_WIDTH_DURATION = 120
    DEFAULT_EASING = QEasingCurve.Type.Linear

    @staticmethod
    def lock_width(widget) -> None:
        try:
            widget.setFixedWidth(widget.width())
        except Exception:
            pass

    @staticmethod
    def animate_width(
        widget, duration: int | None = None, easing: QEasingCurve.Type | None = None, start_width: int | None = None
    ) -> None:
        if duration is None:
            duration = KomorebiAnimation.DEFAULT_WIDTH_DURATION
        if easing is None:
            easing = KomorebiAnimation.DEFAULT_EASING

        try:
            if start_width is None:
                start_width = widget.width()
            target_width = widget.sizeHint().width()
        except Exception:
            return

        # If widths are equal, set and release constraints
        try:
            if int(target_width) == int(start_width):
                widget.setFixedWidth(int(target_width))
                QTimer.singleShot(0, lambda: (widget.setMinimumWidth(0), widget.setMaximumWidth(16777215)))
                return
        except Exception:
            pass

        # Stop any previous animation and mark this one as active
        try:
            prev = getattr(widget, "_yasb_width_anim", None)
            if prev is not None:
                try:
                    setattr(widget, "_yasb_width_anim", None)
                except Exception:
                    pass
                try:
                    prev.stop()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            widget.setFixedWidth(start_width)
        except Exception:
            pass

        anim = QVariantAnimation(widget)
        try:
            setattr(widget, "_yasb_width_anim", anim)
        except Exception:
            pass

        anim.setStartValue(float(start_width))
        anim.setEndValue(float(target_width))
        anim.setDuration(duration)
        anim.setEasingCurve(easing)

        def _on_value(v):
            try:
                if getattr(widget, "_yasb_width_anim", None) is not anim:
                    return
                widget.setFixedWidth(int(round(float(v))))
            except Exception:
                pass

        def _on_finished():
            try:
                if getattr(widget, "_yasb_width_anim", None) is not anim:
                    return
                widget.setFixedWidth(int(target_width))
                QTimer.singleShot(0, lambda: (widget.setMinimumWidth(0), widget.setMaximumWidth(16777215)))
                try:
                    setattr(widget, "_yasb_width_anim", None)
                except Exception:
                    pass
            except Exception:
                pass

        anim.valueChanged.connect(_on_value)  # type: ignore[arg-type]
        anim.finished.connect(_on_finished)
        anim.start()

    @staticmethod
    def _animate_width_next_tick(
        widget, width_duration: int | None, easing: QEasingCurve.Type | None, start_width: int | None = None
    ) -> None:
        QTimer.singleShot(
            0, lambda: KomorebiAnimation.animate_width(widget, width_duration, easing, start_width=start_width)
        )

    @staticmethod
    def animate_state_transition(
        widget, new_status, width_duration: int | None = None, easing: QEasingCurve.Type | None = None
    ) -> None:
        if width_duration is None:
            width_duration = KomorebiAnimation.DEFAULT_WIDTH_DURATION
        if easing is None:
            easing = KomorebiAnimation.DEFAULT_EASING

        try:
            current_visual_width = widget.width()
        except Exception:
            current_visual_width = None

        widget.update_and_redraw(new_status, lock_width=True)
        KomorebiAnimation._animate_width_next_tick(widget, width_duration, easing, start_width=current_visual_width)
