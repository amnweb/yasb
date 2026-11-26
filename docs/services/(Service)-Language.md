# Keyboard language

`import Yasb`

Keyboard language and layout of the window in front, installed layouts, and caps lock, with a function to switch
layouts. Updated every `updateInterval`. While a YASB window has the focus (such as a popup), the language of the
previous window stays.

## KeyboardLanguage

### Properties

#### updateInterval : int

Milliseconds between readings of the language, layouts and caps lock, 250 to 3600000.

Default: `1000`

#### language : object `read-only`

Language of the window in front. `{}` until read.

- `language_code` : string, two-letter code, such as `"en"`.
- `iso_language_code` : string, three-letter code, such as `"eng"`.
- `country_code` : string, two-letter country code, such as `"US"`.
- `full_name` : string, language name in Windows' language, such as `"English (United States)"`.
- `native_lang_name` : string, language name in that language, such as `"Deutsch"`.
- `native_country_name` : string, country name in that language, such as `"Deutschland"`.
- `layout_name` : string, keyboard layout locale, such as `"en-US"`.
- `full_layout_name` : string, keyboard layout language, in Windows' language.
- `layout_country_name` : string, keyboard layout country, in Windows' language.

#### capsLock : bool `read-only`

`true` when caps lock is on.

#### layouts : list `read-only`

Installed keyboard layouts, sorted by language name. Each is an object:

- `id` : string, layout handle in hex. Used by `activate()`.
- `name` : string, language name, such as `"English (United States)"`.
- `code` : string, three-letter language code in capitals, such as `"ENG"`.
- `layout` : string, keyboard layout name, such as `"US"`.
- `current` : bool, `true` for the layout of the window in front.

### Functions

#### refresh()

Reads the language, layouts and caps lock now.

#### rememberWindow()

Remembers the window in front, so `activate()` switches that window. Call it before opening a layout menu, because
the menu takes the focus.

#### activate(id: string)

Switches to the layout with this `id`. The window remembered by `rememberWindow()` comes back to the front and gets
the layout. If there is none, or it was the desktop or taskbar, YASB's own layout is switched instead. `language`
updates at once. Unknown ids are ignored.

## Used by

YASB's own Keyboard language widget, listed in [Widgets](./Widgets).
