# BackdropPopup

`import Yasb.Common` · inherits [QtObject](https://doc.qt.io/qt-6/qml-qtqml-qtobject.html)

A widget popup that opens in its own window. Put the popup's content inside it. When the bar has `backdrop: true`, the
area behind `backdropItem` is blurred.

The popup closes when you press Escape, when it loses focus, or when you press the mouse on the bar or on the empty
space around the popup. Pressing `anchor` doesn't close it. While hidden, its window releases its graphics resources.

Guide: [Writing widgets](./Writing-Widgets)

## Example

This widget opens a popup when clicked. The popup appears below the widget, or above it on a bar at the bottom. It uses
the theme's popup colours and gets a blurred background when the bar has `backdrop: true`:

```qml
// %USERPROFILE%\.config\yasb\widgets\HelloPopup\HelloPopup.qml
import QtQuick
import QtQuick.Controls
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: root

    required property BarBase bar
    readonly property Theme theme: bar.theme

    function togglePopup() {
        if (popup.visible) {
            popup.close()
            return
        }
        const start = mapToGlobal(0, 0)
        popup.x = Math.round(start.x + (width - popup.width) / 2)
        popup.y = Math.round(bar.edge === "bottom" ? start.y - popup.height - theme.popup.gap
            : start.y + height + theme.popup.gap)
        popup.open()
    }

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight

    // The popup is a separate window, so hide it when the widget is destroyed
    Component.onDestruction: popup.hide()

    Label {
        id: label

        anchors.verticalCenter: parent.verticalCenter
        text: "Hello"
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.togglePopup()
    }

    BackdropPopup {
        id: popup

        width: 240
        height: 80
        anchor: root
        theme: root.theme
        font.family: root.theme.popup.font.family
        font.pixelSize: 13
        backdropItem: surface

        Rectangle {
            id: surface

            anchors.fill: parent
            radius: root.theme.popup.radius
            color: root.theme.popup.background
            border.width: 1
            border.color: root.theme.popup.border

            Label {
                anchors.centerIn: parent
                text: "Hello from the popup"
            }
        }
    }
}
```

The widget places the popup by setting `x` and `y` before `open()`. Because `anchor` is the widget, clicking it again
closes the popup instead of closing and reopening it. `backdropItem` is the rectangle, so the blur gets the same rounded
corners.

To fade the popup in and out, give it `enter` and `exit` animations. The built-in Quick Launch widget does this:

```qml
BackdropPopup {
    id: popup

    property real reveal: 0

    enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: root.theme.popup.openDuration; easing.type: Easing.OutCubic }
    exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: root.theme.popup.closeDuration; easing.type: Easing.InCubic }
    onVisibleChanged: {
        if (!visible)
            reveal = 0
    }

    // ... and on the Rectangle: opacity: popup.reveal
}
```

## Shapes in a popup

A Shape inside the popup loses its geometry when the popup hides and releases its graphics. A path that changes
with each update, like a live graph line, is rebuilt anyway. A path that stays the same, like a graph's grid, isn't
drawn again when the popup reopens. Leave it empty while the popup is hidden, so it's rebuilt each time it opens:

```qml
PathSvg {
    path: popup.visible ? root.gridPath : ""
}
```

## BackdropPopup

Every Label and control inside the popup uses `font`. Controls get their accent and text colours from `theme`.

### Properties

#### x, y, width, height : real

The popup's position on screen and its size.

Default: `0`

#### anchor : Item

The item that opens the popup, usually the widget. Pressing it doesn't close the popup, so it can toggle it.

Default: `null`

#### theme : Theme

The widget's [Theme](./(Type)-Theme). Required.

#### font : font

The font used by every Label and control in the popup, usually the widget's popup font.

#### backdropItem : Item

The item that defines the blurred area. The blur follows its position, size, rounded corners and opacity. Set it to
`null` for no blur.

Default: `null`

#### enter : Animation

Runs each time the popup opens, after it shows.

Default: `null`

#### exit : Animation

Runs each time the popup closes. The popup hides when it finishes.

Default: `null`

#### pinned : bool

When `true`, the popup stays open when it loses focus or the bar is pressed. `close()` and Escape still close it.

Default: `false`

#### title : string

The popup window's title.

#### color : color

The popup window's background, behind the content.

Default: `"transparent"`

#### visible : bool `read-only`

`true` while the popup shows.

#### closing : bool `read-only`

`true` while `exit` runs.

#### window : Window `read-only`

The popup's window. Pass it to functions that focus a window, like `takeFocus()` of
[Window switcher](./(Service)-WindowSwitcher) or `activate()` of [Quick launch](./(Service)-QuickLaunch).

### Functions

#### open()

Shows and focuses the popup, then runs `enter`. Stops `exit` if it's running.

#### close()

Runs `exit` and hides the popup when it finishes. Without `exit`, hides it immediately. Does nothing if the popup is
hidden or already closing.

#### hide()

Hides the popup at once, without `exit`.

BackdropPopup has no signals.

## Used by

The popups of all built-in widgets.
