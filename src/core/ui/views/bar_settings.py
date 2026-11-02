"""On-demand settings for existing bars; no polling, service, or new dependencies."""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.utils.settings_editor import SECTIONS, SettingsDocument

DATE_FORMATS = {
    "Weekday, day and month": "%a %d %b",
    "Year-month-day": "%Y-%m-%d",
    "Month/day/year": "%m/%d/%Y",
    "Day/month/year": "%d/%m/%Y",
    "No date": "",
}


class BarSettingsDialog(QDialog):
    def __init__(self, directory: Path, reload_callback=None, fixed_height: int | None = None, windhawk_dock=False):
        super().__init__()
        self.document = SettingsDocument(directory)
        self.reload_callback = reload_callback
        self.fixed_height = fixed_height
        self._loaded_bar = None
        self._loaded_clock = None
        self.setWindowTitle("YASB · Bar settings")
        self.resize(680, 630)
        self.setMinimumSize(600, 520)
        self.setStyleSheet("QTabWidget::pane { border: 0; } QLabel#hint { color: #888; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        title = QLabel("Bar settings")
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        self.bar = QComboBox()
        self.bar.addItems(self.document.config["bars"])
        bar_line = QHBoxLayout()
        bar_line.addWidget(QLabel("Bar"))
        bar_line.addWidget(self.bar, 1)
        layout.addLayout(bar_line)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self._build_widgets()
        self._build_appearance()
        self._build_clock()
        self.dock_settings = None
        if windhawk_dock:
            self._build_dock()
            self.setWindowTitle("Bar and dock settings")
            title.setText("Bar and dock settings")
        self.status = QLabel("Changes apply only when you save. A backup is kept automatically.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        footer = QHBoxLayout()
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        self.apply = QPushButton("Save and apply" if reload_callback else "Save")
        self.apply.setDefault(True)
        self.apply.clicked.connect(self.save)
        footer.addStretch()
        footer.addWidget(close)
        footer.addWidget(self.apply)
        layout.addLayout(footer)
        self.bar.currentTextChanged.connect(self._load_bar)
        self._load_bar()

    def _hint(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("hint")
        label.setWordWrap(True)
        return label

    def _build_widgets(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._hint("Toggle your configured widgets, choose a position, and move them into order."))
        self.widgets = QTableWidget(0, 3)
        self.widgets.setHorizontalHeaderLabels(["Show", "Widget", "Position"])
        self.widgets.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.widgets.setColumnWidth(0, 60)
        self.widgets.setColumnWidth(2, 120)
        self.widgets.verticalHeader().hide()
        self.widgets.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.widgets.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.widgets)
        buttons = QHBoxLayout()
        for text, direction in (("Move up", -1), ("Move down", 1)):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, delta=direction: self.move_widget(delta))
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.tabs.addTab(page, "Widgets")

    def _spin(self, minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setSuffix(" px")
        return spin

    def _build_appearance(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._hint("Text size, spacing, opacity and tray icon size apply across all bars."))
        form = QFormLayout()
        values = self.document.appearance()
        self.font_size = self._spin(8, 32, values["font_size"])
        self.spacing = self._spin(0, 32, values["spacing"])
        self.height = self._spin(16, 96, 26)
        self.tray_size = self._spin(8, 32, 16)
        tray_sizes = [
            widget.get("options", {}).get("icon_size", 16)
            for widget in self.document.config["widgets"].values()
            if isinstance(widget, dict) and widget.get("type") == "yasb.systray.SystrayWidget"
        ]
        if tray_sizes:
            self.tray_size.setValue(tray_sizes[0])
        else:
            self.tray_size.setEnabled(False)
        self.tray_size_changed = False
        self.tray_size.valueChanged.connect(self._tray_changed)
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(values["opacity"])
        self.opacity_label = QLabel(f"{values['opacity']}% opaque")
        self.opacity.valueChanged.connect(lambda value: self.opacity_label.setText(f"{value}% opaque"))
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self.opacity)
        opacity_row.addWidget(self.opacity_label)
        form.addRow("Text size", self.font_size)
        form.addRow("Widget spacing", self.spacing)
        form.addRow("Tray icons", self.tray_size)
        form.addRow("Background", opacity_row)
        form.addRow("Bar height", self.height)
        layout.addLayout(form)
        if self.fixed_height is not None:
            self.height.setEnabled(False)
            layout.addWidget(
                self._hint(
                    "Height is fixed by your Windhawk dock integration. Text, tray icons and spacing remain adjustable."
                )
            )
        layout.addStretch()
        self.tabs.addTab(page, "Appearance")

    def _tray_changed(self):
        self.tray_size_changed = True

    def _build_dock(self):
        from core.utils.windhawk_dock import MAX_SIZE, MIN_SIZE, DockIconSettings

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._hint("Size applies to app icons on all monitors and follows Windows display scaling."))
        form = QFormLayout()
        self.dock_size = self._spin(MIN_SIZE, MAX_SIZE, 32)
        form.addRow("App icon size", self.dock_size)
        layout.addLayout(form)
        try:
            self.dock_settings = DockIconSettings()
            self.dock_size.setValue(self.dock_settings.original[0])
        except (OSError, ValueError) as error:
            self.dock_size.setEnabled(False)
            layout.addWidget(self._hint(f"Dock settings unavailable: {error}"))
        self.dock_size_changed = False
        self.dock_size.valueChanged.connect(self._dock_changed)
        layout.addWidget(
            self._hint("32 px is the default for this setup. Dock height and hide behavior stay unchanged.")
        )
        layout.addWidget(
            self._hint("Save and apply may ask for Windows administrator approval when dock size changes.")
        )
        layout.addStretch()
        self.tabs.addTab(page, "Dock")

    def _dock_changed(self):
        self.dock_size_changed = True

    def _build_clock(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.clock = QComboBox()
        for name, widget in self.document.config["widgets"].items():
            if isinstance(widget, dict) and widget.get("type") == "yasb.clock.ClockWidget":
                self.clock.addItem(name)
        form = QFormLayout()
        form.addRow("Clock widget", self.clock)
        self.change_clock = QCheckBox("Use the format below")
        layout.addLayout(form)
        layout.addWidget(self.change_clock)
        format_form = QFormLayout()
        self.time_format = QComboBox()
        self.time_format.addItems(["12-hour (AM/PM)", "24-hour"])
        self.seconds = QCheckBox("Show seconds")
        self.date_format = QComboBox()
        self.date_format.addItems(DATE_FORMATS)
        format_form.addRow("Time", self.time_format)
        format_form.addRow("", self.seconds)
        format_form.addRow("Date", self.date_format)
        layout.addLayout(format_form)
        self.clock_preview = QLabel()
        self.clock_preview.setWordWrap(True)
        layout.addWidget(self.clock_preview)
        layout.addWidget(
            self._hint(
                "Existing custom formats are preserved unless you enable the new format. The alternate clock label uses the same selected format."
            )
        )
        layout.addStretch()
        for control in (self.time_format, self.date_format):
            control.currentIndexChanged.connect(self._clock_edited)
        self.seconds.toggled.connect(self._clock_edited)
        self.change_clock.toggled.connect(self._preview_clock)
        self.clock.currentTextChanged.connect(self._load_clock)
        page.setEnabled(self.clock.count() > 0)
        self.tabs.addTab(page, "Clock")
        self._load_clock()

    def _load_clock(self):
        self._store_clock()
        if not self.clock.currentText():
            return
        self._loaded_clock = self.clock.currentText()
        options = self.document.config["widgets"][self.clock.currentText()].get("options", {})
        label = options.get("label", "{%H:%M}")
        for control in (self.time_format, self.seconds, self.date_format):
            control.blockSignals(True)
        self.time_format.setCurrentIndex(0 if "%I" in label else 1)
        self.seconds.setChecked("%S" in label)
        selected = "No date"
        for name, pattern in DATE_FORMATS.items():
            if pattern and pattern in label:
                selected = name
                break
        self.date_format.setCurrentText(selected)
        for control in (self.time_format, self.seconds, self.date_format):
            control.blockSignals(False)
        self.change_clock.setChecked(False)
        self._preview_clock()

    def _store_clock(self):
        if self._loaded_clock and self.change_clock.isChecked():
            label = self._clock_label()
            options = self.document.config["widgets"][self._loaded_clock].setdefault("options", {})
            options.update(label=label, label_alt=label, update_interval=1000 if "%S" in label else 60000)

    def _clock_label(self) -> str:
        time = "%I:%M" if self.time_format.currentIndex() == 0 else "%H:%M"
        if self.seconds.isChecked():
            time += ":%S"
        if self.time_format.currentIndex() == 0:
            time += " %p"
        date = DATE_FORMATS[self.date_format.currentText()]
        return "{" + (date + "  ·  " if date else "") + time + "}"

    def _clock_edited(self):
        self.change_clock.setChecked(True)
        self._preview_clock()

    def _preview_clock(self):
        if self.change_clock.isChecked():
            self.clock_preview.setText("Preview: " + datetime.now().strftime(self._clock_label()[1:-1]))
        elif self.clock.currentText():
            self.clock_preview.setText("Current format will be kept.")

    def _rows(self) -> list:
        return [
            (
                self.widgets.item(row, 0).checkState() == Qt.CheckState.Checked,
                self.widgets.item(row, 1).text(),
                self.widgets.cellWidget(row, 2).currentText(),
            )
            for row in range(self.widgets.rowCount())
        ]

    def _set_rows(self, rows: list):
        self.widgets.setRowCount(len(rows))
        for row, (enabled, name, section) in enumerate(rows):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            check.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
            self.widgets.setItem(row, 0, check)
            label = QTableWidgetItem(name)
            label.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.widgets.setItem(row, 1, label)
            position = QComboBox()
            position.addItems(SECTIONS)
            position.setCurrentText(section)
            self.widgets.setCellWidget(row, 2, position)

    def _load_bar(self):
        self._store_bar()
        self._loaded_bar = self.bar.currentText()
        placements = self.document.config["bars"][self.bar.currentText()]["widgets"]
        rows = [(True, name, section) for section in SECTIONS for name in placements.get(section, [])]
        used = {name for _, name, _ in rows}
        rows += [(False, name, "right") for name in self.document.config["widgets"] if name not in used]
        self._set_rows(rows)
        height = self.document.config["bars"][self.bar.currentText()].get("dimensions", {}).get("height", 30)
        self.height.setValue(self.fixed_height if self.fixed_height is not None else height)

    def _store_bar(self):
        if self._loaded_bar:
            bar = self.document.config["bars"][self._loaded_bar]
            bar["widgets"].update({section: [] for section in SECTIONS})
            for enabled, name, section in self._rows():
                if enabled:
                    bar["widgets"][section].append(name)
            if self.fixed_height is None:
                bar.setdefault("dimensions", {})["height"] = self.height.value()

    def move_widget(self, delta: int):
        row = self.widgets.currentRow()
        destination = row + delta
        if row < 0 or not 0 <= destination < self.widgets.rowCount():
            return
        rows = self._rows()
        rows[row], rows[destination] = rows[destination], rows[row]
        self._set_rows(rows)
        self.widgets.selectRow(destination)

    def save(self):
        try:
            self._store_bar()
            self._store_clock()
            placements = {section: [] for section in SECTIONS}
            for enabled, name, section in self._rows():
                if enabled:
                    placements[section].append(name)
            appearance = self.document.appearance()
            appearance.update(
                font_size=self.font_size.value(), spacing=self.spacing.value(), opacity=self.opacity.value()
            )
            if self.fixed_height is None:
                appearance["height"] = self.height.value()
            if self.tray_size_changed:
                appearance["tray_icon_size"] = self.tray_size.value()
            clock = None
            if self.change_clock.isChecked():
                label = self._clock_label()
                clock = (self.clock.currentText(), label, label)
            config, css = self.document.render(self.bar.currentText(), placements, appearance, clock)
            self.document.save(config, css)
        except (OSError, ValueError, KeyError, TypeError) as error:
            QMessageBox.warning(self, "Settings were not saved", str(error))
            return
        self.status.setText("Saved. Previous settings are backed up in the configuration folder.")
        if self.reload_callback:
            try:
                self.reload_callback()
            except Exception as error:
                QMessageBox.warning(
                    self, "Saved, but reload failed", f"Your changes are saved. Reload YASB to apply them.\n\n{error}"
                )
        if self.dock_settings is not None and self.dock_size_changed:
            try:
                if self.dock_settings.save(self.dock_size.value()):
                    self.status.setText("Bar settings saved. Dock icon size applied through Windhawk.")
                self.dock_size_changed = False
            except (OSError, ValueError) as error:
                self.status.setText("Bar settings saved. Dock size could not be applied.")
                QMessageBox.warning(self, "Dock size was not applied", f"Bar settings were saved.\n\n{error}")


def main():
    parser = argparse.ArgumentParser(description="YASB bar settings")
    parser.add_argument(
        "--config", type=Path, default=Path(os.getenv("YASB_CONFIG_HOME", Path.home() / ".config/yasb"))
    )
    parser.add_argument("--yasbc", type=Path)
    parser.add_argument("--fixed-height", type=int)
    parser.add_argument("--windhawk-dock", action="store_true", help="Show settings for the installed Windhawk dock")
    parser.add_argument("--apply-dock-size", type=int, nargs=3, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.apply_dock_size is not None:
        from core.utils.windhawk_dock import write_sizes

        size, normal, small = args.apply_dock_size
        try:
            write_sizes(size, (normal, small))
        except ValueError:
            return 2
        except OSError:
            return 3
        return 0
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")

    def reload_bar():
        if args.yasbc is None:
            return
        environment = dict(os.environ, YASB_CONFIG_HOME=str(args.config))
        result = subprocess.run(
            [str(args.yasbc), "reload"],
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "YASB did not accept reload.")

    try:
        window = BarSettingsDialog(
            args.config, reload_bar if args.yasbc else None, args.fixed_height, args.windhawk_dock
        )
    except Exception as error:
        QMessageBox.critical(None, "Cannot open bar settings", str(error))
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
