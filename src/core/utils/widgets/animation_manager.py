import logging

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QGraphicsOpacityEffect


class AnimationManager:
    _instances = {}
    ALLOWED_ANIMATIONS = ["fadeInOut"]

    @classmethod
    def animate(cls, widget, animation_type: str, duration: int = 200):
        if animation_type not in cls.ALLOWED_ANIMATIONS:
            logging.error(f"Animation type '{animation_type}' not supported. Allowed types: {cls.ALLOWED_ANIMATIONS}")
            return
        key = f"{animation_type}_{duration}"
        if key not in cls._instances:
            cls._instances[key] = cls(animation_type, duration)
        cls._instances[key]._animate(widget)

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
        if hasattr(widget, "_opacity_effect") and widget._opacity_effect is not None:
            widget._opacity_effect.setOpacity(1.0)
            if hasattr(widget, "_animation_timer") and widget._animation_timer.isActive():
                widget._animation_timer.stop()

        widget._opacity_effect = QGraphicsOpacityEffect()
        widget._opacity_effect.setEnabled(True)
        widget.setGraphicsEffect(widget._opacity_effect)
        widget._opacity_effect.setOpacity(0.5)

        widget._animation_timer = QTimer()
        step = 0
        steps = 20
        increment = 0.5 / steps

        def animate():
            nonlocal step
            new_opacity = widget._opacity_effect.opacity() + increment
            if new_opacity >= 1.0:
                new_opacity = 1.0
                widget._opacity_effect.setOpacity(new_opacity)
                widget._animation_timer.stop()
                widget._opacity_effect.setEnabled(False)
                widget._opacity_effect = None
                return
            widget._opacity_effect.setOpacity(new_opacity)
            step += 1

        widget._animation_timer.timeout.connect(animate)
        widget._animation_timer.start(self.duration // steps)
