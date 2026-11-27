# Layouts

A layout is the bar's own look: its background, corners, border, padding and spacing, and anything else you draw on it.
The widgets come from `config.yaml`, and the layout decides where their slots go. Depending on the style you picked, the
setup created `layouts\bar.qml`, `layouts\floating.qml` or `layouts\islands.qml` in your config folder.

## Pick a layout

A bar's `layout` in `config.yaml` picks its layout, as [Layouts and themes](./Configuration#layouts-and-themes)
explains. Without one, the bar uses the default [Bar](./(Type)-Bar) with the theme's bar background. The bar
changes as soon as you save its layout. A layout with an error isn't used. The bar falls back to the
default, and an alert shows the error.

## YASB's layouts

Each of the setup's three styles is a short layout file. This is `floating.qml`:

```qml
// %USERPROFILE%\.config\yasb\layouts\floating.qml
import Yasb.Bar

// A bar with rounded corners and a border all around; the gap to the screen edges is the bar's margin in
// config.yaml. The widgets come from config.yaml; this file sets how the bar looks, for example its color, radius,
// border, padding or spacing.
Bar {
    color: theme.bar.background
    border.width: 1
    border.color: theme.bar.border
    radius: 8
    padding: 12
    spacing: 12
}
```

- `bar.qml` is a [Bar](./(Type)-Bar) with square corners and a line on the side away from the screen edge.
- `floating.qml` is a [Bar](./(Type)-Bar) with rounded corners and a border all around. The setup gives it a
  `margin` in `config.yaml`, so it floats away from the screen edges.
- `islands.qml` is an [IslandBar](./(Type)-IslandBar): a thin rail along the screen edge, with each group of widgets
  on its own island.

## What a layout sets

A layout's root is [Bar](./(Type)-Bar), [IslandBar](./(Type)-IslandBar) or [BarBase](./(Type)-BarBase), from
`import Yasb.Bar`. These are the values you'll change most:

| Value | What it is |
| --- | --- |
| `color` or `gradient` | The bar's fill. |
| `radius` | How round its corners are, in pixels. |
| `border.width` and `border.color` | Its outline. |
| `padding` | The space between the bar's ends and its first and last widgets. |
| `spacing` | The space between two widgets. |
| `railHeight`, `edgeRadius` and `fillGradient` | On an IslandBar: how thick the rail is, how round the curve is where an island at an end of the bar meets the side of the screen, and a gradient for the fill. Its `radius` rounds the islands' corners. |

A layout can read `theme`, the bar's [Theme](./(Type)-Theme), and also `edge`, `vertical`, `dark`, `name` and
`screenName`, so one layout can look different on each bar. `hasMaximizedWindow` is `true` while a window is maximized
on the bar's screen. This bar loses its corners while a window is maximized:

```qml
// %USERPROFILE%\.config\yasb\layouts\square-when-maximized.qml
import Yasb.Bar

Bar {
    color: theme.bar.background
    radius: hasMaximizedWindow ? 0 : 8
}
```

## Draw on the bar

Anything you put inside the root is drawn on the bar. Give it `parent: bar.background` to draw it under the
widgets. `bar.qml` draws its line this way:

```qml
// %USERPROFILE%\.config\yasb\layouts\bar.qml
import QtQuick
import Yasb.Bar

// A bar across the whole screen edge. The widgets come from config.yaml; this file sets how the bar looks, for
// example its color, radius, border, padding or spacing.
Bar {
    id: bar

    color: theme.bar.background
    radius: 0
    padding: 12
    spacing: 12

    // A line along the side away from the screen: under a bar at the top, over a bar at the bottom
    Rectangle {
        parent: bar.background
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: bar.edge === "bottom" ? parent.top : undefined
        anchors.bottom: bar.edge === "bottom" ? undefined : parent.bottom
        height: 1
        color: bar.border.color
    }
}
```

## Islands

On an [IslandBar](./(Type)-IslandBar), the widgets of each slot share one island. To take a widget out of its island,
add `property bool island: false` to your [copy of the widget](./Widgets), beside its `settings`. The widget then sits
on the rail outside any island, and the widgets after it start a new island:

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

## Custom slots

[Bar](./(Type)-Bar) has three slots. For different slots, start from [BarBase](./(Type)-BarBase), which has none, and
add a [WidgetSlot](./(Type)-WidgetSlot) for each slot you want. Each one shows the widgets that `config.yaml` lists
under its `name`. This layout, for a bar at the top or bottom, has a `start` slot and an `end` slot:

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

## The right-click menu

A right-click on the bar, outside its widgets, opens YASB's bar menu: Task Manager, a screenshot of the bar, auto-hide,
reload and exit. `contextMenu: null` in the layout turns it off.

## Blur

With `backdrop: true`, YASB blurs the area defined by `backdropShapes`. By default that's the whole bar with its
`radius`. Set it when you draw a custom shape, as a list of `{x, y, width, height, radius}` in the bar's coordinates.
The blur only shows through a fill you can see through, as [Themes](./Themes#blur) explains.

## Share a layout

A layout can be an [addon](./Addons). It goes in its own folder in `layouts`, and `config.yaml` names it by its id,
such as `layout: amnweb.rounded`.
