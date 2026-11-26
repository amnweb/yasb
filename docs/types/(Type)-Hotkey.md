# Hotkey

`import Yasb`

A global keyboard shortcut for your widget. While YASB is running, pressing the keys anywhere in Windows triggers
`onActivated`.

Guide: [Writing widgets](./Writing-Widgets)

## Example

A Hotkey works inside a widget that a bar loads. This widget shows a toast on Alt+Shift+H:

```qml
// %USERPROFILE%\.config\yasb\widgets\HelloKey\HelloKey.qml
import QtQuick
import Yasb
import Yasb.Bar

Item {
    // Set by YASB to the bar the widget is in
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

Built-in widgets that support a shortcut have a `hotkey` option. It's empty by default, except Launchpad's, which is
`alt+l`. Some have more, like OBS's `recordHotkey`. To set one, run `yasbc addons install Cpu` to get the widget's
options, then set `hotkey` in `%USERPROFILE%\.config\yasb\widgets\Cpu\Cpu.qml` and save. See
[Widgets](./Widgets#get-a-widgets-options).

## Which bar gets it

If you have a bar on each screen, each bar has its own copy of your widget. Only the copies on the screen chosen by
`screen` receive the key press. Holding the keys down triggers it once.

YASB reads shortcuts when the bars load, and again when saving a file rebuilds a bar. If `keys` changes while the widget
is running, the change takes effect at that point.

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

A shortcut isn't registered if it has an unknown key or more than one key, or if another app already uses it. Each case
logs a warning.

Default: `""`

#### screen : string

Which bar's widget gets the press: `active` (the screen of the foreground window), `cursor` (the screen under the mouse)
or `primary` (the primary screen). When several widgets use the same keys, the `screen` of the first one YASB finds
applies to all of them.

Default: `"active"`

### Signals

#### activated()

Emitted when the keys are pressed. If several widgets on that bar use the same keys, all of them receive it.
