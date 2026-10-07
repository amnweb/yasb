import os
import re
import shutil
import subprocess
import sysconfig
from dataclasses import dataclass
from functools import cache
from pathlib import Path

_TARGETS = {"win-amd64": "x64", "win-arm64": "arm64"}
_VC_COMPONENTS = {
    "x64": "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
    "arm64": "Microsoft.VisualStudio.Component.VC.Tools.ARM64",
}
_VCVARS_ARCHS = {"x64": ("x64", "arm64_x64"), "arm64": ("arm64", "x64_arm64")}
_DIAGNOSTIC = re.compile(r"^(?P<file>[^\s(][^(]*)\((?P<line>\d+)(?:,\d+)?\)\s*:\s*(?P<text>.*)$")


class ToolchainMissing(RuntimeError):
    pass


@dataclass(frozen=True)
class Diagnostic:
    file: str
    line: int
    text: str


@dataclass(frozen=True)
class Toolchain:
    target: str
    env: tuple[tuple[str, str], ...]
    msvc_version: str
    sdk_version: str

    @property
    def description(self) -> str:
        return f"MSVC {self.msvc_version}, Windows SDK {self.sdk_version}, target {self.target}"


@dataclass(frozen=True)
class Build:
    ok: bool
    output: str
    diagnostics: tuple[Diagnostic, ...]
    executable: Path | None


@cache
def find_toolchain() -> Toolchain:
    target = _TARGETS.get(sysconfig.get_platform())
    if target is None:
        raise ToolchainMissing(f"no MSVC target for Python platform {sysconfig.get_platform()!r}")

    program_files = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    vswhere = Path(program_files) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if not vswhere.is_file():
        raise ToolchainMissing("vswhere.exe not found: install Visual Studio or Build Tools with the C++ workload")

    query = [
        str(vswhere),
        *("-latest", "-prerelease", "-products", "*"),
        *("-requires", _VC_COMPONENTS[target]),
        *("-property", "installationPath"),
    ]
    install = subprocess.run(query, capture_output=True, text=True, check=False).stdout.strip()
    vcvars = Path(install) / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat" if install else None
    if vcvars is None or not vcvars.is_file():
        raise ToolchainMissing(f"no Visual Studio installation with {_VC_COMPONENTS[target]}")

    # Native host tools first, then the cross compiler running on the other architecture.
    for arch in _VCVARS_ARCHS[target]:
        # cmd /s strips the outer quotes, which keeps the quoted path to vcvarsall.bat intact.
        result = subprocess.run(
            f'cmd.exe /d /s /c ""{vcvars}" {arch} >nul 2>&1 && set"',
            capture_output=True,
            text=True,
            check=False,
        )
        env = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        if result.returncode == 0 and "VCToolsVersion" in env and _compiler(env):
            return Toolchain(
                target=target,
                env=tuple(sorted(env.items())),
                msvc_version=env["VCToolsVersion"],
                sdk_version=env.get("WindowsSDKVersion", "unknown").strip("\\"),
            )
    raise ToolchainMissing(f"vcvarsall.bat found no cl.exe for {target} (tried {', '.join(_VCVARS_ARCHS[target])})")


def _compiler(env: dict[str, str]) -> str | None:
    # CreateProcess searches the parent's PATH, not the one passed in env, so resolve cl.exe here.
    return shutil.which("cl.exe", path=env.get("PATH") or env.get("Path"))


def compile_cpp(toolchain: Toolchain, source: str, workdir: Path, name: str = "probe") -> Build:
    workdir.mkdir(parents=True, exist_ok=True)
    cpp = workdir / f"{name}.cpp"
    exe = workdir / f"{name}.exe"
    cpp.write_text(source, encoding="utf-8")
    env = dict(toolchain.env)
    compiler = _compiler(env)
    if compiler is None:
        raise ToolchainMissing(f"cl.exe is no longer on the PATH of {toolchain.description}")
    result = subprocess.run(
        [compiler, "/nologo", "/std:c++17", "/EHsc", "/W0", "/utf-8", cpp.name, f"/Fe:{exe.name}"],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    diagnostics = tuple(
        Diagnostic(Path(m["file"]).name, int(m["line"]), m["text"])
        for m in map(_DIAGNOSTIC.match, output.splitlines())
        if m
    )
    ok = result.returncode == 0 and exe.is_file()
    return Build(ok=ok, output=output, diagnostics=diagnostics, executable=exe if ok else None)


def run(executable: Path) -> str:
    result = subprocess.run([str(executable)], capture_output=True, text=True, check=True)
    return result.stdout
