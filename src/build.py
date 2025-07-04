import datetime

from cx_Freeze import Executable, setup

from settings import APP_ID, BUILD_VERSION

build_options = {
    "packages": [
        "core.widgets.yasb.power_menu",
        "core.widgets.yasb.volume",
        "core.widgets.yasb.weather",
        "core.widgets.yasb.memory",
        "core.widgets.yasb.cpu",
        "core.widgets.yasb.libre_monitor",
        "core.widgets.yasb.active_window",
        "core.widgets.yasb.applications",
        "core.widgets.yasb.battery",
        "core.widgets.yasb.clock",
        "core.widgets.yasb.custom",
        "core.widgets.yasb.github",
        "core.widgets.yasb.media",
        "core.widgets.yasb.microphone",
        "core.widgets.yasb.bluetooth",
        "core.widgets.yasb.wallpapers",
        "core.widgets.yasb.traffic",
        "core.widgets.yasb.wifi",
        "core.widgets.yasb.language",
        "core.widgets.yasb.launchpad",
        "core.widgets.yasb.disk",
        "core.widgets.yasb.obs",
        "core.widgets.yasb.whkd",
        "core.widgets.yasb.taskbar",
        "core.widgets.yasb.brightness",
        "core.widgets.yasb.update_check",
        "core.widgets.yasb.windows_desktops",
        "core.widgets.yasb.server_monitor",
        "core.widgets.yasb.notifications",
        "core.widgets.yasb.home",
        "core.widgets.yasb.cava",
        "core.widgets.yasb.systray",
        "core.widgets.yasb.pomodoro",
        "core.widgets.yasb.notes",
        "core.widgets.yasb.recycle_bin",
        "core.widgets.yasb.vscode",
        "core.widgets.yasb.power_plan",
        "core.widgets.yasb.grouper",
        "core.widgets.yasb.todo",
        "core.widgets.komorebi.control",
        "core.widgets.komorebi.active_layout",
        "core.widgets.komorebi.stack",
        "core.widgets.komorebi.workspaces",
        "core.widgets.glazewm.binding_mode",
        "core.widgets.glazewm.tiling_direction",
        "core.widgets.glazewm.workspaces",
    ],
    "silent_level": 1,
    "silent": True,
    "excludes": ["PySide6", "pydoc_data", "email", "tkinter", "PyQt5", "PySide2", "unittest"],
    "zip_exclude_packages": ["*"],
    "build_exe": "dist",
    "include_msvcr": True,
    "includes": [
        "winrt.windows.ui.notifications",
        "winrt.windows.ui.notifications.management",
        "winrt.windows.data.xml.dom",
        "winrt.windows.media",
        "winrt.windows.media.control",
        "winrt.windows.networking",
        "winrt.windows.networking.connectivity",
        "winrt.windows.storage",
        "winrt.windows.storage.streams",
        "winrt.windows.foundation",
        "winrt.windows.foundation.collections",
        "winrt.windows.devices.wifi",
        "winrt.windows.security.credentials",
    ],
    "optimize": 1,
    "include_files": [
        ("assets/images/app_icon.png", "assets/images/app_icon.png"),
        ("assets/images/app_transparent.png", "assets/images/app_transparent.png"),
        ("assets/sound/notification01.wav", "assets/sound/notification01.wav"),
        ("config.yaml", "config.yaml"),
        ("styles.css", "styles.css"),
    ],
}

directory_table = [
    ("ProgramMenuFolder", "TARGETDIR", "."),
    ("MyProgramMenu", "ProgramMenuFolder", "."),
]

msi_data = {
    "Directory": directory_table,
    "ProgId": [
        ("Prog.Id", None, None, "A highly configurable Windows status bar", "IconId", None),
    ],
    "Icon": [
        ("IconId", "assets/images/app_icon.ico"),
    ],
    "Registry": [
        ("AppUserModelId", -1, f"Software\\Classes\\AppUserModelId\\{APP_ID}", "DisplayName", "YASB", "TARGETDIR"),
        (
            "AppUserModelIdIcon",
            -1,
            f"Software\\Classes\\AppUserModelId\\{APP_ID}",
            "IconUri",
            "[TARGETDIR]assets\\images\\app_icon.png",
            "TARGETDIR",
        ),
    ],
}

bdist_msi_options = {
    "data": msi_data,
    "install_icon": "assets/images/app_icon.ico",
    "upgrade_code": "{3f620cf5-07b5-47fd-8e37-9ca8ad14b608}",
    "add_to_path": True,
    "dist_dir": "dist/out",
    "initial_target_dir": r"[ProgramFiles64Folder]\YASB",
    "all_users": True,
    "summary_data": {
        "author": "AmN",
        "comments": "A highly configurable Windows status bar",
        "keywords": "windows; statusbar; ricing; customization; topbar; taskbar; yasb",
    },
}

executables = [
    Executable(
        "main.py",
        base="gui",
        icon="assets/images/app_icon.ico",
        shortcut_name="YASB",
        shortcut_dir="MyProgramMenu",
        copyright=f"Copyright (C) {datetime.datetime.now().year} AmN",
        target_name="yasb",
    ),
    Executable(
        "core/utils/themes.py",
        base="gui",
        icon="assets/images/app_icon.ico",
        copyright=f"Copyright (C) {datetime.datetime.now().year} AmN",
        target_name="yasb_themes",
    ),
    Executable(
        "cli.py",
        base="Console",
        copyright=f"Copyright (C) {datetime.datetime.now().year} AmN",
        target_name="yasbc",
    ),
]

setup(
    name="yasb",
    version=BUILD_VERSION,
    author="AmN",
    description="Yasb Status Bar",
    executables=executables,
    options={
        "build_exe": build_options,
        "bdist_msi": bdist_msi_options,
    },
)
