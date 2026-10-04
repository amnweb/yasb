# YASB tests

```bash
pip install -e .[test]       # or .[dev], which includes it
python -m pytest             # everything, about 10 seconds
python -m pytest tests/win32 # one area
python -m pytest "tests/win32/test_structs.py::test_layout_matches_sdk[core.utils.win32.structs.MIB_IF_ROW2]"
```

The same suite runs in CI on every push to `main` and on every pull request, for x64 and arm64. On a
pull request the bot posts the failures as a comment, and the installers are not built until the
tests pass.

## Layout

| Folder | What it guards against |
|---|---|
| `tests/win32/` | ctypes code that disagrees with Windows: wrong struct layouts, `argtypes`/`restype`, COM vtables and constants, checked against the real Windows SDK headers. Also results ctypes would read with the wrong size, names a DLL does not export, and window helpers run against real windows (`test_window_actions.py`). |
| `tests/widgets/` | Qt rules for bar widgets, such as never calling `winId()` on a widget inside the bar. |
| `tests/smoke/` | Every module in `src/core` imports, and every widget's config schema builds. |
| `tests/cloud/` | YASB Cloud: API errors, encryption, snapshots, restore, settings. `tests/cloud/conftest.py` points the client at a closed local port, so no test reaches the live server. |
| `tests/support/` | Helpers shared by the tests, not tests themselves. |

`tests/conftest.py` points `YASB_CONFIG_HOME` and `LOCALAPPDATA` at a temporary folder for the whole
run, so no test reads or writes your real configuration, and runs Qt with the offscreen platform.

## The Windows SDK checks

A ctypes mistake does not raise an exception. A struct that is 8 bytes too short (`MIB_IF_ROW2`
without `OutQLen`), a `restype` that is a string pointer instead of a `DWORD`
(`WlanReasonCodeToString`), or a `c_int` where Windows returns a 64-bit `LRESULT` corrupts memory or
crashes the process with no Python traceback.

`tests/win32` finds every ctypes `Structure`/`Union`, every `argtypes`/`restype` declaration, every
comtypes interface and every constant in `core.utils.win32`. It writes one C++ file that includes
the Windows SDK headers, compiles it with MSVC, and compares:

- `sizeof` and `offsetof` of every field with the ctypes layout
- each function's return and parameter types (size, signedness, pointer or integer) with `argtypes`/`restype`
- the result of every call made without `restype`, which ctypes reads as a 4-byte C `int`. That is only
  right when the function returns a 4-byte integer or nothing, or when the code ignores the result, so
  `user32.MessageBeep(0)` needs no declaration but `hwnd = user32.GetForegroundWindow()` does: an `HWND`
  is 8 bytes.
- each COM method's vtable slot and parameters with the comtypes `_methods_`
- each constant's value

This needs Visual Studio or the Build Tools with the **Desktop development with C++** workload (which
installs the Windows SDK). Without it, those tests are skipped locally. CI sets `YASB_REQUIRE_SDK=1`,
which turns a missing compiler into an error. The compiled results are cached in `.pytest_cache`
until the code or the SDK changes.

Two checks in `tests/win32` need no compiler and always run:

- `test_referenced_functions_are_exported`: a name the DLL does not export, like `user32.GetWindowLong`
  (only `GetWindowLongW` exists; `GetWindowLong` is a macro in the headers).
- `test_window_actions.py`: window helpers such as `can_minimize`, run against real windows with and
  without a minimize box.

### When a check fails

| Message | What to do |
|---|---|
| `sizeof is 1344, the SDK's MIB_IF_ROW2 is 1352` | The ctypes struct is wrong. Fix its fields. |
| `X is not declared by the SDK headers` | Name the class or function after its SDK name. If it really is not in the SDK, see `specs.py` below. |
| `restype c_int is signed int(4), the SDK returns signed int(8)` | Fix the declaration in `src`. |
| `X returns pointer(8) but has no restype` | Declare `restype` and `argtypes`, like the modules in `src/core/utils/win32/bindings` do. |
| `user32.dll does not export GetWindowLong` | Call the exported name (`GetWindowLongW`). |

[`win32/specs.py`](win32/specs.py) is the only place to describe how Python names map onto the SDK.
A struct, function or interface named exactly like its SDK counterpart needs no entry. Otherwise:

- `STRUCTS`: a different C name (`WNDCLASS` is `WNDCLASSW`), renamed fields, padding fields, or a
  struct that only declares the first members (`prefix=True`).
- `VENDORED_DECLARATIONS`: the C declaration of a type no SDK header has (undocumented or third party,
  such as AMD ADL or NVML), copied from the header that defines it.
- `NOT_IN_SDK`, `UNDOCUMENTED_INTERFACES`: undocumented exports and interfaces, with a reason.
- `CONSTANT_ALIASES`: a constant the code names differently from the headers.

## Known issues

[`win32/known_issues.py`](win32/known_issues.py) lists problems the tests found in the existing code
that are not fixed yet, so CI can be green while they stay on record. Do not add to it to make a new
failure go away: fix the code. When you fix one of the listed problems its test starts failing with
"fixed now, delete ..." or `XPASS(strict)`. Delete the entry and the run is green again.

## CI

- [`.github/workflows/tests.yaml`](../.github/workflows/tests.yaml) runs pytest on `windows-latest` and
  `windows-11-arm`. It is triggered on pushes to `main`, by hand, and from PR Check.
- [`.github/workflows/pr-check.yaml`](../.github/workflows/pr-check.yaml) runs it next to Ruff; the
  builds wait for both.
- [`.github/workflows/pr-comment.yaml`](../.github/workflows/pr-comment.yaml) posts, updates or deletes
  the bot's test comment, using [`.github/scripts/test_report.py`](../.github/scripts/test_report.py).
  If pytest dies without a report, which is what an access violation in native code looks like, the
  comment says so and shows the end of the log. GitHub runs this workflow from the copy on `main`, so
  a change to it only takes effect once it is merged.
