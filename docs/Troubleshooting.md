# Troubleshooting

When something looks wrong, start with the log. When YASB can't use a file, it shows an alert saying which file and why.
This page explains each alert.

## The log

YASB writes what it does to `yasb.log` in your config folder, `%USERPROFILE%\.config\yasb`. Follow it as it's
written:

```powershell
yasbc log
```

The log keeps errors and warnings from YASB and from your QML files, such as a typo in a widget. For more detail,
set `debug: true` in `config.yaml`:

```yaml
debug: true
```

When `yasb.log` reaches 1 MB, YASB starts a new one and keeps the last five as `yasb.log.1` to `yasb.log.5`.

When you ask for help, in [Discussions](https://github.com/amnweb/yasb/discussions) or on
[Discord](https://discord.gg/qkeunvBFgX), include the lines from the log around the problem.

## YASB doesn't start

### YASB could not start

config.yaml can't be used, and the alert says why:

- It can't be found, or can't be read.
- It isn't valid YAML, such as a wrong indent. The details show the line.
- A setting has a wrong name or value. The details list each one.
- It has no bars. Add a bar to `bars`.

Fix config.yaml and start YASB again. See [Configuration](./Configuration).

### YASB stopped while starting

YASB hit an unexpected error. The details show it. Include them when you ask for help.

### Your config.yaml is from YASB 2

The setup opens with this message when config.yaml is from YASB 2, which YASB 3 can't read. Close YASB, move config.yaml
out of your config folder (or back it up and delete it), then start YASB again. The setup then makes a new one.

### Nothing happens

Only one instance of YASB can run at a time. Starting it again while it's running does nothing, and the log says
"Another instance of the YASB is already running."

## Alerts while YASB runs

With `watch` on, YASB loads each file again when you save it. A file with an error isn't used, and an alert says
so:

| Alert | What happened | What YASB does |
| --- | --- | --- |
| Failed to load recently updated config file. | The saved config.yaml has an error. | Keeps the bars it shows. |
| A QML file has errors | A saved widget, layout or theme file has an error. | Keeps the version it shows. |
| Failed to reload the layout of bar '...' | The saved layout has an error. | Keeps the layout it shows. |

Fix the file and save it again. The details say which file and which line.

## Alerts when the bars load

| Alert | What happened | What YASB does |
| --- | --- | --- |
| Some widgets could not load | A widget's QML file has an error. | Shows the bar without that widget. |
| Undefined widget(s) in config.yaml | A bar lists a widget that is neither in your `widgets` folder nor one of YASB's own. | Leaves it out. Check its name, or [install it](./Addons). |
| Some of your widgets no longer fit this YASB | Your copy of one of YASB's widgets is from an older YASB. | Uses YASB's own widget. Run `yasbc addons update`, see [Addons](./Addons#when-yasb-updates-its-widget). |
| Failed to load the theme of bar '...' | The bar's theme file has an error. | Uses the default theme. |
| Failed to load the layout of bar '...' | The bar's layout file has an error. | Shows its built-in bar. |

## Warnings in the log

Some problems don't show an alert, only a warning in the log:

- A bar lists widgets under a slot its layout doesn't have. Those widgets aren't shown. See
  [Layouts](./Layouts#custom-slots).
- A widget's shortcut isn't valid, or another app already uses it. See [Hotkey](./(Type)-Hotkey).
- A layout's `backdropShapes` isn't valid, so the bar has no blur. See [BarBase](./(Type)-BarBase).

## Icons are missing

YASB draws its icons with the Segoe Fluent Icons font, which Windows 10 doesn't include. The setup warns with
"Segoe Fluent Icons is missing" when it isn't installed. [Download it](https://aka.ms/SegoeFluentIcons), open the font file, click **Install**, then restart YASB.
