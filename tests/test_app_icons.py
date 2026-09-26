import ctypes
import threading
import time
import unittest
import uuid
from unittest.mock import patch

import pywintypes
import win32con
import win32gui
from PIL import Image
from win32gui import SendMessageTimeout

from core.utils.win32 import app_icons


class BoundedIconLookupTests(unittest.TestCase):
    def setUp(self):
        self.image = Image.new("RGBA", (16, 16), (30, 80, 120, 255))
        self.send = self.mock(
            "win32gui.SendMessageTimeout", side_effect=pywintypes.error(0, "SendMessageTimeout", "Timed out")
        )
        self.blocking_send = self.mock("win32gui.SendMessage", return_value=0)
        self.destroy = self.mock("win32gui.DestroyIcon")
        self.convert = self.mock("hicon_to_image", return_value=self.image)
        self.aumid = self.mock("get_aumid_for_window", return_value=None)
        self.aumid_icon = self.mock("get_icon_for_aumid", return_value=self.image)
        self.class_icon = self.mock("win32gui.GetClassLongPtr", return_value=0, create=True)
        self.mock("win32gui.GetClassLong", return_value=0)
        self.default_icon = self.mock("win32gui.LoadImage", return_value=321)
        self.mock("win32api.GetSystemMetrics", return_value=32)

    def mock(self, name, **kwargs):
        patcher = patch(f"core.utils.win32.app_icons.{name}", **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_success_preserves_pointer_width_and_borrowed_icon(self):
        handle = (1 << (ctypes.sizeof(ctypes.c_void_p) * 8 - 1)) + 123

        self.send.side_effect = None
        self.send.return_value = (1, handle)
        self.assertIs(app_icons.get_window_icon(123), self.image)
        self.convert.assert_called_once_with(handle)
        args = self.send.call_args.args
        self.assertEqual(
            args,
            (123, win32con.WM_GETICON, win32con.ICON_BIG, 0, win32con.SMTO_ABORTIFHUNG | win32con.SMTO_BLOCK, 200),
        )
        self.blocking_send.assert_not_called()
        self.destroy.assert_not_called()
        self.aumid.assert_not_called()

    def test_window_icon_is_not_destroyed_by_reader(self):
        self.blocking_send.return_value = 987

        self.send.side_effect = None
        self.send.return_value = (1, 987)
        self.assertIs(app_icons.get_window_icon(123), self.image)
        self.destroy.assert_not_called()

    def test_timeout_preserves_aumid_fallback(self):
        self.aumid.return_value = "Package!Application"
        self.assertIs(app_icons.get_window_icon(123), self.image)
        self.aumid_icon.assert_called_once_with("Package!Application")
        self.assertEqual(self.send.call_count, 1)
        self.convert.assert_not_called()
        self.destroy.assert_not_called()

    def test_timeout_preserves_class_icon_fallback(self):
        self.class_icon.return_value = 456
        self.assertIs(app_icons.get_window_icon(123), self.image)
        self.convert.assert_called_once_with(456)
        self.assertEqual(self.send.call_count, 1)
        self.default_icon.assert_not_called()
        self.destroy.assert_not_called()

    def test_timeout_preserves_default_icon_fallback(self):
        self.assertIs(app_icons.get_window_icon(123), self.image)
        self.convert.assert_called_once_with(321)
        self.assertEqual(self.send.call_count, 1)
        self.assertEqual(self.default_icon.call_args.args[-1], win32con.LR_SHARED)
        self.destroy.assert_not_called()

    def test_real_unresponsive_window_has_bounded_message_wait(self):
        ready, release = threading.Event(), threading.Event()
        handles, errors = [], []

        def window_thread():
            class_name = f"YasbIconTimeoutTest-{uuid.uuid4()}"
            hwnd = None
            atom = None
            try:
                window_class = win32gui.WNDCLASS()
                window_class.lpszClassName = class_name
                window_class.lpfnWndProc = win32gui.DefWindowProc
                atom = win32gui.RegisterClass(window_class)
                hwnd = win32gui.CreateWindow(class_name, "", 0, 0, 0, 1, 1, 0, 0, 0, None)
                handles.append(hwnd)
                ready.set()
                # A private hidden HWND on a separate thread that deliberately does not pump messages.
                release.wait(3)
            except Exception as error:
                errors.append(error)
                ready.set()
            finally:
                if hwnd:
                    win32gui.DestroyWindow(hwnd)
                if atom:
                    win32gui.UnregisterClass(class_name, 0)

        worker = threading.Thread(target=window_thread)
        worker.start()
        try:
            self.assertTrue(ready.wait(2))
            self.assertFalse(errors)
            self.send.side_effect = SendMessageTimeout
            started = time.monotonic()
            self.assertIs(app_icons.get_window_icon(handles[0]), self.image)
            self.assertLess(time.monotonic() - started, 1.8)
            self.assertEqual(self.send.call_count, 1)
            self.convert.assert_called_once_with(321)
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())

    def test_missing_icons_try_smaller_variants(self):
        for missing in (1, 2):
            with self.subTest(missing=missing):
                self.send.reset_mock()
                self.convert.reset_mock()
                self.send.side_effect = [(1, 0)] * missing + [(1, 987)]
                self.assertIs(app_icons.get_window_icon(123), self.image)
                self.convert.assert_called_once_with(987)
                self.assertEqual(
                    [call.args[2] for call in self.send.call_args_list],
                    [win32con.ICON_BIG, win32con.ICON_SMALL, getattr(win32con, "ICON_SMALL2", 2)][: missing + 1],
                )
                self.aumid.assert_not_called()
                self.destroy.assert_not_called()

    def test_missing_all_window_icons_preserves_fallback(self):
        self.send.side_effect = None
        self.send.return_value = (1, 0)
        self.assertIs(app_icons.get_window_icon(123), self.image)
        self.convert.assert_called_once_with(321)
        self.assertEqual(self.send.call_count, 3)
        self.destroy.assert_not_called()

    def test_timeout_after_missing_icon_stops_remaining_requests(self):
        self.send.side_effect = [(1, 0), pywintypes.error(0, "SendMessageTimeout", "Timed out"), (1, 999)]
        self.assertIs(app_icons.get_window_icon(123), self.image)
        self.convert.assert_called_once_with(321)
        self.assertEqual(self.send.call_count, 2)
        self.destroy.assert_not_called()

    def test_transparent_icon_tries_next_variant(self):
        self.send.side_effect = [(1, 987), (1, 654)]
        self.convert.side_effect = [Image.new("RGBA", (16, 16), (0, 0, 0, 0)), self.image]
        self.assertIs(app_icons.get_window_icon(123), self.image)
        self.assertEqual([call.args[0] for call in self.convert.call_args_list], [987, 654])
        self.assertEqual(self.send.call_count, 2)
        self.aumid.assert_not_called()
        self.destroy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
