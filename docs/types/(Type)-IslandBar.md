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

To set a widget apart on the rail, add `property bool island: false` to your copy of the widget, as from
`yasbc addons install Clock`:

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

The widgets of a slot share one island, which reaches `padding` past its first and last widget. Islands that touch
become one, and an island within `radius` of a bar end runs to that end. A widget that declares
`property bool island: false` sits on the rail instead, outside any island, and the widgets after it start a new
one.

The fill is `color`, or `fillGradient`. `border` outlines only the side away from the screen edge. The blur
follows the rail and the islands.

### Properties

#### railHeight : real

How thick the rail is, in pixels, at most the bar's thickness.

Default: `4`

#### radius : real

How round the islands' corners are, and the curves where they rise from the rail, at most half of what an island
stands above the rail.

Default: `12`

#### edgeRadius : real

How round the curve is where an island at an end of the bar meets the side of the screen. The curve reaches
outside the bar, into space the bar's window adds for it. `0` for none.

Default: `0`

#### fillGradient : ShapeGradient

A gradient for the fill, in place of `color`, such as a LinearGradient from `import QtQuick.Shapes`. `gradient`
isn't used on an IslandBar, setting it only logs a warning.

Default: `null`

IslandBar has no functions or signals for layouts.
