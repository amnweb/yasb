# IslandBar

`import Yasb.Bar` · inherits [Bar](./(Type)-Bar)

A [Bar](./(Type)-Bar) drawn as a thin rail along the screen edge, with each group of widgets on an island that
rises from it. Same three slots as Bar, and everything from [BarBase](./(Type)-BarBase) applies.

Guide: [Layouts](./Layouts)

## Example

YASB's `islands.qml`, a 1-pixel rail with outlined islands:

```qml
// %USERPROFILE%\.config\yasb\layouts\islands.qml
import Yasb.Bar

IslandBar {
    color: theme.bar.background
    border.width: 1
    border.color: theme.bar.border
    railHeight: 1
    radius: 16
    edgeRadius: 16
    padding: 12
    spacing: 10
}
```

To put a widget on the rail outside the islands, add `property bool island: false` to your copy of the widget (from
`yasbc addons install Clock`):

```qml
// %USERPROFILE%\.config\yasb\widgets\Clock\Clock.qml
import Yasb.Widgets

Clock {
    property bool island: false

    settings {
        // your settings
    }
}
```

## IslandBar

Each slot's widgets share one island, which extends `padding` beyond its first and last widget. Islands that touch merge
into one, and an island within `radius` of either end of the bar extends to that end. A widget that declares
`property bool island: false` sits on the rail outside any island, and the widgets after it start a new island.

The fill is `color` or `fillGradient`. `border` only draws on the side facing away from the screen edge. The blur covers
the rail and the islands.

### Properties

#### railHeight : real

How thick the rail is, in pixels, at most the bar's thickness.

Default: `4`

#### radius : real

Corner radius of the islands and of the curves where they rise from the rail. At most half the island's height above the
rail.

Default: `12`

#### edgeRadius : real

Radius of the curve where an island at either end of the bar meets the side of the screen. The curve extends outside the
bar, into extra space the bar's window adds for it. `0` for none.

Default: `0`

#### fillGradient : ShapeGradient

A gradient for the fill, in place of `color`, such as a LinearGradient from `import QtQuick.Shapes`. IslandBar ignores
`gradient`. Setting it only logs a warning.

Default: `null`

IslandBar has no functions or signals for layouts.
