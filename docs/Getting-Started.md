# Getting started

After the [setup](./Installation#first-run-the-setup), YASB runs from a few files in your config folder. This page
shows what they are, how YASB picks up your changes, and where to look when something goes wrong.

## Your config folder

Your config folder is `%USERPROFILE%\.config\yasb`. To keep it somewhere else, set the `YASB_CONFIG_HOME`
environment variable to that folder. Right-click YASB's tray icon and click **Open Config** to open it, or run
`yasbc config-dir`. `yasbc --config` prints its path.

```text
%USERPROFILE%\.config\yasb
├── config.yaml       YASB's settings and your bars
├── .env              variables for config.yaml and widgets, if you add one
├── layouts
│   └── floating.qml  the bar's look, for the style you picked in the setup
├── themes
│   └── yasb.qml      the colors and fonts of the bar, its widgets, popups and menus
├── widgets           your copies of YASB's widgets, and widgets of your own
└── yasb.log          what YASB did, and what went wrong
```

- [`config.yaml`](./Configuration) names your bars, the screens they're on, their size and place, the layout and
  theme each one uses, and the widgets in it.
- A [layout](./Layouts) is a QML file with the bar's own look: its color, corners, border, padding and spacing.
- A [theme](./Themes) is a QML file with the colors and fonts that the bar and every widget take.
- The `widgets` folder appears once you [change a widget's options](./Widgets) or install a widget
  [addon](./Addons). Each widget there has its own folder.
- `.env` holds variables such as API tokens, one `NAME=value` per line, so they stay out of your other files.
  `config.yaml` reads one as `$env:NAME`, and a widget as `Environment.value("NAME")`.

## How YASB picks up your changes

While `watch` is `true` in `config.yaml` (the default), YASB watches your config folder:

- When you save `config.yaml`, YASB restarts with it. If the file has an error, YASB shows the error and keeps running
  with the config it had.
- When you save a QML file in the `widgets` folder, or the layout or theme that `config.yaml` names, the bars that use
  it load it again, without a restart. If the file has an error, YASB lists the errors and the bars keep the version
  they're showing.
- Other QML files in your config folder are left alone, so you can keep drafts there.
- YASB reads `.env` when it starts. After you change it, right-click the tray icon and click **Reload YASB**, or run
  `yasbc reload`.

With `watch: false`, changes only apply when you reload YASB.

## When something goes wrong

YASB writes what it does to `yasb.log` in your config folder. Run `yasbc log` to follow it as it's written, and set
`debug: true` in `config.yaml` for more detail. [Troubleshooting](./Troubleshooting) explains the alerts YASB shows.

## Next steps

- [Configuration](./Configuration): add a bar, move it to another screen or edge, and pick its widgets.
- [Widgets](./Widgets): change what a widget shows and how it looks.
- [Themes](./Themes) and [Layouts](./Layouts): change how everything looks.
