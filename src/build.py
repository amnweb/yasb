import datetime
import os
import sys
from importlib.util import find_spec

from cx_Freeze import Executable, setup  # pyright: ignore[reportUnknownVariableType, reportMissingTypeStubs]

from core.utils.system import detect_architecture
from settings import APP_ID, BUILD_VERSION, RELEASE_CHANNEL

icon_ico = "assets/images/app_icon.ico"
icon_png = "assets/images/app_icon.png"

if RELEASE_CHANNEL != "stable":
    if os.path.exists("assets/images/app_icon_preview.ico"):
        icon_ico = "assets/images/app_icon_preview.ico"
    if os.path.exists("assets/images/app_icon_preview.png"):
        icon_png = "assets/images/app_icon_preview.png"

arch_info = detect_architecture()
if not arch_info:
    raise RuntimeError("Unsupported or undetected architecture. Cannot build MSI package.")

display_arch, msi_arch_suffix = arch_info

STDLIB_EXCLUDES = {
    "antigravity",
    "curses",
    "doctest",
    "ensurepip",
    "idlelib",
    "lib2to3",
    "pty",
    "pydoc_data",
    "readline",
    "test",
    "this",
    "tkinter",
    "tty",
    "turtle",
    "turtledemo",
    "unittest",
    "venv",
}
plugin_stdlib = {
    name: spec
    for name in sorted(sys.stdlib_module_names)
    if not name.startswith("_") and name not in STDLIB_EXCLUDES and (spec := find_spec(name))
}
stdlib_packages = [name for name, spec in plugin_stdlib.items() if spec.submodule_search_locations is not None]
stdlib_modules = [name for name, spec in plugin_stdlib.items() if spec.submodule_search_locations is None]

hook_dll_name = "YASBTrayHook_arm64.dll" if display_arch == "ARM64" else "YASBTrayHook.dll"
everything_dll_name = "EverythingARM64.dll" if display_arch == "ARM64" else "Everything64.dll"

build_options = {
    "packages": [
        "core.widgets.yasb",
        "core.widgets.komorebi",
        "core.widgets.glazewm",
        "core.plugins",
        "yasb_api",
        *stdlib_packages,
    ],
    "constants": [f"ARCHITECTURE='{display_arch}'"],
    "silent_level": 1,
    "silent": True,
    "excludes": ["PySide6", "PyQt5", "PySide2", *sorted(STDLIB_EXCLUDES)],
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
        *stdlib_modules,
    ],
    "optimize": 1,
    "include_files": [
        (icon_png, "assets/images/app_icon.png"),
        ("assets/images/app_transparent.png", "assets/images/app_transparent.png"),
        ("assets/images/media.png", "assets/images/media.png"),
        ("assets/sound/notification01.wav", "assets/sound/notification01.wav"),
        ("assets/sound/notification02.wav", "assets/sound/notification02.wav"),
        (f"core/widgets/services/quick_launch/providers/resources/{everything_dll_name}", f"lib/{everything_dll_name}"),
        (f"core/widgets/services/systray/hook/{hook_dll_name}", f"lib/{hook_dll_name}"),
        ("core/widgets/services/quick_launch/providers/resources/emoji.json", "lib/emoji.json"),
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
        ("IconId", icon_ico),
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
        ("UriScheme", -1, "Software\\Classes\\yasb-themes", "", "URL:YASB Themes", "TARGETDIR"),
        ("UriSchemeFlag", -1, "Software\\Classes\\yasb-themes", "URL Protocol", "", "TARGETDIR"),
        (
            "UriSchemeCommand",
            -1,
            "Software\\Classes\\yasb-themes\\shell\\open\\command",
            "",
            '"[TARGETDIR]yasb_themes.exe" "%1"',
            "TARGETDIR",
        ),
    ],
}

bdist_msi_options = {
    "data": msi_data,
    "install_icon": icon_ico,
    "upgrade_code": "{3f620cf5-07b5-47fd-8e37-9ca8ad14b608}",
    "add_to_path": True,
    "dist_dir": "dist/out",
    "initial_target_dir": r"[ProgramFiles64Folder]\YASB",
    "all_users": True,
    "skip_build": True,
    "output_name": f"yasb-{BUILD_VERSION if RELEASE_CHANNEL == 'stable' else 'preview'}-{msi_arch_suffix}.msi",
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
        icon=icon_ico,
        shortcut_name="YASB",
        shortcut_dir="MyProgramMenu",
        copyright=f"Copyright (C) {datetime.datetime.now().year} AmN",
        target_name="yasb",
    ),
    Executable(
        "core/ui/views/themes.py",
        base="gui",
        icon=icon_ico,
        copyright=f"Copyright (C) {datetime.datetime.now().year} AmN",
        target_name="yasb_themes",
    ),
    Executable(
        "cli.py",
        base="Console",
        copyright=f"Copyright (C) {datetime.datetime.now().year} AmN",
        target_name="yasbc",
    ),
    Executable(
        "core/cloud/app.py",
        base="gui",
        icon=icon_ico,
        copyright=f"Copyright (C) {datetime.datetime.now().year} AmN",
        target_name="yasb_cloud",
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
