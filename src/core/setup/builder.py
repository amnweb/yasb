from yaml import dump as yaml_dump

from core.setup.bar_config import CONFIG_HEADER, ROOT_BAR, ROOT_CONFIG, ROOT_STYLE
from core.setup.widgets_config import WIDGETS_CONFIG
from core.setup.widgets_styles import WIDGET_STYLES

WINDOW_MANAGER_GROUPS: tuple[tuple[str, str, str], ...] = (
    ("komorebi", "Komorebi", "Workspace switcher with per-workspace app icons and scroll support"),
    ("glazewm", "GlazeWM", "Workspace switcher - click to switch, scroll to cycle workspaces"),
    ("windows_desktops", "Virtual Desktops", "Native Windows desktops - switch, rename, create and delete"),
)
OPTIONAL_GROUPS: tuple[tuple[str, str, str], ...] = (
    ("cpu", "CPU", "Real-time CPU usage with histogram and popup graph"),
    ("memory", "Memory", "RAM usage percentage and free memory display"),
    ("quick_launch", "Quick Launch", "Spotlight-style search for apps, files and more"),
    ("active_window", "Active Window", "Title and icon of the currently focused window"),
    ("systray", "Systray", "System tray icons pinned directly to the bar"),
    ("weather", "Weather", "7-day forecast via Open-Meteo, no API key needed"),
    ("github", "GitHub", "Unread count with popup grouped by repo and type"),
    ("microphone", "Microphone", "Mic mute and input level, scroll to adjust volume"),
    ("media", "Media", "Now playing track with popup playback controls"),
)
FEATURE_GROUPS: tuple[tuple[str, str, str], ...] = (*OPTIONAL_GROUPS,)

# Groups written when the user skips the wizard
DEFAULT_GROUPS = ["base", "active_window"]


def build_config(selected_groups: list[str] | None = None, bar_overrides: dict | None = None) -> str:
    if selected_groups is None:
        selected_groups = DEFAULT_GROUPS
    if "base" not in selected_groups:
        selected_groups = ["base", *selected_groups]

    all_widgets: dict = {}
    all_placements: dict = {}

    for group_name in selected_groups:
        preset = WIDGETS_CONFIG[group_name]
        all_widgets.update(preset["config"])
        all_placements.update(preset["placement"])

    left: list[str] = []
    center: list[str] = []
    right: list[str] = []
    section_map = {"left": left, "center": center, "right": right}

    for widget_name, (section, _) in sorted(all_placements.items(), key=lambda x: x[1][1]):
        section_map.get(section, left).append(widget_name)

    config: dict = {**ROOT_CONFIG}

    bar: dict = {
        **ROOT_BAR,
        "alignment": dict(ROOT_BAR["alignment"]),
        "padding": dict(ROOT_BAR["padding"]),
        "animation": dict(ROOT_BAR["animation"]),
        "blur_effect": dict(ROOT_BAR["blur_effect"]),
    }
    if bar_overrides:
        if "screens" in bar_overrides:
            bar["screens"] = bar_overrides["screens"]
        if "bar_style" in bar_overrides:
            if bar_overrides["bar_style"] == "floating":
                bar["alignment"]["center"] = True
                bar["padding"] = {"top": 4, "left": 4, "bottom": 0, "right": 4}
                bar["blur_effect"]["round_corners"] = True
                bar["blur_effect"]["round_corners_type"] = "normal"
                bar["blur_effect"]["border_color"] = "system"
            else:
                bar["alignment"]["center"] = False
                bar["padding"] = {"top": 0, "left": 0, "bottom": 0, "right": 0}
                bar["blur_effect"]["round_corners"] = False
        if "blur_enabled" in bar_overrides:
            bar["blur_effect"]["enabled"] = bar_overrides["blur_enabled"]

    config["bars"] = {
        "primary-bar": {
            **bar,
            "widgets": {"left": left, "center": center, "right": right},
        },
    }

    config["widgets"] = all_widgets

    yaml_body = yaml_dump(config, default_flow_style=False, sort_keys=False, allow_unicode=False)

    return CONFIG_HEADER + yaml_body


def build_styles(
    selected_groups: list[str] | None = None,
    bar_opacity: int = 100,
    bar_style: str = "taskbar",
) -> str:
    if selected_groups is None:
        selected_groups = DEFAULT_GROUPS
    if "base" not in selected_groups:
        selected_groups = ["base", *selected_groups]

    alpha = max(0.01, max(0, min(100, bar_opacity)) / 100)
    bg = f"rgba(36, 36, 36, {alpha:.2f})"
    root_style = ROOT_STYLE.replace("--yasb-bar-bg: rgba(36, 36, 36, 0.60);", f"--yasb-bar-bg: {bg};")
    root_style = root_style.replace("--yasb-popup-bg: rgba(36, 36, 36, 0.60);", f"--yasb-popup-bg: {bg};")
    if bar_style == "taskbar":
        root_style = root_style.replace(
            "    background-color: var(--yasb-bar-bg);\n",
            "    background-color: var(--yasb-bar-bg);\n    border-bottom: 1px solid var(--yasb-bar-border);\n",
        )

    parts = [root_style]

    for group_name in selected_groups:
        style = WIDGET_STYLES.get(group_name, "")
        if style:
            parts.append(style)

    return "\n".join(parts)
