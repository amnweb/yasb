# YASB — Copilot Instructions

## Project Overview
YASB (Yet Another Status Bar) is a **Windows-only** status bar built with **PyQt6** and **Pydantic v2**. It runs as a single-instance GUI app using `qasync` for async integration. Python ≥ 3.14 required. No test suite exists.

## Architecture
- **Entry point**: `src/main.py` → acquires a Windows mutex (single instance), creates `YASBApplication` (QApplication subclass), loads config/stylesheet, initializes `BarManager`.
- **BarManager** (`src/core/bar_manager.py`) owns all `Bar` instances, manages widget lifecycle, hotkeys, and screen change handling.
- **Bar** (`src/core/bar.py`) is a frameless `QWidget` registered as a Win32 AppBar. Each bar has left/center/right widget columns defined in YAML config.
- **EventService** (`src/core/event_service.py`) is a singleton (`@lru_cache`) pub/sub bus using `pyqtSignal`. Widgets register signals for events; cross-widget communication goes through this service.
- **CLI** (`src/cli.py`, binary: `yasbc`) communicates with the running YASB instance via Win32 named pipes (`\\.\pipe\yasb_pipe_cli`).

## Widget System — The Core Pattern
Every widget has two paired files mirroring each other's directory structure:

| Purpose | Path | Base Class |
|---------|------|------------|
| Config/validation model | `src/core/validation/widgets/yasb/<name>.py` | `CustomBaseModel` (Pydantic) |
| Widget implementation | `src/core/widgets/yasb/<name>.py` | `BaseWidget` (QWidget) |

### Creating a New Widget
1. **Validation model** in `src/core/validation/widgets/yasb/<name>.py`:
   ```python
   from core.validation.widgets.base_model import CallbacksConfig, CustomBaseModel
   class MyCallbacks(CallbacksConfig):
       on_left: str = "toggle_label"
   class MyWidgetConfig(CustomBaseModel):
       label: str = "default {info}"
       update_interval: int = Field(default=1000, ge=1000, le=60000)
       callbacks: MyCallbacks = MyCallbacks()
   ```
2. **Widget class** in `src/core/widgets/yasb/<name>.py`:
   ```python
   from core.validation.widgets.yasb.my_widget import MyWidgetConfig
   from core.widgets.base import BaseWidget
   class MyWidget(BaseWidget):
       validation_schema = MyWidgetConfig  # links Pydantic model
       def __init__(self, config: MyWidgetConfig):
           super().__init__(class_name="my-widget")
           self.config = config
           self.register_callback("toggle_label", self._toggle_label)
           self.callback_left = config.callbacks.on_left
   ```
3. **No manual registration needed** — `BaseWidget.__init_subclass__` auto-registers into `WIDGET_REGISTRY` with key `"yasb.<module>.<ClassName>"`.
4. **Reference in config.yaml** using the registry key: `type: "yasb.my_widget.MyWidget"`.

### Widget Conventions
- Class names: `<Name>Widget` (e.g., `CpuWidget`, `ClockWidget`)
- Config model names: `<Name>Config` (e.g., `CpuConfig`, `ClockConfig`)
- The `validation_schema` class attribute **must** be set to the Pydantic model class
- Constructor receives a single `config` parameter (already validated by `WidgetBuilder`)
- Use `self.widget_layout` (inherited `QHBoxLayout`) to add child Qt widgets
- Register callbacks via `self.register_callback(name, method)` and bind to `self.callback_left/right/middle`
- Timer-based updates: pass `timer_interval` to `super().__init__()` and override `_timer_callback`

## Configuration & Styling
- **Config**: YAML at `~/.config/yasb/config.yaml`, validated by `YasbConfig` → `BarConfig` Pydantic models in `src/core/validation/`
- **Styles**: Qt StyleSheet syntax (not standard CSS) at `~/.config/yasb/styles.css`. Supports `:root` CSS variables via `CSSProcessor`. Widgets are targeted by class: `.cpu-widget`, `.clock-widget`
- **Schema**: `schema.json` is auto-generated from all widget `validation_schema` models via `src/core/validation/export_schema.py` for YAML IDE autocompletion
- Environment variables in config use `$env:VARIABLE_NAME` syntax (PowerShell-style)

## Build & Dev Commands
All commands run from the `src/` directory:
```powershell
pip install -e ".[dev]"          # Dev install with ruff + stubs
python build.py build_exe        # cx_Freeze → frozen exe in dist/
python build.py bdist_msi        # MSI installer in dist/out/
python main.py                   # Run from source
```

## Code Style
- **Ruff** with `line-length = 120`, rules: `I` (isort) + `F` (pyflakes)
- Double quotes, space indentation
- Type hints used throughout (`str`, `list[str]`, `dict[str, Any]`, `X | None`)
- Pydantic models use `extra="forbid"` and `validate_default=True` via `CustomBaseModel`

## Key Directories
- `src/core/widgets/yasb/` — all built-in widget implementations (~47 widgets)
- `src/core/validation/widgets/` — mirrors widget dir with Pydantic config models
- `src/core/utils/` — widget builder, CLI server, Win32 utilities, CSS processing
- `src/core/ui/` — color tokens, programmatic button styling, theme windows
- `src/assets/` — bundled images and sounds
- `docs/widgets/` — per-widget documentation pages
