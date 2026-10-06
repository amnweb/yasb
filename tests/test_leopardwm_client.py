import json
import sys
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QEventLoop, QProcess, QTimer
from PyQt6.QtWidgets import QApplication
from test_leopardwm_state import DEVICE, frames

from core.widgets.services.leopardwm.client import LeopardWMClient


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.start = patch.object(LeopardWMClient, "_start_subscription")
        self.start_mock = self.start.start()
        self.client = LeopardWMClient.acquire("test-lwm.exe")
        self.app.processEvents()
        self.states = []
        self.client.state_changed.connect(self.states.append)

    def tearDown(self):
        self.client.release()
        self.app.processEvents()
        self.start.stop()

    def feed(self, events=None):
        data = b"".join(json.dumps(event).encode() + b"\n" for event in (events or frames()))
        self.client._consume_data(data)

    def test_shared_leases_keep_subscription_alive(self):
        second = LeopardWMClient.acquire("test-lwm.exe")
        self.assertIs(self.client, second)
        second.release()
        self.assertFalse(self.client._closed)
        self.assertEqual(self.start_mock.call_count, 1)

    def test_split_utf8_and_atomic_update(self):
        events = frames()
        events[1]["records"][1]["name"] = "開発"
        data = b"".join(json.dumps(event, ensure_ascii=False).encode() + b"\n" for event in events)
        for byte in data[:-1]:
            self.client._consume_data(bytes([byte]))
        self.assertFalse(self.client.connected)
        self.assertIsNone(self.client.snapshot)
        self.client._consume_data(data[-1:])
        self.assertTrue(self.client.connected)
        self.assertEqual(self.client.snapshot.monitors[0].workspaces[0].name, "開発")
        self.assertEqual(len(self.states), 1)

    def test_protocol_failure_clears_visible_stale_state_and_retries(self):
        self.feed()
        self.feed([dict(type="lagged", skipped=10)])
        self.assertFalse(self.client.connected)
        self.assertIsNone(self.client.snapshot)
        self.assertIsNone(self.states[-1])
        self.assertTrue(self.client._reconnect_timer.isActive())
        self.assertTrue(self.client.error_message)

    def test_invalid_frames_recover(self):
        for data in (
            b"\xff\n",
            b"[]\n",
            b"{\n",
            b"x" * 65536,
            b"{}" + b" " * 65534 + b"\n",
            b'{"type":"heartbeat","type":"heartbeat","uptime_seconds":1}\n',
        ):
            with self.subTest(data=data[:50]):
                self.client._recovering = False
                self.client._consume_data(data)
                self.assertTrue(self.client._recovering)
                self.assertEqual(self.client._buffer, b"")

    def test_total_snapshot_size_and_deadline_are_bounded(self):
        self.client.MAX_SNAPSHOT_BYTES = 100
        self.feed([frames()[0]])
        self.assertTrue(self.client._recovering)
        self.client._recovering = False
        self.client.MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024
        self.feed([frames()[0]])
        self.assertTrue(self.client._snapshot_timer.isActive())
        self.client._snapshot_timer.timeout.emit()
        self.assertFalse(self.client._assembler.in_progress)
        self.assertTrue(self.client._recovering)

    def test_liveness_timeout_clears_snapshot(self):
        self.feed()
        self.assertEqual(self.client._heartbeat_timer.interval(), 45_000)
        self.client._heartbeat_timer.timeout.emit()
        self.assertIsNone(self.client.snapshot)
        self.assertFalse(self.client.connected)

    def test_activation_uses_separate_argv_and_one_based_index(self):
        self.feed()
        with patch.object(QProcess, "start") as start:
            self.client.activate_workspace(DEVICE, 8)
            process = next(iter(self.client._commands))
            self.assertEqual(process.program(), "test-lwm.exe")
            self.assertEqual(process.arguments(), ["workspace", "9", "--monitor", DEVICE])
            start.assert_called_once()
            for _ in range(20):
                self.client.activate_workspace(DEVICE, 0)
            self.assertEqual(len(self.client._commands), self.client.MAX_COMMANDS)

    def test_invalid_activation_does_not_start_process(self):
        self.feed()
        with patch.object(QProcess, "start") as start:
            for device, index in ((DEVICE, -1), (DEVICE, 9), (DEVICE, True), ("missing", 0)):
                self.client.activate_workspace(device, index)
            start.assert_not_called()

    def test_command_timeout_and_failed_start_are_cleaned_up(self):
        self.feed()
        with patch.object(QProcess, "start"):
            self.client.activate_workspace(DEVICE, 1)
        process, timer = next(iter(self.client._commands.items()))
        timer.timeout.emit()
        self.assertFalse(self.client._commands)
        self.assertTrue(self.client.connected)
        self.assertIn("timed out", self.client.error_message)

    def test_release_stops_timers_and_all_children(self):
        self.feed()
        self.client.release()
        self.assertTrue(self.client._closed)
        self.assertFalse(self.client._heartbeat_timer.isActive())
        self.assertFalse(self.client._snapshot_timer.isActive())
        self.assertFalse(self.client._reconnect_timer.isActive())
        self.assertNotIn("test-lwm.exe", LeopardWMClient._instances)


class ProcessIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_for(self, predicate, timeout=3000):
        loop = QEventLoop()
        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: loop.quit() if predicate() else None)
        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        timer.start()
        deadline.start(timeout)
        if not predicate():
            loop.exec()
        timer.stop()
        deadline.stop()
        self.assertTrue(predicate(), "Timed out waiting for QProcess state")

    def child(self, source):
        client = LeopardWMClient.acquire(sys.executable)
        client._process.setArguments(["-u", "-c", source])
        self.addCleanup(client.release)
        return client

    def test_real_child_stream_and_release_reaps_process(self):
        payload = "".join(json.dumps(event) + "\n" for event in frames())
        client = self.child(f"import sys,time;sys.stdout.write({payload!r});sys.stdout.flush();time.sleep(30)")
        self.wait_for(lambda: client.connected)
        destroyed = []
        client.destroyed.connect(lambda: destroyed.append(True))
        self.assertGreater(client._process.processId(), 0)
        client.release()
        self.wait_for(lambda: bool(destroyed))

    def test_eof_discards_partial_snapshot_and_schedules_reconnect(self):
        payload = json.dumps(frames()[0]) + "\n"
        client = self.child(f"import sys;sys.stdout.write({payload!r});sys.stdout.flush()")
        self.wait_for(lambda: client._reconnect_timer.isActive())
        self.assertIsNone(client.snapshot)
        self.assertFalse(client._assembler.in_progress)
        self.assertFalse(client.connected)

    def test_missing_executable_reports_error_and_retries(self):
        client = LeopardWMClient.acquire("nonexistent-leopardwm-test-executable.exe")
        self.addCleanup(client.release)
        self.wait_for(lambda: client._reconnect_timer.isActive())
        self.assertIn("Cannot start", client.error_message)
        self.assertFalse(client.connected)

    def test_reconnect_starts_fresh_session_after_failed_child(self):
        client = self.child("raise SystemExit(1)")
        self.wait_for(lambda: client._reconnect_timer.isActive())
        payload = "".join(json.dumps(event) + "\n" for event in frames(session="restarted"))
        client._process.setArguments(
            ["-u", "-c", f"import sys,time;sys.stdout.write({payload!r});sys.stdout.flush();time.sleep(30)"]
        )
        client._reconnect_timer.start(1)
        self.wait_for(lambda: client.connected)
        self.assertEqual(client.snapshot.session_id, "restarted")
        client._on_quit()
        self.assertEqual(client._process.state(), QProcess.ProcessState.NotRunning)


if __name__ == "__main__":
    unittest.main()
