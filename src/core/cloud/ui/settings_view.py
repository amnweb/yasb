"""Settings panel"""

from pathlib import Path

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from core.cloud.constants import APP_LOG_FILE, MAX_EXCLUDE_RULES
from core.cloud.session import cloud_dir
from core.cloud.settings import Settings, clean_rules
from core.cloud.snapshot import ALWAYS_INCLUDE
from core.cloud.ui.icons import BACK, svg_icon
from core.ui.components.button import Button
from core.ui.components.card import Card
from core.ui.components.info_bar import InfoBar, InfoBarSeverity
from core.ui.components.link import Link
from core.ui.components.text_block import TextBlock
from core.ui.components.toggle_switch import ToggleSwitchWithLabel
from core.ui.theme import FONT_FAMILIES, get_tokens

# The card's two descriptions. A switch that will not move says nothing about why, so the
# second names the reason and the limit of it.
AUTO_BACKUP_DESCRIPTION = "Back up your configuration shortly after you change it"
AUTO_BACKUP_NEEDS_PLAN = "Needs an active subscription. Your exclude rules are kept either way."


def label(text: str, font_size: int = 14, font_weight: int = 600, color_key: str = "text_primary") -> QLabel:
    """A label taking the same four arguments the backups rows use, but wrapping rather
    than eliding, because these are whole sentences."""
    t = get_tokens()
    widget = QLabel(text)
    widget.setStyleSheet(f"color: {t.get(color_key, t['text_primary'])}; background: transparent;")
    font = widget.font()
    font.setFamilies(list(FONT_FAMILIES))
    font.setPixelSize(font_size)
    font.setWeight(QFont.Weight(font_weight))
    widget.setFont(font)
    widget.setWordWrap(True)
    return widget


class SettingCard(Card):
    def __init__(
        self,
        title: str,
        description: str,
        control: QWidget,
        parent: QWidget | None = None,
        title_size: int = 14,
        title_weight: int = 600,
        title_color: str = "text_primary",
        description_size: int = 12,
        description_weight: int = 600,
        description_color: str = "text_secondary",
    ) -> None:
        super().__init__(parent, hover=False)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 16, 16, 16)
        row.setSpacing(12)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)
        self.title = label(title, title_size, title_weight, title_color)
        self.description = label(description, description_size, description_weight, description_color)
        text.addWidget(self.title)
        text.addWidget(self.description)
        row.addLayout(text, 1)

        row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)


class RuleRow(Card):
    removed = pyqtSignal(str)

    def __init__(self, rule: str, parent: QWidget | None = None) -> None:
        super().__init__(parent, hover=False)
        self.rule = rule

        row = QHBoxLayout(self)
        row.setContentsMargins(18, 8, 8, 8)
        row.setSpacing(8)
        row.addWidget(label(rule, 14, 600, "text_primary"), 1)

        remove = Button("Remove", variant="default", font_size=13)
        remove.setFixedHeight(24)
        remove.clicked.connect(lambda: self.removed.emit(self.rule))
        row.addWidget(remove)


class ExcludedFilesCard(Card):
    rules_changed = pyqtSignal(list)
    preview_requested = pyqtSignal()
    add_requested = pyqtSignal()
    docs_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, hover=False)
        self._rules: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        heading = QVBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(2)
        heading.addWidget(label("Excluded files", 14, 600, "text_primary"))
        heading.addWidget(label("Files and folders left out of every backup", 12, 600, "text_secondary"))
        header.addLayout(heading, 1)

        preview = Button("Preview", variant="default")
        preview.setFixedHeight(28)
        preview.clicked.connect(self.preview_requested.emit)
        header.addWidget(preview, 0, Qt.AlignmentFlag.AlignVCenter)

        add = Button("Add rule", variant="accent")
        add.setFixedHeight(28)
        add.clicked.connect(self.add_requested.emit)
        header.addWidget(add, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header)

        # Only the rule that silently overrides what the user typed. The rest is a link.
        always = " and ".join(sorted(ALWAYS_INCLUDE))
        layout.addWidget(
            label(
                f"Logs, caches and temporary files are already excluded. {always} are always kept.",
                12,
                600,
                "text_secondary",
            )
        )

        docs = Link("Learn more", font_size=13, font_weight="demibold")
        docs.clicked.connect(self.docs_requested.emit)
        layout.addWidget(docs, 0, Qt.AlignmentFlag.AlignLeft)

        self.info = InfoBar("", "", InfoBarSeverity.WARNING, parent=self)
        self.info.hide()
        layout.addWidget(self.info)

        self._rule_box = QVBoxLayout()
        self._rule_box.setContentsMargins(0, 0, 0, 0)
        self._rule_box.setSpacing(1)
        layout.addLayout(self._rule_box)

        self._rebuild()

    def set_rules(self, rules: tuple[str, ...]) -> None:
        self._rules = list(rules)
        self._rebuild()

    def show_message(self, title: str, message: str, severity: InfoBarSeverity) -> None:
        self.info.set_severity(severity)
        self.info.set_title(title)
        self.info.set_message(message)
        self.info.show()

    def _rebuild(self) -> None:
        while self._rule_box.count():
            widget = self._rule_box.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if not self._rules:
            self._rule_box.addWidget(label("No patterns yet", 12, 600, "text_secondary"))

        for rule in self._rules:
            row = RuleRow(rule)
            row.removed.connect(self._remove)
            self._rule_box.addWidget(row)

    def add_rule(self, rule: str) -> None:
        rule = rule.strip()
        if not rule or rule in self._rules:
            return
        if len(self._rules) >= MAX_EXCLUDE_RULES:
            self.show_message("Too many rules", f"The limit is {MAX_EXCLUDE_RULES}.", InfoBarSeverity.WARNING)
            return

        self._rules = list(clean_rules([*self._rules, rule]))
        self._rebuild()
        self.rules_changed.emit(list(self._rules))

    def _remove(self, rule: str) -> None:
        self._rules = [existing for existing in self._rules if existing != rule]
        self._rebuild()
        self.rules_changed.emit(list(self._rules))


class SettingsView(QWidget):
    """Holds no settings of its own; the window owns them and does the saving."""

    back_requested = pyqtSignal()
    rules_changed = pyqtSignal(list)
    auto_backup_changed = pyqtSignal(bool)
    debug_logging_changed = pyqtSignal(bool)
    preview_requested = pyqtSignal()
    add_rule_requested = pyqtSignal()
    docs_requested = pyqtSignal()
    open_log_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._suppress_toggle = False
        self._can_write = False  # until an account says otherwise, inert is the safe default
        self._init_ui()

    def _init_ui(self) -> None:
        t = get_tokens()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(TextBlock("Settings", variant="subtitle"), alignment=Qt.AlignmentFlag.AlignVCenter)
        header.addStretch()
        back = Button("", variant="default", padding="0")
        back.setIcon(svg_icon(BACK, 14, t["text_primary"]))
        back.setIconSize(QSize(14, 14))
        back.setFixedSize(32, 28)
        back.setToolTip("Back")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        root.addLayout(header)

        self.excluded = ExcludedFilesCard()
        self.excluded.rules_changed.connect(self.rules_changed)
        self.excluded.preview_requested.connect(self.preview_requested)
        self.excluded.add_requested.connect(self.add_rule_requested)
        self.excluded.docs_requested.connect(self.docs_requested)

        self.auto_switch = ToggleSwitchWithLabel(on_text="On", off_text="Off")
        self.auto_switch.toggled.connect(self._on_auto_toggled)
        self._auto_card = SettingCard(
            "Automatic backup",
            AUTO_BACKUP_DESCRIPTION,
            self.auto_switch,
        )

        self.debug_switch = ToggleSwitchWithLabel(on_text="On", off_text="Off")
        self.debug_switch.toggled.connect(self._on_debug_toggled)
        debug = SettingCard(
            "Detailed logging",
            "Record everything the app does, not only problems. Turn on before reporting a bug.",
            self.debug_switch,
        )

        open_log = Button("Open", variant="default")
        open_log.setFixedHeight(28)
        open_log.clicked.connect(self.open_log_requested.emit)
        log = SettingCard("Log file", str(Path(cloud_dir()) / APP_LOG_FILE), open_log)

        body = QWidget()
        cards = QVBoxLayout(body)
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setSpacing(4)
        cards.addWidget(self.excluded)
        cards.addWidget(self._auto_card)
        cards.addWidget(debug)
        cards.addWidget(log)
        cards.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(body)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
            QScrollBar:vertical {{
                border: none; background: transparent; width: 4px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {t["control_strong_fill_default"]}; border-radius: 2px; min-height: 28px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {t["text_secondary"]}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)
        root.addWidget(scroll)

    def set_can_write(self, can_write: bool) -> None:
        self._can_write = can_write
        self.auto_switch.setEnabled(can_write)
        self._auto_card.description.setText(AUTO_BACKUP_DESCRIPTION if can_write else AUTO_BACKUP_NEEDS_PLAN)

    def _on_debug_toggled(self, checked: bool) -> None:
        if not self._suppress_toggle:
            self.debug_logging_changed.emit(checked)

    def _on_auto_toggled(self, checked: bool) -> None:
        if not self._suppress_toggle and self._can_write:
            self.auto_backup_changed.emit(checked)

    def set_settings(self, settings: Settings) -> None:
        self.excluded.set_rules(settings.exclude)
        self._suppress_toggle = True
        try:
            self.auto_switch.setChecked(settings.auto_backup)
            self.debug_switch.setChecked(settings.debug_logging)
        finally:
            self._suppress_toggle = False

    def add_rule(self, rule: str) -> None:
        self.excluded.add_rule(rule)

    def show_preview(self, excluded: int, total: int, saved: str) -> None:
        if excluded:
            message = f"{excluded} of {total} files would be left out, saving {saved}."
        else:
            message = "Your rules do not match anything in the configuration folder."
        self.excluded.show_message("Preview", message, InfoBarSeverity.INFORMATIONAL)
