# Quick launch

`import Yasb`

Search across Quick Launch's providers (apps, files, calculator, web search and more), with functions to run what
the user picks. All QuickLaunchSearch objects share one search thread and one set of providers, so the
`providers` set last applies to all of them.

Two types:

- [QuickLaunchSearch](#quicklaunchsearch): the one a widget creates.
- [ResultModel](#resultmodel): the results, available as `results`. See [Row fields](#row-fields).

## QuickLaunchSearch

### Properties

#### providers : object

Settings of each provider, by name: `apps`, `bookmarks`, `calculator`, `clipboard_history`, `color`, `binance`,
`currency`, `dev_tools`, `emoji`, `file_search`, `github_notifications`, `hacker_news`, `ip_info`,
`kill_process`, `port_viewer`, `settings`, `snippets`, `ssh`, `system_commands`, `unit_converter`, `vscode`,
`web_search`, `window_switcher`, `windows_terminal`, `world_clock` and `wsl`. A provider left out runs with its
defaults.

Keys every provider reads:

- `enabled` : bool, `false` leaves the provider out. Default `true`.
- `prefix` : string, text typed first, followed by a space, to search only this provider. `"*"`, or no `prefix`, gives
  none: the provider's results join the others' without a prefix.
- `priority` : int, providers with lower values run and list their results first. Default `0`.
- `show_preview` : bool, the `shown` key of the provider's previews, see `preview()`. Default `true`.

The other keys are the provider's own options.

Default: `{}`

#### maxResults : int

The maximum number of results per search, from 1 to 500.

Default: `50`

#### homePage : bool

When `true` and nothing is typed, the results are the providers with a prefix, and picking one types its prefix.
When `false`, an empty search runs the providers.

Default: `false`

#### results : ResultModel `read-only`

The results of the last search. See [ResultModel](#resultmodel).

#### loading : bool `read-only`

`true` while a search is in progress, or while some of its results are still loading.

#### prediction : string `read-only`

What the first app result would complete the typed text to: `""` unless its title starts with the typed text, in
any case.

#### prefixes : list `read-only`

The providers with a prefix, each an object:

- `prefix` : string, the prefix.
- `name` : string, the provider's name.
- `placeholder` : string, a hint for the search box.

### Functions

#### search(text: string)

Searches for `text`. A provider's prefix followed by a space searches only that provider.

#### refresh()

Runs the last search again, if it's in progress or has results. Providers also call it when what they show changes.

#### execute(row: int)

Runs the result in this row. Depending on the result, it sends `queryRequested`, `colorPickRequested` or
`closeRequested`, or runs the search again. Ignored for a separator.

#### contextActions(row: int) : list

The actions of the result's right-click menu, each an object:

- `id` : string, for `runContextAction()`.
- `label` : string, the action's text.
- `enabled` : bool, `false` when it can't run now.
- `separatorBefore` : bool, `true` when a separator goes above it.

Empty when the result has no menu.

#### runContextAction(row: int, actionId: string)

Runs the action with this `id` on the result. Afterwards, it sends `closeRequested` or runs the search again, as
the action asks.

#### preview(row: int) : object

The preview of the result, `{}` when it has none. Keys a provider can give:

- `kind` : string, `text`, `image` or `edit` (a form).
- `shown` : bool, the provider's `show_preview`.
- `title` : string, the preview's title.
- `subtitle` : string, a line under the title.
- `text` : string, the text to show.
- `icon` : string, image URL of a large icon, from a file or from SVG text. `""` when it is neither.
- `image_data` : string, the image as a data URL.
- `metadata` : list&lt;string&gt;, details: each label followed by its value.
- `fields` : list&lt;object&gt;, the form's fields, with `id`, `label`, `type` (`text` or `multiline`), `value` and
  `placeholder`.
- `action` : string, the `id` to send with the form's values.

#### previewAction(row: int, actionId: string, values: object)

Sends the preview form's `values`, by field `id`, with `actionId`. Afterwards, it sends `closeRequested` or runs
the search again.

#### cancelEdit()

Tells the providers the preview form was closed without saving.

#### deactivate()

Clears the results and tells the providers the search was closed. Call it when the popup closes.

#### activate(window: Window)

Gives `window` the keyboard focus, even when it was opened by a hotkey.

#### excludeFromCapture(window: Window)

Keeps `window` out of screen captures, so the colour picker doesn't see itself.

#### colorsAround(x: int, y: int, size: int) : list&lt;string&gt;

Colours of the `size` × `size` physical pixels centred on the screen point `x`, `y`, row by row, as `#RRGGBB`.
Empty when no screen is there.

### Signals

#### closeRequested()

A result asked for the popup to close.

#### queryRequested(text: string)

A result asked for `text` in the search box, its prefix included.

#### colorPickRequested(prefix: string)

A result asked to pick a colour from the screen. `prefix` is its provider's prefix, with a space after it.

## ResultModel

Every search replaces all rows. Icons update in place once they load.

### Row fields

#### title : string

The result's title.

#### description : string

A line under the title.

#### icon : string

Image URL of the result's icon. `""` when it has none, or its icon is text.

#### iconText : string

The result's icon when it is text, such as an emoji. `""` when its icon is an image.

#### separator : bool

`true` for a heading between results, which can't be run.

#### loading : bool

`true` for a row shown while the provider still loads its results.

#### provider : string

Name of the provider that gave the result.

#### path : string

Path of a file or folder result, or of an app result (a shortcut, or an id such as `UWP::<app id>`). `""` for
other results.

## Used by

YASB's own Quick Launch widget, listed in [Widgets](./Widgets).
