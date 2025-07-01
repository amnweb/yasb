import logging
import os
from dataclasses import replace
from typing import Any, override

from PyQt6 import sip
from PyQt6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    Qt,
    QTimer,
    pyqtSignal,
    pyqtSlot,  # pyright: ignore [reportUnknownVariableType]
)
from PyQt6.QtGui import QCursor, QMouseEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)
from winrt.windows.devices.wifi import WiFiConnectionStatus

from core.utils.utilities import PopupWidget
from core.utils.widgets.wifi.wifi_managers import (
    NetworkInfo,
    ScanResultStatus,
    WiFiConnectWorker,
    WifiDisconnectWorker,
    WiFiManager,
    WifiState,
)
from core.utils.win32.utilities import qmenu_rounded_corners  # type: ignore

logger = logging.getLogger("wifi_widget")


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._clickable = False

    @property
    def clickable(self) -> bool:
        return self._clickable

    @clickable.setter
    def clickable(self, value: bool):
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor) if value else QCursor(Qt.CursorShape.ArrowCursor))
        self._clickable = value

    @override
    def mousePressEvent(self, ev: QMouseEvent | None):
        if ev and ev.button() == Qt.MouseButton.LeftButton and self._clickable:
            self.clicked.emit()
            return
        super().mousePressEvent(ev)


class WifiItem(QFrame):
    clicked = pyqtSignal()
    connect_pressed = pyqtSignal(NetworkInfo, str, str)
    disconnect_pressed = pyqtSignal(NetworkInfo)
    forget_pressed = pyqtSignal(NetworkInfo)
    auto_connect_toggled = pyqtSignal(NetworkInfo)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._active = False
        self._data = NetworkInfo()
        self.state = WifiState.SECURED

        self.auto_connect_checkbox = None

        self.setProperty("class", "wifi-item")
        self.setContentsMargins(0, 0, 0, 0)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)  # type: ignore

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.wifi_details_container = QFrame(self)
        self.wifi_details_container.setContentsMargins(0, 0, 0, 0)
        self.wifi_details_container.setProperty("class", "details-container")
        self.wifi_details_container_layout = QHBoxLayout(self.wifi_details_container)
        self.wifi_details_container_layout.setSpacing(0)
        self.wifi_details_container_layout.setContentsMargins(0, 0, 0, 0)

        self.wifi_icon = QLabel(self)
        self.wifi_icon.setProperty("class", "icon")
        self.wifi_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wifi_icon.setContentsMargins(0, 0, 0, 0)

        self.wifi_name = QLabel(self)
        self.wifi_name.setProperty("class", "name")

        # Right container
        self.right_container = QFrame(self)
        self.right_container.setProperty("class", "right-container")
        self.right_container.setContentsMargins(0, 0, 0, 0)
        self.right_container_layout = QVBoxLayout(self.right_container)
        self.right_container_layout.setSpacing(0)
        self.right_container_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel(self)
        self.status_label.setProperty("class", "status")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignRight)
        self.status_label.setContentsMargins(0, 0, 0, 0)
        self.status_label.setText("N/A")

        self.wifi_strength = QLabel(self)
        self.wifi_strength.setProperty("class", "strength")
        self.wifi_strength.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignRight)
        self.wifi_strength.setContentsMargins(0, 0, 0, 0)
        self.wifi_strength.setText("N/A")

        self.right_container_layout.addWidget(self.status_label)
        self.right_container_layout.addWidget(self.wifi_strength)

        self.wifi_details_container_layout.addWidget(self.wifi_icon)
        self.wifi_details_container_layout.addWidget(self.wifi_name)
        self.wifi_details_container_layout.addStretch()
        self.wifi_details_container_layout.addWidget(self.right_container)

        # Controls container
        self.wifi_controls_container = QFrame(self)
        self.wifi_controls_container.setContentsMargins(0, 0, 0, 0)
        self.wifi_controls_container.setProperty("class", "controls-container")
        self.wifi_controls_container_layout = QHBoxLayout(self.wifi_controls_container)
        self.wifi_controls_container_layout.setSpacing(0)
        self.wifi_controls_container_layout.setContentsMargins(0, 0, 0, 0)

        self.ssid_field = QLineEdit(self)
        self.ssid_field.setPlaceholderText("SSID")
        self.ssid_field.setProperty("class", "password")
        self.ssid_field.returnPressed.connect(self._manage_connection_click)  # pyright: ignore[reportUnknownMemberType]

        self.password_field = QLineEdit(self)
        self.password_field.setPlaceholderText("Password")
        self.password_field.setProperty("class", "password")
        self.password_field.returnPressed.connect(self._manage_connection_click)  # pyright: ignore[reportUnknownMemberType]
        self.password_field.setEchoMode(QLineEdit.EchoMode.Password)

        self.connect_button = QPushButton(self)
        self.connect_button.setProperty("class", "connect")
        self.connect_button.setText("Connect")
        self.connect_button.clicked.connect(self._manage_connection_click)  # pyright: ignore[reportUnknownMemberType]

        self.wifi_controls_container_layout.addWidget(self.ssid_field)
        self.wifi_controls_container_layout.addWidget(self.password_field)
        self.wifi_controls_container_layout.addStretch()
        self.wifi_controls_container_layout.addWidget(self.connect_button)

        self.main_layout.addWidget(self.wifi_details_container)
        self.main_layout.addWidget(self.wifi_controls_container)

    @pyqtSlot(QPoint)
    def show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setProperty("class", "context-menu")
        menu.aboutToShow.connect(lambda: qmenu_rounded_corners(menu))  # pyright: ignore[reportUnknownMemberType]

        # Auto-connect checkbox
        self.auto_connect_checkbox = QCheckBox("Auto-connect")
        self.auto_connect_checkbox.setChecked(self.data.auto_connect)
        self.auto_connect_checkbox.clicked.connect(self._toggle_auto_connect)  # pyright: ignore[reportUnknownMemberType]
        self.auto_connect_checkbox.setProperty("class", "checkbox")

        # Container with hover effects
        container = QWidget(menu)
        container.setProperty("class", "menu-checkbox")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.auto_connect_checkbox)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        class ClickToggleFilter(QObject):
            """Event filter to toggle the checkbox on click"""

            def __init__(self, checkbox: QCheckBox):
                super().__init__()
                self.checkbox = checkbox

            def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
                if isinstance(a1, QMouseEvent):
                    if a1.type() == QEvent.Type.MouseButtonPress and a1.button() == Qt.MouseButton.LeftButton:
                        if self.checkbox and not sip.isdeleted(self.checkbox):
                            self.checkbox.toggle()
                        return True
                return False

        click_filter = ClickToggleFilter(self.auto_connect_checkbox)
        container.installEventFilter(click_filter)

        auto_connect_action = QWidgetAction(menu)
        auto_connect_action.setDefaultWidget(container)
        menu.addAction(auto_connect_action)  # pyright: ignore[reportUnknownMemberType]

        # Forget button
        forget_button_widget = menu.addAction("Forget Network")  # type: ignore
        if forget_button_widget:
            forget_button_widget.setEnabled(self.data.profile_exists)
            forget_button_widget.triggered.connect(lambda: (self.forget_pressed.emit(self.data), menu.close()))  # pyright: ignore[reportUnknownMemberType]

        menu.exec(self.mapToGlobal(pos))  # pyright: ignore[reportUnknownMemberType]

    @pyqtSlot()
    def _enable_auto_connect_checkbox(self):
        if self.auto_connect_checkbox and not sip.isdeleted(self.auto_connect_checkbox):
            self.auto_connect_checkbox.setEnabled(True)

    @pyqtSlot()
    def _toggle_auto_connect(self):
        self.data.auto_connect = not self.data.auto_connect
        self.auto_connect_toggled.emit(self.data)
        if self.auto_connect_checkbox and not sip.isdeleted(self.auto_connect_checkbox):
            self.auto_connect_checkbox.setDisabled(True)
            QTimer.singleShot(3000, self._enable_auto_connect_checkbox)  # type: ignore

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, value: bool):
        self._active = value
        self.update_state(value)

    @property
    def data(self) -> NetworkInfo:
        return self._data

    @data.setter
    def data(self, data: NetworkInfo):
        self._data = data
        self.state = data.state
        self.wifi_name.setText(data.ssid)
        self.wifi_strength.setText(f"{data.quality}%")
        self.wifi_icon.setText(data.icon)
        self.update_state()

    @pyqtSlot()
    def _manage_connection_click(self):
        """Disconnect from the current network"""
        if self.state & WifiState.CONNECTED:
            self.disconnect_pressed.emit(self.data)
        else:
            self.connect_pressed.emit(self.data, self.password_field.text(), self.ssid_field.text())

    def update_state(self, set_active: bool | None = None):
        if set_active is not None:
            self._active = set_active
        self.setProperty("active", self._active)
        self.wifi_controls_container.setVisible(self._active)
        if self._active:
            # Update the connect button text and password field visibility
            requires_pass = bool(not self.state & WifiState.CONNECTED) and bool(self.state & WifiState.SECURED)
            known_profile = self.data.profile_exists
            self.password_field.setVisible(requires_pass and not known_profile)
            self.connect_button.setText("Disconnect" if self.state & WifiState.CONNECTED else "Connect")
        # Update the status label
        if self.state == WifiState.CONNECTED:
            self.status_label.setText("Connected")
        elif self.state == WifiState.CONNECTED | WifiState.SECURED:
            self.status_label.setText("Connected, Secured")
        elif self.state == WifiState.SECURED:
            self.status_label.setText("Secured")
        else:
            self.status_label.setText("Unsecured")
        # Set the SSID field visibility for hidden network
        self.ssid_field.setVisible(self.data.ssid == "<Hidden Network>")
        # Update the style
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)

    @override
    def mousePressEvent(self, a0: QMouseEvent | None):
        super().mousePressEvent(a0)
        if not a0:
            return
        if a0.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        elif a0.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(a0.pos())


class WifiList(QScrollArea):
    connect_pressed = pyqtSignal(NetworkInfo, str, str)
    disconnect_pressed = pyqtSignal(NetworkInfo)
    forget_pressed = pyqtSignal(NetworkInfo)
    auto_connect_toggled = pyqtSignal(NetworkInfo)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 0, -4, 0)
        self.setStyleSheet("""
            QScrollArea { background: transparent; border: none; border-radius:0; }
            QScrollBar:vertical { border: none; background:transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

        self.container = QFrame(self)
        self.container.setProperty("class", "wifi-list")
        self._main_layout = QVBoxLayout(self.container)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(2)
        self._main_layout.addStretch()

        self.setWidget(self.container)
        self._items: dict[str, WifiItem] = {}

    def add_item(self, item: WifiItem):
        item.clicked.connect(lambda: self._on_item_clicked(item))  # pyright: ignore[reportUnknownMemberType]
        item.disconnect_pressed.connect(self.disconnect_pressed.emit)  # pyright: ignore[reportUnknownMemberType]
        item.connect_pressed.connect(self.connect_pressed.emit)  # pyright: ignore[reportUnknownMemberType]
        item.forget_pressed.connect(self.forget_pressed.emit)  # pyright: ignore[reportUnknownMemberType]
        item.auto_connect_toggled.connect(self.auto_connect_toggled.emit)  # pyright: ignore[reportUnknownMemberType]

        item.setParent(self)
        self._main_layout.insertWidget(self._main_layout.count() - 1, item)
        self._items[item.data.ssid] = item

    def update_or_add_item(self, item: WifiItem):
        """Modify an existing item in place or add a new one if it doesn't exist"""
        if item.data.ssid in self._items:
            self._items[item.data.ssid].data = item.data
        else:
            self.add_item(item)

    def remove_item(self, ssid: str):
        item = self._items.pop(ssid, None)
        if item is None:
            return
        item.setParent(None)
        item.deleteLater()

    def get_items(self) -> dict[str, WifiItem]:
        return self._items

    def get_item(self, ssid: str) -> WifiItem | None:
        return self._items.get(ssid)

    def sort_items(self):
        items_list = sorted(self._items.items(), key=lambda item: item[1].data.quality, reverse=True)
        # Find the current connection if exists and move it to the top
        for item in items_list:
            if item[1].data.state & WifiState.CONNECTED:
                items_list.remove(item)
                items_list.insert(0, item)
                break
        # Find a hidden network and move it to the bottom
        for item in items_list:
            if item[1].data.ssid == "<Hidden Network>":
                items_list.remove(item)
                items_list.append(item)
                break
        self._items = dict(items_list)
        # Remove all widgets from layout except the stretch at the end
        while self._main_layout.count() > 1:  # Keep the stretch
            child = self._main_layout.takeAt(0)
            if child is not None and (cw := child.widget()):
                cw.setParent(None)
        # Add all items back to the layout
        for item in self._items.values():
            item.setParent(self.container)
            self._main_layout.insertWidget(self._main_layout.count() - 1, item)

    def clear_items(self):
        for item in self._items.values():
            item.setParent(None)
            item.deleteLater()
        self._items.clear()

    def clear_fields(self):
        for item in self._items.values():
            item.password_field.setText("")
            item.ssid_field.setText("")

    def activate_item(self, name: str):
        for key, item in self._items.items():
            item.active = key == name

    @pyqtSlot(WifiItem)
    def _on_item_clicked(self, selected: WifiItem):
        for item in self._items.values():
            item.update_state(item is selected)


class WifiMenu(QWidget):
    """Container for the wifi menu"""

    _networks_cache: dict[str, NetworkInfo] = {}

    def __init__(
        self,
        parent: QWidget,
        menu_config: dict[str, Any],
    ):
        super().__init__(parent)
        self._parent = parent
        self.menu_config = menu_config
        self.wifi_manager = WiFiManager(self)
        self.wifi_manager.wifi_scan_completed.connect(self._on_wifi_scan_completed)  # pyright: ignore[reportUnknownMemberType]
        self.wifi_manager.wifi_disconnected.connect(self._on_wifi_disconnected)  # pyright: ignore[reportUnknownMemberType]

        self.wifi_connection_worker: WiFiConnectWorker | None = None
        self.wifi_disconnect_worker: WifiDisconnectWorker | None = None

        self.list_update_timer = QTimer(self)
        self.list_update_timer.setSingleShot(True)
        self.list_update_timer.timeout.connect(self._update_wifi_items_list)  # pyright: ignore[reportUnknownMemberType]

        self.error_connection = None

    def show_menu(self):
        self.popup_window = PopupWidget(
            self._parent,
            self.menu_config["blur"],
            self.menu_config["round_corners"],
            self.menu_config["round_corners_type"],
            self.menu_config["border_color"],
        )
        self.popup_window.setProperty("class", "wifi-menu")
        main_layout = QVBoxLayout(self.popup_window)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        header_label = QLabel("WiFi Networks")
        header_label.setProperty("class", "header")

        self.menu_progress_bar = QProgressBar(self.popup_window)
        self.menu_progress_bar.setRange(0, 0)  # Undetermined progress bar
        self.menu_progress_bar.setTextVisible(False)
        self.menu_progress_bar.setContentsMargins(0, 0, 0, 0)
        self.menu_progress_bar.setProperty("class", "progress-bar")
        self.menu_progress_bar.setHidden(True)

        self.error_message = ClickableLabel(self.popup_window)
        self.error_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_message.setProperty("class", "error-message")
        self.error_message.setHidden(True)

        self.menu_wifi_list = WifiList(self.popup_window)
        self.menu_wifi_list.disconnect_pressed.connect(self._disconnect)  # pyright: ignore[reportUnknownMemberType]
        self.menu_wifi_list.connect_pressed.connect(self._connect)  # pyright: ignore[reportUnknownMemberType]
        self.menu_wifi_list.forget_pressed.connect(self._forget_network)  # pyright: ignore[reportUnknownMemberType]
        self.menu_wifi_list.auto_connect_toggled.connect(self._on_auto_connect_toggled)  # pyright: ignore[reportUnknownMemberType]

        footer_container = QFrame(self.popup_window)
        footer_container.setProperty("class", "footer")

        footer_layout = QHBoxLayout(footer_container)
        footer_layout.setSpacing(0)
        footer_layout.setContentsMargins(0, 0, 0, 0)

        more_settings_button = QPushButton("More Wi-Fi settings")
        more_settings_button.setProperty("class", "settings-button")
        more_settings_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        more_settings_button.clicked.connect(lambda: os.startfile("ms-settings:network-wifi"))  # type: ignore[reportUnknownMemberType]

        refresh_icon = QPushButton(self.popup_window)
        refresh_icon.setText("\ue72c")
        refresh_icon.setProperty("class", "refresh-icon")
        refresh_icon.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        refresh_icon.clicked.connect(self._scan_wifi)  # pyright: ignore[reportUnknownMemberType]

        footer_layout.addWidget(more_settings_button)
        footer_layout.addStretch()
        footer_layout.addWidget(refresh_icon)

        main_layout.addWidget(header_label)
        main_layout.addWidget(self.menu_progress_bar)
        main_layout.addWidget(self.error_message)
        main_layout.addWidget(self.menu_wifi_list)
        main_layout.addWidget(footer_container)

        self.popup_window.adjustSize()
        self.popup_window.setPosition(
            alignment=self.menu_config["alignment"],
            direction=self.menu_config["direction"],
            offset_left=self.menu_config["offset_left"],
            offset_top=self.menu_config["offset_top"],
        )

        self.popup_window.destroyed.connect(self._on_wifi_menu_deleted)  # pyright: ignore[reportUnknownMemberType]
        self.wifi_manager.wifi_updates_enabled = True
        self._update_wifi_items_list()
        self._scan_wifi()
        self.popup_window.show()

    def show_errror_message_briefly(self, message: str):
        """Shows an error message briefly"""
        if sip.isdeleted(self.popup_window):
            return

        def hide_error_message():
            if not sip.isdeleted(self.popup_window):
                self.error_message.setVisible(False)

        if not sip.isdeleted(self.popup_window):
            self.error_message.clickable = False
            self.error_message.setText(message)
            self.error_message.setVisible(True)
            self.menu_progress_bar.setVisible(False)
            QTimer.singleShot(4000, hide_error_message)  # pyright: ignore[reportUnknownMemberType]

    @pyqtSlot()
    def _on_wifi_menu_deleted(self):
        """Called when the wifi menu is deleted"""
        self.wifi_manager.wifi_updates_enabled = False

    @pyqtSlot(NetworkInfo, str, str)
    def _connect(self, network: NetworkInfo, password: str, ssid: str = ""):
        """Connect to the currently selected network"""
        if (
            self.wifi_connection_worker
            and not sip.isdeleted(self.wifi_connection_worker)
            and self.wifi_connection_worker.isRunning()
        ):
            logger.debug("Already connecting to a network")
            return
        logger.debug("Connecting to wifi network...")
        if network.ssid == "<Hidden Network>":
            self.wifi_connection_worker = WiFiConnectWorker(network, ssid, password, True)
        else:
            self.wifi_connection_worker = WiFiConnectWorker(network, network.ssid, password, False)
        self.wifi_connection_worker.result.connect(self._on_connection_attempt_completed)  # pyright: ignore[reportUnknownMemberType]
        self.wifi_connection_worker.start()
        if sip.isdeleted(self.popup_window):
            return
        self.menu_progress_bar.setVisible(True)

    @pyqtSlot(WiFiConnectionStatus, str, NetworkInfo)
    def _on_connection_attempt_completed(self, result: WiFiConnectionStatus, profile_name: str, network: NetworkInfo):
        if result != WiFiConnectionStatus.SUCCESS:
            if result == WiFiConnectionStatus.INVALID_CREDENTIAL:
                self.show_errror_message_briefly("Invalid password")
            elif result == WiFiConnectionStatus.NETWORK_NOT_AVAILABLE:
                self.show_errror_message_briefly("Network not available")
            else:
                logger.error(f"Connection failed to wifi network. Reason: {result.name}")
            return

        logger.debug("Connection completed to wifi network")
        if profile_name in self._networks_cache:
            self._networks_cache[profile_name] = replace(
                self._networks_cache[profile_name],
                state=self._networks_cache[profile_name].state | WifiState.CONNECTED,
            )
        else:
            self._networks_cache[profile_name] = network

        if sip.isdeleted(self.popup_window):
            return
        menu_wifi_list = self.menu_wifi_list.get_items()
        if item := menu_wifi_list.get(profile_name):
            item.data = replace(item.data, state=item.data.state | WifiState.CONNECTED)
        self._update_wifi_items_list()
        self.menu_wifi_list.activate_item(profile_name)
        self.menu_wifi_list.clear_fields()
        self.menu_progress_bar.setVisible(False)

    def _disconnect(self, network: NetworkInfo):
        """Disconnect from the currently connected network"""
        if (
            self.wifi_disconnect_worker
            and not sip.isdeleted(self.wifi_disconnect_worker)
            and self.wifi_disconnect_worker.isRunning()
        ):
            logger.debug("Already disconnecting from a network")

        logger.debug("Disconnecting from wifi network")
        self.wifi_disconnect_worker = WifiDisconnectWorker()
        self.wifi_disconnect_worker.start()
        # Update the cache
        if WifiMenu._networks_cache.get(network.ssid):
            WifiMenu._networks_cache[network.ssid] = replace(network, state=network.state & ~WifiState.CONNECTED)

    @pyqtSlot(str)
    def _on_wifi_disconnected(self, profile_name: str):
        """Handle when a WiFi network is disconnected"""
        logger.debug("WiFi network disconnected")
        if profile_name in self._networks_cache:
            self._networks_cache[profile_name] = replace(
                self._networks_cache[profile_name],
                state=self._networks_cache[profile_name].state & ~WifiState.CONNECTED,
            )

        if sip.isdeleted(self.popup_window):
            return
        # Update the menu
        if item := self.menu_wifi_list.get_item(profile_name):
            item.data = replace(item.data, state=item.data.state & ~WifiState.CONNECTED)

    @pyqtSlot(NetworkInfo)
    def _forget_network(self, network: NetworkInfo):
        """Forget a specific WiFi network"""
        logger.debug("Forgetting wifi network...")
        self.wifi_manager.forget_network(network.ssid)
        # Update the cache
        if network.ssid in WifiMenu._networks_cache:
            WifiMenu._networks_cache[network.ssid] = replace(
                network,
                state=network.state & ~WifiState.CONNECTED,
                profile_exists=False,
            )

        if sip.isdeleted(self.popup_window):
            return
        # Update the menu
        if item := self.menu_wifi_list.get_item(network.ssid):
            item.data = replace(
                network,
                state=network.state & ~WifiState.CONNECTED,
                profile_exists=False,
            )

    @pyqtSlot()
    def _scan_wifi(self):
        """Trigger a WiFi scan"""
        # This is async and will emit a signal when finished
        self.wifi_manager.scan_available_networks()
        if not sip.isdeleted(self.popup_window):
            self.menu_progress_bar.setVisible(True)

    @pyqtSlot(ScanResultStatus, list)
    def _on_wifi_scan_completed(self, result: ScanResultStatus, networks: list[NetworkInfo]):
        """Handle the WiFi scan is completed event"""
        # Check if location services are enabled
        if not sip.isdeleted(self.popup_window):
            if result != ScanResultStatus.SUCCESS:
                if result == ScanResultStatus.ACCESS_DENIED:
                    self.error_message.setText("Error: Location services are disabled...")
                    self.error_message.clickable = True
                    if self.error_connection:
                        self.error_message.disconnect(self.error_connection)
                    self.error_connection = self.error_message.clicked.connect(  # type: ignore[reportUnknownMemberType]
                        lambda: os.startfile("ms-settings:privacy-location")
                    )
                elif result == ScanResultStatus.POWER_STATE_INVALID:
                    self.error_message.setText("Error: WiFi adapter is disabled...")
                    self.error_message.clickable = True
                    if self.error_connection:
                        self.error_message.disconnect(self.error_connection)
                    self.error_connection = self.error_message.clicked.connect(  # type: ignore[reportUnknownMemberType]
                        lambda: os.startfile("ms-settings:network-wifi")
                    )
                elif result == ScanResultStatus.ERROR:
                    self.error_message.clickable = False
                    self.error_message.setText("Unknown error...")
                self.menu_wifi_list.clear_items()
                WifiMenu._networks_cache = {}
                self.menu_progress_bar.setVisible(False)
                self.error_message.setVisible(True)
                return

        # Some wifi adapters can return an empty list, we just ignore it
        # Also, status updates don't need to update the cache
        if not networks:
            return

        WifiMenu._networks_cache = {network.ssid: network for network in networks}
        self.list_update_timer.start(100)  # Avoid unnecessary ui updates

    @pyqtSlot(NetworkInfo)
    def _on_auto_connect_toggled(self, network: NetworkInfo):
        """Handle the auto-connect setting is toggled event"""
        if network.ssid in self._networks_cache:
            self._networks_cache[network.ssid] = replace(
                network,
                auto_connect=network.auto_connect,
            )
        current_connection = self.wifi_manager.get_current_connection()
        active_connection = current_connection and current_connection.ssid == network.ssid
        if active_connection:
            self.wifi_disconnect_worker = WifiDisconnectWorker()
            self.wifi_disconnect_worker.start()

        self.wifi_manager.change_auto_connect(network.ssid, network.auto_connect)

        if active_connection:
            self.wifi_connection_worker = WiFiConnectWorker(network, network.ssid, "", False)
            self.wifi_connection_worker.result.connect(self._on_connection_attempt_completed)  # pyright: ignore[reportUnknownMemberType]
            self.wifi_connection_worker.start()

    @pyqtSlot()
    def _update_wifi_items_list(self):
        """Update the WiFi items list"""
        if sip.isdeleted(self.popup_window):
            return
        self.menu_progress_bar.setVisible(False)
        active_connection = self.wifi_manager.get_current_connection()
        if active_connection:
            item = WifiItem(self.menu_wifi_list)
            is_secured = bool(active_connection.state & WifiState.SECURED)
            quality = active_connection.quality
            active_connection.icon = f"{self._get_wifi_icon(quality, is_secured)}"
            active_connection.profile_exists = True  # Since it's the current connection
            item.data = active_connection
            item.active = bool(active_connection.state & WifiState.CONNECTED)
            self.menu_wifi_list.update_or_add_item(item)
            self._networks_cache[active_connection.ssid] = active_connection
        # Add cached networks except for the current one
        for ssid, network in WifiMenu._networks_cache.items():
            if active_connection and network.ssid == active_connection.ssid:
                WifiMenu._networks_cache[ssid] = active_connection
                continue
            is_secured = bool(network.state & WifiState.SECURED)
            item = WifiItem(self.menu_wifi_list)
            network.icon = self._get_wifi_icon(network.quality, is_secured)
            item.data = network
            item.active = bool(network.state & WifiState.CONNECTED)
            self.menu_wifi_list.update_or_add_item(item)
        # Cleanup missing networks
        cached_networks_ssid = list(WifiMenu._networks_cache)
        current_networks = list(self.menu_wifi_list.get_items())
        for ssid in current_networks:
            if ssid not in cached_networks_ssid:
                self.menu_wifi_list.remove_item(ssid)
        # Re-sort items
        self.menu_wifi_list.sort_items()
        # Focus the first active item
        active_items = [item for item in self.menu_wifi_list.get_items().values() if item.active]
        if not active_items:
            return
        password_field = active_items[0].password_field
        if password_field.isHidden() or password_field.hasFocus():
            return
        password_field.setFocus()

    def _get_wifi_icon(self, strength: int, secured: bool) -> str:
        """Get the WiFi icon based on the signal strength"""
        level = min(strength // 25, 3)
        if secured:
            return self.menu_config["wifi_icons_secured"][level]
        else:
            return self.menu_config["wifi_icons_unsecured"][level]
