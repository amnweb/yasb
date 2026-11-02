"""Small, loss-conscious editor for existing YASB configuration files."""

import copy
import os
import re
import tempfile
from pathlib import Path

import yaml

SECTIONS = ("left", "center", "right")
STYLE_START = "/* YASB settings: begin */"
STYLE_END = "/* YASB settings: end */"
STYLE_BLOCK = re.compile(re.escape(STYLE_START) + r".*?" + re.escape(STYLE_END), re.S)


def atomic_write(path: Path, content: bytes) -> None:
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class SettingsDocument:
    def __init__(self, directory: Path):
        self.directory = directory
        self.config_path = directory / "config.yaml"
        if not self.config_path.exists():
            self.config_path = directory / "config"
        self.style_path = directory / "styles.css"
        self.original_config = self.config_path.read_bytes()
        self.original_style = self.style_path.read_bytes()
        self.config = yaml.safe_load(self.original_config.decode("utf-8-sig"))
        self.css = self.original_style.decode("utf-8-sig")
        if not isinstance(self.config, dict) or not isinstance(self.config.get("bars"), dict):
            raise ValueError("The configuration must contain a bars mapping.")
        if not self.config["bars"] or not isinstance(self.config.get("widgets"), dict):
            raise ValueError("At least one bar and a widgets mapping are required.")
        for bar in self.config["bars"].values():
            if not isinstance(bar, dict) or not isinstance(bar.get("widgets"), dict):
                raise ValueError("Each bar must contain a widgets mapping.")
            for section in SECTIONS:
                items = bar["widgets"].get(section, [])
                if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
                    raise ValueError("Widget placements must be lists of names.")
                if any(item not in self.config["widgets"] for item in items):
                    raise ValueError("A bar references a missing widget definition.")

    def appearance(self) -> dict:
        def last_number(pattern: str, default: float) -> float:
            managed = STYLE_BLOCK.search(self.css)
            matches = re.findall(pattern, managed.group() if managed else "")
            if matches:
                return float(matches[-1])
            matches = re.findall(pattern, self.css)
            return float(matches[0]) if matches else default

        backgrounds = re.findall(
            r"(?:background-color\s*:|--yasb-bar-bg\s*:)\s*rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)",
            self.css,
        )
        # A managed override is the last matching bar background, not a popup background.
        bar_backgrounds = re.findall(r"\.yasb-bar\s*\{[^}]*background-color\s*:\s*rgba\(([^)]+)\)", self.css)
        color = [20, 22, 27, 0.84]
        if backgrounds:
            color = [float(value) for value in backgrounds[0]]
        if bar_backgrounds:
            parts = bar_backgrounds[-1].split(",")
            if len(parts) == 4:
                color = [float(value) for value in parts]
        return {
            "font_size": round(last_number(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", 12)),
            "spacing": round(last_number(r"padding\s*:\s*0\s+(\d+)px", 8)),
            "opacity": round(color[3] * 100),
            "rgb": tuple(round(value) for value in color[:3]),
        }

    def render(
        self, bar_name: str, placements: dict, appearance: dict, clock: tuple | None = None
    ) -> tuple[bytes, bytes]:
        config = copy.deepcopy(self.config)
        for section in SECTIONS:
            items = placements[section]
            if any(item not in config["widgets"] for item in items):
                raise ValueError("Unknown widget selected.")
            config["bars"][bar_name]["widgets"][section] = list(items)
        for key, low, high in (("font_size", 8, 32), ("spacing", 0, 32), ("opacity", 0, 100)):
            if not low <= appearance[key] <= high:
                raise ValueError(f"{key} must be between {low} and {high}.")
        if "height" in appearance:
            if not 16 <= appearance["height"] <= 96:
                raise ValueError("Bar height must be between 16 and 96.")
            config["bars"][bar_name].setdefault("dimensions", {})["height"] = appearance["height"]
        if "tray_icon_size" in appearance:
            if not 8 <= appearance["tray_icon_size"] <= 32:
                raise ValueError("Tray icons must be between 8 and 32 pixels.")
            for widget in config["widgets"].values():
                if isinstance(widget, dict) and widget.get("type") == "yasb.systray.SystrayWidget":
                    widget.setdefault("options", {})["icon_size"] = appearance["tray_icon_size"]
        if clock is not None:
            name, label, label_alt = clock
            widget = config["widgets"][name]
            if not isinstance(widget, dict) or widget.get("type") != "yasb.clock.ClockWidget":
                raise ValueError("The selected widget is not a clock.")
            options = widget.setdefault("options", {})
            options["label"] = label
            options["label_alt"] = label_alt
            options["update_interval"] = 1000 if "%S" in label + label_alt else 60000
        rgb = appearance["rgb"]
        if len(rgb) != 3 or any(not 0 <= value <= 255 for value in rgb):
            raise ValueError("Invalid background colour.")
        rules = (
            f"{STYLE_START}\n"
            f".bar, .yasb-bar {{ background-color: rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {appearance['opacity'] / 100:.2f}); }}\n"
            f".bar .widget, .yasb-bar .widget {{ padding: 0 {appearance['spacing']}px; }}\n"
            f".bar .widget .label, .yasb-bar .widget .label {{ font-size: {appearance['font_size']}px; }}\n"
            f"{STYLE_END}"
        )
        css = STYLE_BLOCK.sub("", self.css).rstrip() + "\n\n" + rules + "\n"
        text = yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
        return text.encode("utf-8"), css.encode("utf-8")

    def save(self, config: bytes, css: bytes) -> None:
        if self.config_path.read_bytes() != self.original_config or self.style_path.read_bytes() != self.original_style:
            raise ValueError("These files changed since the window opened. Close and reopen Settings before saving.")
        # Preserve the previous pair before touching either live file.
        atomic_write(self.directory / "config.settings-backup.yaml", self.original_config)
        atomic_write(self.directory / "styles.settings-backup.css", self.original_style)
        atomic_write(self.style_path, css)
        try:
            atomic_write(self.config_path, config)
        except OSError:
            atomic_write(self.style_path, self.original_style)
            raise
        self.original_config, self.original_style = config, css
        self.config = yaml.safe_load(config.decode("utf-8"))
        self.css = css.decode("utf-8")
