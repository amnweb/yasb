pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    // Not brightness: the id would hide DisplayBrightness's brightness property
    id: brightnessWidget

    required property BarBase bar
    readonly property Theme theme: bar.theme
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
    property int popupWidth: 324
    property int iconSize: theme.bar.iconFont.pixelSize
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

    readonly property bool dark: theme.dark
    // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
    property color textColor: theme.colors.text
    property font font
    // Glyphs take the theme's icon font, each part unless the widget file sets it
    property font iconFont
    iconFont.family: theme.bar.iconFont.family
    iconFont.weight: theme.bar.iconFont.weight
    iconFont.variableAxes: theme.bar.iconFont.variableAxes
    // The popup: the theme's, unless set here
    property color popupColor: theme.popup.background
    property color popupBorderColor: theme.popup.border
    property real popupRadius: theme.popup.radius
    property real popupGap: theme.popup.gap
    // Text in the popup: the theme's font family, in this widget's sizes
    property font popupFont
    popupFont.family: theme.popup.font.family
    popupFont.pixelSize: 13
    property font popupSmallFont
    popupSmallFont.family: theme.popup.font.family
    popupSmallFont.pixelSize: 12
    property int popupOpenDuration: theme.popup.openDuration
    property int popupCloseDuration: theme.popup.closeDuration
    property color popupTextColor: theme.colors.text
    property color popupSecondaryBackgroundColor: theme.colors.backgroundSecondary
    property color popupDividerColor: theme.colors.divider
    property color popupSecondaryTextColor: theme.colors.textSecondary
    property color popupHoverColor: theme.colors.hover
    property font popupTitleFont
    popupTitleFont.family: theme.popup.font.family
    popupTitleFont.pixelSize: 16
    popupTitleFont.weight: Font.DemiBold
    // The glyph beside each display's level, and the arrow of the settings link
    property int popupIconSize: 14
    property int footerIconSize: 10
    readonly property string edge: bar.edge

    // The display under the bar, -1 until it is read; the widget hides where it can't be controlled
    readonly property int percent: control.brightness
    readonly property string text: format(showAlternate ? alternateLabel : label)
    // day or night, whichever auto light set last
    property string lightMode: ""

    function format(template: string): string {
        return template.replace(/\{percent\}/g, String(percent))
    }

    function icon(value: int): string {
        if (value < 0 || icons.length === 0)
            return ""
        return icons[Math.min(icons.length - 1, Math.floor(value * icons.length / 101))]
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
        let px = edge === "left" ? start.x + width + popupGap
            : edge === "right" ? start.x - popup.width - popupGap : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + popupGap
            : edge === "bottom" ? start.y - popup.height - popupGap : start.y + (height - popup.height) / 2
        const screen = brightnessWidget.Screen
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

        window: brightnessWidget.Window.window
        pollInterval: brightnessWidget.pollInterval
    }

    Timer {
        interval: 60000
        repeat: true
        triggeredOnStart: true
        running: brightnessWidget.autoLight && control.available
        onTriggered: brightnessWidget.applyAutoLight()
    }

    Connections {
        target: brightnessWidget.Window.window
        function onVisibleChanged() {
            if (!brightnessWidget.Window.window?.visible)
                popup.hide()
        }
        function onXChanged() { if (popup.visible) brightnessWidget.placePopup() }
        function onYChanged() { if (popup.visible) brightnessWidget.placePopup() }
    }

    Connections {
        target: popup
        function onHeightChanged() { if (popup.visible) brightnessWidget.placePopup() }
    }

    Row {
        id: row
        height: parent.height
        spacing: 6

        Text {
            objectName: "icon"
            anchors.verticalCenter: parent.verticalCenter
            text: brightnessWidget.icon(brightnessWidget.percent)
            color: brightnessWidget.textColor
            font.family: brightnessWidget.iconFont.family
            font.weight: brightnessWidget.iconFont.weight
            font.variableAxes: brightnessWidget.iconFont.variableAxes
            font.pixelSize: brightnessWidget.iconSize
        }

        Label {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: brightnessWidget.text
            textFormat: Text.PlainText
            color: brightnessWidget.textColor
            font: brightnessWidget.font
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
                brightnessWidget.togglePopup()
            else
                brightnessWidget.showAlternate = !brightnessWidget.showAlternate
        }
        onWheel: wheel => {
            const delta = wheel.angleDelta.y || wheel.angleDelta.x
            if (delta !== 0)
                control.setBrightness(brightnessWidget.percent + ((delta > 0) !== brightnessWidget.invertWheel ? brightnessWidget.scrollStep : -brightnessWidget.scrollStep))
        }
    }

    ToolTip {
        popupType: Popup.Window
        visible: brightnessWidget.tooltip && area.containsMouse && !popup.visible
        delay: 400
        text: qsTr("Brightness %1%").arg(brightnessWidget.percent)
        // Away from the bar's edge
        y: brightnessWidget.edge === "bottom" ? -implicitHeight - 6 : brightnessWidget.height + 6
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
            color: brightnessWidget.popupTextColor
            opacity: 0.75
            font.family: brightnessWidget.iconFont.family
            font.weight: brightnessWidget.iconFont.weight
            font.variableAxes: brightnessWidget.iconFont.variableAxes
            font.pixelSize: brightnessWidget.popupIconSize
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
            color: brightnessWidget.popupTextColor
            font: brightnessWidget.popupFont
        }
    }

    BackdropPopup {
        id: popup
        property real reveal: 0
        objectName: "popup"
        title: "Brightness"
        width: brightnessWidget.popupWidth
        height: popupContent.implicitHeight
        anchor: brightnessWidget
        font: brightnessWidget.popupFont
        theme: brightnessWidget.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: brightnessWidget.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: brightnessWidget.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            radius: brightnessWidget.popupRadius
            color: brightnessWidget.popupColor
            border.width: 1
            border.color: brightnessWidget.popupBorderColor
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: brightnessWidget.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: popupContent
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
                        Layout.topMargin: index === 0 ? 12 : 20
                        Layout.bottomMargin: 8
                        spacing: 2

                        Text {
                            Layout.fillWidth: true
                            text: display.name
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            color: brightnessWidget.popupTextColor
                            font: brightnessWidget.popupTitleFont
                        }
                        Text {
                            Layout.fillWidth: true
                            Layout.bottomMargin: 4
                            text: display.subtitle
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            color: brightnessWidget.popupSecondaryTextColor
                            font: brightnessWidget.popupSmallFont
                        }
                        // The display's header line, across the whole popup
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.leftMargin: -16
                            Layout.rightMargin: -12
                            Layout.topMargin: 6
                            Layout.bottomMargin: 8
                            implicitHeight: 1
                            color: brightnessWidget.popupDividerColor
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
                    bottomLeftRadius: brightnessWidget.popupRadius - 1
                    bottomRightRadius: brightnessWidget.popupRadius - 1
                    color: footerArea.containsMouse ? Qt.tint(brightnessWidget.popupSecondaryBackgroundColor, brightnessWidget.popupHoverColor) : brightnessWidget.popupSecondaryBackgroundColor
                    Accessible.role: Accessible.Link
                    Accessible.name: "Display settings"
                    Accessible.onPressAction: {
                        Qt.openUrlExternally("ms-settings:display")
                        popup.close()
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: brightnessWidget.popupDividerColor
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Display settings"
                        color: footerArea.containsMouse ? brightnessWidget.popupTextColor : brightnessWidget.popupSecondaryTextColor
                        font: brightnessWidget.popupSmallFont
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        text: "\ue76c"
                        color: brightnessWidget.popupTextColor
                        opacity: footerArea.containsMouse ? 1 : 0.75
                        font.family: brightnessWidget.iconFont.family
                        font.weight: brightnessWidget.iconFont.weight
                        font.variableAxes: brightnessWidget.iconFont.variableAxes
                        font.pixelSize: brightnessWidget.footerIconSize
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
