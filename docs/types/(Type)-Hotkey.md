# Hotkey

`import Yasb`

A keyboard shortcut for your widget. While YASB runs, pressing the keys anywhere in Windows runs `onActivated` in
your widget.

Guide: [Writing widgets](./Writing-Widgets)

## Example

A Hotkey works inside a widget that a bar loads. This widget shows a toast on Alt+Shift+H:

```qml
// %USERPROFILE%\.config\yasb\widgets\HelloKey\HelloKey.qml
import QtQuick
import Yasb
import Yasb.Bar

Item {
    // The bar the widget is in; YASB sets it
    required property BarBase bar

    Hotkey {
        keys: "alt+shift+h"
        onActivated: Notifier.toast("HelloKey", "Hello from the keyboard")
    }
}
```

Put it on a bar in `config.yaml`:

```yaml
bars:
  yasb-bar:
    widgets:
      right:
        - HelloKey
```

YASB's own widgets with a shortcut have a `hotkey` option, empty by default except Launchpad's `alt+l`. Some have
more, such as OBS's `recordHotkey`. To set one, get the widget's options
with `yasbc addons install Cpu`, set `hotkey` in `%USERPROFILE%\.config\yasb\widgets\Cpu\Cpu.qml` and save. See
[Widgets](./Widgets#get-a-widgets-options).

## Which bar gets it

With a bar on each screen, each bar has its own copy of your widget, and only the copies on the screen that
`screen` picks get the press. Holding the keys down sends it once.

YASB reads the shortcuts when the bars load, and again when a file you save rebuilds a bar. A `keys` that changes
while the widget runs takes effect then.

## Hotkey

### Properties

#### keys : string

The shortcut: modifiers and one key joined by `+`, in any case, such as `alt+shift+c` or `win+f1`. `""` for none.

- Modifiers: `win` (or `windows`, `super`, `meta`), `alt`, `ctrl` (or `control`) and `shift`.
- Keys: a letter or digit, `f1` to `f24`, `space`, `tab`, `enter` (or `return`), `esc` (or `escape`),
  `backspace`, `delete` (or `del`), `insert` (or `ins`), `home`, `end`, `pageup` (or `pgup`), `pagedown` (or
  `pgdn`), `left`, `up`, `right`, `down`, `pause`, `capslock` (or `caps`), `numlock`, `scrolllock`, `printscreen`
  (or `prtsc`), `numpad0` to `numpad9`, `multiply`, `add`, `subtract`, `decimal`, `divide`, `semicolon`, `equal`
  (or `equals`), `comma`, `minus`, `period`, `slash`, `backquote` (or `grave`), `bracketleft`, `backslash`,
  `bracketright` and `quote`.

A shortcut with an unknown key or more than one key isn't registered, and neither is one another app already
uses. Each logs a warning.

Default: `""`

#### screen : string

Which bar's widget gets the press: `active` (the screen of the window in front), `cursor` (the screen under the
mouse) or `primary` (the primary screen). When several widgets use the same keys, the `screen` of the first one
YASB finds counts for all of them.

Default: `"active"`

### Signals

#### activated()

The keys were pressed. When several widgets on that bar use the same keys, each of them gets it.
