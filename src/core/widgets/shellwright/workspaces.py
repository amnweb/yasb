"""
Shellwright workspace widget for YASB.

Displays workspace buttons (empty / populated / active) from ALL monitors
in order, and optionally the current tiling layout for the active workspace.

Config example (config.yaml)
-----------------------------
.. code-block:: yaml

    widgets:
      shellwright_workspaces:
        type: "shellwright.workspaces.WorkspaceWidget"
        options:
          label_offline: "SW Offline"
          label_workspace_btn: "{name}"
          label_workspace_active_btn: "{name}"
          label_workspace_populated_btn: "{name}"
          hide_if_offline: false
          hide_empty_workspaces: true
          show_layout: true
          label_layout: "[{layout}]"

CSS classes
-----------
* ``.shellwright-workspaces``  — outer frame
* ``.ws-btn``                  — every workspace button
* ``.ws-btn.empty``            — empty workspace (grey dot)
* ``.ws-btn.populated``        — has windows, not active (white dot)
* ``.ws-btn.active``           — active workspace on focused monitor (blue bar)
* ``.sw-layout``               — layout label (when show_layout = true)
* ``.sw-offline``              — offline label

Example stylesheet snippet
--------------------------
.. code-block:: css

    .shellwright-workspaces .ws-btn {
        background: transparent;
        border: none;
        min-width: 8px;
        min-height: 8px;
        border-radius: 4px;
        margin: 0 3px;
    }
    .shellwright-workspaces .ws-btn.empty {
        background-color: #555555;
        border-radius: 50%;
    }
    .shellwright-workspaces .ws-btn.populated {
        background-color: #ffffff;
        border-radius: 50%;
    }
    .shellwright-workspaces .ws-btn.active {
        background-color: #5294e2;
        border-radius: 2px;
        min-width: 18px;
    }
"""

import logging
from typing import Literal

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from core.event_enums import ShellwrightEvent
from core.event_service import EventService
from core.utils.utilities import add_shadow, refresh_widget_style
from core.validation.widgets.shellwright.workspaces import ShellwrightWorkspacesConfig
from core.widgets.base import BaseWidget

try:
    from core.utils.widgets.shellwright.event_listener import ShellwrightEventListener
except ImportError:
    ShellwrightEventListener = None
    logging.warning("Failed to load Shellwright Event Listener")

WorkspaceStatus = Literal["EMPTY", "POPULATED", "ACTIVE"]
WS_EMPTY: WorkspaceStatus = "EMPTY"
WS_POPULATED: WorkspaceStatus = "POPULATED"
WS_ACTIVE: WorkspaceStatus = "ACTIVE"


class WorkspaceButton(QPushButton):
    """A single workspace button."""

    def __init__(
        self,
        ws_index: int,
        ws_name: str,
        config: ShellwrightWorkspacesConfig,
    ) -> None:
        super().__init__()
        self.ws_index = ws_index
        self.ws_name = ws_name
        self.status: WorkspaceStatus = WS_EMPTY
        self.setProperty("class", "ws-btn empty")
        self._default_label = config.label_workspace_btn.format(name=ws_name, index=ws_index + 1)
        self._active_label = config.label_workspace_active_btn.format(name=ws_name, index=ws_index + 1)
        self._populated_label = config.label_workspace_populated_btn.format(name=ws_name, index=ws_index + 1)
        self.setText(self._default_label)
        self.hide()

    def update_status(self, status: WorkspaceStatus) -> None:
        self.status = status
        self.setProperty("class", f"ws-btn {status.lower()}")
        if status == WS_ACTIVE:
            self.setText(self._active_label)
        elif status == WS_POPULATED:
            self.setText(self._populated_label)
        else:
            self.setText(self._default_label)
        refresh_widget_style(self)


class WorkspaceWidget(BaseWidget):
    """YASB widget that displays shellwright workspaces and layout.

    Shows ALL workspaces from ALL monitors in order (e.g. 1-3 from monitor 0,
    4-6 from monitor 1, 7-9 from monitor 2).  The active workspace (focused
    workspace on the focused monitor) is highlighted with the ``active`` class.
    """

    validation_schema = ShellwrightWorkspacesConfig
    event_listener = ShellwrightEventListener

    _connect_signal = pyqtSignal(dict)
    _update_signal = pyqtSignal(dict)
    _disconnect_signal = pyqtSignal()

    def __init__(self, config: ShellwrightWorkspacesConfig) -> None:
        super().__init__(class_name="shellwright-workspaces")

        self._config = config
        self._workspace_buttons: list[WorkspaceButton] = []

        # Offline label.
        self._offline_label = QLabel(config.label_offline)
        self._offline_label.setProperty("class", "sw-offline")
        add_shadow(self._offline_label, config.label_shadow.model_dump())

        # Layout label (optional, hidden until connected).
        self._layout_label = QLabel("")
        self._layout_label.setProperty("class", "sw-layout")
        add_shadow(self._layout_label, config.label_shadow.model_dump())
        self._layout_label.setVisible(False)

        # Container padding.
        p = config.container_padding
        self.widget_layout.setContentsMargins(p.left, p.top, p.right, p.bottom)

        self.widget_layout.addWidget(self._offline_label)
        self.widget_layout.addWidget(self._layout_label)

        add_shadow(self._widget_frame, config.container_shadow.model_dump())

        if config.hide_if_offline:
            self.hide()
        else:
            self._offline_label.show()

        # Wire Qt signals → slots.
        self._connect_signal.connect(self._on_connect)
        self._update_signal.connect(self._on_update)
        self._disconnect_signal.connect(self._on_disconnect)

        # Subscribe to shellwright events.
        event_service = EventService()
        event_service.register_event(ShellwrightEvent.ShellwrightConnect, self._connect_signal)
        event_service.register_event(ShellwrightEvent.ShellwrightUpdate, self._update_signal)
        event_service.register_event(ShellwrightEvent.ShellwrightDisconnect, self._disconnect_signal)

    # ── Event slots ───────────────────────────────────────────────────────────

    def _on_connect(self, state: dict) -> None:
        self._offline_label.hide()
        if self._config.hide_if_offline:
            self.show()
        self._apply_state(state)

    def _on_update(self, state: dict) -> None:
        self._apply_state(state)

    def _on_disconnect(self) -> None:
        for btn in self._workspace_buttons:
            btn.hide()
        self._layout_label.setVisible(False)
        if self._config.hide_if_offline:
            self.hide()
        else:
            self._offline_label.show()

    # ── State rendering ───────────────────────────────────────────────────────

    def _apply_state(self, state: dict) -> None:
        try:
            monitors = state.get("monitors", {})
            elements = monitors.get("elements", [])

            if not elements:
                return

            # ── This bar only cares about its own monitor ─────────────────────
            mon_idx = self._config.monitor_index
            if mon_idx < 0:
                # Auto-detect: find which Qt screen this widget lives on.
                screen = self.screen()
                if screen is not None:
                    all_screens = QApplication.screens()
                    try:
                        qt_idx = all_screens.index(screen)
                    except ValueError:
                        qt_idx = 0
                else:
                    qt_idx = 0
                # Apply remap if configured, otherwise use Qt index directly.
                remap = self._config.monitor_index_remap
                if remap and qt_idx < len(remap):
                    mon_idx = remap[qt_idx]
                else:
                    mon_idx = qt_idx
            mon_idx = min(mon_idx, len(elements) - 1)
            mon = elements[mon_idx]
            ws_data = mon.get("workspaces", {})
            ws_els = ws_data.get("elements", [])
            local_focused = ws_data.get("focused", 0)

            if not ws_els:
                return

            # Rebuild buttons if workspace count changed.
            if len(ws_els) != len(self._workspace_buttons):
                self._rebuild_buttons(ws_els)

            # Update each button's status.
            for local_idx, (ws, btn) in enumerate(zip(ws_els, self._workspace_buttons)):
                n_windows = len(ws.get("windows", {}).get("elements", []))
                is_active = local_idx == local_focused
                if is_active:
                    status = WS_ACTIVE
                elif n_windows > 0:
                    status = WS_POPULATED
                else:
                    status = WS_EMPTY

                btn.update_status(status)

                if self._config.hide_empty_workspaces and status == WS_EMPTY:
                    btn.hide()
                else:
                    btn.show()

            # Layout label — show layout of this monitor's focused workspace.
            if self._config.show_layout:
                idx = min(local_focused, len(ws_els) - 1)
                layout_name = ws_els[idx].get("layout", "")
                self._layout_label.setText(
                    self._config.label_layout.format(layout=layout_name)
                )
                self._layout_label.setVisible(True)
            else:
                self._layout_label.setVisible(False)

        except Exception:
            logging.exception("Failed to apply shellwright state")

    def _rebuild_buttons(self, ws_elements: list) -> None:
        """Remove old workspace buttons and create fresh ones."""
        for btn in self._workspace_buttons:
            self.widget_layout.removeWidget(btn)
            btn.deleteLater()
        self._workspace_buttons.clear()

        for global_idx, ws in enumerate(ws_elements):
            ws_name = ws.get("name", str(global_idx + 1))
            btn = WorkspaceButton(global_idx, ws_name, self._config)
            add_shadow(btn, self._config.btn_shadow.model_dump())
            # Insert before _layout_label (always last in layout).
            insert_pos = self.widget_layout.count() - 1
            self.widget_layout.insertWidget(insert_pos, btn)
            self._workspace_buttons.append(btn)
