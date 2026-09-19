import math
import threading
import unittest
from dataclasses import replace
from unittest.mock import patch

from PIL import Image
from pydantic import ValidationError
from PyQt6 import sip
from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from core.validation.widgets.leopardwm.workspaces import LeopardWMWorkspacesConfig
from core.widgets.leopardwm.workspaces import WorkspaceWidget
from core.widgets.services.leopardwm.state import Monitor, Window, Workspace, WorkspaceSnapshot

DISPLAY1 = r"\\.\DISPLAY1"
DISPLAY2 = r"\\.\DISPLAY2"
MODULE = "core.widgets.leopardwm.workspaces"


def snapshot(windows=(), active=0):
    return WorkspaceSnapshot(
        "session",
        1,
        DISPLAY1,
        tuple(
            Monitor(
                device,
                i,
                active,
                tuple(Workspace(n, "Work" if n == 1 else None, tuple(windows) if n == 1 else ()) for n in range(9)),
            )
            for i, device in enumerate((DISPLAY1, DISPLAY2))
        ),
    )


class FakeClient(QObject):
    state_changed = pyqtSignal(object)
    connection_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.snapshot = snapshot()
        self.connected = True
        self.error_message = ""
        self.activations = []
        self.releases = 0

    def activate_workspace(self, device_name, index):
        self.activations.append((device_name, index))

    def release(self):
        self.releases += 1

    def publish(self, state):
        self.snapshot = state
        self.state_changed.emit(state)


class WorkspaceWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.client = FakeClient()
        self.widgets = []
        self.acquire = patch(f"{MODULE}.LeopardWMClient.acquire", return_value=self.client).start()
        self.process = patch(
            f"{MODULE}.get_process_info",
            side_effect=lambda hwnd: {
                "name": "EDITOR.EXE" if hwnd < 3 else "other.exe",
                "pid": hwnd,
                "path": None,
            },
        ).start()
        self.native = patch(
            f"{MODULE}.get_window_icon", return_value=Image.new("RGBA", (16, 16), (255, 0, 0, 128))
        ).start()

    def tearDown(self):
        for widget in self.widgets:
            if not sip.isdeleted(widget):
                sip.delete(widget)
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QThreadPool.globalInstance().waitForDone(1000)
        patch.stopall()

    def widget(self, *, screen_name=DISPLAY2, monitor_hwnd=None, **options):
        widget = WorkspaceWidget(LeopardWMWorkspacesConfig(**options))
        self.widgets.append(widget)
        widget.screen_name = screen_name
        widget.monitor_hwnd = monitor_hwnd
        self.app.processEvents()
        return widget

    def wait_icons(self, widget):
        for _ in range(100):
            self.app.processEvents()
            if not widget._lookup_running:
                return
            QTest.qWait(10)
        self.fail("Icon lookup did not finish")

    def visible(self, widget):
        return {key: button for key, button in widget._buttons.items() if not button.isHidden()}

    def test_defaults_route_to_bar_screen_after_constructor(self):
        widget = self.widget()
        self.assertEqual(len(self.visible(widget)), 9)
        self.assertEqual({key[0] for key in widget._buttons}, {DISPLAY2})
        self.assertEqual(widget._buttons[DISPLAY2, 0].text_label.text(), "1")
        self.process.assert_not_called()
        self.native.assert_not_called()

    def test_friendly_qt_screen_name_routes_by_native_monitor_handle(self):
        widget = self.widget(screen_name="AW3425DW", monitor_hwnd=1)
        self.assertEqual(set(widget._buttons), {(DISPLAY2, i) for i in range(9)})

    def test_identical_friendly_names_route_to_distinct_native_monitors(self):
        state = self.client.snapshot
        self.client.snapshot = replace(
            state,
            monitors=tuple(
                replace(monitor, monitor_id=handle) for monitor, handle in zip(state.monitors, (101, 202), strict=True)
            ),
        )
        first = self.widget(screen_name="AW3425DW", monitor_hwnd=101)
        second = self.widget(screen_name="AW3425DW", monitor_hwnd=202)
        self.assertEqual({key[0] for key in first._buttons}, {DISPLAY1})
        self.assertEqual({key[0] for key in second._buttons}, {DISPLAY2})

    def test_explicit_device_wins_over_native_bar_monitor(self):
        widget = self.widget(screen_name="AW3425DW", monitor_hwnd=1, monitor=DISPLAY1.lower())
        self.assertEqual({key[0] for key in widget._buttons}, {DISPLAY1})

    def test_native_handle_wins_over_screen_name_fallback(self):
        widget = self.widget(screen_name=DISPLAY1, monitor_hwnd=1)
        self.assertEqual({key[0] for key in widget._buttons}, {DISPLAY2})

    def test_gdi_screen_name_fallback_when_native_handle_does_not_match(self):
        widget = self.widget(screen_name=DISPLAY2, monitor_hwnd=999)
        self.assertEqual({key[0] for key in widget._buttons}, {DISPLAY2})

    def test_all_monitor_scroll_gap_uses_native_bar_monitor(self):
        widget = self.widget(screen_name="AW3425DW", monitor_hwnd=1, monitor_exclusive=False)
        event = QWheelEvent(
            QPointF(-1, -1),
            QPointF(-1, -1),
            QPoint(),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        self.app.sendEvent(widget, event)
        self.assertEqual(self.client.activations, [(DISPLAY2, 8)])

    def test_monitor_override_and_all_monitors(self):
        explicit = self.widget(monitor=DISPLAY1.lower(), monitor_exclusive=False)
        self.assertEqual({key[0] for key in explicit._buttons}, {DISPLAY1})
        all_monitors = self.widget(monitor_exclusive=False)
        self.assertEqual(len(all_monitors._buttons), 18)
        missing = self.widget(monitor="missing")
        self.assertFalse(missing._buttons)

    def test_active_focused_and_occupancy_classes_are_distinct(self):
        self.client.snapshot = snapshot((Window(1, True, False),))
        widget = self.widget(monitor_exclusive=False)
        self.assertIn("active", widget._buttons[DISPLAY2, 0].property("class").split())
        self.assertNotIn("focused", widget._buttons[DISPLAY2, 0].property("class").split())
        self.assertIn("focused", widget._buttons[DISPLAY1, 0].property("class").split())
        self.assertIn("populated", widget._buttons[DISPLAY2, 1].property("class").split())
        self.assertIn("empty", widget._buttons[DISPLAY2, 0].property("class").split())

    def test_hide_empty_retains_active_and_floating_occupancy(self):
        self.client.snapshot = snapshot((Window(1, True, False),))
        widget = self.widget(hide_empty_workspaces=True, app_icons={"enabled": True, "hide_floating": True})
        self.assertEqual(set(self.visible(widget)), {(DISPLAY2, 0), (DISPLAY2, 1)})
        self.assertEqual(widget._buttons[DISPLAY2, 1].icon_labels, [])
        self.native.assert_not_called()

    def test_hide_inactive_retains_only_each_monitors_active(self):
        widget = self.widget(show_inactive_workspaces=False, monitor_exclusive=False)
        self.assertEqual(set(self.visible(widget)), {(DISPLAY1, 0), (DISPLAY2, 0)})

    def test_labels_update_even_when_window_count_does_not_change(self):
        self.client.snapshot = snapshot((Window(1, False, False),))
        widget = self.widget(label_workspace_populated_btn="{index}:{name}:{count}:{monitor}")
        self.assertEqual(widget._buttons[DISPLAY2, 1].text_label.text(), f"2:Work:1:{DISPLAY2}")
        monitor = self.client.snapshot.monitors[1]
        workspaces = list(monitor.workspaces)
        workspaces[1] = replace(workspaces[1], name="New")
        updated = replace(self.client.snapshot, monitors=(replace(monitor, workspaces=tuple(workspaces)),))
        self.client.publish(updated)
        self.assertEqual(widget._buttons[DISPLAY2, 1].text_label.text(), f"2:New:1:{DISPLAY2}")

    def test_click_delegates_zero_based_index_and_monitor(self):
        widget = self.widget()
        widget.show()
        self.app.processEvents()
        QTest.mouseClick(widget._buttons[DISPLAY2, 8], Qt.MouseButton.LeftButton)
        self.assertEqual(self.client.activations, [(DISPLAY2, 8)])

    def test_offline_clears_buttons_and_current_handle_cache(self):
        self.client.snapshot = snapshot((Window(1, False, False),))
        widget = self.widget(app_icons={"enabled": True})
        self.wait_icons(widget)
        self.client.connected = False
        self.client.snapshot = None
        self.client.connection_changed.emit(False)
        self.assertFalse(widget._buttons)
        self.assertFalse(widget._icon_cache)
        self.assertFalse(widget._offline_text.isHidden())
        self.assertFalse(widget.isHidden())
        hidden = self.widget(hide_if_offline=True)
        self.assertTrue(hidden.isHidden())

    def test_glyphs_dedupe_executable_and_overflow_keep_occupancy_count(self):
        self.client.snapshot = snapshot(tuple(Window(n, False, False) for n in (1, 2, 3, 4)))
        widget = self.widget(
            label_workspace_populated_btn="{count}",
            app_icons={
                "enabled": True,
                "mode": "glyph",
                "glyphs": {"editor.exe": "E"},
                "fallback_icon": "?",
                "hide_duplicates": True,
                "max_icons": 1,
            },
        )
        self.wait_icons(widget)
        button = widget._buttons[DISPLAY2, 1]
        self.assertEqual([label.text() for label in button.icon_labels], ["E", "+1"])
        self.assertIn("overflow", button.icon_labels[-1].property("class"))
        self.assertEqual(button.text_label.text(), "4")
        self.native.assert_not_called()

    def test_native_fallback_and_monochrome_preserves_alpha(self):
        self.client.snapshot = snapshot((Window(1, False, False), Window(3, False, False)))
        self.native.side_effect = lambda hwnd: Image.new("RGBA", (16, 16), (255, 0, 0, 128)) if hwnd == 1 else None
        widget = self.widget(app_icons={"enabled": True, "monochrome": True, "fallback_icon": "?"})
        self.wait_icons(widget)
        icons = widget._buttons[DISPLAY2, 1].icon_labels
        color = icons[0].pixmap().toImage().pixelColor(0, 0)
        self.assertEqual((color.red(), color.green(), color.blue(), color.alpha()), (76, 76, 76, 128))
        self.assertEqual(icons[1].text(), "?")

    def test_same_count_handle_replacement_prunes_cache_and_updates_icons(self):
        self.client.snapshot = snapshot((Window(1, False, False),))
        widget = self.widget(app_icons={"enabled": True, "mode": "glyph", "glyphs": {"editor.exe": "E"}})
        self.wait_icons(widget)
        self.client.publish(snapshot((Window(3, False, False),)))
        self.wait_icons(widget)
        self.assertEqual(set(widget._icon_cache), {3})
        self.assertEqual(widget._buttons[DISPLAY2, 1].icon_labels[0].text(), widget.config.app_icons.fallback_icon)
        calls = self.process.call_count
        self.client.publish(replace(self.client.snapshot, revision=2))
        self.wait_icons(widget)
        self.assertEqual(self.process.call_count, calls)

    def test_hide_label_only_when_an_icon_is_shown(self):
        self.client.snapshot = snapshot((Window(1, True, False),))
        widget = self.widget(app_icons={"enabled": True, "hide_label": True, "hide_floating": True})
        self.assertFalse(widget._buttons[DISPLAY2, 1].text_label.isHidden())

    def test_destroy_releases_each_lease_once(self):
        widget = self.widget()
        sip.delete(widget)
        self.assertEqual(self.client.releases, 1)
        self.client.publish(snapshot())

    def test_scroll_wrap_reverse_and_disabled(self):
        widget = self.widget()
        widget.show()
        for reverse, expected in ((False, 8), (True, 1)):
            widget.config.reverse_scroll_direction = reverse
            event = QWheelEvent(
                QPointF(0, 0),
                QPointF(0, 0),
                QPoint(),
                QPoint(0, 120),
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
                Qt.ScrollPhase.NoScrollPhase,
                False,
            )
            self.app.sendEvent(widget, event)
            self.assertEqual(self.client.activations[-1], (DISPLAY2, expected))
        widget.config.enable_scroll_switching = False
        self.app.sendEvent(widget, event)
        self.assertEqual(len(self.client.activations), 2)

    def test_glyph_font_size_matches_icon_size(self):
        self.client.snapshot = snapshot((Window(1, False, False),))
        widget = self.widget(app_icons={"enabled": True, "mode": "glyph", "size": 20})
        self.wait_icons(widget)
        label = widget._buttons[DISPLAY2, 1].icon_labels[0]
        self.assertEqual(label.font().family(), "Segoe Fluent Icons")
        self.assertEqual(label.font().pixelSize(), 20)

    def test_icon_lookup_runs_outside_gui_thread(self):
        lookup_threads = []
        self.process.side_effect = lambda hwnd: lookup_threads.append(threading.get_ident()) or {"name": None}
        self.client.snapshot = snapshot((Window(1, False, False),))
        widget = self.widget(app_icons={"enabled": True, "mode": "glyph"})
        self.wait_icons(widget)
        self.assertTrue(lookup_threads)
        self.assertNotIn(threading.get_ident(), lookup_threads)

    def test_late_icon_result_cannot_repopulate_offline_cache(self):
        self.client.snapshot = snapshot((Window(1, False, False),))
        with patch.object(QThreadPool.globalInstance(), "start"):
            widget = self.widget(app_icons={"enabled": True})
            token = widget._handle_tokens[1]
            self.client.connection_changed.emit(False)
            widget._icons_loaded([(1, token, "editor.exe", True, Image.new("RGBA", (16, 16)))])
        self.assertFalse(widget._icon_cache)
        self.assertFalse(widget._buttons)

    def test_destroy_before_connect_does_not_acquire_a_lease(self):
        widget = WorkspaceWidget(LeopardWMWorkspacesConfig())
        sip.delete(widget)
        self.app.processEvents()
        self.acquire.assert_not_called()

    def test_css_can_size_native_icon_cells_independently(self):
        self.client.snapshot = snapshot((Window(1, False, False),))
        widget = self.widget(app_icons={"enabled": True, "size": 16})
        self.wait_icons(widget)
        widget.setStyleSheet(".icon { min-width: 28px; max-width: 28px; }")
        widget.show()
        self.app.processEvents()
        label = widget._buttons[DISPLAY2, 1].icon_labels[0]
        self.assertEqual(label.width(), 28)
        self.assertEqual(label.pixmap().deviceIndependentSize().width(), 16)

    def test_offline_tooltip_includes_transport_error(self):
        self.client.connected = False
        self.client.snapshot = None
        self.client.error_message = "Failed to start missing-lwm.exe"
        with patch(f"{MODULE}.set_tooltip") as tooltip:
            widget = self.widget()
            tooltip.assert_called_with(widget._offline_text, self.client.error_message)
            self.client.error_occurred.emit("Unsupported workspace events")
            tooltip.assert_called_with(widget._offline_text, "Unsupported workspace events")

    def test_workspace_tooltip_identifies_monitor_name_index_and_count(self):
        self.client.snapshot = snapshot((Window(1, False, False),))
        with patch(f"{MODULE}.set_tooltip") as tooltip:
            widget = self.widget()
            button = widget._buttons[DISPLAY2, 1]
            tooltip.assert_any_call(button, f"{DISPLAY2}\nWorkspace 2 (Work)\n1 window")

    def test_constructor_does_not_show_a_top_level_window(self):
        widget = WorkspaceWidget(LeopardWMWorkspacesConfig())
        self.widgets.append(widget)
        self.assertTrue(widget.isHidden())

    def test_schema_rejects_bad_icon_options(self):
        for options in ({"size": 0}, {"max_icons": -1}, {"mode": "file"}):
            with self.subTest(options=options), self.assertRaises(ValidationError):
                LeopardWMWorkspacesConfig(app_icons=options)

    def test_empty_label_override_keeps_accessible_workspace_identity(self):
        for label, expected in (("○", "○"), ("{index}", "1"), ("{name}:{index}", ":1")):
            with self.subTest(label=label):
                widget = self.widget(label_workspace_empty_btn=label, app_icons={"enabled": True, "hide_label": True})
                button = widget._buttons[DISPLAY2, 0]
                self.assertEqual(button.text_label.text(), expected)
                self.assertFalse(button.text_label.isHidden())
                self.assertIn("Workspace 1", button.accessibleName())
        self.client.publish(snapshot((Window(1, False, False),), active=1))
        widget = self.widgets[-1]
        self.wait_icons(widget)
        self.assertTrue(widget._buttons[DISPLAY2, 1].text_label.isHidden())
        self.assertIn("Workspace 2 (Work)", widget._buttons[DISPLAY2, 1].accessibleName())

    def test_separators_only_between_visible_groups_and_removed_offline(self):
        self.client.snapshot = snapshot((Window(1, False, False),))
        widget = self.widget(workspace_separator="|", hide_empty_workspaces=True)
        separators = [s for s in widget._separators.values() if not s.isHidden()]
        self.assertEqual([s.text() for s in separators], ["|"])
        layout = widget._widget_container_layout
        shown = [layout.itemAt(i).widget() for i in range(layout.count()) if not layout.itemAt(i).widget().isHidden()]
        self.assertEqual(shown, [widget._buttons[DISPLAY2, 0], separators[0], widget._buttons[DISPLAY2, 1]])
        self.client.publish(snapshot(active=4))
        self.assertFalse([s for s in widget._separators.values() if not s.isHidden()])
        self.client.connection_changed.emit(False)
        self.assertFalse(widget._separators)

    def test_separator_text_and_all_monitor_boundaries(self):
        widget = self.widget(workspace_separator="·", monitor_exclusive=False, show_inactive_workspaces=False)
        shown = [s for s in widget._separators.values() if not s.isHidden()]
        self.assertEqual([s.text() for s in shown], ["·"])
        self.assertEqual(self.client.activations, [])
        QTest.mouseClick(shown[0], Qt.MouseButton.LeftButton)
        self.assertEqual(self.client.activations, [])
        disabled = self.widget(workspace_separator="")
        self.assertFalse(disabled._separators)

    def test_focus_coloring_switches_cached_icons_without_requery(self):
        self.client.snapshot = snapshot((Window(1, False, False),), active=1)
        widget = self.widget(
            monitor_exclusive=False,
            app_icons={
                "enabled": True,
                "monochrome": True,
                "focused_monochrome": False,
                "inactive_monochrome": True,
            },
        )
        self.wait_icons(widget)

        def pixel(device):
            return widget._buttons[device, 1].icon_labels[0].pixmap().toImage().pixelColor(0, 0)

        self.assertEqual((pixel(DISPLAY1).red(), pixel(DISPLAY1).green()), (255, 0))
        self.assertEqual((pixel(DISPLAY2).red(), pixel(DISPLAY2).green()), (76, 76))
        self.assertEqual(pixel(DISPLAY2).alpha(), 128)
        calls = self.native.call_count
        self.client.publish(replace(self.client.snapshot, focused_monitor_device_name=DISPLAY2, revision=2))
        self.assertEqual((pixel(DISPLAY1).red(), pixel(DISPLAY1).green()), (76, 76))
        self.assertEqual((pixel(DISPLAY2).red(), pixel(DISPLAY2).green()), (255, 0))
        self.assertEqual(self.native.call_count, calls)

    def test_inactive_color_override_can_preserve_color(self):
        self.client.snapshot = snapshot((Window(1, False, False),))
        widget = self.widget(app_icons={"enabled": True, "monochrome": True, "inactive_monochrome": False})
        self.wait_icons(widget)
        color = widget._buttons[DISPLAY2, 1].icon_labels[0].pixmap().toImage().pixelColor(0, 0)
        self.assertEqual((color.red(), color.green()), (255, 0))

    def test_configurable_cell_width_changes_on_focus_and_never_clips_art(self):
        self.client.snapshot = snapshot((Window(1, False, False),), active=1)
        widget = self.widget(
            monitor_exclusive=False,
            app_icons={
                "enabled": True,
                "cell_width": 28,
                "inactive_cell_width": 20,
            },
        )
        self.wait_icons(widget)

        def width(device):
            return widget._buttons[device, 1].icon_labels[0].minimumWidth()

        self.assertEqual((width(DISPLAY1), width(DISPLAY2)), (28, 20))
        self.client.publish(replace(self.client.snapshot, focused_monitor_device_name=DISPLAY2, revision=2))
        self.assertEqual((width(DISPLAY1), width(DISPLAY2)), (20, 28))
        small = self.widget(app_icons={"enabled": True, "size": 24, "cell_width": 8})
        self.wait_icons(small)
        self.assertEqual(small._buttons[DISPLAY2, 1].icon_labels[0].minimumWidth(), 24)

    def test_indicator_toggle_marks_only_globally_focused_workspace(self):
        widget = self.widget(monitor_exclusive=False, show_focus_indicator=True)
        self.assertIn("focus-indicator", widget._buttons[DISPLAY1, 0].property("class").split())
        self.assertNotIn("focus-indicator", widget._buttons[DISPLAY2, 0].property("class").split())
        self.client.publish(replace(self.client.snapshot, focused_monitor_device_name=DISPLAY2, revision=2))
        self.assertNotIn("focus-indicator", widget._buttons[DISPLAY1, 0].property("class").split())
        self.assertIn("focus-indicator", widget._buttons[DISPLAY2, 0].property("class").split())
        disabled = self.widget(show_focus_indicator=False)
        self.assertNotIn("focus-indicator", disabled._buttons[DISPLAY2, 0].property("class").split())

    def test_presentation_schema_defaults_preserve_legacy_behavior(self):
        config = LeopardWMWorkspacesConfig()
        self.assertIsNone(config.label_workspace_empty_btn)
        self.assertEqual(config.workspace_separator, "")
        self.assertFalse(config.show_focus_indicator)
        self.assertIsNone(config.app_icons.focused_monochrome)
        self.assertIsNone(config.app_icons.inactive_monochrome)
        self.assertIsNone(config.app_icons.cell_width)
        self.assertIsNone(config.app_icons.inactive_cell_width)
        for options in ({"cell_width": 0}, {"inactive_cell_width": -1}, {"cell_width": 129}):
            with self.subTest(options=options), self.assertRaises(ValidationError):
                LeopardWMWorkspacesConfig(app_icons=options)

    def test_focus_indicator_css_draws_underline_without_changing_geometry(self):
        widget = self.widget(monitor_exclusive=False, show_focus_indicator=True)
        widget.setStyleSheet(
            ".ws-btn { border: none; border-bottom: 2px solid transparent; min-width: 24px; min-height: 24px; }"
            ".ws-btn.focus-indicator { border-bottom-color: #40ff40; }"
        )
        widget.show()
        self.app.processEvents()
        button = widget._buttons[DISPLAY1, 0]
        size = button.size()

        def underline_band():
            # grab() renders at the screen's device pixel ratio, so the 2px logical
            # border spans ceil(2 * ratio) physical rows and the outermost one may be
            # a partially covered blend rather than the pure border colour. Sample the
            # whole band so the assertion holds at any display scale.
            pixmap = button.grab()
            image = pixmap.toImage()
            rows = math.ceil(2 * pixmap.devicePixelRatio())
            x = image.width() // 2
            return {image.pixelColor(x, image.height() - 1 - row).name() for row in range(rows)}

        self.assertIn("#40ff40", underline_band())
        self.client.publish(replace(self.client.snapshot, focused_monitor_device_name=DISPLAY2, revision=2))
        self.app.processEvents()
        self.assertEqual(button.size(), size)
        self.assertNotIn("#40ff40", underline_band())

    def test_null_focus_has_no_indicator_and_uses_inactive_icon_treatment(self):
        self.client.snapshot = replace(snapshot((Window(1, False, False),), active=1), focused_monitor_device_name=None)
        widget = self.widget(
            monitor_exclusive=False,
            show_focus_indicator=True,
            app_icons={
                "enabled": True,
                "inactive_monochrome": True,
                "focused_monochrome": False,
            },
        )
        self.wait_icons(widget)
        for device in (DISPLAY1, DISPLAY2):
            button = widget._buttons[device, 1]
            self.assertNotIn("focus-indicator", button.property("class").split())
            color = button.icon_labels[0].pixmap().toImage().pixelColor(0, 0)
            self.assertEqual((color.red(), color.green()), (76, 76))


if __name__ == "__main__":
    unittest.main()
