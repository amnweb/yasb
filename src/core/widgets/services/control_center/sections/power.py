import logging
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QVBoxLayout, QWidget

from core.bar_helper import GlobalState
from core.utils.qobject import is_valid_qobject
from core.utils.system import is_windows_10
from core.utils.utilities import ElidedLabel, refresh_widget_style
from core.utils.win32.utils import apply_qmenu_style
from core.widgets.services.power_mode import power_mode_api
from core.widgets.services.power_plan.power_plan_api import PowerPlanService


class PowerPlanButton(QFrame):
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._pressed = False

    def mousePressEvent(self, a0: QMouseEvent | None):
        if a0 and a0.button() == Qt.MouseButton.LeftButton:
            a0.accept()
            self._pressed = True

    def mouseReleaseEvent(self, a0: QMouseEvent | None):
        if a0 and a0.button() == Qt.MouseButton.LeftButton:
            a0.accept()
            if self._pressed and self.rect().contains(a0.position().toPoint()):
                self.clicked.emit()
            self._pressed = False


class PowerSectionWidget(QFrame):
    """Section containing power plan and power mode controls."""

    def __init__(self, parent: QWidget, config: object):
        super().__init__(parent)
        self.config = config
        self.setProperty("class", "section power")

        self._plans = []
        self._power_plan_active_guid = None
        self._menus: dict[str, QMenu] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._action_button = PowerPlanButton(self)
        self._action_button.setProperty("class", "button plan-name")
        self._action_button.clicked.connect(self._show_power_plan_menu)

        self._plan_label = ElidedLabel("Unknown")
        self._setup_button_layout(
            self._action_button,
            config.power_plan_title,
            self._plan_label,
            config.button_menu_icon,
        )

        self._mode_button: PowerPlanButton | None = None
        self._mode_label: ElidedLabel | None = None
        self._mode_enabled: bool = False

        self._update_plans_state()

        # Set up a 2-column Grid Layout
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        if not is_windows_10():
            # each takes 1 column (50% width)
            grid.addWidget(self._action_button, 0, 0)
            self._build_mode_grid(grid)
        else:
            # spans both columns (100% width)
            grid.addWidget(self._action_button, 0, 0, 1, 2)

        layout.addLayout(grid)

        self.destroyed.connect(self._close_dropdown_menus)

    def _close_dropdown_menus(self) -> None:
        for menu in list(self._menus.values()):
            if is_valid_qobject(menu):
                menu.close()
        self._menus.clear()

    def _setup_button_layout(self, button: QWidget, title: str, label: QLabel, icon: str) -> None:
        btn_layout = QHBoxLayout(button)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(0)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        title_lbl = QLabel(title, button)
        title_lbl.setProperty("class", "title")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        text_layout.addWidget(title_lbl)

        label.setProperty("class", "subtext")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        text_layout.addWidget(label)

        icon_lbl = QLabel(icon, button)
        icon_lbl.setProperty("class", "icon")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        btn_layout.addLayout(text_layout, stretch=1)
        btn_layout.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def _show_menu(
        self,
        key: str,
        button: QWidget,
        items: list[tuple[str, Any]],
        on_select: Callable[[Any, str], None],
    ) -> None:
        other_key = "mode" if key == "plan" else "plan"
        if other_key in self._menus:
            menu = self._menus[other_key]
            if is_valid_qobject(menu):
                menu.close()
            self._menus.pop(other_key, None)

        if key in self._menus:
            menu = self._menus[key]
            if is_valid_qobject(menu) and menu.isVisible():
                menu.close()
                self._menus.pop(key, None)
                return
            self._menus.pop(key, None)

        menu = QMenu(self.window())
        apply_qmenu_style(menu)
        menu.setProperty("class", "context-menu dark" if GlobalState.is_dark() else "context-menu")
        menu.setMinimumWidth(button.width())

        for label, val in items:
            action = menu.addAction(label)
            action.triggered.connect(lambda checked=False, v=val, l=label: on_select(v, l))

        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._menus[key] = menu

        pos = button.mapToGlobal(QPoint(0, button.height() + 6))
        button.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
        button.update()
        menu.popup(pos)

    def _show_power_plan_menu(self) -> None:
        items = [(plan.name, plan.guid) for plan in self._plans]
        self._show_menu("plan", self._action_button, items, self._apply_power_plan)

    def _show_power_mode_menu(self) -> None:
        if self._mode_enabled and self._mode_button:
            items = power_mode_api.get_modes()
            self._show_menu("mode", self._mode_button, items, self._apply_power_mode)

    def _update_plans_state(self) -> None:
        svc = PowerPlanService.instance()
        try:
            self._plans, active_guid = svc.get_power_plans()
            self._power_plan_active_guid = active_guid
        except Exception as exc:
            logging.error("Failed to fetch power plans: %s", exc)
            self._plans, active_guid = [], None

        active_name = next(
            (p.name for p in self._plans if active_guid and svc.guids_equal(p.guid, active_guid)),
            "Unknown",
        )
        if self._plan_label and is_valid_qobject(self._plan_label):
            self._plan_label.setText(active_name)

    def refresh_state(self) -> None:
        self._close_dropdown_menus()
        self._update_plans_state()
        if not is_windows_10():
            self._refresh_mode_state()

    def _apply_power_plan(self, guid, name: str) -> None:
        svc = PowerPlanService.instance()
        if self._power_plan_active_guid and svc.guids_equal(guid, self._power_plan_active_guid):
            return
        if self._plan_label and is_valid_qobject(self._plan_label):
            self._plan_label.setText(name)
        try:
            result = svc.set_power_plan(guid)
            if result == 0:
                self._power_plan_active_guid = guid
                if not is_windows_10():
                    self._mode_enabled = power_mode_api.is_mode_supported()
                    self._apply_mode_button_state()
            else:
                logging.error("Failed to activate power plan, error code: %d", result)
                self.refresh_state()
        except Exception as exc:
            logging.error("Error activating power plan: %s", exc)
            self.refresh_state()

    def _build_mode_grid(self, grid: QGridLayout) -> None:
        mode = power_mode_api.get_active_mode()
        self._mode_enabled = power_mode_api.is_mode_supported() if self._power_plan_active_guid else False

        self._mode_button = PowerPlanButton(self)
        self._mode_button.setProperty("class", "button mode-name")
        self._mode_button.clicked.connect(self._show_power_mode_menu)

        self._mode_label = ElidedLabel(mode[0] if mode else "Unknown")
        self._setup_button_layout(
            self._mode_button,
            self.config.power_mode_title,
            self._mode_label,
            self.config.button_menu_icon,
        )

        grid.addWidget(self._mode_button, 0, 1)
        self._apply_mode_button_state()

    def _apply_mode_button_state(self) -> None:
        if self._mode_button and is_valid_qobject(self._mode_button):
            cls = "mode-name" if self._mode_enabled else "mode-name disabled"
            self._mode_button.setProperty("class", cls)
            refresh_widget_style(self._mode_button)

            if not self._mode_enabled:
                if self._mode_label and is_valid_qobject(self._mode_label):
                    self._mode_label.setText("Automatic")
            else:
                mode = power_mode_api.get_active_mode()
                if self._mode_label and is_valid_qobject(self._mode_label):
                    self._mode_label.setText(mode[0] if mode else "Unknown")

    def _refresh_mode_state(self) -> None:
        mode = power_mode_api.get_active_mode()
        if self._mode_label and is_valid_qobject(self._mode_label):
            self._mode_label.setText(mode[0] if mode else "Unknown")
        self._mode_enabled = power_mode_api.is_mode_supported()
        self._apply_mode_button_state()

    def _apply_power_mode(self, guid, name: str) -> None:
        if not power_mode_api.set_mode(guid):
            logging.error("Failed to set power mode to %s", name)
        if self._mode_label and is_valid_qobject(self._mode_label):
            self._mode_label.setText(name)
