from cx_Freeze import setup, Executable
from settings import BUILD_VERSION
import datetime
 
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
        'core.widgets.yasb.language',
        'core.widgets.yasb.disk',
        'core.widgets.yasb.obs',
        'core.widgets.yasb.whkd',
        'core.widgets.yasb.taskbar',
        'core.widgets.komorebi.active_layout',
        'core.widgets.komorebi.workspaces'
    ],

    "silent_level": 1,
    "silent": True,
    "excludes": ['PySide6','pydoc_data','email','colorama','tkinter','PyQt5','PySide2'],
    "build_exe": "dist",
    "include_msvcr": True,
    "includes": ["colorama"],
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
        ("Prog.Id", None, None, "A highly configurable Windows status bar", "IconId", None),
    ],
    "Icon": [
        ("IconId", "assets/images/app_icon.ico"),
    ],
}

bdist_msi_options = {
    "data": msi_data,
    "install_icon": "assets/images/app_icon.ico",
    "upgrade_code": "{3f620cf5-07b5-47fd-8e37-9ca8ad14b608}",
    "add_to_path": True,
    "dist_dir": "dist/out",
    "initial_target_dir": r'[LocalAppDataFolder]\Yasb',
    "all_users": False,
    "summary_data": {
        "author": "AmN",
        "comments": "A highly configurable Windows status bar",
        "keywords": "windows; statusbar; ricing; customization; topbar; taskbar; yasb",
    }
}

executables = [
    Executable(
        "main.py",
        base=base,
        icon="assets/images/app_icon.ico",
        shortcut_name="Yasb",
        shortcut_dir="MyProgramMenu",
        copyright=f"Copyright (C) {datetime.datetime.now().year} AmN",
        target_name="yasb.exe",
    ),  
    Executable(
        "core/utils/cli.py",
        base="Console",
        copyright=f"Copyright (C) {datetime.datetime.now().year} AmN",
        target_name="yasbc.exe",
    )
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