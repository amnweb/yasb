# Updates

`import Yasb`

Updates waiting from Windows Update, winget and Scoop, with functions to install and skip them. Each source is
checked on its own interval, nothing shows before its first check, 10 to 20 seconds after it starts. All
AvailableUpdates objects with the same source and interval share one check.

## AvailableUpdates

### Properties

#### windowsUpdate : bool

When `true`, Windows Update is checked.

Default: `true`

#### winget : bool

When `true`, winget is checked, if it is installed.

Default: `true`

#### scoop : bool

When `true`, Scoop is checked, if it is installed.

Default: `true`

#### windowsInterval : int

Milliseconds between two checks of Windows Update, from 1800000 (30 minutes) to 604800000 (7 days).

Default: `86400000`

#### packageInterval : int

Milliseconds between two checks of winget and of Scoop, from 600000 (10 minutes) to 604800000 (7 days).

Default: `14400000`

#### exclude : list&lt;string&gt;

Updates to leave out: those whose name or id contains one of these, in any case, such as `Microsoft.Edge` or
`Defender`.

Default: `[]`

#### updates : list `read-only`

Every update shown, source by source, without the excluded ones and the versions skipped. Each is an object:

- `source` : string, `windows`, `winget` or `scoop`.
- `id` : string, the update's id. Used by `install()` and `skip()`.
- `name` : string, the update's name.
- `installedVersion` : string, the version installed, as the tool prints it. `""` for Windows updates.
- `availableVersion` : string, the new version. `""` for Windows updates.

Windows updates also have:

- `category` : string, its classification, such as `Security Updates` or `Drivers`.
- `kb` : string, its KB articles, each `KB` and its number, separated by commas.
- `severity` : string, its security severity. `""` when it has none.
- `downloaded` : bool, `true` when Windows has downloaded it.

winget updates also have `origin`, the source it comes from, and Scoop updates `info`, Scoop's note on it.

Windows updates hidden in Settings, and Scoop apps on hold, are left out.

#### count : int `read-only`

How many updates `updates` has.

#### sources : list `read-only`

Each source that is checked, as an object:

- `id` : string, `windows`, `winget` or `scoop`.
- `name` : string, `Windows Update`, `Winget` or `Scoop`.
- `installed` : bool, `false` when the tool is missing, so it is never checked.
- `checking` : bool, `true` while it is checked.
- `installing` : bool, `true` while its update terminal is open.
- `error` : string, what went wrong in its last check or install, `""` when nothing. A failed check keeps the
  updates found before.
- `checked` : date, when it was last checked. Invalid before its first check.
- `count` : int, how many of `updates` are its.

#### checking : bool `read-only`

`true` while any source is checked.

#### checked : date `read-only`

When a source was last checked. Invalid before the first check.

#### restartRequired : bool `read-only`

`true` when Windows waits for a restart to finish installing updates.

#### skipped : list `read-only`

The versions skipped, each an object:

- `source` : string, the update's source.
- `id` : string, the update's id.
- `name` : string, the update's name.
- `version` : string, the version skipped.

Skipped versions are shared by all AvailableUpdates objects, and saved in
`%LOCALAPPDATA%\YASB\updates_skipped.json`.

### Functions

#### check(source: string)

Checks this source again now, or every source for `""`. Ignored for a source that is checked or installing.

#### install(source: string, ids: list&lt;string&gt;)

For `winget` and `scoop`, opens a terminal that updates these packages by `id` and waits for Enter before it
closes, the source is checked again once it closes. Ignored while its terminal is open. For `windows`, opens
Windows Update in Settings, as Windows installs its own updates.

#### skip(source: string, id: string)

Hides this version of the update until a newer one comes.

#### restore(source: string, id: string)

Shows a skipped update again.

AvailableUpdates has no signals.

## Used by

YASB's own Updates widget, listed in [Widgets](./Widgets).
