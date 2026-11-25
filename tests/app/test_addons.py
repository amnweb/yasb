# pyright: reportPrivateUsage=false

import pytest
from PyQt6.QtGui import QGuiApplication

from core.addons.window import Addons, _readme

# As yasb-addons' process-addon.py writes it
TEMPLATE = """# Weather

The weather for your city

```
yasbc addons install john.weather
```

Shows the weather. Set your city in **config.yaml**.

<!-- changes -->
## Changes

### Version 2 (2026-11-25)

Fixed rain

### Version 1 (2026-11-23)

Initial release
"""


def test_the_readme_leaves_out_only_what_the_page_shows():
    about, changes = _readme(TEMPLATE, "The weather for your city")
    assert about == "Shows the weather. Set your city in **config.yaml**."
    assert changes.startswith("### Version 2 (2026-11-25)") and changes.endswith("Initial release")


def test_a_readme_in_another_shape_loses_nothing():
    text = "Intro first\n\n# Weather\n\n```\npip install x\n```\n\nMore text"
    assert _readme(text, "The weather for your city") == (text, "")
    # A different description stays, and so does what follows it
    about, _ = _readme(TEMPLATE.replace("The weather for your city", "Other words"), "The weather for your city")
    assert about.startswith("Other words") and "yasbc addons install" in about


def test_a_config_installs_alone(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch):
    addons = Addons()

    def never_run(_work: object, _failed: object, writes: bool = False) -> None:
        """The jobs stay busy."""

    monkeypatch.setattr(addons, "_run", never_run)
    refused: list[str] = []

    def refuse(title: str, _message: str) -> None:
        refused.append(title)

    addons.messageRequested.connect(refuse)
    addons._work_on("john.weather", "widget", "", lambda: "")
    addons._work_on("john.frame", "config", "", lambda: "")
    assert addons.property("busy") == ["john.weather"] and len(refused) == 1
    addons._worked("john.weather", "", "", [])
    addons._work_on("john.frame", "config", "", lambda: "")
    addons._work_on("john.clock", "widget", "", lambda: "")
    assert addons.property("busy") == ["john.frame"] and addons.property("configBusy") and len(refused) == 2
