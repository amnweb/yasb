pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

// The addon's images at full size
Popup {
    id: viewer

    property list<string> images
    property int index
    readonly property string current: images.length > index ? images[index] : ""
    readonly property real maxZoom: 4
    readonly property real wheelStep: 1.25
    readonly property real doubleTapZoom: 2
    readonly property int zoomDuration: 180
    // Where the zoom is going: times the fitted size, and the picture's centre away from the window's centre
    property real zoom: 1
    property real panX: 0
    property real panY: 0
    // What is drawn, easing towards the above
    property real shownZoom: zoom
    property real shownPanX: panX
    property real shownPanY: panY
    property bool smoothly: true

    Behavior on shownZoom {
        enabled: viewer.smoothly
        NumberAnimation {
            duration: viewer.zoomDuration
            easing.type: Easing.OutCubic
        }
    }
    Behavior on shownPanX {
        enabled: viewer.smoothly && !panning.active
        NumberAnimation {
            duration: viewer.zoomDuration
            easing.type: Easing.OutCubic
        }
    }
    Behavior on shownPanY {
        enabled: viewer.smoothly && !panning.active
        NumberAnimation {
            duration: viewer.zoomDuration
            easing.type: Easing.OutCubic
        }
    }

    function show(at: int) {
        index = at
        open()
    }

    function step(by: int) {
        index = (index + by + images.length) % images.length
    }

    function fitAgain() {
        zoom = 1
        panX = 0
        panY = 0
    }

    // A new picture starts fitted, with no zoom out from the last one
    function reset() {
        smoothly = false
        fitAgain()
        smoothly = true
    }

    function panTo(x: real, y: real) {
        const limitX = Math.max(0, (full.implicitWidth * stage.fit * zoom - stage.width) / 2)
        const limitY = Math.max(0, (full.implicitHeight * stage.fit * zoom - stage.height) / 2)
        panX = Math.max(-limitX, Math.min(limitX, x))
        panY = Math.max(-limitY, Math.min(limitY, y))
    }

    // Keeps the point under the cursor where it is
    function zoomAt(position: point, to: real) {
        const next = Math.max(1, Math.min(maxZoom, to))
        const ratio = next / zoom
        const fromCentreX = position.x - stage.width / 2
        const fromCentreY = position.y - stage.height / 2
        zoom = next
        panTo(fromCentreX - (fromCentreX - panX) * ratio, fromCentreY - (fromCentreY - panY) * ratio)
    }

    onCurrentChanged: reset()
    onAboutToShow: reset()

    parent: Overlay.overlay
    x: 0
    y: 0
    width: parent?.width ?? 0
    height: parent?.height ?? 0
    modal: true
    padding: 0
    background: Rectangle {
        color: Qt.alpha("#000000", 0.85)
    }

    contentItem: Item {
        id: stage

        // Fits the picture beside the buttons, never larger than its own size
        readonly property real fit: full.implicitWidth > 0 && full.implicitHeight > 0
            ? Math.min(1, (width - 160) / full.implicitWidth, (height - 112) / full.implicitHeight) : 0

        focus: true
        clip: true
        Keys.onLeftPressed: viewer.step(-1)
        Keys.onRightPressed: viewer.step(1)
        Keys.onEscapePressed: viewer.close()
        onWidthChanged: viewer.panTo(viewer.panX, viewer.panY)
        onHeightChanged: viewer.panTo(viewer.panX, viewer.panY)

        TapHandler {
            onTapped: viewer.close()
        }

        WheelHandler {
            target: null
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: event => viewer.zoomAt(point.position,
                viewer.zoom * Math.pow(viewer.wheelStep, event.angleDelta.y / 120))
        }

        Image {
            id: full

            property point dragStart

            x: (stage.width - width) / 2 + viewer.shownPanX
            y: (stage.height - height) / 2 + viewer.shownPanY
            width: implicitWidth * stage.fit * viewer.shownZoom
            height: implicitHeight * stage.fit * viewer.shownZoom
            source: viewer.current
            asynchronous: true

            TapHandler {
                onDoubleTapped: eventPoint => viewer.zoom > 1 ? viewer.fitAgain()
                    : viewer.zoomAt(stage.mapFromItem(null, eventPoint.scenePosition), viewer.doubleTapZoom)
            }

            DragHandler {
                id: panning

                target: null
                enabled: viewer.zoom > 1
                cursorShape: Qt.ClosedHandCursor
                onActiveChanged: if (active)
                    full.dragStart = Qt.point(viewer.panX, viewer.panY)
                onActiveTranslationChanged: if (active)
                    viewer.panTo(full.dragStart.x + activeTranslation.x, full.dragStart.y + activeTranslation.y)
            }

            HoverHandler {
                enabled: viewer.zoom > 1
                cursorShape: Qt.OpenHandCursor
            }
        }

        BusyIndicator {
            anchors.centerIn: parent
            running: full.status === Image.Loading
        }

        Button {
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.margins: 16
            flat: true
            contentItem: Glyph {
                text: "\uE8BB"
                color: "#ffffff"
            }
            onClicked: viewer.close()
        }

        Button {
            anchors.left: parent.left
            anchors.leftMargin: 24
            anchors.verticalCenter: parent.verticalCenter
            visible: viewer.images.length > 1
            flat: true
            contentItem: Glyph {
                text: "\uE76B"
                color: "#ffffff"
            }
            onClicked: viewer.step(-1)
        }

        Button {
            anchors.right: parent.right
            anchors.rightMargin: 24
            anchors.verticalCenter: parent.verticalCenter
            visible: viewer.images.length > 1
            flat: true
            contentItem: Glyph {
                text: "\uE76C"
                color: "#ffffff"
            }
            onClicked: viewer.step(1)
        }

        Label {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 24
            visible: viewer.images.length > 1
            text: qsTr("%1 of %2").arg(viewer.index + 1).arg(viewer.images.length)
            color: "#ffffff"
        }
    }
}
