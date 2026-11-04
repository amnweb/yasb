pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: root

    property Item bar: null
    // Label placeholder: {percent}; empty shows only the icon. A right click shows the alternate label
    property string label: ""
    property string alternateLabel: "{percent}%"
    // Percentage points per wheel step
    property int scrollStep: 1
    property bool invertWheel: false
    // Seconds between reads of external monitors, 0 for none
    property int pollInterval: 60
    // The brightness when the pointer rests on the widget
    property bool tooltip: true
    property int popupWidth: 340
    property int iconSize: 16
    // One icon for every level, or several from dimmest to brightest that split 0 to 100% evenly:
    // ["\uec8a", "\ue706"] shows the first up to 50% and the second above, four icons change at 25, 50 and 75%
    property list<string> icons: ["\ue706"]
    // Sets nightLevel between nightStart and nightEnd, as hh:mm, and dayLevel otherwise
    property bool autoLight: false
    property int dayLevel: 100
    property int nightLevel: 50
    property string nightStart: "20:00"
    property string nightEnd: "06:30"

    property bool showAlternate: false

    readonly property bool dark: bar ? bar.dark : Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    // Text on the bar takes the bar's colour and font, each part unless the widget file sets it
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    property font font
    font.family: bar?.font.family ?? Qt.application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})
    // Glyphs take the family and weight of the bar's icon font unless the widget file sets them
    property font iconFont
    iconFont.family: bar?.iconFont?.family ?? "Segoe Fluent Icons"
    iconFont.weight: bar?.iconFont?.weight ?? Font.Normal
    readonly property color foreground: dark ? "#ebebeb" : "#1f1f1f"
    readonly property string edge: bar?.edge ?? "top"

    // The display under the bar, -1 until it is read; the widget hides where it can't be controlled
    readonly property int percent: control.brightness
    readonly property string text: format(showAlternate ? alternateLabel : label)
    // day or night, whichever auto light set last
    property string lightMode: ""

    function format(template: string): string {
        return template.replace(/\{percent\}/g, String(percent))
    }

    function icon(value: int): string {
        return icons.length > 0 ? icons[Math.min(icons.length - 1, Math.floor(value * icons.length / 101))] : ""
    }

    function applyAutoLight() {
        const mode = control.isNight(nightStart, nightEnd) ? "night" : "day"
        if (mode !== lightMode) {
            lightMode = mode
            control.setBrightness(mode === "night" ? nightLevel : dayLevel)
        }
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + 6
            : edge === "right" ? start.x - popup.width - 6 : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + 6
            : edge === "bottom" ? start.y - popup.height - 6 : start.y + (height - popup.height) / 2
        const screen = root.Screen
        px = Math.max(screen.virtualX + 8, Math.min(px, screen.virtualX + screen.width - popup.width - 8))
        py = Math.max(screen.virtualY + 8, Math.min(py, screen.virtualY + screen.desktopAvailableHeight - popup.height - 8))
        popup.x = Math.round(px)
        popup.y = Math.round(py)
    }

    function togglePopup() {
        if (popup.visible)
            popup.close()
        else {
            control.refresh()
            placePopup()
            popup.open()
        }
    }

    implicitWidth: control.available ? row.implicitWidth : 0
    implicitHeight: control.available ? row.implicitHeight : 0
    visible: control.available
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: qsTr("Brightness %1%").arg(percent)
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    Component.onDestruction: popup.hide()

    DisplayBrightness {
        id: control

        window: root.Window.window
        pollInterval: root.pollInterval
    }

    Timer {
        interval: 60000
        repeat: true
        triggeredOnStart: true
        running: root.autoLight && control.available
        onTriggered: root.applyAutoLight()
    }

    Connections {
        target: root.Window.window
        function onVisibleChanged() {
            if (!root.Window.window?.visible)
                popup.hide()
        }
        function onXChanged() { if (popup.visible) root.placePopup() }
        function onYChanged() { if (popup.visible) root.placePopup() }
    }

    Connections {
        target: popup
        function onHeightChanged() { if (popup.visible) root.placePopup() }
    }

    Row {
        id: row
        height: parent.height
        spacing: 6

        Text {
            objectName: "icon"
            anchors.verticalCenter: parent.verticalCenter
            text: root.icon(root.percent)
            color: root.textColor
            font.family: root.iconFont.family
            font.weight: root.iconFont.weight
            font.pixelSize: root.iconSize
        }

        Text {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: root.text
            textFormat: Text.PlainText
            color: root.textColor
            font: root.font
        }
    }

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                root.togglePopup()
            else
                root.showAlternate = !root.showAlternate
        }
        onWheel: wheel => {
            const delta = wheel.angleDelta.y || wheel.angleDelta.x
            if (delta !== 0)
                control.setBrightness(root.percent + ((delta > 0) !== root.invertWheel ? root.scrollStep : -root.scrollStep))
        }
    }

    ToolTip {
        popupType: Popup.Window
        visible: root.tooltip && area.containsMouse && !popup.visible
        delay: 400
        text: qsTr("Brightness %1%").arg(root.percent)
        // Away from the bar's edge
        y: root.edge === "bottom" ? -implicitHeight - 6 : root.height + 6
    }

    component LevelRow: RowLayout {
        id: level

        property string glyph
        property string name
        property int value: -1

        signal moved(int value)

        Layout.fillWidth: true
        spacing: 8

        Text {
            Layout.preferredWidth: 20
            horizontalAlignment: Text.AlignHCenter
            text: level.glyph
            color: root.foreground
            opacity: 0.75
            font.family: root.iconFont.family
            font.weight: root.iconFont.weight
            font.pixelSize: 14
        }
        Slider {
            Layout.fillWidth: true
            from: 0
            to: 100
            value: Math.max(0, level.value)
            enabled: level.value >= 0
            onMoved: level.moved(Math.round(value))
            Accessible.name: level.name
        }
        Text {
            Layout.preferredWidth: 28
            horizontalAlignment: Text.AlignRight
            text: level.value >= 0 ? level.value : ""
            color: root.foreground
            font.pixelSize: 13
        }
    }

    BackdropPopup {
        id: popup
        property real reveal: 0
        objectName: "popup"
        title: "Brightness"
        width: root.popupWidth
        height: content.implicitHeight + 16
        anchor: root
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            anchors.margins: 8
            radius: 8
            color: root.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: root.dark ? "#3A3A3A" : "#D9D9D9"
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: root.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: content
                width: parent.width
                spacing: 0

                Repeater {
                    objectName: "displays"
                    model: control.displays
                    delegate: ColumnLayout {
                        id: display

                        required property int index
                        required property int monitor
                        required property string name
                        required property string subtitle
                        required property int brightness
                        required property int contrast

                        Layout.fillWidth: true
                        Layout.leftMargin: 16
                        Layout.rightMargin: 12
                        Layout.topMargin: index === 0 ? 12 : 4
                        Layout.bottomMargin: 8
                        spacing: 2

                        Text {
                            Layout.fillWidth: true
                            text: display.name
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            color: root.foreground
                            font.pixelSize: 14
                            font.weight: Font.Bold
                        }
                        Text {
                            Layout.fillWidth: true
                            Layout.bottomMargin: 4
                            text: display.subtitle
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            color: Qt.alpha(root.foreground, 0.6)
                            font.pixelSize: 12
                        }
                        LevelRow {
                            glyph: "\ue706"
                            name: qsTr("Brightness of %1").arg(display.name)
                            value: display.brightness
                            onMoved: value => control.setDisplayBrightness(display.monitor, value)
                        }
                        LevelRow {
                            visible: display.contrast >= 0
                            glyph: "\ue793"
                            name: qsTr("Contrast of %1").arg(display.name)
                            value: display.contrast
                            onMoved: value => control.setDisplayContrast(display.monitor, value)
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    Layout.leftMargin: 1
                    Layout.rightMargin: 1
                    Layout.bottomMargin: 1
                    implicitHeight: 40
                    bottomLeftRadius: 7
                    bottomRightRadius: 7
                    color: Qt.alpha("#000000", (root.dark ? 0.15 : 0.03) + (footerArea.containsMouse ? 0.05 : 0))
                    Accessible.role: Accessible.Link
                    Accessible.name: "Display settings"
                    Accessible.onPressAction: {
                        Qt.openUrlExternally("ms-settings:display")
                        popup.close()
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Qt.alpha(root.foreground, 0.08)
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Display settings"
                        color: footerArea.containsMouse ? root.foreground : Qt.alpha(root.foreground, 0.75)
                        font.pixelSize: 12
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        text: "\ue76c"
                        color: root.foreground
                        opacity: footerArea.containsMouse ? 1 : 0.75
                        font.family: root.iconFont.family
                        font.weight: root.iconFont.weight
                        font.pixelSize: 10
                    }

                    MouseArea {
                        id: footerArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            Qt.openUrlExternally("ms-settings:display")
                            popup.close()
                        }
                    }
                }
            }
        }
    }
}
