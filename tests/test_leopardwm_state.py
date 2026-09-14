import copy
import unittest
from dataclasses import FrozenInstanceError

from core.widgets.services.leopardwm.state import SnapshotAssembler

DEVICE = r"\\.\DISPLAY1"


def frames(version=4, revision=0, session="session"):
    records = [dict(kind="monitor", monitor_device_name=DEVICE, monitor_id=1, active_workspace_index=0)]
    records += [dict(kind="workspace", monitor_device_name=DEVICE, workspace_index=i, name=None) for i in range(9)]
    records.append(
        dict(kind="window", monitor_device_name=DEVICE, workspace_index=2, hwnd=123, is_floating=True, is_sticky=False)
    )
    return [
        dict(
            type="workspace_snapshot_begin",
            protocol_version=version,
            session_id=session,
            revision=revision,
            focused_monitor_device_name=DEVICE,
        ),
        dict(type="workspace_snapshot_chunk", revision=revision, records=records),
        dict(type="workspace_snapshot_end", revision=revision),
    ]


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.assembler = SnapshotAssembler()

    def consume(self, events):
        result = None
        for event in events:
            result = self.assembler.feed(event)
        return result

    def test_only_complete_v3_and_v4_snapshots_are_published(self):
        for version in (3, 4):
            self.assembler.reset()
            begin, chunk, end = frames(version)
            self.assertIsNone(self.assembler.feed(begin))
            self.assertIsNone(self.assembler.feed(chunk))
            snapshot = self.assembler.feed(end)
            self.assertEqual(len(snapshot.monitors[0].workspaces), 9)
            self.assertEqual(snapshot.monitors[0].workspaces[2].windows[0].hwnd, 123)
            with self.assertRaises(FrozenInstanceError):
                snapshot.revision = 1

    def test_chunk_order_does_not_change_ownership(self):
        events = frames()
        events[1]["records"].reverse()
        snapshot = self.consume(events)
        self.assertEqual(snapshot.monitors[0].workspaces[2].windows[0].hwnd, 123)

    def test_invalid_records_and_references_discard_staging(self):
        variants = []
        for field, value in (
            ("hwnd", 0),
            ("hwnd", True),
            ("hwnd", 2**64),
            ("workspace_index", 9),
            ("is_floating", 1),
            ("monitor_device_name", "missing"),
        ):
            events = frames()
            events[1]["records"][-1][field] = value
            variants.append(events)
        events = frames()
        events[1]["records"].pop(1)
        variants.append(events)
        for record_index in (0, 1, -1):
            events = frames()
            events[1]["records"].append(copy.deepcopy(events[1]["records"][record_index]))
            variants.append(events)
        events = frames()
        events[0]["focused_monitor_device_name"] = "missing"
        variants.append(events)
        for events in variants:
            with self.subTest(events=events):
                self.assembler.reset()
                with self.assertRaises(ValueError):
                    self.consume(events)
                self.assertFalse(self.assembler.in_progress)

    def test_invalid_boundaries_and_control_events(self):
        for event in (
            frames()[0],
            dict(type="heartbeat", uptime_seconds=1),
            dict(type="lagged", skipped=1),
            dict(type="workspace_snapshot_error", message="bad"),
            dict(type="workspace_snapshot_end", revision=99),
        ):
            self.assembler.reset()
            self.assembler.feed(frames()[0])
            with self.assertRaises(ValueError):
                self.assembler.feed(event)
            self.assertFalse(self.assembler.in_progress)

    def test_monotonic_revisions_and_new_session(self):
        self.consume(frames(revision=3))
        with self.assertRaises(ValueError):
            self.consume(frames(revision=2))
        self.assertEqual(self.consume(frames(session="new")).revision, 0)

    def test_protocol_revision_and_required_fields(self):
        for field, value in (
            ("protocol_version", 2),
            ("protocol_version", True),
            ("revision", -1),
            ("revision", True),
            ("session_id", ""),
        ):
            events = frames()
            events[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.consume(events)
        events = frames()
        del events[1]["records"][1]["name"]
        with self.assertRaises(ValueError):
            self.consume(events)

    def test_record_bound(self):
        self.assembler.MAX_RECORDS = 10
        with self.assertRaises(ValueError):
            self.consume(frames())
        self.assertFalse(self.assembler.in_progress)

    def test_empty_topology_and_idle_heartbeat(self):
        events = frames()
        events[0]["focused_monitor_device_name"] = None
        events[1]["records"] = []
        self.assertEqual(self.consume(events).monitors, ())
        self.assertIsNone(self.assembler.feed(dict(type="heartbeat", uptime_seconds=1)))


if __name__ == "__main__":
    unittest.main()
