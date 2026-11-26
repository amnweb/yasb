# BackdropPopup

`import Yasb.Common` · inherits [QtObject](https://doc.qt.io/qt-6/qml-qtqml-qtobject.html)

A popup for a widget, in a window of its own, blurred behind `backdropItem` when its bar has a backdrop. Put the
popup's content inside it. It closes on Escape, when it loses the focus, and on a press on the bar outside
`anchor` or around the popup. While hidden, its window gives back its graphics memory.

Guide: [Writing widgets](./Writing-Widgets)

## Example

A widget that opens a popup under itself on a click, or over itself on a bar at the bottom, in the theme's popup
colours, with a blur behind it when the bar has `backdrop: true`:

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

    // The popup is a window of its own, so it goes when the widget does
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

The widget places the popup by setting `x` and `y` before `open()`. Because `anchor` is the widget, a second click
on it closes the popup instead of closing and opening it again. `backdropItem` is the rectangle, so the blur has
its rounded corners.

To fade the popup in and out, give it `enter` and `exit` animations, as YASB's Quick Launch does:

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

## BackdropPopup

Every Label and control inside it takes `font`, and the controls take their accent and text colours from `theme`.

### Properties

#### x, y, width, height : real

Where the popup is on screen, and its size.

Default: `0`

#### anchor : Item

The item that opens the popup, usually the widget. Pressing it doesn't close the popup, so it can toggle it.

Default: `null`

#### theme : Theme

The widget's [Theme](./(Type)-Theme). Required.

#### font : font

The font every Label and control in the popup takes, such as the widget's popup font.

#### backdropItem : Item

The item the blur follows, with its position, size, rounded corners and opacity. `null` for no blur.

Default: `null`

#### enter : Animation

Runs each time the popup opens, after it shows.

Default: `null`

#### exit : Animation

Runs each time the popup closes, the popup hides once it ends.

Default: `null`

#### pinned : bool

When `true`, the popup stays open when it loses the focus or the bar is pressed. `close()` and Escape still close
it.

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

The popup's window, for functions that give it the focus, such as `takeFocus()` of
[Window switcher](./(Service)-WindowSwitcher) or `activate()` of [Quick launch](./(Service)-QuickLaunch).

### Functions

#### open()

Shows the popup and gives it the focus, then runs `enter`. A running `exit` stops.

#### close()

Runs `exit`, then hides the popup once it ends, without `exit`, hides it at once. Ignored while the popup is
hidden or already closing.

#### hide()

Hides the popup at once, without `exit`.

BackdropPopup has no signals.

## Used by

The popups of YASB's own widgets.
