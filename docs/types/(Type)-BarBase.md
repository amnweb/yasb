# BarBase

`import Yasb.Bar` · inherits [Item](https://doc.qt.io/qt-6/qml-qtquick-item.html)

The root of a layout with no slots of its own: the bar's surface, its theme and its right-click menu. Place a
[WidgetSlot](./(Type)-WidgetSlot) for each slot the layout has. [Bar](./(Type)-Bar) and
[IslandBar](./(Type)-IslandBar) are built on it. A layout whose root isn't one of the three doesn't load.

Guide: [Layouts](./Layouts)

## Example

A layout with a `start` slot and an `end` slot, for a bar at the top or bottom:

```qml
// %USERPROFILE%\.config\yasb\layouts\two-ends.qml
import Yasb.Bar

BarBase {
    color: theme.bar.background
    radius: 8

    WidgetSlot {
        name: "start"
        height: parent.height
    }

    WidgetSlot {
        name: "end"
        anchors.right: parent.right
        height: parent.height
    }
}
```

The bar picks it by its file name, and lists its widgets under the slots' names:

```yaml
bars:
  yasb-bar:
    layout: two-ends
    widgets:
      start:
        - ActiveWindow
      end:
        - Clock
```

## BarBase

### Properties

#### color : color

The bar's fill.

Default: `theme.bar.background`

#### gradient : Gradient

A gradient for the fill, in place of `color`.

Default: none

#### radius : real

How round the bar's corners are, in pixels.

Default: `0`

#### border : group

The bar's outline: `border.width` and `border.color`.

Default: width `0`, color `theme.bar.border`

#### padding : int

Pixels between the bar's ends and its first and last widgets.

Default: `12`

#### spacing : int

Pixels between two widgets, for each WidgetSlot that doesn't set its own.

Default: `12`

#### backdropShapes : list

Where the blur goes when the bar has `backdrop: true`, as a list of `{x, y, width, height, radius}` in the bar's
coordinates. An invalid list gives no blur, and a warning in the log.

Default: the whole bar, with its `radius`

#### backdropPath : string

An SVG path for the blur's outline instead, which can reach outside the bar, as IslandBar's does.

Default: `""`

#### contextMenu : Component

What a right-click on the bar opens, away from its widgets: YASB's bar menu, `null` for none, or a Component of
your own. Yours is created with `bar` (this bar), `position` (the click, on screen) and `area` (the screen's
rectangle), so it declares those three properties.

Default: YASB's bar menu

#### background : Rectangle `read-only`

The bar's surface, to put items of your own on, with `parent: bar.background`.

#### theme : Theme `read-only`

The bar's [Theme](./(Type)-Theme).

#### dark : bool `read-only`

`true` while Windows is in dark mode.

#### name : string `read-only`

The bar's name in config.yaml.

#### screenName : string `read-only`

The name of the bar's screen, as `yasbc monitor-information` shows it.

#### edge : string `read-only`

The screen edge the bar is on: `top`, `bottom`, `left` or `right`.

#### vertical : bool `read-only`

`true` for a bar at the left or right edge.

#### hasMaximizedWindow : bool `read-only`

`true` while a window is maximized on the bar's screen. YASB only follows maximized windows while the layout reads
this, or the bar hides for them.

### Items inside it

Items you place in a BarBase are laid out inside the bar, `padding` in from its ends, and every Label among them
takes the theme's bar font.

YASB logs a warning for each slot in config.yaml that the layout has no WidgetSlot for, its widgets aren't shown.

BarBase has no functions or signals for layouts.
