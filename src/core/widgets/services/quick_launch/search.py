import base64
import logging
import math
import os
from typing import Any, override

from PyQt6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QPoint,
    Qt,
    QTimer,
    QUrl,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QGuiApplication, QWindow

from core.utils.icons.image_provider import icon_url
from core.utils.icons.service import IconService
from core.utils.qml import qml_property
from core.utils.win32.bindings.user32 import user32
from core.utils.win32.constants import WDA_EXCLUDEFROMCAPTURE
from core.utils.win32.window_actions import force_foreground_focus
from core.widgets.services.quick_launch.base_provider import BaseProvider, ProviderResult
from core.widgets.services.quick_launch.service import QuickLaunchService

ROLES = ["title", "description", "icon", "iconText", "separator", "loading", "provider", "path"]


def image_url(icon: str) -> str:
    """A file path or SVG text as an image URL; empty for a text icon such as an emoji."""
    if icon.lstrip().startswith("<svg"):
        return "data:image/svg+xml;base64," + base64.b64encode(icon.encode()).decode()
    if icon and os.path.isfile(icon):
        return QUrl.fromLocalFile(icon).toString()
    return ""


class ResultModel(QAbstractListModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._results: list[ProviderResult] = []
        # Bumped when IconService finishes loading icons, so QML asks for them again
        self._revision = 0

    @override
    def roleNames(self) -> dict[int, QByteArray]:
        return {Qt.ItemDataRole.UserRole + i: QByteArray(name.encode()) for i, name in enumerate(ROLES)}

    @override
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._results)

    @override
    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not 0 <= role - Qt.ItemDataRole.UserRole < len(ROLES):
            return None
        name = ROLES[role - Qt.ItemDataRole.UserRole]
        result = self.result(index.row())
        # QML turns a missing value into the text "undefined", which an Image then tries to open
        if result is None:
            return False if name in ("separator", "loading") else ""
        match name:
            case "title":
                return result.title
            case "description":
                return result.description
            case "icon":
                if result.icon_source is not None:
                    return icon_url(result.icon_source, self._revision)
                return image_url(result.icon_path) or image_url(result.icon_char)
            case "iconText":
                return "" if image_url(result.icon_char) else result.icon_char
            case "separator":
                return result.is_separator
            case "loading":
                return result.is_loading
            case "provider":
                return result.provider
            case _:
                return result.action_data.get("path", "")

    def result(self, row: int) -> ProviderResult | None:
        return self._results[row] if 0 <= row < len(self._results) else None

    def set_results(self, results: list[ProviderResult]) -> None:
        self.beginResetModel()
        self._results = list(results)
        self.endResetModel()

    def refresh_icons(self) -> None:
        self._revision += 1
        if self._results:
            role = Qt.ItemDataRole.UserRole + ROLES.index("icon")
            self.dataChanged.emit(self.index(0), self.index(len(self._results) - 1), [role])


class QuickLaunchSearch(QObject):
    """Searches the Quick Launch providers for QML and runs what the user picks."""

    settingsChanged = pyqtSignal()
    stateChanged = pyqtSignal()
    prefixesChanged = pyqtSignal()
    # The popup should close
    closeRequested = pyqtSignal()
    # A home page entry was picked: show this provider's prefix
    prefixRequested = pyqtSignal(str)
    # A result asked for this text in the search box, the prefix included
    queryRequested = pyqtSignal(str)
    # A result asked to pick a colour from the screen, for this provider prefix
    colorPickRequested = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._providers_config: dict[str, Any] = {}
        self._max_results = 50
        self._home_page = False
        self._results = ResultModel(self)
        self._query = ""
        self._pending: str | None = None
        self._prediction = ""
        self._service = QuickLaunchService.instance()
        self._service.query_finished.connect(self._receive)
        self._service.request_refresh.connect(self.refresh)
        IconService.instance().icons_changed.connect(self._results.refresh_icons)

        # QML sets the settings after creating the object, so the providers wait for them
        self._configure_timer = QTimer(self)
        self._configure_timer.setSingleShot(True)
        self._configure_timer.setInterval(0)
        self._configure_timer.timeout.connect(self._configure)
        self._configure_timer.start()

    def _get_providers(self) -> dict[str, Any]:
        return self._providers_config

    def _set_providers(self, value: dict[str, Any]) -> None:
        if value != self._providers_config:
            self._providers_config = value
            self.settingsChanged.emit()
            self._configure_timer.start()

    # Settings of each provider by name; QuickLaunch.qml lists every provider with its defaults
    providers = pyqtProperty("QVariantMap", _get_providers, _set_providers, notify=settingsChanged)

    def _get_max_results(self) -> int:
        return self._max_results

    def _set_max_results(self, value: int) -> None:
        value = max(1, min(value, 500))
        if value != self._max_results:
            self._max_results = value
            self.settingsChanged.emit()
            self._configure_timer.start()

    maxResults = pyqtProperty(int, _get_max_results, _set_max_results, notify=settingsChanged)

    def _get_home_page(self) -> bool:
        return self._home_page

    def _set_home_page(self, value: bool) -> None:
        if value != self._home_page:
            self._home_page = value
            self.settingsChanged.emit()

    # With nothing typed, list the providers that have a prefix
    homePage = pyqtProperty(bool, _get_home_page, _set_home_page, notify=settingsChanged)

    @qml_property(QObject, constant=True)
    def results(self) -> ResultModel:
        return self._results

    @qml_property(bool, notify=stateChanged)
    def loading(self) -> bool:
        return self._pending is not None

    # What the first app result would complete the query to
    @qml_property(str, notify=stateChanged)
    def prediction(self) -> str:
        return self._prediction

    @qml_property("QVariantList", notify=prefixesChanged)
    def prefixes(self) -> list[dict[str, str]]:
        return [
            {"prefix": p.prefix, "name": p.display_name or p.name, "placeholder": p.input_placeholder}
            for p in self._service.providers
            if p.prefix
        ]

    def _configure(self) -> None:
        self._service.configure_providers(dict(self._providers_config), self._max_results)
        self.prefixesChanged.emit()

    def _provider(self, result: ProviderResult) -> BaseProvider | None:
        return next((p for p in self._service.providers if p.name == result.provider), None)

    @pyqtSlot(str)
    def search(self, text: str) -> None:
        self._query = text
        self._prediction = ""
        if text.strip() or not self._home_page:
            self._pending = self._service.async_query(text, self._max_results)
        else:
            self._pending = None
            self._results.set_results(self._home_results())
        self.stateChanged.emit()

    @pyqtSlot()
    def refresh(self) -> None:
        if self._pending is not None or self._results.rowCount():
            self.search(self._query)

    def _home_results(self) -> list[ProviderResult]:
        return [
            ProviderResult(
                title=p.prefix,
                description=f"Activate {p.display_name or p.name}",
                icon_path=p.icon,
                provider=p.name,
                action_data={"_home": True, "prefix": p.prefix},
            )
            for p in self._service.providers
            if p.prefix
        ]

    @pyqtSlot(str, list)
    def _receive(self, query_id: str, results: list[ProviderResult]) -> None:
        if query_id != self._pending:
            return
        if not any(result.is_loading for result in results):
            self._pending = None
        self._results.set_results(results)
        typed = self._query
        first_app = next((r for r in results if r.provider == "apps" and not r.is_separator), None)
        if (
            typed
            and first_app
            and first_app.title.lower().startswith(typed.lower())
            and len(first_app.title) > len(typed)
        ):
            self._prediction = typed + first_app.title[len(typed) :]
        self.stateChanged.emit()

    def _apply(self, close: bool, refresh: bool) -> None:
        if close:
            self.closeRequested.emit()
        elif refresh:
            self.refresh()

    @pyqtSlot(int)
    def execute(self, row: int) -> None:
        result = self._results.result(row)
        if result is None or result.is_separator:
            return
        if result.action_data.get("_home"):
            self.prefixRequested.emit(result.action_data["prefix"])
            return
        provider = self._provider(result)
        if provider is None:
            return
        prefix = f"{provider.prefix} " if provider.prefix else ""
        if text := result.action_data.get("_replace_input"):
            self.queryRequested.emit(prefix + text)
            return
        if result.action_data.get("_pick_color"):
            self.colorPickRequested.emit(prefix)
            return
        try:
            outcome = provider.execute(result)
        except Exception:
            logging.exception("Quick Launch provider %s failed to run %r", provider.name, result.title)
            return
        # True closes, False runs the query again, None keeps the popup as it is
        if outcome is not None:
            self._apply(outcome, not outcome)

    @pyqtSlot(int, result="QVariantList")
    def contextActions(self, row: int) -> list[dict[str, Any]]:
        result = self._results.result(row)
        provider = self._provider(result) if result is not None and not result.is_separator else None
        if result is None or provider is None:
            return []
        return [
            {"id": a.id, "label": a.label, "enabled": a.enabled, "separatorBefore": a.separator_before}
            for a in provider.get_context_menu_actions(result)
        ]

    @pyqtSlot(int, str)
    def runContextAction(self, row: int, action_id: str) -> None:
        result = self._results.result(row)
        provider = self._provider(result) if result is not None else None
        if result is not None and provider is not None:
            outcome = provider.execute_context_menu_action(action_id, result)
            self._apply(outcome.close_popup, outcome.refresh_results)

    @pyqtSlot(int, result="QVariantMap")
    def preview(self, row: int) -> dict[str, Any]:
        result = self._results.result(row)
        provider = self._provider(result) if result is not None else None
        if result is None or not result.preview:
            return {}
        preview = dict(result.preview)
        preview["shown"] = provider.show_preview if provider is not None else True
        if "icon" in preview:
            preview["icon"] = image_url(preview["icon"])
        if isinstance(image := preview.get("image_data"), bytes):
            preview["image_data"] = "data:image/png;base64," + base64.b64encode(image).decode()
        if "metadata" in preview:
            # Label and value after each other, for a two column grid
            preview["metadata"] = [str(value) for pair in preview["metadata"] for value in pair]
        return preview

    @pyqtSlot(int, str, "QVariantMap")
    def previewAction(self, row: int, action_id: str, data: dict[str, Any]) -> None:
        result = self._results.result(row)
        provider = self._provider(result) if result is not None else None
        if result is not None and provider is not None:
            outcome = provider.handle_preview_action(action_id, result, data)
            self._apply(outcome.close_popup, not outcome.close_popup)

    @pyqtSlot()
    def cancelEdit(self) -> None:
        for provider in self._service.providers:
            provider.cancel_edit()

    @pyqtSlot()
    def deactivate(self) -> None:
        self._pending = None
        self._results.set_results([])
        for provider in self._service.providers:
            try:
                provider.on_deactivate()
            except Exception:
                logging.exception("Quick Launch provider %s failed to deactivate", provider.name)

    # Windows only lets an app that has focus give it to a window, which a hotkey press does not count as
    @pyqtSlot(QWindow)
    def activate(self, window: QWindow) -> None:
        force_foreground_focus(int(window.winId()))

    # The colour picker reads the screen under its own windows, so they must not be in that capture
    @pyqtSlot(QWindow)
    def excludeFromCapture(self, window: QWindow) -> None:
        user32.SetWindowDisplayAffinity(int(window.winId()), WDA_EXCLUDEFROMCAPTURE)

    @pyqtSlot(int, int, int, result="QStringList")
    def colorsAround(self, x: int, y: int, size: int) -> list[str]:
        """The live colours of the size×size physical pixels centred on the global point x, y, row by row."""
        screen = QGuiApplication.screenAt(QPoint(x, y))
        if screen is None:
            return []
        geometry = screen.geometry()
        scale = screen.devicePixelRatio()
        # Enough logical pixels around the point to cover the grid in physical pixels
        span = math.ceil(size / scale) + 2
        left, top = x - geometry.x() - span // 2, y - geometry.y() - span // 2
        image = screen.grabWindow(x=left, y=top, width=span, height=span).toImage()
        cx = round((x - geometry.x() - left) * scale) - size // 2
        cy = round((y - geometry.y() - top) * scale) - size // 2
        return [image.pixelColor(cx + col, cy + row).name().upper() for row in range(size) for col in range(size)]
