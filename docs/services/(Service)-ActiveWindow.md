# Active window

`import Yasb`

The foreground window: its title, app, icon and details, and a text built from your `label`. Updates when the foreground
window changes, and when its title changes or it closes or is minimized.

Some windows are ignored:

- Desktop, Start and Search: when one of them becomes the foreground window, there is no window.
- Taskbar, YASB, komorebi and Flow Launcher, and windows in your ignore lists: the previous window stays.

## ActiveWindowTracker

### Properties

#### screenName : string

Name of the screen the widget is on. Set it to `bar.screenName`.

Default: `""`

#### monitorExclusive : bool

When `true`, only windows on `screenName` count. A foreground window on another screen shows as no window. Needs
`screenName`. Without it, all screens count.

Default: `true`

#### label : string

The text. Placeholders in braces are filled in from the window:

- `{win[title]}`: title, after `rewrite` and `maxLength`.
- `{win[app_name]}`: app name, after `rewrite`.
- `{win[class_name]}`: window class.
- `{win[hwnd]}`: window handle.
- `{win[process][name]}`: program, such as `notepad.exe`, after `rewrite`.
- `{win[process][pid]}`: process id.
- `{win[process][path]}`: full path of the program.
- `{win[monitor_info][device]}`: name of the screen the window is on.

Default: `"{win[title]}"`

#### alternateLabel : string

The text while `showAlternate` is `true`. Same placeholders as `label`.

Default: `"[class_name='{win[class_name]}' exe='{win[process][name]}' hwnd={win[hwnd]}]"`

#### noWindowLabel : string

The text when there is no window.

Default: `""`

#### showAlternate : bool

When `true`, the text uses `alternateLabel`. `toggleLabel()` switches it.

Default: `false`

#### maxLength : int

Maximum length of the title. Longer titles are cut and end with `ellipsis`. `0` means no limit.

Default: `0`

#### ellipsis : string

Added to the end of a cut title.

Default: `"..."`

#### rewrite : list

Rules that change the title, program name and app name. They run in order on each of the three. Each rule is
`{pattern, replacement, case}`:

- `pattern`: regular expression (Python syntax).
- `replacement`: what each match becomes. `\1`, `\2` and so on insert the match's groups.
- `case` (optional): `lower`, `upper`, `title` or `capitalize`, applied to the whole text if the rule matched.

Rules without `pattern` or `replacement` are skipped. For example, this keeps only the part of a browser title before "
- ": `[{ pattern: "^(.*) - (Google Chrome|Mozilla Firefox)$", replacement: "\\1" }]`.

Default: `[]`

#### ignoreTitles : list&lt;string&gt;

Window titles to ignore, matched exactly.

Default: `[]`

#### ignoreClasses : list&lt;string&gt;

Window classes to ignore, such as `"CabinetWClass"`, matched exactly.

Default: `[]`

#### ignoreProcesses : list&lt;string&gt;

Programs to ignore, such as `"notepad.exe"`, matched exactly.

Default: `[]`

#### hasWindow : bool `read-only`

`true` when there is a window.

#### text : string `read-only`

`label` (or `alternateLabel`) filled in for the window, or `noWindowLabel` when there is none. If a placeholder can't be
filled for the window, the label is shown unchanged.

#### icon : string `read-only`

Image URL of the window's icon. `""` when there is no window.

#### window : object `read-only`

Details of the window. `{}` when there is none.

- `hwnd` : int, window handle.
- `title` : string, title, after `rewrite` and `maxLength`.
- `class_name` : string, window class.
- `process` : object, program: `name` (such as `"notepad.exe"`), `pid` and `path` (full path).
- `app_name` : string, app name, after `rewrite`.
- `monitor` : string, name of the screen it is on, such as `"\\.\DISPLAY1"`.

### Functions

#### toggleLabel()

Switches `showAlternate`.

## Used by

YASB's own Active window widget, listed in [Widgets](./Widgets).
