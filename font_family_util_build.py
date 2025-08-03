import os
import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        project_root = Path(self.root)
        cmake_source_dir = project_root / "src" / "core" / "utils" / "font_family_util"
        build_dir = cmake_source_dir / "Release"

        if build_dir.exists():
            shutil.rmtree(build_dir)

        build_dir.mkdir(parents=True, exist_ok=True)

        print("--- Running CMake configuration ---")

        subprocess.run(
            ["cmake", "-S", str(cmake_source_dir), "-B", str(build_dir)],
            check=True,
        )

        print("--- Running CMake build ---")

        subprocess.run(
            ["cmake", "--build", str(build_dir), "--config", "Debug"],
            check=True,
        )
