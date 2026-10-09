import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tests.win32.msvc import Build, Toolchain, compile_cpp, run

HEADERS = (
    "winsock2.h",
    "ws2tcpip.h",
    "windows.h",
    "winternl.h",
    "winioctl.h",
    "shellapi.h",
    "shlobj.h",
    "shobjidl.h",
    "shobjidl_core.h",
    "shlwapi.h",
    "propsys.h",
    "propidl.h",
    "dwmapi.h",
    "uxtheme.h",
    "psapi.h",
    "tlhelp32.h",
    "iphlpapi.h",
    "netioapi.h",
    "wlanapi.h",
    "windot11.h",
    "setupapi.h",
    "cfgmgr32.h",
    "devpropdef.h",
    "powrprof.h",
    "powersetting.h",
    "pdh.h",
    "physicalmonitorenumerationapi.h",
    "highlevelmonitorconfigurationapi.h",
    "lowlevelmonitorconfigurationapi.h",
    "ntddvdeo.h",
    "batclass.h",
    "bluetoothapis.h",
    "mmsystem.h",
    "mmreg.h",
    "ks.h",
    "ksmedia.h",
    "mmdeviceapi.h",
    "audioclient.h",
    "endpointvolume.h",
    "audiopolicy.h",
    "dxgi.h",
    "wincrypt.h",
    "dpapi.h",
    "bcrypt.h",
    "appmodel.h",
    "winstring.h",
    "roapi.h",
    "shellscalingapi.h",
    "winver.h",
)

MISSING_HEADER_HINT = (
    "If the name is right and the SDK declares it, add the header Microsoft Learn names under "
    "Requirements to HEADERS in tests/win32/probe.py."
)

_PRELUDE = r"""
namespace yasb_probe {
template <class T, class = void> struct is_complete : std::false_type {};
template <class T> struct is_complete<T, std::void_t<decltype(sizeof(T))>> : std::true_type {};
template <class T, bool = std::is_enum_v<T>> struct is_signed : std::is_signed<T> {};
template <class T> struct is_signed<T, true> : std::is_signed<std::underlying_type_t<T>> {};

template <class T> void head() {
    using U = std::remove_cv_t<T>;
    if constexpr (std::is_void_v<U>) std::printf("\"v\",0");
    else if constexpr (std::is_function_v<U>) std::printf("\"fn\",0");
    else if constexpr (std::is_pointer_v<U> || std::is_reference_v<U>) std::printf("\"p\",%zu", sizeof(void*));
    else if constexpr (!is_complete<U>::value) std::printf("\"?\",0");
    else if constexpr (std::is_array_v<U>) std::printf("\"a\",%zu", sizeof(U));
    else if constexpr (std::is_floating_point_v<U>) std::printf("\"f\",%zu", sizeof(U));
    else if constexpr (std::is_enum_v<U> || std::is_integral_v<U>)
        std::printf(is_signed<U>::value ? "\"i\",%zu" : "\"u\",%zu", sizeof(U));
    else std::printf("\"s\",%zu", sizeof(U));
}

template <class T> void abi() {
    using U = std::remove_cv_t<T>;
    std::printf("[");
    head<U>();
    if constexpr (std::is_pointer_v<U> || std::is_reference_v<U>) {
        std::printf(",[");
        head<std::remove_pointer_t<std::remove_reference_t<U>>>();
        std::printf("]");
    } else if constexpr (std::is_array_v<U>) {
        std::printf(",[");
        head<std::remove_extent_t<U>>();
        std::printf("]");
    }
    std::printf("]");
}

template <class... A> void args() {
    std::printf("[");
    int i = 0;
    ((std::printf(i++ ? "," : ""), abi<A>()), ...);
    std::printf("]");
}

template <class R, class... A> void signature(R (*)(A...), bool) {
    std::printf("\"ret\":");
    abi<R>();
    std::printf(",\"args\":");
    args<A...>();
    std::printf(",\"variadic\":false");
}

template <class R, class... A> void signature(R (*)(A..., ...), int) {
    std::printf("\"ret\":");
    abi<R>();
    std::printf(",\"args\":");
    args<A...>();
    std::printf(",\"variadic\":true");
}

template <class F> void function(const char* key, bool macro, F f) {
    std::printf("{\"k\":\"%s\",\"macro\":%s,", key, macro ? "true" : "false");
    signature(f, true);
    std::printf("}\n");
}

template <class F> void method(const char* key, size_t index, F f) {
    std::printf("{\"k\":\"%s\",\"index\":%zu,", key, index);
    signature(f, true);
    std::printf("}\n");
}

template <class T> void constant(const char* key, T value) {
    using U = std::decay_t<T>;
    if constexpr (std::is_pointer_v<U>) {
        using P = std::remove_cv_t<std::remove_pointer_t<U>>;
        if constexpr (std::is_function_v<P> || std::is_same_v<P, char> || std::is_same_v<P, wchar_t>)
            std::printf("{\"k\":\"%s\",\"skip\":true}\n", key);
        else
            std::printf("{\"k\":\"%s\",\"value\":%lld,\"size\":%zu}\n", key, (long long)(intptr_t)value, sizeof(U));
    } else if constexpr (std::is_enum_v<U> || std::is_integral_v<U>) {
        if constexpr (is_signed<U>::value)
            std::printf("{\"k\":\"%s\",\"value\":%lld,\"size\":%zu}\n", key, (long long)value, sizeof(U));
        else
            std::printf("{\"k\":\"%s\",\"value\":%llu,\"size\":%zu}\n", key, (unsigned long long)value, sizeof(U));
    } else {
        std::printf("{\"k\":\"%s\",\"skip\":true}\n", key);
    }
}
}  // namespace yasb_probe

#define Y_STRUCT(key, T) std::printf("{\"k\":\"%s\",\"size\":%zu,\"align\":%zu}\n", key, sizeof(T), alignof(T))
#define Y_FIELD(key, T, m) (std::printf("{\"k\":\"%s\",\"offset\":%zu,\"abi\":", key, offsetof(T, m)), \
    yasb_probe::abi<decltype(((T*)nullptr)->m)>(), std::printf("}\n"))
#define Y_FUNCTION(key, macro, name) yasb_probe::function(key, macro, static_cast<decltype(&name)>(nullptr))
#define Y_VTABLE(key, V) std::printf("{\"k\":\"%s\",\"count\":%zu}\n", key, sizeof(V) / sizeof(void*))
#define Y_METHOD(key, V, m) \
    yasb_probe::method(key, offsetof(V, m) / sizeof(void*), static_cast<decltype(((V*)nullptr)->m)>(nullptr))
#define Y_CONSTANT(key, name) yasb_probe::constant(key, (name))
"""


class ProbeError(RuntimeError):
    pass


@dataclass(frozen=True)
class StructRequest:
    key: str
    c_type: str
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class VtableRequest:
    key: str
    c_interface: str
    methods: tuple[str, ...]


@dataclass
class ProbeResult:
    toolchain: str
    structs: dict[str, dict[str, Any]] = field(default_factory=dict[str, dict[str, Any]])
    fields: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict[str, dict[str, dict[str, Any]]])
    functions: dict[str, dict[str, Any]] = field(default_factory=dict[str, dict[str, Any]])
    vtables: dict[str, dict[str, Any]] = field(default_factory=dict[str, dict[str, Any]])
    methods: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict[str, dict[str, dict[str, Any]]])
    constants: dict[str, dict[str, Any]] = field(default_factory=dict[str, dict[str, Any]])
    errors: dict[str, str] = field(default_factory=dict[str, str])

    def to_json(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ProbeResult:
        return cls(**data)


@dataclass(frozen=True)
class _Item:
    key: str
    lines: tuple[str, ...]
    owner: str = ""


def _guarded(name: str, if_macro: str, otherwise: str) -> tuple[str, ...]:
    return (f"#ifdef {name}", if_macro, "#else", otherwise, "#endif")


def struct_key(key: str) -> str:
    return f"S|{key}"


def field_key(key: str, name: str) -> str:
    return f"SF|{key}|{name}"


def function_key(name: str) -> str:
    return f"F|{name}"


def vtable_key(key: str) -> str:
    return f"V|{key}"


def method_key(key: str, name: str) -> str:
    return f"VM|{key}|{name}"


def constant_key(name: str) -> str:
    return f"C|{name}"


def _items(
    structs: list[StructRequest],
    functions: list[str],
    vtables: list[VtableRequest],
    constants: list[str],
) -> dict[str, _Item]:
    items: dict[str, _Item] = {}
    for req in structs:
        owner = struct_key(req.key)
        items[owner] = _Item(owner, (f'Y_STRUCT("{owner}", {req.c_type});',), owner)
        for py_name, c_member in req.fields:
            key = field_key(req.key, py_name)
            items[key] = _Item(key, (f'Y_FIELD("{key}", {req.c_type}, {c_member});',), owner)
    for name in functions:
        key = function_key(name)
        # A macro such as GetWindowLong resolves to another function; the signature is that
        # function's, and the test still has to check the DLL exports the name Python uses.
        guarded = _guarded(name, f'Y_FUNCTION("{key}", true, {name});', f'Y_FUNCTION("{key}", false, {name});')
        items[key] = _Item(key, guarded)
    for req in vtables:
        vtbl = f"{req.c_interface}Vtbl"
        key = vtable_key(req.key)
        items[key] = _Item(key, (f'Y_VTABLE("{key}", {vtbl});',), key)
        for method in req.methods:
            mkey = method_key(req.key, method)
            items[mkey] = _Item(mkey, (f'Y_METHOD("{mkey}", {vtbl}, {method});',), key)
    for name in constants:
        key = constant_key(name)
        items[key] = _Item(key, (f'Y_CONSTANT("{key}", {name});',))
    return items


def _render(items: dict[str, _Item], vendored: str) -> tuple[str, dict[int, str]]:
    lines = ["#include <cstdio>", "#include <cstddef>", "#include <cstdint>", "#include <type_traits>"]
    # C-style COM declarations, so every interface has an IFooVtbl struct to take offsets in.
    lines.append("#define CINTERFACE")
    # Declarations such as EndTask sit behind the legacy WINNT macro.
    lines.append("#define WINNT 1")
    lines += [f"#include <{header}>" for header in HEADERS]
    lines += ["namespace vendored {", *vendored.splitlines(), "}  // namespace vendored"]
    line_map: dict[int, str] = {}

    lines += _PRELUDE.splitlines()
    for index, item in enumerate(items.values()):
        for text in item.lines:
            if not text.startswith("#"):
                text = f"static void probe_{index}() {{ {text} }}"
            lines.append(text)
            line_map[len(lines)] = item.key
    lines.append("int main() {")
    lines += [f"    probe_{index}();" for index in range(len(items))]
    lines += ["    return 0;", "}"]
    return "\n".join(lines) + "\n", line_map


def _failed_items(build: Build, line_map: dict[int, str], source_name: str) -> dict[str, str]:
    failed: dict[str, str] = {}
    block_error = ""
    block_keys: set[str] = set()

    def flush() -> None:
        for key in block_keys:
            failed.setdefault(key, block_error)

    for diag in build.diagnostics:
        is_error = " error " in f" {diag.text}" or diag.text.startswith("error")
        if is_error:
            flush()
            block_error, block_keys = diag.text, set[str]()
        if diag.file == source_name and diag.line in line_map:
            block_keys.add(line_map[diag.line])
    flush()
    return failed


def _probe_once(
    items: dict[str, _Item], vendored: str, toolchain: Toolchain, workdir: Path
) -> tuple[str, dict[str, str]]:
    excluded: dict[str, str] = {}
    for attempt in range(25):
        active = {k: v for k, v in items.items() if k not in excluded}
        if not active:
            return "", excluded
        source, line_map = _render(active, vendored)
        build = compile_cpp(toolchain, source, workdir, name=f"probe{attempt}")
        if build.ok:
            assert build.executable is not None
            return run(build.executable), excluded
        failed = _failed_items(build, line_map, f"probe{attempt}.cpp")
        if not failed:
            raise ProbeError(f"SDK probe failed to compile:\n{build.output[-6000:]}")
        missing_types = {key for key in failed if key.startswith(("S|", "V|"))}
        for key, item in active.items():
            if item.owner in missing_types and key not in failed:
                failed[key] = failed[item.owner]
        excluded.update(failed)
    raise ProbeError("SDK probe did not converge after 25 compiles")


def _parse(output: str, result: ProbeResult) -> None:
    for line in output.splitlines():
        record: dict[str, Any] = json.loads(line)
        kind, _, rest = record.pop("k").partition("|")
        if kind == "S":
            result.structs[rest] = record
        elif kind == "SF":
            owner, _, name = rest.rpartition("|")
            result.fields.setdefault(owner, {})[name] = record
        elif kind == "F":
            result.functions[rest] = record
        elif kind == "V":
            result.vtables[rest] = record
        elif kind == "VM":
            owner, _, name = rest.rpartition("|")
            result.methods.setdefault(owner, {})[name] = record
        elif kind == "C" and not record.get("skip"):
            result.constants[rest] = record


def run_probe(
    toolchain: Toolchain,
    workdir: Path,
    *,
    structs: list[StructRequest],
    functions: list[str],
    vtables: list[VtableRequest],
    constants: list[str],
    vendored: str = "",
) -> ProbeResult:
    items = _items(structs, functions, vtables, constants)
    result = ProbeResult(toolchain=toolchain.description)
    output, errors = _probe_once(items, vendored, toolchain, workdir / "all")
    _parse(output, result)
    if errors:
        # An error can cascade into neighbouring items; probing the failures on their own rescues those.
        retry = {key: item for key, item in items.items() if key in errors}
        output, confirmed = _probe_once(retry, vendored, toolchain, workdir / "retry")
        _parse(output, result)
        errors = confirmed
    result.errors = errors
    return result
