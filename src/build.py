import datetime

from cx_Freeze import Executable, setup

from core.utils.utilities import detect_architecture
from settings import APP_ID, BUILD_VERSION, RELEASE_CHANNEL

arch_info = detect_architecture()
if not arch_info:
    raise RuntimeError("Unsupported or undetected architecture. Cannot build MSI package.")

display_arch, msi_arch_suffix = arch_info

build_options = {
    "packages": [
        "core.widgets.yasb",
        "core.widgets.komorebi",
        "core.widgets.glazewm",
    ],
    "constants": [f"ARCHITECTURE='{display_arch}'"],
    "silent_level": 1,
    "silent": True,
    "excludes": ["PySide6", "pydoc_data", "email", "tkinter", "PyQt5", "PySide2", "unittest"],
    "bin_excludes": ["Qt6Pdf.dll", "_avif.cp314-win_amd64.pyd"],
    "zip_exclude_packages": [],
    "zip_include_packages": ["*"],
    "no_compress": True,
    "zip_filename": "library.zip",
    "build_exe": "dist",
    "include_msvcr": True,
    "includes": [
        "holidays.countries",
        "winrt.windows.applicationmodel",
    ],
    "optimize": 1,
    "include_files": [
        ("assets/images/app_icon.png", "assets/images/app_icon.png"),
        ("assets/images/app_transparent.png", "assets/images/app_transparent.png"),
        ("assets/sound/notification01.wav", "assets/sound/notification01.wav"),
        ("assets/sound/notification02.wav", "assets/sound/notification02.wav"),
        ("core/utils/widgets/quick_launch/providers/resources/Everything64.dll", "lib/Everything64.dll"),
        ("core/utils/widgets/quick_launch/providers/resources/emoji.json", "lib/emoji.json"),
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
    "skip_build": True,
    "output_name": f"yasb-{BUILD_VERSION if RELEASE_CHANNEL == 'stable' else 'dev'}-{msi_arch_suffix}.msi",
    "product_name": "YASB Reborn",
    "product_version": BUILD_VERSION,
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
        "core/ui/windows/themes.py",
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
    name="YASB",
    version=BUILD_VERSION,
    author="AmN",
    description="YASB",
    executables=executables,
    options={
        "build_exe": build_options,
        "bdist_msi": bdist_msi_options,
    },
)
