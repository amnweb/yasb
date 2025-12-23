import logging

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QWidget


class AnimationManager:
    _instances = {}
    _repeating_animations = {}  # Track widgets with repeating animations
    ALLOWED_ANIMATIONS = ["fadeInOut"]

    @classmethod
    def animate(cls, widget: QWidget, animation_type: str, duration: int = 200):
        """Execute a single animation on a widget.

        Args:
            widget: The widget to animate
            animation_type: Type of animation ('fadeInOut',  etc.)
            duration: Duration of the animation in milliseconds
        """
        if animation_type not in cls.ALLOWED_ANIMATIONS:
            logging.error(f"Animation type '{animation_type}' not supported. Allowed types: {cls.ALLOWED_ANIMATIONS}")
            return
        key = f"{animation_type}_{duration}"
        if key not in cls._instances:
            cls._instances[key] = cls(animation_type, duration)
        cls._instances[key]._animate(widget)

    @classmethod
    def start_animation(
        cls,
        widget,
        animation_type: str,
        animation_duration: int = 800,
        repeat_interval: int = 2000,
        timeout: int = 5000,
    ):
        """Start a repeating animation on a widget.

        Args:
            widget: The widget to animate
            animation_type: Type of animation ('fadeInOut', etc.)
            animation_duration: Duration of each animation cycle in ms (default 800ms)
            repeat_interval: Time between animation cycles in ms (default 2000ms = 2s)
            timeout: Auto-stop after this many ms (default 5000ms = 5s), 0 = no timeout
        """
        if animation_type not in cls.ALLOWED_ANIMATIONS:
            logging.error(f"Animation type '{animation_type}' not supported. Allowed types: {cls.ALLOWED_ANIMATIONS}")
            return

        # Stop any existing animation for this widget
        cls.stop_animation(widget)

        # Create repeating timer for the animation
        repeat_timer = QTimer()
        repeat_timer.setInterval(repeat_interval)
        repeat_timer.timeout.connect(lambda: cls.animate(widget, animation_type, animation_duration))
        repeat_timer.start()

        # Trigger first animation immediately
        cls.animate(widget, animation_type, animation_duration)

        # Create timeout timer if specified
        timeout_timer = None
        if timeout > 0:
            timeout_timer = QTimer()
            timeout_timer.setSingleShot(True)
            timeout_timer.timeout.connect(lambda: cls.stop_animation(widget))
            timeout_timer.start(timeout)

        # Store timers
        cls._repeating_animations[id(widget)] = (repeat_timer, timeout_timer, animation_type)

    @classmethod
    def stop_animation(cls, widget):
        """Stop any repeating animation on a widget.

        Args:
            widget: The widget to stop animating
        """
        widget_id = id(widget)
        if widget_id in cls._repeating_animations:
            timers = cls._repeating_animations.pop(widget_id)
            if timers:
                repeat_timer, timeout_timer, _ = timers
                if repeat_timer:
                    repeat_timer.stop()
                    repeat_timer.deleteLater()
                if timeout_timer:
                    timeout_timer.stop()
                    timeout_timer.deleteLater()

            # Clean up any graphics effect
            try:
                widget.setGraphicsEffect(None)
            except Exception:
                pass

    def __init__(self, animation_type: str, duration: int = 200):
        self.animation_type = animation_type
        self.duration = duration
        self._opacity_effect = None
        self._animation_timer = None

    def _animate(self, widget):
        animation_method = getattr(self, self.animation_type, None)
        if animation_method:
            animation_method(widget)

    def fadeInOut(self, widget):
        effect = QGraphicsOpacityEffect(widget)
        effect.setEnabled(True)
        effect.setOpacity(0.6)
        widget.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(self.duration)
        anim.setStartValue(0.6)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def on_finished():
            try:
                effect.setEnabled(False)
            except Exception:
                pass
            try:
                widget.setGraphicsEffect(None)
            except Exception:
                pass
            try:
                widget._yasb_animation = None
            except Exception:
                pass

        anim.finished.connect(on_finished)

        # Keep reference to prevent garbage collection if not cleared
        widget._yasb_animation = anim
        anim.start()
