# LoadingLine

`import Yasb.Common` · inherits [Item](https://doc.qt.io/qt-6/qml-qtquick-item.html)

A thin line with a bar sliding along it while `running`, to show that something is loading, such as under a
popup's header.

Guide: [Writing widgets](./Writing-Widgets)

## Example

YASB's Power plan widget puts one under its popup's header, running while the power plans are read:

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Common

ColumnLayout {
    Label {
        text: "Power plan"
    }

    LoadingLine {
        Layout.fillWidth: true
        running: PowerPlans.loading
        trackColor: root.theme.colors.divider
    }
}
```

Here `root.theme` is the widget's theme, and the ColumnLayout sits inside the widget's
[BackdropPopup](./(Type)-BackdropPopup). With `trackColor` set, the line also shows as a divider while nothing
loads.

## LoadingLine

The line is 1 pixel tall unless you set its `height`. The sliding bar is 40% of the line's width, and only moves
while the line is visible and wider than 0.

### Properties

#### running : bool

When `true`, the bar slides along the line, over and over.

Default: `false`

#### color : color

The sliding bar's colour. Inside a BackdropPopup, `palette.accent` is the theme's accent.

Default: `palette.accent`

#### trackColor : color

The line's colour behind the bar.

Default: `"transparent"`

#### duration : int

Milliseconds the bar takes to cross the line once.

Default: `1600`

LoadingLine has no functions or signals.

## Used by

The popups of YASB's own Bluetooth, Network, Power plan, Quick Launch, Server monitor, Updates and Weather widgets.
