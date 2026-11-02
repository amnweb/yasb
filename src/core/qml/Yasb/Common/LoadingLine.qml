import QtQuick

Item {
    id: line

    property bool running: false
    property color color: palette.accent
    property color trackColor: "transparent"
    property int duration: 1600

    implicitHeight: 1
    clip: true

    Rectangle {
        anchors.fill: parent
        color: line.trackColor
    }

    Rectangle {
        id: bar

        objectName: "loadingBar"
        x: -width
        width: Math.round(line.width * 0.4)
        height: line.height
        radius: height / 2
        visible: line.running
        color: line.color

        NumberAnimation on x {
            running: line.running && line.visible && line.width > 0
            loops: Animation.Infinite
            from: -bar.width
            to: line.width
            duration: line.duration
            easing.type: Easing.InOutQuad
        }
    }
}
