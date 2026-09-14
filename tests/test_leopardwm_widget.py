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

    def widget(self, **options):
        widget = WorkspaceWidget(LeopardWMWorkspacesConfig(**options))
        self.widgets.append(widget)
        widget.screen_name = DISPLAY2
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


if __name__ == "__main__":
    unittest.main()
