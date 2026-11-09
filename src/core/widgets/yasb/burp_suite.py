import re
from typing import Any

from core.utils.tooltip import set_tooltip
from core.utils.utilities import refresh_widget_style
from core.validation.widgets.yasb.burp_suite import BurpSuiteConfig
from core.widgets.base import BaseWidget
from core.widgets.services.burp_suite.burp_client import (
    STATE_OFFLINE,
    BurpStatusWorker,
)


class BurpSuiteWidget(BaseWidget):
    validation_schema = BurpSuiteConfig

    def __init__(self, config: BurpSuiteConfig):
        super().__init__(class_name="burp-suite-widget")
        self.config = config
        self._show_alt_label = False
        self._worker: BurpStatusWorker | None = None
        self._data: dict[str, Any] = {"state": STATE_OFFLINE, "edition": "", "rest_ready": False}

        self._icons = config.icons.model_dump()
        self._status_text = config.status_text.model_dump()

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("refresh", self._refresh)

        self.callback_left = self.config.callbacks.on_left
        self.callback_middle = self.config.callbacks.on_middle
        self.callback_right = self.config.callbacks.on_right
        self.callback_timer = "refresh"

        self.timer.setInterval(self.config.update_interval * 1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

        self.destroyed.connect(lambda *_: self._stop_worker())
        self._tick()
        self._update_label()

    def _stop_worker(self) -> None:
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(2000)

    def _tick(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return  # a probe is already in flight
        worker = BurpStatusWorker(
            self.config.rest_api.enabled,
            self.config.rest_api.host,
            self.config.rest_api.port,
            self,
        )
        worker.status_ready.connect(self._on_status)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _on_worker_finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def _refresh(self) -> None:
        self._tick()

    def _on_status(self, data: dict[str, Any]) -> None:
        self._data = data
        self._update_label()

    def _format_values(self) -> dict[str, str]:
        state = str(self._data.get("state", STATE_OFFLINE))
        return {
            "icon": self._icons.get(state, ""),
            "status": self._status_text.get(state, ""),
            "edition": str(self._data.get("edition", "")),
        }

    def _toggle_label(self) -> None:
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _update_label(self) -> None:
        state = str(self._data.get("state", STATE_OFFLINE))

        if self.config.hide_when_offline:
            self._widget_frame.setVisible(state != STATE_OFFLINE)

        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_template = self.config.label_alt if self._show_alt_label else self.config.label
        values = self._format_values()
        # Drop whitespace-only parts so widget/template indices stay aligned with
        # build_widget_label (which discards them); otherwise multi-span labels misalign.
        label_parts = [part for part in re.split(r"(<span.*?>.*?</span>)", active_template) if part.strip()]

        for index, part in enumerate(label_parts):
            if index >= len(active_widgets):
                continue
            current_widget = active_widgets[index]
            is_icon = "<span" in part and "</span>" in part
            base_class = "icon" if is_icon else "label"
            current_widget.setProperty("class", f"{base_class} {state}")
            if is_icon:
                text = re.sub(r"<span.*?>|</span>", "", part).strip()
            else:
                text = part.strip()
            try:
                current_widget.setText(text.format(**values))
            except Exception:
                current_widget.setText(text)
            if self.config.tooltip:
                edition = values["edition"]
                summary = f"Burp Suite — {values['status']}"
                if edition:
                    summary += f" ({edition})"
                set_tooltip(current_widget, summary)
        refresh_widget_style(*active_widgets)
