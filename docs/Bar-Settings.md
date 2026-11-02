# Bar settings

Open **Bar settings** from the YASB tray menu. The dialog uses YASB's existing Qt
runtime and runs only while open. Save and apply reloads YASB.
You can also right-click empty space on a bar and choose **Bar Settings**.

- Enable, disable, position and reorder widgets already defined in your configuration.
- Change text size, horizontal widget spacing, background opacity and tray icon size.
- Set each bar's height.
- Choose a 12-hour or 24-hour clock, seconds and a date format.

In **Widgets**, each widget has its own **Position** (left, center or right).
Select its row and use **Move up/down** to change its order within that position.
You can also drag any widget directly on the bar, including the clock, Ceiling,
sound and network. Hold the left mouse button and move to an insertion marker
between widgets or tray icons. Release to snap there. Layouts restore after
restart separately for each monitor; clicking without dragging keeps the
widget's normal action. Ceiling moves as one widget containing its providers.

Sound (`volume`) and network (`network`) are independent widgets, so they can
sit in different positions. Drag an individual application tray icon from the
tray or its overflow onto the bar. An insertion marker shows where it will snap
between widgets or other icons. Placed icons stay visible, and their positions
are remembered separately for each monitor. Alt-click an icon or drag it back
into the tray overflow to return it to the tray.

Any registered application tray icon can be placed this way. Applications that
do not provide a stable icon GUID must reuse their executable path and icon ID
for their placement to survive an application restart.

Existing sound and network widget callbacks are preserved on save. You can use
the existing native Quick Settings callbacks in your configuration. Moving a
widget does not change the anchor of Windows' own panels. The Windows tray
speaker icon opens native Quick Settings on left-click.

Text size, spacing, opacity and tray icon size apply across bars. Widget positions
and height belong to the selected bar. Clock changes belong to the selected clock
widget. Custom clock formats remain intact until you choose to replace them;
replacement uses the chosen format for both normal and alternate labels.

Changes take effect only after saving. Existing custom widget options and other
configuration values are preserved. YAML comments and formatting are normalized
on save. The previous files are kept as `config.settings-backup.yaml` and
`styles.settings-backup.css` in the configuration folder. These backups are replaced
on each save. If another application edits either file, reopen settings before saving.

Appearance overrides are appended to a marked block in `styles.css`. Existing theme
rules remain intact; more specific theme selectors may still override these controls.
Opacity controls the bar background, not the opacity of text or icons.

This first version edits configured widgets. Adding new widget definitions and
advanced widget-specific options still uses the existing configuration workflow.

For a standalone launcher, run `settings_launcher.py` with `src` on `PYTHONPATH`:

```
python settings_launcher.py --config PATH --yasbc PATH_TO_YASBC
```
