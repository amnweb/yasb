import ctypes
import threading
import time
import unittest
import uuid
from unittest.mock import patch

import win32con
import win32gui
from PIL import Image

from core.utils.win32 import app_icons
from core.utils.win32.bindings import SendMessageTimeoutW


class BoundedIconLookupTests(unittest.TestCase):
    def setUp(self):
        self.image = Image.new("RGBA", (16, 16), (30, 80, 120, 255))
        self.send = self.mock("SendMessageTimeoutW", return_value=0, create=True)
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

        def success(hwnd, message, which, dpi, flags, timeout, result):
            result._obj.value = handle
            return 1

        self.send.side_effect = success
        self.assertIs(app_icons.get_window_icon(123), self.image)
        self.convert.assert_called_once_with(handle)
        args = self.send.call_args.args
        self.assertEqual(
            args[:6],
            (123, win32con.WM_GETICON, win32con.ICON_BIG, 0, win32con.SMTO_ABORTIFHUNG | win32con.SMTO_BLOCK, 200),
        )
        self.blocking_send.assert_not_called()
        self.destroy.assert_not_called()
        self.aumid.assert_not_called()

    def test_window_icon_is_not_destroyed_by_reader(self):
        self.blocking_send.return_value = 987

        def success(*args):
            args[-1]._obj.value = 987
            return 1

        self.send.side_effect = success
        self.assertIs(app_icons.get_window_icon(123), self.image)
        self.destroy.assert_not_called()

    def test_timeout_preserves_aumid_fallback(self):
        self.aumid.return_value = "Package!Application"
        self.assertIs(app_icons.get_window_icon(123), self.image)
        self.aumid_icon.assert_called_once_with("Package!Application")
        self.assertEqual(self.send.call_count, 3)
        self.convert.assert_not_called()
        self.destroy.assert_not_called()

    def test_timeout_preserves_class_icon_fallback(self):
        self.class_icon.return_value = 456
        self.assertIs(app_icons.get_window_icon(123), self.image)
        self.convert.assert_called_once_with(456)
        self.assertEqual(self.send.call_count, 3)
        self.default_icon.assert_not_called()
        self.destroy.assert_not_called()

    def test_timeout_preserves_default_icon_fallback(self):
        self.assertIs(app_icons.get_window_icon(123), self.image)
        self.convert.assert_called_once_with(321)
        self.assertEqual(self.send.call_count, 3)
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
            self.send.side_effect = SendMessageTimeoutW
            started = time.monotonic()
            self.assertIs(app_icons.get_window_icon(handles[0]), self.image)
            self.assertLess(time.monotonic() - started, 1.8)
            self.assertEqual(self.send.call_count, 3)
            self.convert.assert_called_once_with(321)
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())

    def test_failed_send_does_not_use_output_parameter(self):
        def failure(*args):
            args[-1]._obj.value = 999
            return 0

        self.send.side_effect = failure
        self.assertIs(app_icons.get_window_icon(123), self.image)
        self.convert.assert_called_once_with(321)
        self.assertEqual(self.send.call_count, 3)
        self.destroy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
