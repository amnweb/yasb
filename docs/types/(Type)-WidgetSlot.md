# WidgetSlot

`import Yasb.Bar` · inherits [Item](https://doc.qt.io/qt-6/qml-qtquick-item.html)

A container for widgets in a layout. It shows the widgets listed under its `name` in config.yaml, in a row along the
bar, or in a column on a bar at the left or right edge. [Bar](./(Type)-Bar) has three. In a [BarBase](./(Type)-BarBase)
layout you add your own.

Guide: [Layouts](./Layouts)

## Example

Two slots in a [BarBase](./(Type)-BarBase) layout: `start` at the bar's start, `end` anchored to its end:

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

config.yaml lists each slot's widgets under its `name`:

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

## WidgetSlot

A slot is as long as its widgets unless you size it, and as thick as the bar. A widget that fails to load is skipped and
a warning is logged.

### Properties

#### name : string

The slot's name in config.yaml. Required.

#### alignment : string

Where the widgets sit in a slot longer than they are: `left` or `top` at its start, `center` in its middle,
`right` or `bottom` at its end.

Default: `"left"`

#### stretch : bool

In a Bar, whether the slot shares the bar's free length. See [Bar](./(Type)-Bar#slot-lengths).

Default: `true`

#### spacing : int

Pixels between two widgets.

Default: the bar's `spacing`

#### bar : BarBase

The bar the slot belongs to. If `null`, the slot finds the BarBase it's in automatically, and logs a warning if there
isn't one.

Default: `null`

#### widgets : list `read-only`

The widgets config.yaml lists under `name`, in order, each as `{name, url}`.

#### vertical : bool `read-only`

`true` on a bar at the left or right edge.

WidgetSlot has no functions or signals for layouts.
