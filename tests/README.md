# Tests

## Running them

```bash
pip install -e .[test]
python -m pytest
```

You can also run one folder or one file:

```bash
python -m pytest tests/cloud
python -m pytest tests/win32/test_structs.py
```

The tests never touch your real YASB setup. `tests/conftest.py` points `YASB_CONFIG_HOME` and
`LOCALAPPDATA` at a temporary folder, and Qt runs offscreen, so no windows pop up.

## What's in here

| Folder | What it checks |
|---|---|
| `smoke/` | Every module imports, and every widget's config schema builds. |
| `widgets/` | Rules for bar widgets, for example that a widget never calls `winId()` on itself. |
| `win32/` | Our ctypes code against the real Windows SDK, plus window helpers tested on real windows. |
| `cloud/` | YASB Cloud: API errors, encryption, backups, restores, settings. None of them contact the real server. |
| `support/` | Helpers the tests share. |

## Writing a test

Add a file named `test_<something>.py` to the folder that fits. Each test is a function whose name
starts with `test_` and checks things with `assert`. This one is from `cloud/test_footer_reason.py`:

```python
from core.cloud.models import Access
from core.cloud.ui.window import _reason


def test_never_having_subscribed_is_not_an_expiry():
    assert _reason(Access(reason="no_subscription")) == "No active subscription"
```

A few things that help:

- `src` is on the import path, so import YASB code as `core.something`.
- Ask for the `qapp` fixture if your test creates Qt widgets.
- Use pytest's `tmp_path` for files and `monkeypatch` to swap a function or an environment variable
  for one test.
- Don't call real servers or depend on hardware. CI runs on GitHub's Windows machines (x64 and ARM64),
  which have no GPU, Bluetooth or Wi-Fi.
- When you fix a bug, the best test is one that fails before your fix and passes after it.

## The Windows checks

A mistake in ctypes code doesn't raise a Python error. If a struct is missing a field, or a function
is declared to return 4 bytes when Windows returns 8, YASB reads garbage or crashes without a
traceback. The tests in `win32/` catch that before it ships.

They collect every ctypes struct, function declaration and constant in `src/core`, then ask the
Windows SDK about each one: its size, its field offsets, its return and argument types, its value.
To get those answers they write a small C++ program, compile it with Visual Studio's compiler and run
it. Then they compare the answers with our Python code. If `MIB_IF_ROW2` were missing its last field,
you'd see:

```text
sizeof is 1344, the SDK's MIB_IF_ROW2 is 1352
```

For this you need Visual Studio or the Build Tools with the "Desktop development with C++" workload.
Without it these checks are skipped on your PC; set `YASB_REQUIRE_SDK=1` to make them fail instead,
which is what CI does. The answers are cached in `.pytest_cache`, and the last lines of the output say
which compiler and SDK were used.

Two checks in `win32/` don't need the compiler. Every function we use must exist in its DLL
(`user32.dll` has `GetWindowLongW` but no `GetWindowLong`), and `test_window_actions.py` tries the
window helpers on real windows.

### The files

| File | What it does | Do you edit it? |
|---|---|---|
| `test_*.py` | The checks themselves | Only to add a new kind of check |
| `specs.py` | Python names that differ from the SDK (`WNDCLASS` for `WNDCLASSW`), and things that aren't in the SDK at all (undocumented functions, AMD, NVIDIA) | Yes, when a check asks for it |
| `known_issues.py` | Problems we know about but haven't fixed yet | Only to delete entries |
| `probe.py` | Writes, compiles and runs the C++ program | Only its `HEADERS` list, when a check asks for it |
| `msvc.py` | Finds Visual Studio's compiler | No |
| `foreign.py`, `discovery.py` | Find the ctypes code in `src/core` | No |
| `abi.py` | Compares Python types with C types | No |
| `conftest.py` | Runs the C++ program once and caches its answers | No |

### When a check fails

| Message | What to do |
|---|---|
| `sizeof is 1344, the SDK's MIB_IF_ROW2 is 1352` | The struct doesn't match Windows. Fix its fields. |
| `argtypes has 4 entries, the SDK takes 5 parameters` | Fix the function's `argtypes`. |
| `restype c_int is signed int(4), the SDK returns signed int(8)` | Fix the function's `restype`. |
| `X returns pointer(8) but has no restype` | Declare `restype` and `argtypes`, like the files in `src/core/utils/win32/bindings` do. |
| `user32.dll does not export GetWindowLong` | Call the name the DLL really has, here `GetWindowLongW`. |
| `X is not declared by the SDK headers` | Check the spelling. If it's right, add its header to `HEADERS` in `win32/probe.py` (Microsoft Learn lists the header under Requirements). Only undocumented names belong in `NOT_IN_SDK` in `specs.py`. |

### Known issues

`win32/known_issues.py` lists problems we know about but haven't fixed yet, so CI can stay green
in the meantime. Don't add to it to get rid of a new failure; fix the code instead. When you fix a
listed problem, its test tells you to delete the entry.

## CI

Every pull request and every push to `main` runs the tests on Windows x64 and Windows ARM64. When
something fails on a pull request, the bot comments with the failures, and the installers aren't
built until the tests pass. If pytest crashes outright, which is what a bad ctypes call usually
looks like, the comment says so and shows the end of the log.

The workflows are `.github/workflows/tests.yaml` (runs the tests), `pr-check.yaml` (Ruff, tests and
builds) and `pr-comment.yaml` (the bot's comment). GitHub always runs `pr-comment.yaml` from `main`,
so a change to it only takes effect after it's merged.
