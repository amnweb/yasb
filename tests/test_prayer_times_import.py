import importlib
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


class PrayerTimesImportTest(unittest.TestCase):
    def test_prayer_times_widget_module_imports(self) -> None:
        sys.modules.pop("core.widgets.yasb.prayer_times", None)

        module = importlib.import_module("core.widgets.yasb.prayer_times")

        self.assertTrue(hasattr(module, "PrayerTimesWidget"))


if __name__ == "__main__":
    unittest.main()
