# Contributing

How to work on YASB itself: run it from the source code, check your change, and send it as a pull request. To make a
widget, theme or layout of your own, you don't need any of this: see [Writing widgets](./Writing-Widgets) and
[Addons](./Addons).

## Set up

You need Windows, [Python 3.15](https://www.python.org/downloads/) or newer, and Git.

```powershell
git clone https://github.com/amnweb/yasb.git
cd yasb
python -m pip install -e ".[dev]"
pre-commit install
```

`.[dev]` installs YASB with its tests, its build tools, Ruff and Pyright. `pre-commit install` makes Git run Ruff on
each commit.

## Run YASB from the source

```powershell
python src/main.py
```

It uses your normal config folder, `%USERPROFILE%\.config\yasb`, and writes `yasb.log` there. Close an installed
YASB first: only one YASB runs at a time. To keep your own config out of it, set `YASB_CONFIG_HOME` to another
folder before starting it:

```powershell
$env:YASB_CONFIG_HOME = "$env:TEMP\yasb-dev"
python src/main.py
```

## Check your change

The pull request runs the same checks, so it's faster to run them first.

Format and lint with Ruff:

```powershell
ruff format .
ruff check --fix .
```

Check types with Pyright:

```powershell
pyright
```

Run the tests:

```powershell
python -m pytest
```

You can run a single folder or file, for example `python -m pytest tests/cloud`. The tests never touch your real YASB
setup, and no windows open. [tests/README.md](https://github.com/amnweb/yasb/blob/main/tests/README.md) explains where a
test goes, how to write one, and the checks of YASB's ctypes code against the Windows SDK, which need Visual Studio's
C++ compiler.

## Build the installer

```powershell
python -m pip install -e ".[packaging]"
cd src
python build.py build
python build.py bdist_msi
```

`build` makes the app in `src\dist`, and `bdist_msi` the MSI installer.

## Pull requests

Each pull request runs Ruff, Pyright and the tests on Windows x64 and Windows ARM64, then builds the installers. When
something fails, a bot comments on the pull request with the failures. When you fix a bug, a test that fails before
your fix and passes after it helps the review.

The code style is in `pyproject.toml`: lines up to 120 characters, double quotes, Windows line endings, and Pyright in
strict mode.

## Report a bug or ask for a feature

[Open an issue](https://github.com/amnweb/yasb/issues/new/choose) and pick the bug report or the feature request.
For a bug, include the lines of `yasb.log` around it, see [Troubleshooting](./Troubleshooting).
