from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QMenu, QWidget

from core.utils.widgets.quick_launch.base_provider import (
    BaseProvider,
    ProviderMenuActionResult,
    ProviderResult,
)
from core.utils.win32.utilities import apply_qmenu_style


class QuickLaunchContextMenuService:
    """Build and execute provider-driven context menus for Quick Launch results."""

    @staticmethod
    def show(
        parent: QWidget,
        provider: BaseProvider,
        result: ProviderResult,
        global_pos: QPoint,
    ) -> ProviderMenuActionResult:
        actions = provider.get_context_menu_actions(result)
        if not actions:
            return ProviderMenuActionResult()

        menu = QMenu(parent)
        menu.setProperty("class", "context-menu")
        apply_qmenu_style(menu)
        menu.setContentsMargins(0, 0, 0, 0)

        action_map = {}
        for item in actions:
            if item.separator_before:
                menu.addSeparator()
            action = menu.addAction(item.label)
            if not action:
                continue
            action.setEnabled(item.enabled)
            action_map[action] = item.id

        selected = menu.exec(global_pos)
        if not selected:
            return ProviderMenuActionResult()

        action_id = action_map.get(selected)
        if not action_id:
            return ProviderMenuActionResult()

        return provider.execute_context_menu_action(action_id, result)
