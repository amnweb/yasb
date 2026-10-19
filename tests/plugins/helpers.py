import importlib
import io
import json
import sys
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

from core.plugins.loader import PLUGIN_NAMESPACE

FIXTURE = Path(__file__).parent / "fixtures" / "hello"
PLUGIN_ID = "hello"
PACKAGE = f"{PLUGIN_NAMESPACE}.hello"
WIDGET_TYPE = f"plugins.{PLUGIN_ID}.HelloWidget"


def manifest_data(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    return data | changes


def write_manifest(plugin_dir: Path, **changes: Any) -> None:
    (plugin_dir / "manifest.json").write_text(json.dumps(manifest_data(**changes)), encoding="utf-8")


def plugin_modules() -> list[str]:
    return [name for name in sys.modules if name == PLUGIN_NAMESPACE or name.startswith(f"{PLUGIN_NAMESPACE}.")]


def zip_folder(folder: Path, prefix: str = "") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, prefix + path.relative_to(folder).as_posix())
    return buffer.getvalue()


def boom_module(plugin_dir: Path) -> ModuleType:
    from core.plugins.resolver import resolve_widget_class

    (plugin_dir / "boom.py").write_text("def explode():\n    raise RuntimeError('boom')\n", encoding="utf-8")
    resolve_widget_class(WIDGET_TYPE)
    return importlib.import_module(f"{PACKAGE}.boom")
