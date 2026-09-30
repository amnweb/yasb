import logging
import re
from functools import partial

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, refresh_widget_style
from core.validation.widgets.yasb.ms_teams_status import MSTeamsStatusConfig
from core.widgets.base import BaseWidget
from core.widgets.services.ms_teams_status.ms_teams_status_api import (
    AvailabilitySettable,
    AvailabilityStatus,
    AvailabilityStatusClass,
    AvailabilityStatusText,
    MSTeamsStatusAPI,
)
from core.widgets.services.ms_teams_status.widgets import ClickableWidget


class MSTeamsStatusWidget(BaseWidget):
    validation_schema = MSTeamsStatusConfig

    _instance: list[MSTeamsStatusWidget] = []

    def __init__(self, config: MSTeamsStatusConfig):
        super().__init__(config.update_interval, class_name=f"ms-teams-status-widget {config.class_name}")
        self.config = config
        self._show_alt_label = False

        self._label_content = config.label
        self._label_alt_content = config.label_alt
        self.unread = 0
        self._skip_ticks = 0
        # None until the first status is read from the Teams logs
        self.teams_status: AvailabilityStatus | None = None

        self._teams_api = MSTeamsStatusAPI.get_instance(self)

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)
        self.register_callback("update_label", self._update_label)
        self.register_callback("toggle_card", self._toggle_card)
        self.register_callback("toggle_label", self._toggle_label)

        self.callback_left = config.callbacks.on_left
        self.callback_right = config.callbacks.on_right
        self.register_callback("timer_update", self._timer_update)
        self.callback_timer = "timer_update"
        self.start_timer()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _timer_update(self):
        """Timer entry point — honours the post-selection suppression window."""
        if self._skip_ticks > 0:
            self._skip_ticks -= 1
            return
        self._update_label()

    def _update_label(self, new_status: AvailabilityStatus = None):  # , status: AvailabilityStatus):
        if new_status is None:
            teams_status = self._teams_api.get_status()
        else:
            teams_status = new_status
        if teams_status is None:
            return
        self.unread = teams_status.unread
        self.teams_status = teams_status
        dot_colour = getattr(self.config.status_colours, (self.teams_status.status_class.value).replace("-", "_"))
        dot_icon = getattr(self.config.status_icons, (self.teams_status.status_class.value).replace("-", "_"))

        ms_teams_data = {
            "{dot}": f'<span style="color:{dot_colour}">{dot_icon}</span>',
            "{status_text}": self.teams_status.status.value,
            "{unread_notifs}": self.teams_status.unread,
        }

        active_widgets = self._show_alt_label and self._widgets_alt or self._widgets
        active_label_content = self._show_alt_label and self._label_alt_content or self._label_content
        label_parts = re.split(r"(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]

        if self.config.tooltip:
            tooltip = f"<strong>{self.teams_status.status.value}</strong>"
            set_tooltip(self, tooltip)

        widget_index = 0

        try:
            for part in label_parts:
                part = part.strip()
                # Decide icon vs label from the template, before substitution —
                # substituted values may themselves contain <span> markup.
                is_icon = "<span" in part and "</span>" in part
                if is_icon:
                    # Strip only the template's span, so a substituted {dot} keeps its inline colour
                    part = re.sub(r"^<span.*?>|</span>$", "", part).strip()
                for option, value in ms_teams_data.items():
                    part = part.replace(option, str(value))
                if not part or widget_index >= len(active_widgets):
                    continue
                if is_icon:
                    active_widgets[widget_index].setText(part)
                else:
                    label_class = "label alt" if self._show_alt_label else "label"
                    formatted_text = part.format(info=ms_teams_data)
                    active_widgets[widget_index].setText(formatted_text)
                    new_class = f"{label_class} status-{self.teams_status.status_class.value}"
                    if active_widgets[widget_index].property("class") != new_class:
                        active_widgets[widget_index].setProperty("class", new_class)
                        refresh_widget_style(active_widgets[widget_index])
                widget_index += 1
        except Exception as e:
            logging.exception("Failed to update label: %s", e)

    def _toggle_card(self):
        self._popup_card()

    def _popup_card(self):
        self.dialog = PopupWidget(
            self,
            self.config.status_card.blur,
            self.config.status_card.round_corners,
            self.config.status_card.round_corners_type,
            self.config.status_card.border_color,
            pinnable=True,
        )
        self.dialog.setProperty("class", "ms-teams-status-card")

        self._build_teams_card()

    def _build_teams_card(self):
        main_layout = QVBoxLayout()
        show_icons = self.config.status_card.show_icons
        icons_before = self.config.status_card.icons_before_status
        dividers = self.config.status_card.section_dividers

        def make_divider():
            line = QFrame()
            line.setProperty("class", "card-divider")
            return line

        def create_option_frame(status):
            status_toggle_frame = ClickableWidget()

            self._availibitiy_toggles.append(status_toggle_frame)

            status_toggle_frame.clicked.connect(partial(self._on_status_selected, status))

            status_toggle_frame.setProperty("class", "availability-option")

            status_toggle_layout = QHBoxLayout()
            status_toggle_layout.setContentsMargins(0, 0, 0, 0)
            status_toggle_layout.setSpacing(0)
            status_toggle_layout.setAlignment(Qt.AlignmentFlag.AlignJustify)
            status_toggle_frame.setLayout(status_toggle_layout)

            # Status Text
            status_label = QLabel(AvailabilityStatusText[status.name].value)
            status_label.setProperty("class", f"label-text {AvailabilityStatusClass[status.name].value}")

            if not icons_before:
                status_toggle_layout.addWidget(status_label)
                status_toggle_layout.addStretch()

            # Status Icon
            if show_icons:
                status_class = AvailabilityStatusClass[status.name].value.replace("-", "_")
                colour = getattr(self.config.status_colours, status_class)
                icon = getattr(self.config.status_icons, status_class)
                icon_label = QLabel(f'<span style="color:{colour}">{icon}</span>')
                icon_label.setProperty("class", "icon-label")
                status_toggle_layout.addWidget(icon_label)

            if icons_before:
                status_toggle_layout.addWidget(status_label)
                status_toggle_layout.addStretch()

            return status_toggle_frame

        if self.config.status_card.display_current_info and self.teams_status is not None:
            # Wrapped in QFrames rather than bare layouts, since stylesheets only apply to widgets
            current_info_frame = QFrame()
            current_info_frame.setProperty("class", "current-info")
            current_info_layout = QHBoxLayout(current_info_frame)
            current_info_layout.setContentsMargins(0, 0, 0, 0)
            current_info_layout.setSpacing(4)

            current_status_frame = QFrame()
            current_status_frame.setProperty("class", "current-status")
            current_status_layout = QHBoxLayout(current_status_frame)
            current_status_layout.setContentsMargins(0, 0, 0, 0)
            current_status_layout.setSpacing(8)
            current_status_text_layout = QVBoxLayout()
            current_status_text_layout.setContentsMargins(0, 0, 0, 0)
            current_status_layout.setSpacing(0)

            # Text
            current_status_text_label = QLabel("Current status")
            current_status_text_label.setProperty("class", "current-status-text-label")
            current_status_text_layout.addWidget(current_status_text_label)

            current_status_label = QLabel(f"{self.teams_status.status.value}")
            current_status_label.setProperty("class", "current-status-label")
            current_status_text_layout.addWidget(current_status_label)

            current_status_class = AvailabilityStatusClass[self.teams_status.status.name].value.replace("-", "_")
            current_colour = getattr(self.config.status_colours, current_status_class)
            current_icon = getattr(self.config.status_icons, current_status_class)
            current_icon_label = QLabel(f'<span style="color:{current_colour}">{current_icon}</span>')
            current_icon_label.setProperty("class", "current-status-icon icon-label")

            current_status_layout.addWidget(current_icon_label)

            # current_status_text_layout.addStretch()
            current_status_layout.addLayout(current_status_text_layout)

            unread_frame = QFrame()
            unread_frame.setProperty("class", "current-notification")
            unread_layout = QHBoxLayout(unread_frame)
            unread_layout.setContentsMargins(0, 0, 0, 0)
            # Text
            unread_label = QLabel(f"{self.config.status_icons.notification_bell}   {self.teams_status.unread}")
            unread_label.setProperty("class", "notification-label")
            unread_layout.addWidget(unread_label)

            current_info_layout.addWidget(current_status_frame)
            current_info_layout.addStretch()
            current_info_layout.addWidget(unread_frame)

            main_layout.addWidget(current_info_frame)

            if dividers:
                main_layout.addWidget(make_divider())

        availability_widgets: list[QWidget] = []
        self._availibitiy_toggles = []
        for status in AvailabilitySettable:
            # Skip the reset status
            if status.value is None:
                continue

            status_option = create_option_frame(status)

            availability_widgets.append(status_option)

        status_grid = QGridLayout()
        status_grid.setContentsMargins(0, 0, 0, 0)
        status_grid.setSpacing(4)

        columns = self.config.status_card.columns
        for i, widget in enumerate(availability_widgets):
            row, col = divmod(i, columns)
            status_grid.addWidget(widget, row, col)
        for col in range(columns):
            status_grid.setColumnStretch(col, 1)

        status_reset_frame = ClickableWidget()

        self._availibitiy_toggles.append(status_reset_frame)

        status_reset_frame.clicked.connect(partial(self._on_status_selected, AvailabilitySettable.Reset))

        status_reset_frame.setProperty("class", "availability-option reset")

        status_reset_layout = QHBoxLayout()
        status_reset_layout.setContentsMargins(0, 0, 0, 0)
        status_reset_layout.setSpacing(4)
        status_reset_layout.setAlignment(Qt.AlignmentFlag.AlignJustify)
        status_reset_frame.setLayout(status_reset_layout)

        # Status Text
        status_label = QLabel("Reset")
        status_label.setProperty("class", "label-text reset")

        if not icons_before:
            status_reset_layout.addWidget(status_label)
            status_reset_layout.addStretch()

        # Status Icon
        if show_icons:
            colour = self.config.status_colours.reset
            icon = self.config.status_icons.reset
            icon_label = QLabel(f'<span style="color:{colour}">{icon}</span>')
            icon_label.setProperty("class", "icon-label")
            status_reset_layout.addWidget(icon_label)

        if icons_before:
            status_reset_layout.addWidget(status_label)
            status_reset_layout.addStretch()

        main_layout.addLayout(status_grid)
        if dividers:
            main_layout.addWidget(make_divider())
        main_layout.addWidget(status_reset_frame)

        self.dialog.setLayout(main_layout)
        self.dialog.adjustSize()
        self.dialog.setPosition(
            alignment=self.config.status_card.alignment,
            direction=self.config.status_card.direction,
            offset_left=self.config.status_card.offset_left,
            offset_top=self.config.status_card.offset_top,
        )

        self.dialog.show()
        self.dialog.set_pinned(self.config.status_card.pinnable)

    def _on_status_selected(self, status: AvailabilitySettable):
        if not self._teams_api.set_status(status):
            return

        self.dialog.hide()
        if status is AvailabilitySettable.Reset:
            return

        self._skip_ticks = 5
        self._update_label(
            AvailabilityStatus(
                status=AvailabilityStatusText[status.name],
                status_class=AvailabilityStatusClass[status.name],
                unread=self.unread,
            )
        )
