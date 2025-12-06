"""About dialog for the application, providing information and update controls."""

import os
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from winmica import BackdropType, EnableMica, is_mica_supported

from core.ui.style import apply_button_style, apply_link_button_style
from core.ui.windows.update_dialog import ReleaseFetcher, ReleaseInfo, UpdateDialog
from core.utils.tooltip import set_tooltip
from core.utils.update_service import get_update_service
from core.utils.utilities import get_architecture, is_valid_qobject, refresh_widget_style
from settings import (
    APP_NAME,
    BUILD_VERSION,
    GITHUB_THEME_URL,
    GITHUB_URL,
    RELEASE_CHANNEL,
    SCRIPT_PATH,
)

ARCHITECTURE = get_architecture()

if TYPE_CHECKING:
    from core.tray import SystemTrayManager


class AboutDialog(QDialog):
    _STATE_CONFIG = {
        "idle": {"text": "Check for Updates", "enabled": True, "attr": "idle"},
        "checking": {"text": "Checking for Updates", "enabled": False, "attr": "checking"},
        "available": {"text": "New Update Available", "enabled": True, "attr": "available"},
        "unsupported": {
            "text": "Updates disabled",
            "enabled": False,
            "attr": "unsupported",
            "tooltip": "Automatic updates are disabled for PR build."
            if RELEASE_CHANNEL.startswith("pr-")
            else "Install YASB to enable automatic updates.",
        },
    }

    def __init__(self, tray_manager: "SystemTrayManager"):
        parent_widget: Optional[QWidget] = tray_manager if isinstance(tray_manager, QWidget) else None
        super().__init__(parent_widget)
        self._tray = tray_manager
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)

        self._release_fetcher: Optional[ReleaseFetcher] = None
        self._update_dialog: Optional[UpdateDialog] = None

        update_service = get_update_service()
        self._updates_supported = update_service.is_update_supported()

        self._link_buttons: list[QPushButton] = []
        self._secondary_buttons: list[QPushButton] = []

        self._build_window()
        self._build_ui()

        self._reset_timer.timeout.connect(lambda: self._apply_state("idle"))
        self._apply_palette()
        self._apply_state("idle")

    def _build_window(self) -> None:
        self.setWindowTitle(f"About {APP_NAME}")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumSize(360, 480)
        if is_mica_supported():
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            hwnd = int(self.winId())
            EnableMica(hwnd, BackdropType.MICA)

        icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        if not icon.isNull():
            self.setWindowIcon(icon)
        self._window_icon = icon

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if not self._window_icon.isNull():
            icon_label.setPixmap(self._window_icon.pixmap(90, 90))
        layout.addWidget(icon_label)

        title_label = QLabel("YASB Reborn")
        title_label.setContentsMargins(0, 8, 0, 0)
        title_font = title_label.font()
        title_font.setPointSize(title_font.pointSize() + 10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        arch_suffix = f" {ARCHITECTURE}" if ARCHITECTURE else ""
        version_label = QLabel(f"Version {BUILD_VERSION}{arch_suffix} ({RELEASE_CHANNEL})")
        version_label.setContentsMargins(0, 4, 0, 0)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_font = version_label.font()
        version_font.setPointSize(version_font.pointSize() + 1)
        version_label.setFont(version_font)
        version_effect = QGraphicsOpacityEffect()
        version_effect.setOpacity(0.7)
        version_label.setGraphicsEffect(version_effect)
        layout.addWidget(version_label)

        release_url = self._get_release_notes_url()
        release_label = "View PR Details" if RELEASE_CHANNEL.startswith("pr-") else "View Release Notes"
        release_note_btn = self._create_link_button(release_label, lambda: self._tray._open_in_browser(release_url))
        layout.addWidget(release_note_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        links_container = QWidget()
        links_container.setContentsMargins(0, 32, 0, 0)
        links_layout = QHBoxLayout(links_container)
        links_layout.setContentsMargins(0, 0, 0, 0)
        links_layout.setSpacing(0)
        links_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        github_btn = self._create_link_button("GitHub", lambda: self._tray._open_in_browser(GITHUB_URL))
        themes_btn = self._create_link_button("Themes", lambda: self._tray._open_in_browser(GITHUB_THEME_URL))
        discord_btn = self._create_link_button(
            "Discord", lambda: self._tray._open_in_browser("https://discord.gg/qkeunvBFgX")
        )
        links_layout.addWidget(github_btn)
        links_layout.addWidget(themes_btn)
        links_layout.addWidget(discord_btn)
        layout.addWidget(links_container)

        button_layout = QVBoxLayout()
        button_layout.setContentsMargins(0, 12, 0, 0)
        button_layout.setSpacing(12)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._support_project_button = self._create_action_button(
            "Support the Project",
            lambda: self._tray._open_in_browser("https://ko-fi.com/amnweb"),
        )
        self._contributors_button = self._create_action_button(
            "Contributors",
            lambda: self._tray._open_in_browser(f"{GITHUB_URL}/graphs/contributors"),
        )
        self._open_config_button = self._create_action_button("Open Config", self._tray._open_config)
        idle_text = self._STATE_CONFIG["idle"]["text"]
        self._update_button = self._create_action_button(idle_text, self._handle_update_clicked)
        if not self._updates_supported:
            self._disable_update_capability()

        for button in (
            self._support_project_button,
            self._contributors_button,
            self._open_config_button,
            self._update_button,
        ):
            button.setMinimumWidth(180)
            button_layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addLayout(button_layout)

    def _get_release_notes_url(self) -> str:
        if RELEASE_CHANNEL.startswith("pr-"):
            pr_part = RELEASE_CHANNEL.split("-", 1)[1] if "-" in RELEASE_CHANNEL else ""
            pr_number = pr_part.split("-", 1)[0]
            if pr_number.isdigit():
                return f"{GITHUB_URL}/pull/{pr_number}"
            return GITHUB_URL

        if RELEASE_CHANNEL.startswith("dev-"):
            return f"{GITHUB_URL}/releases/tag/dev"

        return f"{GITHUB_URL}/releases/tag/v{BUILD_VERSION}"

    def _create_link_button(self, text: str, callback) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("yasbLinkButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFlat(True)
        size_policy = button.sizePolicy()
        size_policy.setHorizontalPolicy(QSizePolicy.Policy.Fixed)
        size_policy.setVerticalPolicy(QSizePolicy.Policy.Fixed)
        button.setSizePolicy(size_policy)
        button.clicked.connect(callback)
        self._link_buttons.append(button)
        return button

    def _create_action_button(self, text: str, callback) -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        self._secondary_buttons.append(button)
        return button

    def _apply_palette(self) -> None:
        for button in self._link_buttons:
            apply_link_button_style(button)

        for button in (
            self._support_project_button,
            self._contributors_button,
            self._open_config_button,
        ):
            apply_button_style(button, "secondary")

        self._refresh_update_button_style()

    def _refresh_update_button_style(self) -> None:
        if not is_valid_qobject(self._update_button):
            return
        state = self._update_button.property("updateState") or "idle"
        variant = "primary" if state == "available" else "secondary"
        apply_button_style(self._update_button, variant)
        refresh_widget_style(self._update_button)

    def _apply_state(
        self,
        state: str,
        *,
        release_info: Optional[ReleaseInfo] = None,
        text_override: Optional[str] = None,
        revert_after: Optional[int] = None,
    ) -> None:
        if not is_valid_qobject(self._update_button):
            return
        if not self._updates_supported:
            self._reset_timer.stop()
            self._disable_update_capability()
            return
        self._reset_timer.stop()
        config = self._STATE_CONFIG[state]
        self._update_button.setProperty("updateState", state)
        self._update_button.setProperty("releaseInfo", release_info)
        self._update_button.setEnabled(config["enabled"])
        self._update_button.setProperty("state", config["attr"])
        if text_override:
            self._update_button.setText(text_override)
        else:
            self._update_button.setText(config["text"])
        self._refresh_update_button_style()
        if revert_after:
            self._reset_timer.start(revert_after)

    def _handle_update_available(self, release_info: ReleaseInfo, fetcher_ref: Optional[ReleaseFetcher] = None) -> None:
        self._clear_fetcher(fetcher_ref)
        self._apply_state("available", release_info=release_info)

    def _handle_up_to_date(self, _message: str, fetcher_ref: Optional[ReleaseFetcher] = None) -> None:
        self._clear_fetcher(fetcher_ref)
        self._apply_state("idle", text_override="You're on the latest version", revert_after=2400)

    def _handle_check_failed(self, _message: str, fetcher_ref: Optional[ReleaseFetcher] = None) -> None:
        self._clear_fetcher(fetcher_ref)
        self._apply_state("idle", text_override="Update Check Failed", revert_after=3200)

    def _clear_fetcher(self, fetcher_ref: Optional[ReleaseFetcher] = None) -> None:
        if fetcher_ref is None or self._release_fetcher is fetcher_ref:
            self._release_fetcher = None

    def _start_update_check(self) -> None:
        if not self._updates_supported:
            return
        if not is_valid_qobject(self._update_button):
            return
        if self._release_fetcher and self._release_fetcher.isRunning():
            return
        self._apply_state("checking")
        fetcher = ReleaseFetcher(BUILD_VERSION, self)
        self._release_fetcher = fetcher
        fetcher.update_available.connect(lambda info, f=fetcher: self._handle_update_available(info, f))
        fetcher.up_to_date.connect(lambda msg, f=fetcher: self._handle_up_to_date(msg, f))
        fetcher.error.connect(lambda msg, f=fetcher: self._handle_check_failed(msg, f))
        fetcher.finished.connect(lambda f=fetcher: self._clear_fetcher(f))
        fetcher.finished.connect(fetcher.deleteLater)
        fetcher.start()

    def _handle_update_clicked(self) -> None:
        if not self._updates_supported:
            return
        if not is_valid_qobject(self._update_button):
            return
        state = self._update_button.property("updateState") or "idle"
        if state == "checking":
            return
        if state == "available":
            release_info = self._update_button.property("releaseInfo")
            if release_info:
                dialog = self._ensure_update_dialog(release_info)
                if dialog:
                    self.close()
                    return
            self._start_update_check()
            return
        self._apply_state("idle")
        self._start_update_check()

    def _ensure_update_dialog(self, release_info: Optional[ReleaseInfo] = None) -> Optional[UpdateDialog]:
        dialog = self._update_dialog
        if is_valid_qobject(dialog):
            if release_info:
                try:
                    dialog.set_release_info(release_info)
                except Exception:
                    pass
            dialog.present()
            return dialog

        dialog = UpdateDialog(None, release_info=release_info)
        self._update_dialog = dialog

        def _handle_finished(_result):
            if self._update_dialog is dialog:
                self._update_dialog = None

        dialog.finished.connect(_handle_finished)
        dialog.destroyed.connect(lambda _obj=None: self._clear_update_dialog(dialog))
        dialog.present()
        return dialog

    def _clear_update_dialog(self, dialog: Optional[UpdateDialog] = None) -> None:
        if dialog is None or dialog is self._update_dialog:
            self._update_dialog = None

    def _disable_update_capability(self) -> None:
        if not is_valid_qobject(self._update_button):
            return
        config = self._STATE_CONFIG.get("unsupported", {})
        self._update_button.setEnabled(False)
        self._update_button.setProperty("updateState", "unsupported")
        self._update_button.setProperty("releaseInfo", None)
        self._update_button.setProperty("state", config.get("attr", "unsupported"))
        self._update_button.setText(config.get("text", config["text"]))
        set_tooltip(self._update_button, config["tooltip"], 0, position="top")

        apply_button_style(self._update_button, "secondary")
        refresh_widget_style(self._update_button)

    def showEvent(self, event) -> None:
        self._apply_palette()
        super().showEvent(event)

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.PaletteChange:
            self._apply_palette()
        return super().event(event)
