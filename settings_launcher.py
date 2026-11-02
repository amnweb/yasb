import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from core.ui.views.bar_settings import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
