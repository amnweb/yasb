# WidgetSlot

`import Yasb.Bar` · inherits [Item](https://doc.qt.io/qt-6/qml-qtquick-item.html)

A place for widgets in a layout: it shows the widgets config.yaml lists under its `name`, in a row along the bar,
or a column on a bar at the left or right edge. [Bar](./(Type)-Bar) has three, in a
[BarBase](./(Type)-BarBase) layout you place your own.

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

Along the bar, a slot is as long as its widgets unless you size it, and across it, as thick as the bar. A widget
that fails to load is left out, with a warning in the log.

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

The bar the slot belongs to. When left `null`, the slot finds the BarBase it sits in by itself, and logs a warning
when there is none.

Default: `null`

#### widgets : list `read-only`

The widgets config.yaml lists under `name`, in order, each as `{name, url}`.

#### vertical : bool `read-only`

`true` on a bar at the left or right edge.

WidgetSlot has no functions or signals for layouts.
