# Bar

`import Yasb.Bar` · inherits [BarBase](./(Type)-BarBase)

A layout with three slots: `left`, `center` and `right`, or `top`, `center` and `bottom` on a bar at the left or
right edge. They show the widgets config.yaml lists under those names, side by side along the bar. The left slot's
widgets sit at its start, the center slot's in its middle and the right slot's at its end.

Everything from [BarBase](./(Type)-BarBase) applies, such as `color`, `radius`, `padding` and `spacing`.

Guide: [Layouts](./Layouts)

## Example

YASB's `floating.qml`, a bar with rounded corners and a border all around:

```qml
// %USERPROFILE%\.config\yasb\layouts\floating.qml
import Yasb.Bar

Bar {
    color: theme.bar.background
    border.width: 1
    border.color: theme.bar.border
    radius: 8
    padding: 12
    spacing: 12
}
```

YASB's `bar.qml` draws on the bar too: a line on the side away from the screen edge, placed on `background`:

```qml
// %USERPROFILE%\.config\yasb\layouts\bar.qml
import QtQuick
import Yasb.Bar

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

config.yaml lists the widgets under `left`, `center` and `right`, or `top`, `center` and `bottom`.

## Bar

### Properties

#### leftSlot, centerSlot, rightSlot : WidgetSlot `read-only`

The three slots, each a [WidgetSlot](./(Type)-WidgetSlot), such as to set `stretch` or `spacing` on one.
`topSlot` is the same slot as `leftSlot`, and `bottomSlot` the same as `rightSlot`.

### Slot lengths

A slot whose `stretch` is `false` is as long as its widgets. The others share the rest of the bar equally, in whole
pixels, but none gets shorter than its widgets.

Bar has no functions or signals for layouts.
