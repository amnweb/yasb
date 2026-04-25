import re
from collections import deque

from humanize import naturalsize
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from core.utils.stat_popup import GraphWidget, build_stat_popup
from core.utils.utilities import (
    PopupWidget,
    build_progress_widget,
    refresh_widget_style,
)
from core.validation.widgets.yasb.gpu import GpuConfig
from core.widgets.base import BaseWidget
from core.widgets.services.gpu.gpu_api import GpuData, GpuWorker


class GpuWidget(BaseWidget):
    validation_schema = GpuConfig

    # Class-level shared data and worker
    _instances: list[GpuWidget] = []
    _worker: GpuWorker | None = None

    def __init__(self, config: GpuConfig):
        super().__init__(class_name=f"gpu-widget {config.class_name}")
        self.config = config
        self._gpu_util_history = deque([0] * config.histogram_num_columns, maxlen=config.histogram_num_columns)
        self._gpu_mem_history = deque([0] * config.histogram_num_columns, maxlen=config.histogram_num_columns)
        self._show_alt_label = False
        self._last_gpu_data: GpuData | None = None
        self._history: deque = deque(maxlen=config.menu.graph_history_size)
        self._temp_history: deque = deque(maxlen=config.menu.graph_history_size)

        self.progress_widget = None
        self.progress_widget = build_progress_widget(self, self.config.progress_bar.model_dump())

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._show_popup)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

        # Add this instance to the shared instances list
        if self not in GpuWidget._instances:
            GpuWidget._instances.append(self)

        # Start the shared GPU worker thread
        if self.config.update_interval > 0:
            worker = GpuWorker.get_instance(self.config.update_interval)
            worker.add_index(self.config.gpu_index)
            if GpuWidget._worker is None:
                worker.data_ready.connect(GpuWidget._on_gpu_data)
                worker.start()
                GpuWidget._worker = worker

        self.hide()

    @classmethod
    def _on_gpu_data(cls, gpu_data_list: list[GpuData]):
        """Slot called on main thread when GPU worker emits data."""
        for inst in cls._instances[:]:
            try:
                gpu_data = next((g for g in gpu_data_list if g.index == inst.config.gpu_index), None)
                if gpu_data:
                    if inst.isHidden():
                        inst.show()
                    inst._update_label(gpu_data)
                    if inst.config.menu.enabled:
                        inst._history.append(gpu_data.utilization)
                        inst._temp_history.append(gpu_data.temp)
                        inst._update_popup(gpu_data)
                elif not inst.isHidden():
                    inst.hide()
            except RuntimeError:
                cls._instances.remove(inst)

    def _update_label(self, gpu_data: GpuData):
        """Update the label with GPU data."""
        self._last_gpu_data = gpu_data
        self._gpu_util_history.append(gpu_data.utilization)
        self._gpu_mem_history.append(gpu_data.mem_used)
        _temp = gpu_data.temp if self.config.units == "metric" else (gpu_data.temp * (9 / 5) + 32)
        _temp = round(_temp) if self.config.hide_decimal else _temp
        _fmt = "%.0f" if self.config.hide_decimal else "%.1f"
        _naturalsize = lambda value: naturalsize(value, True, True, _fmt)
        _round = round if self.config.hide_decimal else lambda v: round(v, 1)
        gpu_info = {
            "index": gpu_data.index,
            "name": gpu_data.name,
            "utilization": _round(gpu_data.utilization),
            "mem_total": _naturalsize(gpu_data.mem_total),
            "mem_used": _naturalsize(gpu_data.mem_used),
            "mem_free": _naturalsize(gpu_data.mem_free),
            "mem_shared": _naturalsize(gpu_data.mem_shared_used),
            "mem_shared_total": _naturalsize(gpu_data.mem_shared_total),
            "mem_shared_used": _naturalsize(gpu_data.mem_shared_used),
            "temp": _temp,
            "fan_speed": gpu_data.fan_speed,
            "power_draw": _round(gpu_data.power_draw),
            "histograms": {
                "utilization": "".join([self._get_histogram_bar(val, 0, 100) for val in self._gpu_util_history]),
                "mem_used": "".join(
                    [self._get_histogram_bar(val, 0, gpu_data.mem_total or 1) for val in self._gpu_mem_history]
                ),
            },
        }

        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self.config.label_alt if self._show_alt_label else self.config.label
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        if self.config.progress_bar.enabled and self.progress_widget:
            if self._widget_container_layout.indexOf(self.progress_widget) == -1:
                self._widget_container_layout.insertWidget(
                    0 if self.config.progress_bar.position == "left" else self._widget_container_layout.count(),
                    self.progress_widget,
                )
            self.progress_widget.set_value(gpu_data.utilization)

        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if "<span" in part and "</span>" in part:
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    label_class = "label alt" if self._show_alt_label else "label"
                    formatted_text = part.format(info=gpu_info)
                    active_widgets[widget_index].setText(formatted_text)
                    active_widgets[widget_index].setProperty("class", label_class)
                    active_widgets[widget_index].setProperty(
                        "class", f"{label_class} status-{self._get_gpu_threshold(gpu_data.utilization)}"
                    )
                    refresh_widget_style(active_widgets[widget_index])
                widget_index += 1

    def _get_gpu_threshold(self, utilization: float) -> str:
        if utilization <= self.config.gpu_thresholds.low:
            return "low"
        elif self.config.gpu_thresholds.low < utilization <= self.config.gpu_thresholds.medium:
            return "medium"
        elif self.config.gpu_thresholds.medium < utilization <= self.config.gpu_thresholds.high:
            return "high"
        elif self.config.gpu_thresholds.high < utilization:
            return "critical"

    def _get_histogram_bar(self, num: float, num_min: float, num_max: float) -> str:
        if num_max == num_min:
            return self.config.histogram_icons[0]
        bar_index = int((num - num_min) / (num_max - num_min) * (len(self.config.histogram_icons) - 1))
        bar_index = min(max(bar_index, 0), len(self.config.histogram_icons) - 1)
        return self.config.histogram_icons[bar_index]

    def _update_popup(self, gpu_data: GpuData):
        """Push fresh data into the open popup if visible."""
        popup = PopupWidget._open_popups.get(id(self))
        if popup is None or not popup.isVisible():
            return
        try:
            if popup._graph is not None:
                popup._graph.set_data(list(self._history))
            if popup._temp_graph is not None:
                popup._temp_graph.set_data(list(self._temp_history))
            format_size = popup._format_size
            labels = popup._stat_labels
            labels["usage"].setText(f"{gpu_data.utilization:.0f}%")
            labels["mem"].setText(f"{format_size(gpu_data.mem_used)} / {format_size(gpu_data.mem_total)}")
            if "temp" in labels:
                labels["temp"].setText(f"{gpu_data.temp}°C")
            if "power" in labels:
                labels["power"].setText(f"{gpu_data.power_draw:.1f} W")
            if "fan" in labels:
                labels["fan"].setText(f"{gpu_data.fan_speed}%")
            if "mem_shared" in labels:
                labels["mem_shared"].setText(
                    f"{format_size(gpu_data.mem_shared_used)} / {format_size(gpu_data.mem_shared_total)}"
                )
        except Exception:
            pass

    def _show_popup(self):
        """Build and show or toggle the GPU details popup."""
        if not self.config.menu.enabled:
            return
        menu = self.config.menu
        data = self._last_gpu_data
        format_size = lambda v: naturalsize(v, True, False, "%.1f").replace("i", "")

        has_temp = data and data.temp > 0
        has_power = data and data.power_draw > 0
        has_fan = data and (data.fan_speed > 0 or has_temp)
        has_shared = data and data.mem_shared_total > 0

        stat_rows = [
            (
                "Usage",
                "usage",
                f"{data.utilization:.0f}%" if data else "\u2014",
                "Memory",
                "mem",
                f"{format_size(data.mem_used)} / {format_size(data.mem_total)}" if data else "\u2014",
            ),
        ]

        if has_temp or has_power:
            stat_rows.append(
                (
                    "Temperature" if has_temp else None,
                    "temp",
                    f"{data.temp}°C" if has_temp else "",
                    "Power draw" if has_power else None,
                    "power",
                    f"{data.power_draw:.1f} W" if has_power else "",
                )
            )

        if has_fan or has_shared:
            stat_rows.append(
                (
                    "Fan speed" if has_fan else None,
                    "fan",
                    f"{data.fan_speed}%" if has_fan else "",
                    "Shared memory" if has_shared else None,
                    "mem_shared",
                    f"{format_size(data.mem_shared_used)} / {format_size(data.mem_shared_total)}" if has_shared else "",
                )
            )

        popup = build_stat_popup(
            parent=self,
            menu_config=menu,
            popup_class_name="gpu-popup",
            title="<b>GPU</b> Usage",
            history=self._history,
            stat_rows=stat_rows,
            graph_class="gpu-graph",
        )
        popup._format_size = format_size

        # Add title label above the utilization graph container
        if menu.show_graph and popup._graph is not None:
            main_layout = popup.layout()
            graph_container = popup._graph.parentWidget()
            graph_idx = main_layout.indexOf(graph_container)
            util_label = QLabel("Utilization")
            util_label.setProperty("class", "graph-title first")
            main_layout.insertWidget(graph_idx, util_label)

        # Add temperature graph if temp data is available
        has_temp = data and data.temp > 0
        if menu.show_graph and has_temp:
            main_layout = popup.layout()
            stats_index = main_layout.count() - 1

            temp_label = QLabel("Temperature")
            temp_label.setProperty("class", "graph-title")
            main_layout.insertWidget(stats_index, temp_label)
            stats_index += 1

            temp_graph_container = QFrame()
            temp_graph_container.setProperty("class", "graph-container")
            temp_layout = QVBoxLayout(temp_graph_container)
            temp_layout.setContentsMargins(0, 0, 0, 0)
            temp_layout.setSpacing(0)
            temp_graph = GraphWidget("gpu-temp-graph", show_grid=menu.show_graph_grid)
            temp_layout.addWidget(temp_graph)
            if self._temp_history:
                temp_graph.set_data(list(self._temp_history))
            main_layout.insertWidget(stats_index, temp_graph_container)

            popup._temp_graph = temp_graph
        else:
            popup._temp_graph = None

        popup.show()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        for inst in GpuWidget._instances[:]:
            try:
                inst._update_label(inst._last_gpu_data)
            except RuntimeError:
                GpuWidget._instances.remove(inst)
