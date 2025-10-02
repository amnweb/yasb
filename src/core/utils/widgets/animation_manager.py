import logging

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation
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
        effect = QGraphicsOpacityEffect(widget)
        effect.setEnabled(True)
        effect.setOpacity(0.5)
        widget.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(self.duration)
        anim.setStartValue(0.5)
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

        anim.finished.connect(on_finished)

        widget._yasb_animation = anim
        anim.start()
