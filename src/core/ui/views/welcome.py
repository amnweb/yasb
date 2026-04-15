import ctypes
import logging
import os
import tempfile
import winreg
import zipfile
from enum import Enum, auto
from os import makedirs, path

from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
    QThread,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import QDesktopServices, QFontDatabase
from PyQt6.QtWidgets import (
    QDialog,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.setup.builder import (
    FEATURE_GROUPS,
    OPTIONAL_GROUPS,
    WINDOW_MANAGER_GROUPS,
    build_config,
    build_styles,
)
from core.ui.components.button import Button
from core.ui.components.card import Card
from core.ui.components.content_dialog import ContentDialog, ContentDialogButton
from core.ui.components.dropdown import DropDown
from core.ui.components.indicator import StepIndicator
from core.ui.components.info_bar import InfoBar, InfoBarSeverity
from core.ui.components.link import Link
from core.ui.components.loader import Spinner
from core.ui.components.slider import Slider
from core.ui.components.text_block import TextBlock
from core.ui.components.toggle_switch import ToggleSwitchWithLabel
from core.ui.theme import get_tokens
from core.ui.views.view_base import ViewBase
from settings import (
    APP_NAME,
    DEFAULT_CONFIG_DIRECTORY,
    DEFAULT_CONFIG_FILENAME,
    DEFAULT_STYLES_FILENAME,
    GITHUB_URL,
    WEBSITE_DOCS_URL,
)

HOME_CONFIG_PATH = path.normpath(path.join(DEFAULT_CONFIG_DIRECTORY, DEFAULT_CONFIG_FILENAME))
HOME_STYLES_PATH = path.normpath(path.join(DEFAULT_CONFIG_DIRECTORY, DEFAULT_STYLES_FILENAME))

NERD_FONT_URL = "https://downloads.yasb.dev/fonts/JetBrainsMonoNerdFont/JetBrainsMono.zip"
NERD_FONT_FALLBACK_URL = "https://github.com/ryanoasis/nerd-fonts/releases/download/v3.4.0/JetBrainsMono.zip"
NERD_FONT_FAMILIES = ["JetBrainsMono NFP", "JetBrainsMono Nerd Font Propo"]
SEGOE_FLUENT_URL = "https://aka.ms/SegoeFluentIcons"
SEGOE_FLUENT_FAMILY = "Segoe Fluent Icons"

REQUIRED_FONTS = [
    {"label": "JetBrains Mono Nerd Font", "check_families": NERD_FONT_FAMILIES},
    {"label": "Segoe Fluent Icons", "check_families": [SEGOE_FLUENT_FAMILY]},
]

RESULT_SKIP = 0
RESULT_CREATED = 1
RESULT_CANCELLED = 2


class _FontState(Enum):
    IDLE = auto()
    CHECKING = auto()
    INSTALLING = auto()
    DONE = auto()


class FontCheckWorker(QThread):
    """Checks which required fonts are already installed."""

    finished = pyqtSignal(dict)

    def run(self) -> None:
        db_families = set(QFontDatabase.families())
        result = {}
        for font in REQUIRED_FONTS:
            result[font["label"]] = any(f in db_families for f in font["check_families"])
        self.finished.emit(result)


class FontInstallWorker(QThread):
    """Downloads and installs missing fonts for the current user."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, list)

    def __init__(self, install_nerd: bool = False, install_segoe: bool = False) -> None:
        super().__init__()
        self._install_nerd = install_nerd
        self._install_segoe = install_segoe
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        try:
            fonts_dir = os.path.join(
                os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Microsoft", "Windows", "Fonts"
            )
            os.makedirs(fonts_dir, exist_ok=True)
            installed: list[str] = []

            if self._install_nerd:
                if self._stop:
                    self.finished.emit(False, "Installation cancelled.", [])
                    return
                self.progress.emit("Downloading JetBrains Mono Nerd Font...")
                nerd_url = self._resolve_nerd_font_url()
                nerd_paths = self._download_and_extract_zip(nerd_url, fonts_dir)
                if self._stop:
                    self.finished.emit(False, "Installation cancelled.", nerd_paths)
                    return
                self.progress.emit("Installing JetBrains Mono Nerd Font...")
                self._install_fonts(nerd_paths)
                installed.extend(nerd_paths)

            if self._install_segoe:
                if self._stop:
                    self.finished.emit(False, "Installation cancelled.", installed)
                    return
                self.progress.emit("Downloading Segoe Fluent Icons...")
                segoe_paths = self._download_and_extract_zip(SEGOE_FLUENT_URL, fonts_dir)
                if self._stop:
                    self.finished.emit(False, "Installation cancelled.", installed)
                    return
                self.progress.emit("Installing Segoe Fluent Icons...")
                self._install_fonts(segoe_paths)
                installed.extend(segoe_paths)

            if self._stop:
                self.finished.emit(False, "Installation cancelled.", installed)
                return

            self.progress.emit("Finalizing installation...")
            try:
                ctypes.windll.user32.SendNotifyMessageW(0xFFFF, 0x001D, 0, 0)
            except Exception:
                pass
            self.finished.emit(True, "All fonts installed successfully.", installed)
        except Exception as exc:
            self.finished.emit(False, self._urllib_error(exc), [])

    def _resolve_nerd_font_url(self) -> str:
        import urllib.request

        # Try primary CDN first
        try:
            req = urllib.request.Request(NERD_FONT_URL, method="HEAD", headers={"User-Agent": "YASB-Setup"})
            with urllib.request.urlopen(req, timeout=10):
                return NERD_FONT_URL
        except Exception:
            return NERD_FONT_FALLBACK_URL

    def _download_and_extract_zip(self, url: str, fonts_dir: str) -> list[str]:
        import urllib.request

        fd, tmp_zip = tempfile.mkstemp(suffix=".zip")
        try:
            os.close(fd)
            req = urllib.request.Request(url, headers={"User-Agent": "YASB-Setup"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                with open(tmp_zip, "wb") as f:
                    f.write(resp.read())

            installed: list[str] = []
            with zipfile.ZipFile(tmp_zip) as zf:
                for name in zf.namelist():
                    if self._stop:
                        break
                    lower = name.lower()
                    if not lower.endswith((".ttf", ".otf")):
                        continue
                    if lower.endswith("windowscompatible.ttf"):
                        continue
                    basename = os.path.basename(name)
                    if not basename:
                        continue
                    dest = os.path.join(fonts_dir, basename)
                    if not os.path.exists(dest):
                        with zf.open(name) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                    installed.append(dest)
            return installed
        finally:
            try:
                os.remove(tmp_zip)
            except OSError:
                pass

    @staticmethod
    def _urllib_error(exc: Exception) -> str:
        import urllib.error

        if isinstance(exc, urllib.error.URLError):
            reason = getattr(exc, "reason", "")
            if isinstance(reason, OSError) and reason.errno == 11001:
                return "Unable to connect. Check your internet connection and try again."
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                return "Connection timed out. Please check your network and try again."
            return "Unable to download fonts. Check your internet connection and try again."
        if isinstance(exc, OSError):
            s = str(exc)
            if s.startswith("HTTP "):
                return f"Download failed ({s}). The file may no longer be available."
            if getattr(exc, "errno", None) == 13 or getattr(exc, "winerror", None) == 5:
                return "Permission denied. Close any apps using the font and try again."
            return "A file system error occurred while installing fonts."
        if isinstance(exc, TimeoutError):
            return "Connection timed out. Please check your network and try again."
        return "An unexpected error occurred while installing fonts."

    def _install_fonts(self, paths: list[str]) -> None:
        for dest in paths:
            if self._stop:
                break
            basename = os.path.basename(dest)
            self._register(basename, dest)
            QFontDatabase.addApplicationFont(dest)

    @staticmethod
    def _register(font_name: str, dest: str) -> None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts", 0, winreg.KEY_SET_VALUE
            ) as reg_key:
                winreg.SetValueEx(reg_key, os.path.splitext(font_name)[0] + " (TrueType)", 0, winreg.REG_SZ, dest)
        except OSError:
            pass
        try:
            ctypes.windll.gdi32.AddFontResourceExW(dest, 0, None)
        except Exception:
            pass


def run_setup_wizard() -> bool:
    """Run the setup wizard. Returns True if completed or skipped, False if cancelled."""

    wizard = WelcomeWizard()
    wizard.exec()
    return wizard.result_code != RESULT_CANCELLED


class WelcomeWizard(ViewBase, QDialog):
    def __init__(self) -> None:
        super().__init__()
        self._result_code = RESULT_CANCELLED
        self._selected_wm: str = "none"
        self._wm_cards: dict[str, Card] = {}
        self._feature_selected: dict[str, bool] = {key: False for key, *_ in FEATURE_GROUPS}
        self._feature_cards: dict[str, Card] = {}
        self._option_selected: dict[str, bool] = {"blur": True}
        self._bar_style: str = "floating"
        self._bar_opacity: int = 85
        self._screen_selected: str = "*"
        self._font_state = _FontState.IDLE
        self._font_check_worker: FontCheckWorker | None = None
        self._font_worker: FontInstallWorker | None = None
        self._fonts_missing: dict[str, bool] = {}
        self._font_status_labels: dict[str, TextBlock] = {}
        self._anim_group: QParallelAnimationGroup | None = None
        self._anim_target: int = 0
        self._build_window()
        self._build_ui()

    def _build_window(self) -> None:
        self.setObjectName("WelcomeWizard")
        self.setWindowTitle(f"Welcome to {APP_NAME}")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedSize(900, 580)
        self.build_view()
        self._app_icon = self.build_app_icon()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self._stack = QStackedWidget()
        root_layout.addWidget(self._stack, 1)
        for builder in (
            self._page_welcome,
            self._page_fonts,
            self._page_wm,
            self._page_optional,
            self._page_bar_options,
            self._page_summary,
        ):
            self._stack.addWidget(builder())
        self._stack.currentChanged.connect(self._on_page_changed)
        self._step_indicator = StepIndicator(count=self._stack.count())
        indicator_container = QWidget()
        indicator_container.setFixedHeight(32)
        indicator_layout = QHBoxLayout(indicator_container)
        indicator_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        indicator_layout.setContentsMargins(0, 0, 0, 0)
        indicator_layout.addWidget(self._step_indicator)
        root_layout.addWidget(indicator_container)

    def _header(self, layout: QVBoxLayout, title: str, desc: str, spacing: int = 24) -> None:
        title_label = TextBlock(title, variant="subtitle")
        layout.addWidget(title_label)
        layout.addSpacing(4)
        desc_label = TextBlock(desc, variant="caption")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        layout.addSpacing(spacing)

    def _card(self, key, label: str, desc: str, on_click, registry: dict) -> Card:
        card = Card()
        card.setFixedHeight(90)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(2)
        for text, cls in ((label, "body-strong"), (desc, "caption")):
            card_label = TextBlock(text, variant=cls)
            card_label.setWordWrap(cls == "caption")
            card_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            card_layout.addWidget(card_label)
        card.mousePressEvent = lambda _ev, k=key: on_click(k)
        registry[key] = card
        return card

    def _nav(self, back_page: int, next_page: int) -> QHBoxLayout:
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(12)
        back_btn = Button("Back", padding="24,8,24,8")
        back_btn.clicked.connect(lambda: self._go(back_page))
        nav_layout.addWidget(back_btn)
        nav_layout.addStretch()
        next_btn = Button("Next", variant="accent", padding="24,8,24,8")
        next_btn.clicked.connect(lambda: self._go(next_page))
        nav_layout.addWidget(next_btn)
        return nav_layout

    @staticmethod
    def _link(text: str, on_click) -> Link:
        link = Link(text)
        link.clicked.connect(on_click)
        return link

    def _toggle_row(self, title: str, desc: str, option_key: str, checked: bool = True) -> Card:
        row_frame = Card()
        row_layout = QHBoxLayout(row_frame)
        row_layout.setContentsMargins(16, 14, 16, 14)
        row_layout.setSpacing(12)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        title_label = TextBlock(title, variant="body-strong")
        text_layout.addWidget(title_label)
        desc_label = TextBlock(desc, variant="caption")
        text_layout.addWidget(desc_label)
        row_layout.addLayout(text_layout)
        row_layout.addStretch()
        toggle = ToggleSwitchWithLabel(on_text="On", off_text="Off", checked=checked)
        toggle.toggled.connect(lambda val, k=option_key: self._option_selected.__setitem__(k, val))
        row_layout.addWidget(toggle)
        return row_frame

    def _option_row(self, title: str, desc: str, widget: QWidget) -> Card:
        row_frame = Card()
        row_layout = QHBoxLayout(row_frame)
        row_layout.setContentsMargins(16, 14, 16, 14)
        row_layout.setSpacing(12)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        title_label = TextBlock(title, variant="body-strong")
        text_layout.addWidget(title_label)
        desc_label = TextBlock(desc, variant="caption")
        text_layout.addWidget(desc_label)
        row_layout.addLayout(text_layout)
        row_layout.addStretch()
        row_layout.addWidget(widget)
        return row_frame

    def _show_dialog(
        self,
        title: str,
        content: str,
        primary_text: str = "",
        close_text: str = "OK",
        default: ContentDialogButton = ContentDialogButton.CLOSE,
    ) -> ContentDialog:
        return ContentDialog(
            parent=self,
            title=title,
            content=content,
            primary_button_text=primary_text,
            close_button_text=close_text,
            default_button=default,
        )

    def _radio(self, registry: dict, key) -> None:
        for card_key, card in registry.items():
            card.set_selected(card_key == key)

    def _card_grid_page(
        self,
        title: str,
        desc: str,
        entries: list[tuple[str, str, str]],
        cols: int,
        on_click,
        registry: dict,
        back_page: int,
        next_page: int,
        default: str | None = None,
    ) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(40, 28, 40, 20)
        page_layout.setSpacing(0)
        self._header(page_layout, title, desc)
        grid = QGridLayout()
        grid.setSpacing(8)
        for col in range(cols):
            grid.setColumnStretch(col, 1)
        for idx, (key, label, card_desc) in enumerate(entries):
            grid.addWidget(self._card(key, label, card_desc, on_click, registry), idx // cols, idx % cols)
        page_layout.addLayout(grid)
        if default is not None:
            on_click(default)
        page_layout.addStretch()
        page_layout.addLayout(self._nav(back_page, next_page))
        return page

    def _page_welcome(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(48, 40, 48, 24)
        page_layout.setSpacing(0)
        page_layout.addStretch(2)
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if not self._app_icon.isNull():
            icon_label.setPixmap(self._app_icon.pixmap(128, 128))
        page_layout.addWidget(icon_label)
        page_layout.addSpacing(16)
        title_label = TextBlock(f"Welcome to {APP_NAME}", variant="title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_layout.addWidget(title_label)
        page_layout.addSpacing(16)
        subtitle_label = TextBlock(
            "Let's get your bar set up. Some essential widgets are already included.\nYou can customise everything later in the config file.",
            variant="body-secondary",
        )
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setWordWrap(True)
        page_layout.addWidget(subtitle_label)
        page_layout.addStretch(3)
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(12)
        buttons_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        start_btn = Button("Get Started", variant="accent", padding="32,12,32,12", font_size=16)
        start_btn.clicked.connect(lambda: self._go(1))
        buttons_layout.addWidget(start_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        buttons_layout.addWidget(
            self._link("Skip and create minimal configuration", self._on_skip), alignment=Qt.AlignmentFlag.AlignCenter
        )
        page_layout.addLayout(buttons_layout)
        page_layout.addSpacing(8)
        return page

    def _page_fonts(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(40, 28, 40, 20)
        page_layout.setSpacing(0)
        self._header(
            page_layout,
            "Fonts & Icons",
            "YASB requires specific fonts for the bar and UI icons. Missing fonts will be downloaded and installed for your user account.",
            spacing=16,
        )

        self._font_results_container = QWidget()
        self._font_results_container.setVisible(False)
        results_layout = QVBoxLayout(self._font_results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(8)
        for font in REQUIRED_FONTS:
            row = Card()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(16, 14, 16, 14)
            row_layout.setSpacing(12)
            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)
            title_label = TextBlock(font["label"], variant="body-strong")
            text_layout.addWidget(title_label)
            desc = (
                "Bar font with 10,000+ icons from popular icon sets"
                if "Nerd" in font["label"]
                else "System icon font used for UI elements"
            )
            desc_label = TextBlock(desc, variant="caption")
            text_layout.addWidget(desc_label)
            row_layout.addLayout(text_layout)
            row_layout.addStretch()
            status_label = TextBlock("", variant="caption")
            self._font_status_labels[font["label"]] = status_label
            row_layout.addWidget(status_label)
            results_layout.addWidget(row)
        page_layout.addWidget(self._font_results_container)
        page_layout.addSpacing(16)

        spinner_row = QHBoxLayout()
        spinner_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner_row.setSpacing(8)
        self._font_spinner = Spinner(size=20, color=get_tokens()["text_secondary"], pen_width=2)
        self._font_spinner.setVisible(False)
        spinner_row.addWidget(self._font_spinner)
        self._font_status = TextBlock("", variant="caption")
        self._font_status.setFixedHeight(20)
        spinner_row.addWidget(self._font_status)
        page_layout.addLayout(spinner_row)
        page_layout.addStretch(1)

        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(12)
        self._font_back_btn = Button("Back", padding="24,8,24,8")
        self._font_back_btn.clicked.connect(lambda: self._go(0))
        nav_layout.addWidget(self._font_back_btn)
        nav_layout.addStretch()
        self._font_install_btn = Button("Install", variant="accent", padding="24,8,24,8")
        self._font_install_btn.setVisible(False)
        self._font_install_btn.clicked.connect(self._on_font_install_clicked)
        nav_layout.addWidget(self._font_install_btn)
        self._font_next = Button("Next", variant="accent", padding="24,8,24,8")
        self._font_next.setEnabled(False)
        self._font_next.clicked.connect(lambda: self._go(2))
        nav_layout.addWidget(self._font_next)
        page_layout.addLayout(nav_layout)
        return page

    def _page_wm(self) -> QWidget:
        entries = [*WINDOW_MANAGER_GROUPS, ("none", "Skip", "I don't use a tiling window manager")]

        def on_wm(wm_key: str) -> None:
            self._selected_wm = wm_key
            self._radio(self._wm_cards, wm_key)

        return self._card_grid_page(
            "Tiling Window Manager",
            "A tiling window manager automatically arranges your windows.\nYASB can show workspaces and controls for Komorebi and GlazeWM. If you don't use one, select Skip.",
            entries,
            2,
            on_wm,
            self._wm_cards,
            1,
            3,
            default="none",
        )

    def _page_optional(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(40, 28, 40, 20)
        page_layout.setSpacing(0)
        self._header(
            page_layout,
            "Optional Widgets",
            "Choose additional widgets to add to your bar. Essential widgets are included by default.",
        )
        grid = QGridLayout()
        grid.setSpacing(8)
        cols = 3
        for col in range(cols):
            grid.setColumnStretch(col, 1)
        entries = list(OPTIONAL_GROUPS)
        on_click = lambda feature_key: self._toggle_select(feature_key)
        for idx, (key, label, card_desc) in enumerate(entries):
            grid.addWidget(self._card(key, label, card_desc, on_click, self._feature_cards), idx // cols, idx % cols)
        page_layout.addLayout(grid)
        page_layout.addSpacing(12)
        page_layout.addWidget(
            InfoBar(
                "",
                "Quick Launch is configured to show on <b>Alt+Space</b>.",
                InfoBarSeverity.INFORMATIONAL,
            )
        )
        page_layout.addStretch()
        page_layout.addLayout(self._nav(2, 4))
        return page

    def _toggle_select(self, key: str) -> None:
        self._feature_selected[key] = not self._feature_selected[key]
        self._feature_cards[key].set_selected(self._feature_selected[key])

    def _page_bar_options(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(40, 28, 40, 20)
        page_layout.setSpacing(0)
        self._header(
            page_layout, "Display & Effects", "Choose which screen to show the bar on and configure visual effects."
        )

        screen_dd = DropDown(items=[("*", "All screens"), ("primary", "Primary")])
        screen_dd.set_current("*")
        screen_dd.currentChanged.connect(lambda key: setattr(self, "_screen_selected", key))

        page_layout.addWidget(
            self._option_row(
                "Show bar on",
                "Select which monitor displays the bar",
                screen_dd,
            )
        )

        page_layout.addSpacing(4)
        style_dd = DropDown(items=[("floating", "Floating"), ("taskbar", "Taskbar")])
        style_dd.set_current("floating")
        style_dd.currentChanged.connect(lambda key: setattr(self, "_bar_style", key))
        page_layout.addWidget(
            self._option_row(
                "Bar style",
                "Floating adds spacing around the bar, taskbar sits flush against the edge.",
                style_dd,
            )
        )

        page_layout.addSpacing(4)
        page_layout.addWidget(
            self._toggle_row(
                "Enable blur effect", "Applies a blur-behind effect to the background of the bar.", "blur", checked=True
            )
        )

        page_layout.addSpacing(4)
        opacity_slider = Slider(minimum=0, maximum=100, value=self._bar_opacity, suffix="%")
        opacity_slider.valueChanged.connect(lambda v: setattr(self, "_bar_opacity", v))
        page_layout.addWidget(
            self._option_row(
                "Bar opacity",
                "Set the background opacity of the bar.",
                opacity_slider,
            )
        )

        page_layout.addStretch()
        page_layout.addLayout(self._nav(3, 5))
        return page

    def _page_summary(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(48, 40, 48, 24)
        page_layout.setSpacing(0)
        page_layout.addStretch(2)
        title_label = TextBlock("All Set!", variant="title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_layout.addWidget(title_label)
        page_layout.addSpacing(12)
        tip_label = TextBlock(
            "Visit the documentation to learn more about customization and styling.", variant="caption"
        )
        tip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip_label.setWordWrap(True)
        page_layout.addWidget(tip_label)
        page_layout.addSpacing(8)
        links_layout = QHBoxLayout()
        links_layout.setSpacing(8)
        links_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        links_layout.addWidget(self._link("GitHub Wiki", lambda: QDesktopServices.openUrl(QUrl(f"{GITHUB_URL}/wiki"))))
        links_layout.addWidget(self._link("Documentation", lambda: QDesktopServices.openUrl(QUrl(WEBSITE_DOCS_URL))))
        page_layout.addLayout(links_layout)
        page_layout.addStretch(3)
        start_btn = Button("Start YASB", variant="accent", padding="32,12,32,12", font_size=16)
        start_btn.clicked.connect(self._on_create)
        page_layout.addWidget(start_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        page_layout.addSpacing(12)
        page_layout.addWidget(self._link("Back", lambda: self._go(4)), alignment=Qt.AlignmentFlag.AlignCenter)
        page_layout.addSpacing(8)
        return page

    def _on_page_changed(self, index: int) -> None:
        if index != 1:
            return
        if self._font_state == _FontState.DONE:
            return
        if self._font_state == _FontState.IDLE:
            self._start_font_check()

    def _start_font_check(self) -> None:
        self._font_state = _FontState.CHECKING
        self._font_spinner.setVisible(True)
        self._font_status.setText("Checking requirements...")
        self._font_check_worker = FontCheckWorker()
        self._font_check_worker.finished.connect(self._on_font_check_done)
        self._font_check_worker.start()

    def _on_font_check_done(self, results: dict) -> None:
        self._font_spinner.setVisible(False)
        self._font_status.setText("")
        self._font_check_worker = None

        self._fonts_missing = {}
        all_installed = True
        for font in REQUIRED_FONTS:
            label = font["label"]
            installed = results.get(label, False)
            self._fonts_missing[label] = not installed
            status = self._font_status_labels.get(label)
            if status:
                if installed:
                    status.setText("Installed")
                else:
                    status.setText("Will be installed")
                    all_installed = False

        self._font_results_container.setVisible(True)

        if all_installed:
            self._font_state = _FontState.DONE
            self._font_next.setEnabled(True)
            self._font_install_btn.setVisible(False)
        else:
            self._font_state = _FontState.IDLE
            self._font_install_btn.setVisible(True)
            self._font_next.setEnabled(False)

    def _on_font_install_clicked(self) -> None:
        if self._font_state == _FontState.INSTALLING:
            return
        install_nerd = self._fonts_missing.get("JetBrains Mono Nerd Font", False)
        install_segoe = self._fonts_missing.get("Segoe Fluent Icons", False)
        if not install_nerd and not install_segoe:
            self._font_state = _FontState.DONE
            self._font_next.setEnabled(True)
            self._font_install_btn.setVisible(False)
            return
        self._font_state = _FontState.INSTALLING
        self._font_install_btn.setEnabled(False)
        self._font_back_btn.setEnabled(False)
        self._font_spinner.setVisible(True)
        self._font_status.setText("")
        self._font_worker = FontInstallWorker(install_nerd=install_nerd, install_segoe=install_segoe)
        self._font_worker.progress.connect(self._font_status.setText)
        self._font_worker.finished.connect(self._on_font_finished)
        self._font_worker.start()

    def _on_font_finished(self, success: bool, msg: str, paths: list) -> None:
        self._font_spinner.setVisible(False)
        self._font_back_btn.setEnabled(True)
        self._font_install_btn.setEnabled(True)
        if success:
            self._font_state = _FontState.DONE
            self._font_install_btn.setVisible(False)
            self._font_next.setEnabled(True)
            self._font_status.setText("")
            for label, status_lbl in self._font_status_labels.items():
                status_lbl.setText("Installed")
            self._go(2)
        else:
            self._font_state = _FontState.IDLE
            self._font_status.setText("")
            dlg = self._show_dialog(
                "Font Installation Failed",
                f"{msg}\n\nYou can retry.",
                primary_text="Retry",
                close_text="OK",
                default=ContentDialogButton.PRIMARY,
            )
            dlg.primary_button_click.connect(self._on_font_install_clicked)
            dlg.show_dialog()

    def _finish_animation(self) -> None:
        if self._anim_group is not None:
            self._anim_group.stop()
            for i in range(self._stack.count()):
                w = self._stack.widget(i)
                w.move(0, 0)
                w.setGraphicsEffect(None)
            self._stack.setCurrentIndex(self._anim_target)
            self._anim_group = None

    def _go(self, index: int) -> None:
        self._finish_animation()
        current_idx = self._stack.currentIndex()
        current_page = self._stack.currentWidget()
        target_page = self._stack.widget(index)
        if current_page is not target_page:
            offset = 200 if index > current_idx else -200
            self._stack.setCurrentIndex(index)
            target_page.setGeometry(current_page.geometry())
            target_page.move(offset, 0)
            fade_effect = QGraphicsOpacityEffect(target_page)
            fade_effect.setOpacity(0.0)
            target_page.setGraphicsEffect(fade_effect)
            target_page.show()
            self._anim_target = index
            self._anim_group = QParallelAnimationGroup(self)
            # Fade in
            fade_anim = QPropertyAnimation(fade_effect, b"opacity")
            fade_anim.setDuration(300)
            fade_anim.setStartValue(0.0)
            fade_anim.setEndValue(1.0)
            fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim_group.addAnimation(fade_anim)
            # Slide in horizontally
            slide_anim = QPropertyAnimation(target_page, b"pos")
            slide_anim.setDuration(300)
            slide_anim.setStartValue(QPoint(offset, 0))
            slide_anim.setEndValue(QPoint(0, 0))
            slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim_group.addAnimation(slide_anim)
            self._anim_group.finished.connect(self._on_anim_finished)
            self._anim_group.start()
        self._update_dots(index)

    def _on_anim_finished(self) -> None:
        if self._anim_group is None:
            return
        for i in range(self._stack.count()):
            w = self._stack.widget(i)
            w.move(0, 0)
            w.setGraphicsEffect(None)
        self._stack.setCurrentIndex(self._anim_target)
        self._anim_group.deleteLater()
        self._anim_group = None

    def _update_dots(self, current: int) -> None:
        self._step_indicator.set_current(current)

    def _collect_selections(self) -> list[str]:
        groups = ["base"]
        if self._selected_wm != "none" and self._selected_wm in {k for k, *_ in WINDOW_MANAGER_GROUPS}:
            groups.append(self._selected_wm)
        groups.extend(k for k, v in self._feature_selected.items() if v)
        return groups

    def _write_config(
        self,
        groups: list[str] | None = None,
        overrides: dict | None = None,
    ) -> None:
        if not path.isdir(DEFAULT_CONFIG_DIRECTORY):
            makedirs(DEFAULT_CONFIG_DIRECTORY)
        with open(HOME_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(build_config(groups, overrides))
        logging.info("Created config file at %s", HOME_CONFIG_PATH)
        with open(HOME_STYLES_PATH, "w", encoding="utf-8") as f:
            f.write(
                build_styles(
                    groups,
                    bar_opacity=(overrides or {}).get("bar_opacity", 100),
                    bar_style=(overrides or {}).get("bar_style", "taskbar"),
                )
            )
        logging.info("Created styles file at %s", HOME_STYLES_PATH)

    def _on_skip(self) -> None:
        if self._try_write_config(None):
            self._result_code = RESULT_SKIP
            self.accept()

    def _on_create(self) -> None:
        groups = self._collect_selections()
        overrides = {
            "screens": [self._screen_selected],
            "bar_style": self._bar_style,
            "blur_enabled": self._option_selected["blur"],
            "bar_opacity": self._bar_opacity,
        }
        if self._try_write_config(groups, overrides):
            self._result_code = RESULT_CREATED
            self.accept()

    def _try_write_config(
        self,
        groups: list[str] | None = None,
        overrides: dict | None = None,
    ) -> bool:
        try:
            self._write_config(groups, overrides)
            return True
        except Exception as exc:
            self._show_dialog(
                "Configuration Error",
                f"Failed to save configuration:\n{exc}",
            ).show_dialog()
            return False

    @property
    def result_code(self) -> int:
        return self._result_code

    def closeEvent(self, event) -> None:
        if self._font_check_worker is not None and self._font_check_worker.isRunning():
            self._font_check_worker.finished.disconnect()
        if self._font_worker is not None and self._font_worker.isRunning():
            self._font_worker.progress.disconnect()
            self._font_worker.finished.disconnect()
            self._font_worker.request_stop()
        if self._result_code == RESULT_CANCELLED:
            self.reject()
        super().closeEvent(event)
