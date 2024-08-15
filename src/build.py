import sys
from cx_Freeze import setup, Executable

version = "1.0.2"
#base = "console"
base = "gui"
build_options = {
    "packages": [
        'core.widgets.yasb.power_menu',
        'core.widgets.yasb.volume',
        'core.widgets.yasb.weather',
        'core.widgets.yasb.memory',
        'core.widgets.yasb.cpu',
        'core.widgets.yasb.active_window',
        'core.widgets.yasb.applications',
        'core.widgets.yasb.battery',
        'core.widgets.yasb.clock',
        'core.widgets.yasb.custom',
        'core.widgets.yasb.github',
        'core.widgets.yasb.media',
        'core.widgets.yasb.wallpapers',
        'core.widgets.yasb.traffic',
        'core.widgets.yasb.wifi',
        'core.widgets.komorebi.active_layout',
        'core.widgets.komorebi.workspaces',
        'core',
        'core.bar',
        'core.bar_manager',
        'core.config',
        'core.event_enums',
        'core.event_service',
        'core.log',
        'core.tray',
        'core.utils.alert_dialog',
        'core.utils.komorebi.client',
        'core.utils.komorebi.event_listener',
        'core.utils.utilities',
        'core.utils.widget_builder',
        'core.utils.win32',
        'core.utils.win32.app_icons',
        'core.utils.win32.app_uwp',
        'core.utils.win32.event_listener',
        'core.utils.win32.media',
        'core.utils.win32.power',
        'core.utils.win32.system_function',
        'core.utils.win32.utilities',
        'core.utils.win32.windows',
        'core.validation.bar',
        'core.validation.config',
        'core.validation.widgets.example',
        'core.validation.widgets.komorebi.active_layout',
        'core.validation.widgets.komorebi.workspaces',
        'core.validation.widgets.yasb.active_window',
        'core.validation.widgets.yasb.applications',
        'core.validation.widgets.yasb.battery',
        'core.validation.widgets.yasb.clock',
        'core.validation.widgets.yasb.cpu',
        'core.validation.widgets.yasb.custom',
        'core.validation.widgets.yasb.github',
        'core.validation.widgets.yasb.media',
        'core.validation.widgets.yasb.memory',
        'core.validation.widgets.yasb.power_menu',
        'core.validation.widgets.yasb.traffic',
        'core.validation.widgets.yasb.volume',
        'core.validation.widgets.yasb.wallpapers',
        'core.validation.widgets.yasb.weather',
        'core.validation.widgets.yasb.wifi',
        'core.watcher',
        'core.widgets.base',
    ],
    "silent_level": 1,
    "excludes": ['PySide6','pydoc_data','email','colorama','tkinter'],
    "build_exe": "dist",
    "include_msvcr": True,
    "optimize": 1,
    "include_files": [
            ("assets/images/app_icon.png","lib/assets/images/app_icon.png"),
            ("config.yaml","config.yaml"),
            ("styles.css","styles.css")
        ]
}

directory_table = [
    ("ProgramMenuFolder", "TARGETDIR", "."),
    ("MyProgramMenu", "ProgramMenuFolder", "."),
]

msi_data = {
    "Directory": directory_table,
    "ProgId": [
        ("Prog.Id", None, None, "This is a description", "IconId", None),
    ],
    "Icon": [
        ("IconId", "assets/images/app_icon.ico"),
    ],
}

bdist_msi_options = {
    "data": msi_data,
    #"target_name": f"yasb_installer.msi",
    "upgrade_code": "{3f620cf5-07b5-47fd-8e37-9ca8ad14b608}",
    "add_to_path": False,
    "dist_dir": "dist/out",
    "initial_target_dir": r'[LocalAppDataFolder]\Yasb',
    "all_users": False,
    "summary_data": {
        "author": "AmN",
        "comments": "Yet Another Status Bar",
        "keywords": "windows; statusbar"
    }
}

executables = [
    Executable(
        "main.py",
        base=base,
        icon="assets/images/app_icon.ico",
        shortcut_name="Yasb",
        shortcut_dir="MyProgramMenu",
        copyright="Copyright (C) 2024 AmN",
        target_name="yasb.exe",
    )
]
setup(
    name="yasb",
    version=version,
    author="AmN",
    description="Yet Another Status Bar",
    executables=executables,
    options={
        "build_exe": build_options,
        "bdist_msi": bdist_msi_options,
    },
)