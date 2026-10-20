# Plugins

Plugins are widgets that aren't built into YASB. The official ones live in [amnweb/yasb-plugins](https://github.com/amnweb/yasb-plugins), where every plugin is reviewed before it's published. You install them with `yasbc plugin`. YASB keeps them in the `plugins` folder of your config folder: `%USERPROFILE%\.config\yasb\plugins`, or `plugins` inside `YASB_CONFIG_HOME` if you set it. YASB Cloud backups include that folder, so restoring a backup brings your plugins back too.

> **Warning:**
> A plugin is Python code that runs inside YASB with the same access to your PC as YASB itself. Plugins from the official repository were reviewed; plugins you install from a folder or a `.zip` weren't.

## Installing a plugin

```bash
yasbc plugin install lyrics
```

This downloads the plugin from the official repository, checks that the download matches what was published, and checks that it works with your version of YASB. `yasbc` never changes `config.yaml`: add the widget yourself, as the plugin's README shows. YASB reloads by itself when `watch_config` is on. Otherwise, run:

```bash
yasbc reload
```

To install a plugin that isn't in the official repository, give the path to its folder or `.zip` file. `yasbc` warns you that its code wasn't reviewed:

```bash
yasbc plugin install C:\path\to\my-plugin
yasbc plugin install C:\Downloads\my-plugin.zip
```

You can also install a plugin straight from its GitHub repository, optionally at a tag or branch:

```bash
yasbc plugin install github.com/owner/repo
yasbc plugin install github.com/owner/repo@v1.2.0
```

`yasbc` downloads the repository, shows the plugin's name, version and author, warns that nobody reviewed it, and asks before installing. The answer defaults to no; `-y` skips the question. `manifest.json` must be at the top of the repository. `yasbc plugin update` gets newer versions from the same repository.

`--force` reinstalls a plugin that is already installed. If the plugin you're installing is a different one with the same ID, for example a GitHub plugin with the same ID as an official one, `yasbc` says so and asks before replacing it. `-y` answers yes to every question.

## Using a plugin widget

A plugin widget's `type` is `plugins.`, the plugin's name, a dot, and the widget's class name, the same pattern as built-in types like `yasb.clock.ClockWidget`:

```yaml
widgets:
  lyrics:
    type: "plugins.lyrics.LyricsWidget"
```

You can add more, with other names and options, and put them on any bar like any other widget. YASB only loads the plugins your config uses.

## Managing plugins

| Command | What it does |
|---|---|
| `yasbc plugin search [words]` | Searches the official repository by ID, name, author and description, and shows one plugin per row. |
| `yasbc plugin list` | Lists installed plugins with their ID, name, version and where they came from. A plugin YASB can't use says why, for example that it was made for a different plugin API. |
| `yasbc plugin update [name]` | Updates plugins from the official repository, and plugins installed from GitHub from their repository. Without a name it updates all of them. If a plugin is temporarily disabled in the repository, it says so and leaves your copy alone. |
| `yasbc plugin remove name` | Uninstalls a plugin and lists the widgets in `config.yaml` that still use it, for you to remove. Until you do, YASB shows a **Failed to load plugin widget(s)** message. `--purge` also deletes the data the plugin saved, `-y` skips the question. |
| `yasbc plugin create` | Asks a few questions and creates a new plugin in the plugins folder. See [Writing a plugin](#writing-a-plugin). |
| `yasbc plugin path` | Prints the plugins folder. |

## When a plugin fails

- If a plugin can't load (it isn't installed, it was made for another version of YASB, or its code fails to import), YASB shows a **Failed to load plugin widget(s)** message with the reason and starts without that widget.
- If a plugin raises an error while YASB is running, the error is written to `yasb.log` with the plugin's name, and YASB keeps running. Run `yasbc log` to watch for it.

## Writing a plugin

The quickest start is:

```bash
yasbc plugin create
```

It asks for the plugin ID, name, author and description, then creates a working plugin in the plugins folder: a `manifest.json` filled in for your version of YASB, a `widget.py` with a small widget that shows a label, and a `README.md` with the `config.yaml` entry and the CSS. Change them from there.

A plugin is a folder with a `manifest.json` and Python files. The example below is the plugin YASB's tests use, in `tests/plugins/fixtures/hello`. It's also in the official repository as `plugins/hello`.

```
hello/
├── manifest.json
├── __init__.py        (optional)
├── widget.py
└── text.py
```

### manifest.json

```json
{
  "id": "hello",
  "name": "Hello",
  "version": "1.0.0",
  "author": "YASB",
  "description": "Says hello.",
  "api": "1",
  "min_yasb": "2.0.0",
  "widgets": {
    "HelloWidget": "widget:HelloWidget"
  }
}
```

| Field | Required | Meaning |
|---|---|---|
| `id` | Yes | The plugin's name: lowercase letters, digits and `-`, like `spotify-controls`. It's what people type in `yasbc plugin install`, and the folder name in the official repository. Names there are first come, first served. |
| `name` | Yes | The name people see. |
| `version` | Yes | Your plugin's version, like `1.0.0`. Raise it with every update. |
| `author` | Yes | You. |
| `description` | Yes | One sentence for `yasbc plugin search`, up to 70 characters. |
| `api` | Yes | The plugin API version you wrote it for, as a string. It is `"1"` today. YASB skips a plugin made for a different API. |
| `min_yasb` | Yes | The oldest YASB version your plugin works with, like `2.0.0`. |
| `widgets` | Yes | The widgets your plugin provides. The key is the class name people write in `type`, the value is `module:ClassName` inside your folder. |

### The widget

Import everything from `yasb_api`, not from YASB's internal `core` modules. `yasb_api` stays the same within a plugin API version, while `core` can change in any release.

```python
from PyQt6.QtWidgets import QLabel

from yasb_api import BaseWidget, WidgetConfig, set_tooltip

from .text import greeting


class HelloConfig(WidgetConfig):
    name: str = "world"
    tooltip: bool = True


class HelloWidget(BaseWidget):
    validation_schema = HelloConfig

    def __init__(self, config: HelloConfig):
        super().__init__(class_name="plugin-hello")
        self.label = QLabel(greeting(config.name))
        self.label.setProperty("class", "label")
        self.widget_layout.addWidget(self.label)
        if config.tooltip:
            set_tooltip(self.label, "Loaded from a YASB plugin")
```

Everything in [Writing Widget](./Writing-Widget) applies to plugin widgets too.

### What `yasb_api` provides (API 1)

| Name | What it is |
|---|---|
| `BaseWidget` | The class every widget inherits from. |
| `WidgetConfig` | The base class for your config model. Unknown options are rejected. |
| `CallbacksConfig`, `KeybindingConfig` | Shared config models for mouse callbacks and keybindings. |
| `PopupWidget` | A popup window attached to the bar. See [Writing Widget](./Writing-Widget). |
| `ElidedLabel` | A `QLabel` that shortens its text with `...` to fit. |
| `refresh_widget_style(*widgets)` | Re-applies CSS after you change a widget's `class` property. |
| `set_tooltip(widget, text)` | Shows a YASB-styled tooltip. |
| `is_valid_qobject(obj)` | Whether a Qt object still exists and hasn't been deleted. |
| `shell_open(path_or_url)` | Opens a file, folder or link the way Explorer would. |
| `data_dir(__name__)` | A folder where your plugin can save data while it runs, like a cache or settings. It's kept separate from the plugin's code and survives updates; `yasbc plugin remove --purge` deletes it. |
| `config_dir()` | The user's YASB config folder. |
| `API_VERSION`, `YASB_VERSION` | The plugin API version and the running YASB version. |

### Rules

- **Import your own files with relative imports**, like `from .text import greeting`. Your folder is loaded as its own package and is not on Python's import path, so `import text` doesn't work.
- **You can use** the Python standard library, PyQt6, and the packages YASB itself ships, such as `pydantic`, `PIL` and `humanize`. Plugins can't install packages from PyPI.
- **Write a README** that shows the `config.yaml` entry for your widget, its options, and the CSS to add to `styles.css`. YASB doesn't add any of it for the user, so the README is how people learn to set your widget up.
- **Leave styling to the user's `styles.css`.** Don't call `setStyleSheet()` in your widget: a stylesheet set on a widget beats `styles.css`, so users couldn't change it. Give your widget the class `plugin-` plus your plugin id, like `plugin-hello`, so it never shares a class with a built-in widget, and use YASB's usual classes such as `label` inside it, so the user's theme applies.
- **Save data in `data_dir(__name__)`**, like caches or tokens, not in your plugin folder. Updating a plugin replaces its folder.
- **Don't block the bar.** Do slow work, like network requests, in a `QThread` or with `asyncio`, as the built-in widgets do.

### Trying it locally

Work on your plugin right inside the plugins folder, where `yasbc plugin create` puts it. YASB loads every folder there that has a `manifest.json`, so there's nothing to install while you develop. `yasbc plugin path` prints where the folder is:

```
%USERPROFILE%\.config\yasb\plugins\hello\
```

Add your widget to `config.yaml`, then after each change run:

```bash
yasbc reload
yasbc log
```

`yasbc log` shows `Loaded plugin "hello"` when it works, or the error when it doesn't.

### Publishing

Open a pull request that adds your plugin folder to `plugins/` in [amnweb/yasb-plugins](https://github.com/amnweb/yasb-plugins). A check runs on it, a maintainer reviews the code, and once it's merged anyone can install it by its name. To update it, change the files, raise `"version"`, and open another pull request.

## Plugin API versions

The plugin API version only changes when something in `yasb_api` is removed or changes in a way that breaks plugins. Adding new names doesn't change it. When it changes, plugins made for the old version are skipped with a message that names the plugin, until their authors publish an update.
