import json
import logging
import re
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QCursor, QKeyEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QVBoxLayout

from core.utils.qobject import is_valid_qobject
from core.utils.utilities import PopupWidget, refresh_widget_style
from core.utils.win32.hotkeys import parse_hotkey
from core.utils.win32.utils import apply_qmenu_style
from core.validation.widgets.yasb.monitor_profile import MonitorProfileConfig
from core.widgets.base import BaseWidget
from core.widgets.services.monitor_profile.monitor_profile_api import (
    _ROTATION_NAMES,
    MonitorProfileError,
    apply_profile,
    capture_profile,
    get_active_monitor_names,
    get_inactive_monitors,
    get_monitors,
    profile_matches_current,
    set_monitor_enabled,
)
from core.widgets.services.monitor_profile.runtime_hotkeys import RuntimeHotkeyManager

logger = logging.getLogger("monitor_profile_widget")


class MonitorProfileWidget(BaseWidget):
    """Widget for switching between saved monitor layout profiles."""

    validation_schema = MonitorProfileConfig

    _instances: list[MonitorProfileWidget] = []
    hotkeys_changed = pyqtSignal()

    def __init__(self, config: MonitorProfileConfig) -> None:
        super().__init__(class_name=f"monitor-profile-widget {config.class_name}")
        self.config = config
        self._show_alt_label = False
        self._active_profile: str = ""
        self._popup_menu = None
        self._rename_popup = None
        self._menu_delete_mode = False
        self._pending_capture: dict | None = None

        if self not in MonitorProfileWidget._instances:
            MonitorProfileWidget._instances.append(self)

        self._profiles_dir.mkdir(parents=True, exist_ok=True)

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        self.register_callback("toggle_menu", self._show_menu)
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("save_profile", self._show_save_dialog)
        self.register_callback("next_profile", self._cycle_profile_next)
        self.register_callback("prev_profile", self._cycle_profile_prev)
        self.register_callback("apply_profile", self._cb_apply_profile)
        self.register_callback("toggle_monitor", self._cb_toggle_monitor)
        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

        self.hotkeys_changed.connect(self._on_hotkeys_changed)
        self._register_saved_hotkeys()

        self._refresh_active_profile()

    @classmethod
    def instances(cls) -> list[MonitorProfileWidget]:
        """Return live instances only, purging any whose C++ object was destroyed."""
        from core.utils.qobject import is_valid_qobject

        cls._instances[:] = [w for w in cls._instances if is_valid_qobject(w)]
        return list(cls._instances)

    @property
    def _hotkeys_path(self) -> Path:
        return self._profiles_dir / "hotkeys.json"

    @property
    def _profiles_dir(self) -> Path:
        from settings import DEFAULT_CONFIG_DIRECTORY

        return Path(DEFAULT_CONFIG_DIRECTORY) / "monitor_profiles"

    def _list_profiles(self) -> list[str]:
        """Return sorted profile names (filenames without .json)."""
        if not self._profiles_dir.exists():
            return []
        return sorted(p.stem for p in self._profiles_dir.glob("*.json") if p.name != "hotkeys.json")

    # ------------------------------------------------------------- hotkeys

    def _load_hotkeys(self) -> dict[str, str]:
        """Load saved action -> hotkey mappings from disk."""
        try:
            with open(self._hotkeys_path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception as exc:
            logging.error("Error loading monitor profile hotkeys: %s", exc)
            return {}

    def _save_hotkeys(self, hotkeys: dict[str, str]) -> None:
        try:
            self._profiles_dir.mkdir(parents=True, exist_ok=True)
            with open(self._hotkeys_path, "w", encoding="utf-8") as f:
                json.dump(hotkeys, f, indent=2)
        except Exception as exc:
            logging.error("Error saving monitor profile hotkeys: %s", exc)

    def _register_saved_hotkeys(self) -> None:
        """Register all saved hotkeys with the runtime hotkey manager."""
        try:
            hotkeys = self._load_hotkeys()
            bindings: dict[str, tuple[str, int, int]] = {}
            for action, keys in hotkeys.items():
                parsed = parse_hotkey(keys)
                if parsed is None:
                    logging.warning("Ignoring invalid hotkey '%s' for action '%s'", keys, action)
                    continue
                modifiers, vk = parsed
                bindings[action] = (action, vk, modifiers)
            RuntimeHotkeyManager.instance().set_bindings(bindings)
        except Exception as exc:
            logging.error("Error registering monitor profile hotkeys: %s", exc)

    def _on_hotkeys_changed(self) -> None:
        self._register_saved_hotkeys()
        self._refresh_menu_if_visible()

    def _set_hotkey_for_action(self, action: str) -> None:
        """Open the key-capture dialog for an action."""
        current = self._load_hotkeys().get(action, "")
        self._show_hotkey_dialog(action, current)

    def _clear_hotkey_for_action(self, action: str) -> None:
        hotkeys = self._load_hotkeys()
        hotkeys.pop(action, None)
        self._save_hotkeys(hotkeys)
        self.hotkeys_changed.emit()

    def _cb_apply_profile(self, name: str = "") -> None:
        """Callback entry point for profile-apply hotkeys."""
        if name:
            self._apply_profile(name=name)

    def _cb_toggle_monitor(self, name: str = "") -> None:
        """Callback entry point for monitor-toggle hotkeys."""
        self._toggle_monitor_by_name(name)

    # ---------------------------------------------------------- row menus

    def _show_profile_row_menu(self, name: str) -> None:
        """Show the ... context menu for a profile row."""
        hotkey = self._load_hotkeys().get(f'apply_profile "{name}"', "")
        menu = QMenu(self.window())
        apply_qmenu_style(menu)
        menu.setProperty("class", "context-menu")

        if hotkey:
            hk_action = QAction(f"Hotkey: {hotkey}", self)
            hk_action.setEnabled(False)
            menu.addAction(hk_action)
            menu.addSeparator()

        act_apply = QAction("Apply", self)
        act_apply.triggered.connect(lambda checked=False, n=name: self._apply_profile(name=n))
        menu.addAction(act_apply)

        act_hotkey = QAction("Set Hotkey...", self)
        act_hotkey.triggered.connect(lambda checked=False, a=f'apply_profile "{name}"': self._set_hotkey_for_action(a))
        menu.addAction(act_hotkey)

        if hotkey:
            act_clear = QAction("Remove Hotkey", self)
            act_clear.triggered.connect(
                lambda checked=False, a=f'apply_profile "{name}"': self._clear_hotkey_for_action(a)
            )
            menu.addAction(act_clear)

        menu.addSeparator()

        act_info = QAction("View Info", self)
        act_info.triggered.connect(lambda checked=False, n=name: self._show_profile_info(n))
        menu.addAction(act_info)

        act_rename = QAction("Rename...", self)
        act_rename.triggered.connect(lambda checked=False, n=name: self._show_rename_dialog(n))
        menu.addAction(act_rename)

        act_delete = QAction("Delete Profile", self)
        act_delete.triggered.connect(lambda checked=False, n=name: self._delete_profile(name=n))
        menu.addAction(act_delete)

        menu.popup(QCursor.pos())
        menu.activateWindow()

    def _show_monitor_row_menu(self, monitor, enabled: bool) -> None:
        """Show the ... context menu for a monitor row."""
        action = f'toggle_monitor "{monitor.device_name}"'
        hotkey = self._load_hotkeys().get(action, "")
        menu = QMenu(self.window())
        apply_qmenu_style(menu)
        menu.setProperty("class", "context-menu")

        if hotkey:
            hk_action = QAction(f"Hotkey: {hotkey}", self)
            hk_action.setEnabled(False)
            menu.addAction(hk_action)
            menu.addSeparator()

        act_toggle = QAction("Hide Monitor" if enabled else "Show Monitor", self)
        act_toggle.triggered.connect(lambda checked=False, m=monitor, e=enabled: self._toggle_monitor(m, e))
        menu.addAction(act_toggle)

        act_hotkey = QAction("Set Hotkey...", self)
        act_hotkey.triggered.connect(lambda checked=False, a=action: self._set_hotkey_for_action(a))
        menu.addAction(act_hotkey)

        if hotkey:
            act_clear = QAction("Remove Hotkey", self)
            act_clear.triggered.connect(lambda checked=False, a=action: self._clear_hotkey_for_action(a))
            menu.addAction(act_clear)

        menu.popup(QCursor.pos())
        menu.activateWindow()

    def _refresh_menu_if_visible(self) -> None:
        if self._popup_menu and is_valid_qobject(self._popup_menu) and self._popup_menu.isVisible():
            self._show_menu()

    def _toggle_monitor_by_name(self, name: str) -> None:
        r"""Toggle a monitor identified by GDI device name or friendly name.

        GDI device names (\\.\DISPLAY2) change across reboots, so persisted
        hotkey actions fall back to matching by the monitor's friendly name;
        as a last resort all monitors are re-enabled.
        """
        try:
            monitors = get_monitors()
            target = next((m for m in monitors if m.device_name == name), None)
            if target is None:
                target = next((m for m in monitors if m.friendly_name == name), None)
            if target is None:
                set_monitor_enabled(None, True)
            else:
                set_monitor_enabled(target, False)
            self._refresh_active_profile()
        except MonitorProfileError as exc:
            logging.error("Failed to toggle monitor '%s': %s", name, exc)
        except Exception as exc:
            logging.error("Error toggling monitor '%s': %s", name, exc)

    def _refresh_active_profile(self) -> None:
        """Determine which saved profile (if any) matches the current display config."""
        try:
            current = capture_profile()
        except Exception as exc:
            logging.error("Error capturing display config: %s", exc)
            self._active_profile = ""
            self._update_label()
            return

        self._active_profile = ""
        for name in self._list_profiles():
            try:
                import json

                with open(self._profiles_dir / f"{name}.json", encoding="utf-8") as f:
                    profile = json.load(f)
                    if profile_matches_current(profile, current):
                        self._active_profile = name
                        break
            except Exception:
                continue
        self._update_label()

    def _toggle_label(self) -> None:
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _update_label(self) -> None:
        # Skip when the widget has been torn down (e.g. during a config reload);
        # touching the destroyed QLabels raises RuntimeError.
        if not is_valid_qobject(self) or not is_valid_qobject(self._widget_frame):
            return
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self.config.label_alt if self._show_alt_label else self.config.label
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        profile_name = self._active_profile if self._active_profile else "Custom"
        label_options = {"{active_profile}": profile_name}

        for part in label_parts:
            part = part.strip()
            if part:
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                if (
                    widget_index < len(active_widgets)
                    and isinstance(active_widgets[widget_index], QLabel)
                    and is_valid_qobject(active_widgets[widget_index])
                ):
                    active_widgets[widget_index].setText(formatted_text)
                    alt_class = "alt" if self._show_alt_label else ""
                    base_class = "icon" if "<span" in part else f"label {alt_class}"
                    state_class = "active" if self._active_profile else "unsaved"
                    active_widgets[widget_index].setProperty("class", f"{base_class} {state_class}")
                    refresh_widget_style(active_widgets[widget_index])
                widget_index += 1

    def _hide_popup_menu(self) -> None:
        """Hide the popup menu if it is alive (it self-deletes after hiding)."""
        if self._popup_menu and is_valid_qobject(self._popup_menu) and self._popup_menu.isVisible():
            self._popup_menu.hide_animated()

    def _show_menu(self) -> None:
        """Show the monitor profile selection popup."""
        self.clear_hover_state()
        self._menu_delete_mode = False
        self._popup_menu = PopupWidget(
            self,
            self.config.menu.blur,
            self.config.menu.round_corners,
            self.config.menu.round_corners_type,
            self.config.menu.border_color,
        )
        self._popup_menu.setProperty("class", "monitor-profile-menu")

        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Profiles block
        profiles_frame = QFrame()
        profiles_frame.setProperty("class", "menu-block profiles-block")

        frame_layout = QVBoxLayout()
        frame_layout.setSpacing(0)
        frame_layout.setContentsMargins(0, 0, 0, 0)

        profiles = self._list_profiles()
        for name in profiles:
            row = QFrame()
            row.setProperty("class", "profile-row")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)

            btn = QPushButton(name)
            is_active = name == self._active_profile
            btn.setProperty("class", "button active" if is_active else "button")
            btn.clicked.connect(lambda checked, n=name: self._apply_profile(name=n))
            row_layout.addWidget(btn, 1)

            more_btn = QPushButton("⋯")
            more_btn.setProperty("class", "button more")
            more_btn.setToolTip(f"Options for profile '{name}'")
            more_btn.clicked.connect(lambda checked, n=name: self._show_profile_row_menu(n))
            row_layout.addWidget(more_btn, 0)

            frame_layout.addWidget(row)

        save_btn = QPushButton("Save current layout...")
        save_btn.setProperty("class", "button save")
        save_btn.clicked.connect(lambda checked: self._show_save_dialog())
        frame_layout.addWidget(save_btn)

        profiles_frame.setLayout(frame_layout)
        main_layout.addWidget(profiles_frame)

        # Monitors block (separate card so each section can be styled independently)
        if self.config.menu.monitors_section:
            monitors_layout = QVBoxLayout()
            monitors_layout.setSpacing(0)
            monitors_layout.setContentsMargins(0, 0, 0, 0)
            if self._build_monitors_section(monitors_layout):
                monitors_frame = QFrame()
                monitors_frame.setProperty("class", "menu-block monitors-block")
                monitors_frame.setLayout(monitors_layout)
                main_layout.addWidget(monitors_frame)

        self._popup_menu.setLayout(main_layout)
        self._popup_menu.adjustSize()
        self._popup_menu.setPosition(
            self.config.menu.alignment,
            self.config.menu.direction,
            self.config.menu.offset_left,
            self.config.menu.offset_top,
        )
        self._popup_menu.show()

    def _build_monitors_section(self, layout: QVBoxLayout) -> bool:
        """Populate the Monitors block layout. Returns False when there is nothing to show."""
        try:
            monitors = get_monitors()
            inactive = get_inactive_monitors()
        except Exception as exc:
            logging.error("Error querying monitors: %s", exc)
            return False
        if not inactive and len(monitors) < 2:
            return False

        for m in monitors:
            row = QFrame()
            row.setProperty("class", "monitor-row")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)

            btn = QPushButton(m.friendly_name or m.device_name)
            btn.setProperty("class", "button monitor")
            btn.setEnabled(False)
            row_layout.addWidget(btn, 1)

            toggle_btn = QPushButton("⋯")
            toggle_btn.setProperty("class", "button more")
            toggle_btn.setToolTip(f"Options for monitor '{m.friendly_name}'")
            toggle_btn.clicked.connect(lambda checked, mon=m: self._show_monitor_row_menu(mon, True))
            row_layout.addWidget(toggle_btn, 0)
            layout.addWidget(row)

        for name in inactive:
            row = QFrame()
            row.setProperty("class", "monitor-row disabled")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)

            btn = QPushButton(name)
            btn.setProperty("class", "button monitor disabled-monitor")
            btn.setEnabled(False)
            row_layout.addWidget(btn, 1)

            toggle_btn = QPushButton("⋯")
            toggle_btn.setProperty("class", "button more")
            toggle_btn.setToolTip(f"Options for monitor '{name}'")
            toggle_btn.clicked.connect(lambda checked, n=name: self._show_disabled_monitor_menu(n))
            row_layout.addWidget(toggle_btn, 0)
            layout.addWidget(row)

        return True

    def _show_disabled_monitor_menu(self, name: str) -> None:
        """Show the ... context menu for a disabled monitor row."""
        action = f'toggle_monitor "{name}"'
        hotkey = self._load_hotkeys().get(action, "")
        menu = QMenu(self.window())
        apply_qmenu_style(menu)
        menu.setProperty("class", "context-menu")

        if hotkey:
            hk_action = QAction(f"Hotkey: {hotkey}", self)
            hk_action.setEnabled(False)
            menu.addAction(hk_action)
            menu.addSeparator()

        act_toggle = QAction("Show Monitor", self)
        act_toggle.triggered.connect(lambda checked=False, n=name: self._enable_monitor_by_name(n))
        menu.addAction(act_toggle)

        act_hotkey = QAction("Set Hotkey...", self)
        act_hotkey.triggered.connect(lambda checked=False, a=action: self._set_hotkey_for_action(a))
        menu.addAction(act_hotkey)

        if hotkey:
            act_clear = QAction("Remove Hotkey", self)
            act_clear.triggered.connect(lambda checked=False, a=action: self._clear_hotkey_for_action(a))
            menu.addAction(act_clear)

        menu.popup(QCursor.pos())
        menu.activateWindow()

    def _toggle_monitor(self, monitor, enable: bool) -> None:
        """Enable or disable a monitor and rebuild the menu."""
        try:
            set_monitor_enabled(monitor, enable)
        except MonitorProfileError as exc:
            logging.error("Failed to toggle monitor '%s': %s", monitor.friendly_name, exc)
            return
        except Exception as exc:
            logging.error("Error toggling monitor '%s': %s", monitor.friendly_name, exc)
            return
        self._refresh_active_profile()
        if self._popup_menu and is_valid_qobject(self._popup_menu) and self._popup_menu.isVisible():
            self._show_menu()

    def _enable_monitor_by_name(self, name: str) -> None:
        """Re-enable a disabled monitor (the CCD restores the whole database config)."""
        try:
            set_monitor_enabled(None, True)
            self._refresh_active_profile()
            if self._popup_menu and is_valid_qobject(self._popup_menu) and self._popup_menu.isVisible():
                self._show_menu()
        except MonitorProfileError as exc:
            logging.error("Failed to enable monitor '%s': %s", name, exc)
        except Exception as exc:
            logging.error("Error enabling monitor '%s': %s", name, exc)

    def _delete_profile(self, name: str) -> None:
        """Delete a saved profile file."""
        try:
            (self._profiles_dir / f"{name}.json").unlink(missing_ok=True)
            if self._active_profile == name:
                self._active_profile = ""
                self._update_label()
            # Rebuild the menu so the deleted profile disappears
            if self._popup_menu and is_valid_qobject(self._popup_menu) and self._popup_menu.isVisible():
                self._show_menu()
        except Exception as exc:
            logging.error("Failed to delete monitor profile '%s': %s", name, exc)

    def _show_profile_info(self, name: str) -> None:
        """Show a popup describing what a profile contains (monitors, resolution, refresh, rotation)."""
        self._hide_popup_menu()
        try:
            with open(self._profiles_dir / f"{name}.json", encoding="utf-8") as f:
                profile = json.load(f)
        except Exception as exc:
            logging.error("Error reading monitor profile '%s': %s", name, exc)
            return

        # Friendly monitor names, matched to profile paths by stable device path
        # (targets), falling back to path order when the section is missing.
        current_names = get_active_monitor_names()
        try:
            current = capture_profile()
        except Exception:
            current = None
        curr_targets = current.get("targets", []) if current else []

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        frame = QFrame()
        frame.setProperty("class", "monitor-profile-popup-container")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        title = QLabel(f"{name} — {len(profile['paths'])} monitor(s)")
        title.setProperty("class", "popup-title")
        frame_layout.addWidget(title)

        rows = QFrame()
        rows.setProperty("class", "monitor-profile-popup-rows")
        rows_layout = QVBoxLayout(rows)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(6)

        for i, path in enumerate(profile["paths"]):
            target = path["target"]
            rotation = _ROTATION_NAMES.get(target["rotation"], "Unknown")
            refresh = f"{target['refresh_rate']['num'] / target['refresh_rate']['den']:.2f}Hz" if target["refresh_rate"]["den"] else "?"
            # Resolution: prefer the source mode (active desktop surface); the
            # desktop-image mode shares the target id with the target mode, so
            # match by info_type first.
            source = path["source"]
            sm = next(
                (
                    m
                    for m in profile.get("modes", [])
                    if m.get("info_type") == 1
                    and tuple(m["adapter_luid"]) == tuple(source["adapter_luid"])
                    and m["id"] == source["id"]
                ),
                None,
            )
            if sm:
                width, height = sm["source_mode"]["width"], sm["source_mode"]["height"]
            else:
                tm = next(
                    (
                        m
                        for m in profile.get("modes", [])
                        if m.get("info_type") == 2
                        and tuple(m["adapter_luid"]) == tuple(target["adapter_luid"])
                        and m["id"] == target["id"]
                    ),
                    None,
                )
                width, height = (tm["target_mode"]["active_size"] if tm else (0, 0))
            resolution = f"{width}x{height}" if width else "?"

            monitor_name = ""
            targets_section = profile.get("targets", [])
            if i < len(targets_section):
                dev_path = targets_section[i].get("device_path", "")
                if dev_path and current:
                    # Match the device path against the currently connected monitors
                    for j, cp in enumerate(current.get("paths", [])):
                        if j < len(curr_targets) and curr_targets[j].get("device_path") == dev_path:
                            if j < len(current_names):
                                monitor_name = current_names[j]
                                break
            if not monitor_name:
                monitor_name = f"Monitor {i + 1}"

            info = f"{monitor_name}  {resolution}  {rotation}  {refresh}"
            row = QFrame()
            row.setProperty("class", "info-row")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(QLabel(info), 1)
            rows_layout.addWidget(row)

        frame_layout.addWidget(rows)
        layout.addWidget(frame)

        popup = PopupWidget(self, blur=True, round_corners=True, round_corners_type="normal", border_color="system")
        popup.setProperty("class", "monitor-profile-popup info")
        popup.setLayout(layout)
        popup.adjustSize()
        popup.setPosition(
            alignment="center",
            direction="down",
            offset_left=0,
            offset_top=6,
        )
        popup.show()

    def _apply_profile(self, name: str) -> None:
        """Apply the profile chosen from the popup menu."""
        self._hide_popup_menu()
        try:
            import json

            with open(self._profiles_dir / f"{name}.json", encoding="utf-8") as f:
                profile = json.load(f)
            apply_profile(profile)
            self._refresh_active_profile()
        except MonitorProfileError as exc:
            logging.error("Failed to apply monitor profile '%s': %s", name, exc)
        except Exception as exc:
            logging.error("Error loading monitor profile '%s': %s", name, exc)

    def _cycle_profile_next(self) -> None:
        self._cycle_profile(1)

    def _cycle_profile_prev(self) -> None:
        self._cycle_profile(-1)

    def _cycle_profile(self, direction: int) -> None:
        """Switch to the next/previous profile in the list."""
        profiles = self._list_profiles()
        if not profiles:
            return
        try:
            index = profiles.index(self._active_profile)
        except ValueError:
            index = -1 if direction > 0 else 0
        next_index = (index + direction) % len(profiles)
        self._apply_profile(name=profiles[next_index])

    def _rename_profile(self, old_name: str, new_name: str) -> None:
        """Rename a profile file and remap any hotkey bound to it."""
        new_name = new_name.strip()
        if not new_name or new_name == old_name:
            return
        old_path = self._profiles_dir / f"{old_name}.json"
        new_path = self._profiles_dir / f"{new_name}.json"
        try:
            if new_path.exists():
                logging.error("Cannot rename profile: '%s' already exists", new_name)
                return
            old_path.rename(new_path)
        except Exception as exc:
            logging.error("Failed to rename monitor profile '%s' to '%s': %s", old_name, new_name, exc)
            return

        # Remap the apply hotkey if one was bound to the old name
        old_action = f'apply_profile "{old_name}"'
        hotkeys = self._load_hotkeys()
        if old_action in hotkeys:
            hotkeys[f'apply_profile "{new_name}"'] = hotkeys.pop(old_action)
            self._save_hotkeys(hotkeys)
            self.hotkeys_changed.emit()

        self._refresh_active_profile()
        self._refresh_menu_if_visible()

    def _show_rename_dialog(self, name: str) -> None:
        """Show an input popup to rename an existing profile."""
        self._hide_popup_menu()
        self._show_prompt_dialog(
            title="Rename Profile",
            description=f"Enter a new name for '{name}'.",
            initial_text=name,
            placeholder="Profile name",
            on_submit=lambda new_name: self._rename_profile(name, new_name),
        )

    def _show_prompt_dialog(
        self,
        title: str,
        description: str,
        initial_text: str = "",
        placeholder: str = "",
        on_submit=None,
        show_clear: bool = False,
        on_clear=None,
    ) -> None:
        """Show a text-input popup; on_submit receives the trimmed input."""
        self._rename_popup = PopupWidget(
            self,
            blur=True,
            round_corners=True,
            round_corners_type="normal",
            border_color="system",
        )
        self._rename_popup.setProperty("class", "monitor-profile-popup save")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._rename_popup.setLayout(layout)

        container_frame = QFrame()
        container_frame.setProperty("class", "monitor-profile-popup-container")
        container_layout = QVBoxLayout(container_frame)
        container_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(title)
        title_label.setProperty("class", "popup-title")
        container_layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setProperty("class", "popup-description")
        container_layout.addWidget(desc_label)

        name_edit = QLineEdit()
        name_edit.setProperty("class", "rename-input")
        name_edit.setText(initial_text)
        name_edit.setPlaceholderText(placeholder)
        name_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        name_edit.selectAll()
        name_edit.setFocus()
        container_layout.addWidget(name_edit)

        save_btn = QPushButton("Save")
        save_btn.setProperty("class", "button save")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "button cancel")
        clear_btn = None
        if show_clear:
            clear_btn = QPushButton("Remove")
            clear_btn.setProperty("class", "button delete")

        def do_save():
            value = name_edit.text().strip()
            if not value:
                return
            if on_submit is not None:
                on_submit(value)
            self._rename_popup.close()

        if on_clear is not None and clear_btn is not None:
            clear_btn.clicked.connect(lambda: (on_clear(), self._rename_popup.close()))

        def update_save_enabled():
            save_btn.setEnabled(bool(name_edit.text().strip()))

        update_save_enabled()
        name_edit.textChanged.connect(lambda _text: update_save_enabled())
        name_edit.returnPressed.connect(do_save)
        save_btn.clicked.connect(do_save)
        cancel_btn.clicked.connect(lambda: self._rename_popup.close())

        footer_frame = QFrame()
        footer_frame.setProperty("class", "monitor-profile-popup-footer")
        button_layout = QHBoxLayout(footer_frame)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(0)
        button_layout.addWidget(save_btn)
        if clear_btn is not None:
            button_layout.addWidget(clear_btn)
        button_layout.addWidget(cancel_btn)

        layout.addWidget(container_frame)
        layout.addWidget(footer_frame)

        self._rename_popup.adjustSize()
        self._rename_popup.setPosition(
            alignment="center",
            direction="down",
            offset_left=0,
            offset_top=6,
        )
        self._rename_popup.show()

    def _show_save_dialog(self) -> None:
        """Show an input popup to save the current layout as a new profile."""
        self._hide_popup_menu()
        try:
            self._pending_capture = capture_profile()
        except Exception as exc:
            logging.error("Error capturing display config: %s", exc)
            return

        monitors = get_monitors()
        summary = ", ".join(f"{m.resolution} @ {m.refresh_rate}Hz" for m in monitors) or "No monitors detected"

        def do_save(name: str):
            try:
                path = self._profiles_dir / f"{name}.json"
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self._pending_capture, f, indent=2)
                self._refresh_active_profile()
            except Exception as exc:
                logging.error("Failed to save monitor profile '%s': %s", name, exc)

        self._show_prompt_dialog(
            title="Save Monitor Profile",
            description=summary,
            placeholder="Profile name",
            on_submit=do_save,
        )

    def _show_hotkey_dialog(self, action: str, current: str) -> None:
        """Show a popup that captures a key combination for the given action."""
        self._hide_popup_menu()

        self._hotkey_popup = PopupWidget(
            self,
            blur=True,
            round_corners=True,
            round_corners_type="normal",
            border_color="system",
        )
        self._hotkey_popup.setProperty("class", "monitor-profile-popup hotkey")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._hotkey_popup.setLayout(layout)

        container_frame = QFrame()
        container_frame.setProperty("class", "monitor-profile-popup-container")
        container_layout = QVBoxLayout(container_frame)
        container_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("Set Hotkey")
        title_label.setProperty("class", "popup-title")
        container_layout.addWidget(title_label)

        desc_label = QLabel("Press a key combination, then click Save.")
        desc_label.setProperty("class", "popup-description")
        container_layout.addWidget(desc_label)

        keys_edit = _HotkeyLineEdit(self._hotkey_popup)
        keys_edit.setProperty("class", "rename-input")
        keys_edit.setText(current)
        keys_edit.setPlaceholderText("e.g. ctrl+alt+1")
        keys_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        keys_edit.setFocus()
        container_layout.addWidget(keys_edit)

        clear_btn = QPushButton("Remove Hotkey")
        clear_btn.setProperty("class", "button delete")

        def do_clear():
            self._clear_hotkey_for_action(action)
            self._hotkey_popup.close()

        clear_btn.clicked.connect(do_clear)
        if not current:
            clear_btn.setVisible(False)

        save_btn = QPushButton("Save")
        save_btn.setProperty("class", "button save")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "button cancel")

        def do_save():
            keys = keys_edit.text().strip().lower()
            if keys:
                if parse_hotkey(keys) is None:
                    desc_label.setText(f"Invalid key combination: {keys}")
                    return
                hotkeys = self._load_hotkeys()
                # Drop another action bound to the same keys
                for a in [a for a, k in hotkeys.items() if k.lower() == keys and a != action]:
                    hotkeys.pop(a, None)
                hotkeys[action] = keys
                self._save_hotkeys(hotkeys)
                self.hotkeys_changed.emit()
            self._hotkey_popup.close()

        save_btn.clicked.connect(do_save)
        cancel_btn.clicked.connect(lambda: self._hotkey_popup.close())
        keys_edit.returnPressed.connect(do_save)

        footer_frame = QFrame()
        footer_frame.setProperty("class", "monitor-profile-popup-footer")
        button_layout = QHBoxLayout(footer_frame)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(0)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(clear_btn)
        button_layout.addWidget(cancel_btn)

        layout.addWidget(container_frame)
        layout.addWidget(footer_frame)

        self._hotkey_popup.adjustSize()
        self._hotkey_popup.setPosition(
            alignment="center",
            direction="down",
            offset_left=0,
            offset_top=6,
        )
        self._hotkey_popup.show()


class _HotkeyLineEdit(QLineEdit):
    """QLineEdit that records pressed key combinations as hotkey strings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suppress = False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()

        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            # Show only the modifiers held so far
            self.setText("+".join(self._combo_parts(modifiers, None)))
            return

        if key == Qt.Key.Key_Backspace and not modifiers:
            self.clear()
            return

        if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            # Allow Enter to submit via returnPressed, unless a modifier is held
            if modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
                self.setText(self._combo_text(modifiers, key))
                return
            super().keyPressEvent(event)
            return

        if key == Qt.Key.Key_Escape and not modifiers:
            self.clear()
            return

        text = self._combo_text(modifiers, key)
        if text:
            self.setText(text)

    @staticmethod
    def _combo_parts(modifiers, key) -> list[str]:
        parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("win")

        if key is None:
            return parts

        key_names = {
            Qt.Key.Key_Space: "space",
            Qt.Key.Key_Tab: "tab",
            Qt.Key.Key_Return: "enter",
            Qt.Key.Key_Enter: "enter",
            Qt.Key.Key_Escape: "esc",
            Qt.Key.Key_Backspace: "backspace",
            Qt.Key.Key_Delete: "delete",
            Qt.Key.Key_Insert: "insert",
            Qt.Key.Key_Home: "home",
            Qt.Key.Key_End: "end",
            Qt.Key.Key_PageUp: "pageup",
            Qt.Key.Key_PageDown: "pagedown",
            Qt.Key.Key_Left: "left",
            Qt.Key.Key_Up: "up",
            Qt.Key.Key_Right: "right",
            Qt.Key.Key_Down: "down",
            Qt.Key.Key_Print: "printscreen",
        }
        name = key_names.get(key)
        if name is None:
            ch = None
            # A-Z (0x41-0x5A) and 0-9 (0x30-0x39) map directly to ASCII
            if 0x41 <= key <= 0x5A or 0x30 <= key <= 0x39:
                ch = chr(key).lower()
            elif 0x01000030 <= key <= 0x01000047:  # Qt.Key_F1..F24
                ch = f"f{key - 0x01000030 + 1}"
            if ch is None:
                return parts
            name = ch
        parts.append(name)
        return parts

    @classmethod
    def _combo_text(cls, modifiers, key) -> str:
        return "+".join(cls._combo_parts(modifiers, key))
