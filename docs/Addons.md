# Addons

An addon is a widget, theme, layout or whole config that someone shared for YASB. You can find and install them in the
YASB Addons window or with `yasbc addons`. Both do the same thing. The same tools also copy the built-in widgets so you
can change their options, and keep those copies up to date.

## Find and install

### In the Addons window

Open **YASB Addons** from YASB's tray menu. **Browse** lists the addons in
[amnweb/yasb-addons](https://github.com/amnweb/yasb-addons), sorted into Widgets, Themes, Layouts and Configs. Open
one to see its pictures and description, then install it. **Installed** lists what you have, with **Update all**,
and **Install from a GitHub link...** for an addon that isn't in yasb-addons.

### With yasbc

Search YASB's widgets and yasb-addons by name, id, description, author or type:

```powershell
yasbc addons search clock
```

Install an addon by its id, the one the search shows:

```powershell
yasbc addons install amnweb.clock
```

`--version 2` installs that version instead of the newest. `--force` replaces an addon you already have.

## Use what you installed

An addon's id is its author's GitHub name and its own name, with a dot, such as `amnweb.clock`. Each type goes into its
own folder in your config folder, and config.yaml refers to it by id:

- A widget goes to `widgets\amnweb.clock`. Add `amnweb.clock` to a bar's widgets.
- A theme goes to `themes\amnweb.nord`. Set a bar's `theme: amnweb.nord`.
- A layout goes to `layouts\amnweb.rounded`. Set a bar's `layout: amnweb.rounded`.

```yaml
bars:
  yasb-bar:
    theme: amnweb.nord
    layout: amnweb.rounded
    widgets:
      right:
        - amnweb.clock
```

See [Configuration](./Configuration) for the rest of config.yaml.

### A config

A config addon replaces your whole config folder. YASB asks first, then saves yours as a ZIP file in
`%USERPROFILE%\.config\yasb-backups`, named after the config it was, such as `backup_mine_2026-11-26_101500.zip`. Your
`.env` file, `.git` folder and YASB's log are left untouched. If YASB is running, it stops while the files are replaced
and restarts afterwards.

## Change one of YASB's own widgets

YASB's own widgets keep their options in their QML file. To change them, install the widget by its name:

```powershell
yasbc addons install Clock
```

This writes `widgets\Clock\Clock.qml` in your config folder, with every option that has a value, and its comments:

```qml
import Yasb.Widgets

// YASB's Clock with its settings; change any value here
Clock {
    settings {
        // ... every option of the Clock
    }
}
```

Change what you like and save. YASB uses your copy from then on. Delete the `widgets\Clock` folder to go back to YASB's
own options. `--full` copies the whole widget instead, so you can change more than its options. A widget without options
can only be copied this way.

### When YASB updates its widget

Your copy records which version of the widget it came from. When a YASB update ships a new version of that widget, YASB
uses the built-in widget instead of your copy and shows an alert that your copy is out of date. Update the copy:

```powershell
yasbc addons update Clock
```

The new copy keeps every value you changed, and lists any option the widget no longer has. A copy made with
`--full` can't be updated this way: install it again with `--full --force`.

## Updates

`yasbc addons update` lists what has a newer version: your addons, and your copies of YASB's widgets.

```powershell
yasbc addons update amnweb.clock
yasbc addons update --all
```

`--all` updates everything except a config, because that replaces your whole config folder. Update a config by its id.
`yasbc addons list` shows everything you have, with its version and where it came from.

## From a GitHub link

An addon that isn't in yasb-addons can be installed from its GitHub repository:

```powershell
yasbc addons install https://github.com/amnweb/clock
```

YASB's developers haven't reviewed it, so YASB shows a warning and asks first. An addon runs with your user rights:
it can read, change and delete your files. Install one only if you trust its author.

## Share your own

Put your widget, theme, layout or config in a public GitHub repository, with a `manifest.json` at its root:

```json
{
  "id": "yourname.clock",
  "type": "widget",
  "title": "Clock",
  "description": "A clock with the date under it",
  "version": 1
}
```

- `id`: your GitHub name and the addon's name, with a dot, in lower case. The name starts with a letter and has only
  letters and digits.
- `type`: `widget`, `theme`, `layout` or `config`.
- `title` and `description`: text on one line each.
- `version`: a whole number. Raise it for each update, so `yasbc addons update` offers it.

The repository holds the addon's QML file, named after the part of the id after the dot, such as `clock.qml`, or
`config.yaml` for a config. Files and folders whose names start with a dot are left out, and an addon can't hold
`.exe` or `.dll` files. Others then install it with your repository's link.

To list it in the Addons window's Browse page, it has to be in [amnweb/yasb-addons](https://github.com/amnweb/yasb-addons).
