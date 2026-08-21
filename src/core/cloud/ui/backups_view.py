"""Backups panel snapshot history and the manual backup control."""

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFontMetrics, QGuiApplication
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.cloud.constants import EMPTY_BACKUPS
from core.cloud.models import Snapshot, format_size, relative_time
from core.cloud.ui.icons import GEAR, SHARE, SHIELD, svg_icon
from core.ui.components.button import Button
from core.ui.components.card import Card
from core.ui.components.content_dialog import ContentDialog, ContentDialogButton
from core.ui.components.dropdown import DropDown
from core.ui.components.loader import Spinner
from core.ui.components.text_block import TextBlock
from core.ui.theme import FONT_FAMILIES, get_tokens


class ElidedLabel(QLabel):
    """A label that shortens its text to whatever width it is given. Notes are user text of
    any length and would otherwise push the actions dropdown off the card."""

    def __init__(self, text="", font_size=13, font_weight=600, color_key="text_primary", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        t = get_tokens()
        colour = t.get(color_key, t["text_primary"])
        self.setStyleSheet(f"color: {colour}; background: transparent; border: none; padding: 0px;")
        font = self.font()
        font.setFamilies(list(FONT_FAMILIES))
        font.setPixelSize(font_size)
        font.setWeight(font_weight)
        self.setFont(font)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text: str):
        self._full_text = text
        self._update_elided_text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self):
        metrics = QFontMetrics(self.font())
        super().setText(metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, max(self.width(), 10)))


class BackupItemWidget(Card):
    """One snapshot: a title, a line of details, and the actions dropdown. Holds no state
    beyond the id, so every signal carries it."""

    restore_requested = pyqtSignal(str)
    download_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    rename_requested = pyqtSignal(str)
    share_requested = pyqtSignal(str)
    unshare_requested = pyqtSignal(str)
    copy_link_requested = pyqtSignal(str)

    def __init__(self, snapshot: Snapshot, parent=None):
        super().__init__(parent)
        self.snapshot_id = snapshot.id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        device = snapshot.device_name or "Unknown PC"
        version = snapshot.app_version or "Unknown"
        note = snapshot.note.strip()
        when = relative_time(snapshot.created_at)
        size = format_size(snapshot.size_bytes)
        shared = bool(snapshot.share_url)

        t = get_tokens()
        mark = QLabel()
        mark.setPixmap(
            svg_icon(
                SHARE if shared else SHIELD, 16, t["accent_text_primary"] if shared else t["text_secondary"]
            ).pixmap(16, 16)
        )
        mark.setFixedWidth(20)
        mark.setStyleSheet("background: transparent;")
        if shared:
            mark.setToolTip("Anyone with the link can download this backup")
        layout.addWidget(mark, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        text_layout.addWidget(ElidedLabel(note, 14, 600, "text_primary"))
        text_layout.addWidget(ElidedLabel(f"{when} - {size} - {device} (v{version})", 12, 600, "text_secondary"))
        layout.addLayout(text_layout, 1)

        sharing = (
            [("copy_link", "Copy link"), ("unshare", "Stop sharing")]
            if snapshot.share_url
            else [("share", "Share publicly")]
        )
        self.menu_dropdown = DropDown(
            items=[
                ("actions", "Actions"),
                ("restore", "Restore"),
                ("download", "Save a copy"),
                *sharing,
                ("rename", "Edit note"),
                ("delete", "Delete"),
            ],
            parent=self,
        )
        self.menu_dropdown.currentChanged.connect(self._on_action_selected)
        layout.addWidget(self.menu_dropdown, alignment=Qt.AlignmentFlag.AlignVCenter)

    def set_actions_enabled(self, enabled: bool) -> None:
        self.menu_dropdown.setEnabled(enabled)

    def _on_action_selected(self, key: str):
        if key == "restore":
            self.restore_requested.emit(self.snapshot_id)
        elif key == "download":
            self.download_requested.emit(self.snapshot_id)
        elif key == "rename":
            self.rename_requested.emit(self.snapshot_id)
        elif key == "share":
            self.share_requested.emit(self.snapshot_id)
        elif key == "unshare":
            self.unshare_requested.emit(self.snapshot_id)
        elif key == "copy_link":
            self.copy_link_requested.emit(self.snapshot_id)
        elif key == "delete":
            self.delete_requested.emit(self.snapshot_id)
        else:
            return
        self._reset_dropdown()

    def _reset_dropdown(self):
        """Put the label back to "Actions" after one is picked. set_current emits, so signals
        are blocked to keep the reset out of the handler."""
        self.menu_dropdown.blockSignals(True)
        self.menu_dropdown.set_current("actions")
        self.menu_dropdown.blockSignals(False)


class BackupsView(QWidget):
    backup_now_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    restore_requested = pyqtSignal(str)
    download_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    rename_requested = pyqtSignal(str)
    share_requested = pyqtSignal(str)
    unshare_requested = pyqtSignal(str)
    copy_link_requested = pyqtSignal(str)
    load_more_requested = pyqtSignal(int)  # offset of the next page

    def __init__(self, parent=None):
        super().__init__(parent)
        self._can_write = False
        self._empty_message = EMPTY_BACKUPS
        self._running = False
        self._loading = False
        self._total = 0
        self._dialog = None
        self._init_ui()

    def _init_ui(self):
        t = get_tokens()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(TextBlock("Backups", variant="subtitle"), alignment=Qt.AlignmentFlag.AlignVCenter)
        header.addStretch()

        self.spinner_container = QWidget()
        self.spinner_container.setFixedSize(24, 24)
        spinner_layout = QHBoxLayout(self.spinner_container)
        spinner_layout.setContentsMargins(0, 0, 0, 0)
        spinner_layout.setSpacing(0)
        self.backup_spinner = Spinner(size=18, color=t["accent_fill_default"], parent=self.spinner_container)
        spinner_layout.addWidget(self.backup_spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        self.backup_spinner.hide()
        header.addWidget(self.spinner_container)

        self.backup_btn = Button("Backup Now", variant="accent")
        self.backup_btn.setFixedHeight(28)
        self.backup_btn.setEnabled(self._can_write)
        self.backup_btn.clicked.connect(self.backup_now_requested.emit)
        header.addWidget(self.backup_btn)

        # After the action, so the last thing on the row is the quiet control. padding="0"
        # because Button centres an icon in whatever the padding leaves.
        self.settings_btn = Button("", variant="default", padding="0")
        self.settings_btn.setIcon(svg_icon(GEAR, 15, t["text_primary"]))
        self.settings_btn.setIconSize(QSize(15, 15))
        self.settings_btn.setFixedSize(32, 28)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        header.addWidget(self.settings_btn)

        layout.addLayout(header)

        self.rows = QWidget()
        self.row_layout = QVBoxLayout(self.rows)
        self.row_layout.setContentsMargins(0, 0, 0, 0)
        self.row_layout.setSpacing(4)
        self.row_layout.addStretch(1)

        self.scroll = QScrollArea()
        self.scroll.setWidget(self.rows)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(f"""
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
        self.scroll.verticalScrollBar().valueChanged.connect(self._maybe_load_more)
        layout.addWidget(self.scroll)

    def set_can_write(self, can_write: bool) -> None:
        self._can_write = can_write
        self.backup_btn.setEnabled(can_write and not self._running)

    def set_busy(self, running: bool, label: str = "") -> None:
        """A backup, restore or save is under way.

        Only the button that starts one is disabled. Backup against restore is refused by
        config_lock, which is a real lock rather than a greyed-out control.
        """
        self._running = running
        self.backup_spinner.setVisible(running)
        self.backup_btn.setText(label if running and label else "Backup Now")
        self.backup_btn.setEnabled(self._can_write and not running)

    def show_error(self, message: str, title: str = "Error"):
        ContentDialog(parent=self.window() or self, title=title, content=message, close_button_text="OK").show_dialog()

    def show_share_link(self, url: str) -> None:
        self._dialog = ContentDialog(
            parent=self.window() or self,
            title="Share link",
            content=f"{url}\n\nAnyone who has this link can download this backup.",
            primary_button_text="Copy link",
            default_button=ContentDialogButton.PRIMARY,
        )
        self._dialog.primary_button_click.connect(lambda: QGuiApplication.clipboard().setText(url))
        self._dialog.show_dialog()

    def confirm(self, title: str, message: str, action: str, on_accept, *, accent_action: bool = False) -> None:
        self._dialog = ContentDialog(
            parent=self.window() or self,
            title=title,
            content=message,
            primary_button_text=action,
            close_button_text="Cancel",
            default_button=ContentDialogButton.PRIMARY if accent_action else ContentDialogButton.CLOSE,
        )
        self._dialog.primary_button_click.connect(on_accept)
        self._dialog.show_dialog()

    def _clear_rows(self) -> None:
        while self.row_layout.count() > 1:
            widget = self.row_layout.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _show_empty(self) -> None:
        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(12, 12, 12, 12)
        empty_layout.addWidget(TextBlock(self._empty_message, variant="body"))
        self.row_layout.insertWidget(self.row_layout.count() - 1, empty)

    def _rows(self) -> list[BackupItemWidget]:
        return [
            widget
            for index in range(self.row_layout.count())
            if isinstance(widget := self.row_layout.itemAt(index).widget(), BackupItemWidget)
        ]

    def _row_for(self, snapshot_id: str) -> BackupItemWidget | None:
        for widget in self._rows():
            if widget.snapshot_id == snapshot_id:
                return widget
        return None

    def _maybe_load_more(self, value: int) -> None:
        """Ask for the next page on reaching the bottom.

        `_loading` holds until the page arrives or fails, or one flick to the bottom asks for
        the same page dozens of times.
        """
        if self._loading or len(self._rows()) >= self._total:
            return
        bar = self.scroll.verticalScrollBar()
        if bar.maximum() - value > 240:
            # How near the bottom, in pixels, the next page is asked for.
            return
        self._loading = True
        self.load_more_requested.emit(len(self._rows()))

    def append_snapshots(self, snapshots: list[Snapshot], *, total: int) -> None:
        self._total = total
        self._loading = False
        for snapshot in snapshots:
            self._add_row(snapshot)
        self._fill_viewport()

    def _fill_viewport(self) -> None:
        """Ask for another page when the loaded ones do not reach the bottom of the view.

        Paging follows the scrollbar, so a first page that fits on screen never moves it.
        Deferred a tick because the layout has not measured the new rows yet.
        """
        if self._loading or len(self._rows()) >= self._total:
            return
        QTimer.singleShot(0, self._load_if_short)

    def _load_if_short(self) -> None:
        bar = self.scroll.verticalScrollBar()
        if bar.maximum() == 0:
            self._maybe_load_more(bar.value())

    def loading_failed(self) -> None:
        """Release the guard so the next scroll can try again."""
        self._loading = False

    def set_snapshots(self, snapshots: list[Snapshot], *, total: int = 0, empty_message: str = EMPTY_BACKUPS):
        self._empty_message = empty_message
        self._total = max(total, len(snapshots))
        self._loading = False
        bar = self.scroll.verticalScrollBar()
        position = bar.value()

        self._clear_rows()
        if not snapshots:
            self._show_empty()
            return

        for snapshot in snapshots:
            self._add_row(snapshot)

        self.row_layout.activate()
        bar.setValue(position)
        self._fill_viewport()

    def _add_row(self, snapshot: Snapshot, index: int | None = None) -> BackupItemWidget:
        widget = BackupItemWidget(snapshot)
        widget.restore_requested.connect(self.restore_requested.emit)
        widget.download_requested.connect(self.download_requested.emit)
        widget.rename_requested.connect(self.rename_requested.emit)
        widget.share_requested.connect(self.share_requested.emit)
        widget.unshare_requested.connect(self.unshare_requested.emit)
        widget.copy_link_requested.connect(self.copy_link_requested.emit)
        widget.delete_requested.connect(self._handle_item_delete)
        self.row_layout.insertWidget(self.row_layout.count() - 1 if index is None else index, widget)
        return widget

    def replace_row(self, snapshot: Snapshot) -> None:
        """Rebuild one card in place, for a note, a share or a revoke."""
        row = self._row_for(snapshot.id)
        if row is None:
            return
        index = self.row_layout.indexOf(row)
        self.row_layout.removeWidget(row)
        row.setParent(None)
        row.deleteLater()
        self._add_row(snapshot, index)

    def insert_row(self, snapshot: Snapshot) -> None:
        """A new backup, which is always the newest, so it goes on top."""
        if self._row_for(snapshot.id) is not None:
            return
        self._total += 1
        if not self._rows():
            self._clear_rows()  # drops the empty-state placeholder
        self._add_row(snapshot, 0)

    def remove_row(self, snapshot_id: str) -> None:
        row = self._row_for(snapshot_id)
        if row is not None:
            self.row_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        if not self._rows():
            self._show_empty()

    def _handle_item_delete(self, snapshot_id: str):
        self.confirm(
            "Delete this backup?",
            "This cannot be undone.",
            "Delete",
            lambda: self._begin_delete(snapshot_id),
        )

    def _begin_delete(self, snapshot_id: str) -> None:
        """Take this row's actions out until the server answers. Nothing else is affected."""
        row = self._row_for(snapshot_id)
        if row is None:
            return
        row.set_actions_enabled(False)
        self.delete_requested.emit(snapshot_id)

    def finish_delete(self, snapshot_id: str, ok: bool) -> None:
        if ok:
            self.remove_row(snapshot_id)
        elif (row := self._row_for(snapshot_id)) is not None:
            row.set_actions_enabled(True)
