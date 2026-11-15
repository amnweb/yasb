pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: microphone

    required property BarBase bar
    readonly property Theme theme: bar.theme
    // Percentage points per wheel step
    property int scrollStep: 2
    property bool invertWheel: false
    property int popupWidth: 324
    // The microphone on the bar, drawn in iconFont and the text colour
    property int iconSize: theme.bar.iconFont.pixelSize
    property string icon: "\ue720"
    // Also shown when there is no microphone
    property string mutedIcon: "\uf781"

    readonly property bool dark: theme.dark
    property color textColor: theme.colors.text
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
    property font popupTitleFont
    popupTitleFont.family: theme.popup.font.family
    popupTitleFont.pixelSize: 16
    popupTitleFont.weight: Font.DemiBold
    // Each device's glyph, the mark on the device in use, and the arrow of the settings link
    property int deviceIconSize: 14
    property int checkIconSize: 12
    property int footerIconSize: 10
    property int popupOpenDuration: theme.popup.openDuration
    property int popupCloseDuration: theme.popup.closeDuration
    property color popupTextColor: theme.colors.text
    property color popupSecondaryBackgroundColor: theme.colors.backgroundSecondary
    property color popupDividerColor: theme.colors.divider
    property color popupSecondaryTextColor: theme.colors.textSecondary
    property color popupHoverColor: theme.colors.hover
    property color popupSelectedColor: theme.colors.selected
    readonly property string edge: bar.edge
    property color accentColor: theme.colors.accent
    readonly property string currentIcon: audio.available && !audio.muted ? icon : mutedIcon

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + popupGap
            : edge === "right" ? start.x - popup.width - popupGap : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + popupGap
            : edge === "bottom" ? start.y - popup.height - popupGap : start.y + (height - popup.height) / 2
        const screen = microphone.Screen
        px = Math.max(screen.virtualX + 8, Math.min(px, screen.virtualX + screen.width - popup.width - 8))
        py = Math.max(screen.virtualY + 8, Math.min(py, screen.virtualY + screen.desktopAvailableHeight - popup.height - 8))
        popup.x = Math.round(px)
        popup.y = Math.round(py)
    }

    function togglePopup() {
        if (popup.visible)
            popup.close()
        else {
            popup.devicesOpen = false
            placePopup()
            popup.open()
        }
    }

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: !audio.available ? "No microphone" : audio.muted ? "Microphone, muted" : `Microphone ${audio.volume}%`
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    Component.onDestruction: popup.hide()

    AudioInput { id: audio }

    Connections {
        target: microphone.Window.window
        function onVisibleChanged() {
            if (!microphone.Window.window?.visible)
                popup.hide()
        }
        function onXChanged() { if (popup.visible) microphone.placePopup() }
        function onYChanged() { if (popup.visible) microphone.placePopup() }
    }

    Row {
        id: label
        height: parent.height
        Text {
            objectName: "icon"
            anchors.verticalCenter: parent.verticalCenter
            text: microphone.currentIcon
            color: microphone.textColor
            font.family: microphone.iconFont.family
            font.weight: microphone.iconFont.weight
            font.variableAxes: microphone.iconFont.variableAxes
            font.pixelSize: microphone.iconSize
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                microphone.togglePopup()
            else
                audio.toggleMute()
        }
        onWheel: wheel => {
            const delta = wheel.angleDelta.y || wheel.angleDelta.x
            if (delta !== 0 && audio.available)
                audio.setVolume(audio.volume + ((delta > 0) !== microphone.invertWheel ? microphone.scrollStep : -microphone.scrollStep))
        }
    }

    component IconButton: Item {
        id: button

        property string glyph
        property int iconSize: 14
        property bool checked: false
        property string tip

        signal clicked

        implicitWidth: iconSize + 12
        implicitHeight: iconSize + 12
        opacity: enabled ? 1 : 0.4
        Accessible.role: Accessible.Button
        Accessible.onPressAction: button.clicked()
        ToolTip.visible: area.containsMouse && tip !== ""
        ToolTip.delay: 500
        ToolTip.text: tip

        Rectangle {
            anchors.fill: parent
            radius: 4
            color: area.containsMouse ? microphone.popupHoverColor : button.checked ? microphone.popupSelectedColor : "transparent"
        }

        Text {
            anchors.centerIn: parent
            text: button.glyph
            color: microphone.popupTextColor
            opacity: button.checked || area.containsMouse ? 1 : 0.6
            font.family: microphone.iconFont.family
            font.weight: microphone.iconFont.weight
            font.variableAxes: microphone.iconFont.variableAxes
            font.pixelSize: button.iconSize
        }

        MouseArea {
            id: area
            anchors.fill: parent
            hoverEnabled: true
            onClicked: button.clicked()
        }
    }

    BackdropPopup {
        id: popup
        property real reveal: 0
        property bool devicesOpen: false
        objectName: "popup"
        title: "Microphone"
        width: microphone.popupWidth
        height: popupContent.implicitHeight
        anchor: microphone
        font: microphone.popupFont
        theme: microphone.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: microphone.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: microphone.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            radius: microphone.popupRadius
            color: microphone.popupColor
            // Active and inactive only, so disabled controls keep the style's dimmed colours
            palette.active.accent: microphone.accentColor
            palette.inactive.accent: microphone.accentColor
            border.width: 1
            border.color: microphone.popupBorderColor
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: microphone.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: popupContent
                width: parent.width
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 10
                    Layout.topMargin: 12
                    Layout.bottomMargin: 10
                    spacing: 2

                    Text {
                        objectName: "deviceName"
                        Layout.fillWidth: true
                        text: audio.deviceName || "No microphone"
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: microphone.popupTextColor
                        font: microphone.popupTitleFont
                    }
                    IconButton {
                        visible: audio.devices.length > 1
                        glyph: popup.devicesOpen ? "\ue70e" : "\ue70d"
                        iconSize: 12
                        checked: popup.devicesOpen
                        tip: "Microphones"
                        onClicked: popup.devicesOpen = !popup.devicesOpen
                        Accessible.name: popup.devicesOpen ? "Hide microphones" : "Choose microphone"
                    }
                }
                // The header's bottom line
                Rectangle {
                    Layout.fillWidth: true
                    Layout.bottomMargin: 8
                    implicitHeight: 1
                    color: microphone.popupDividerColor
                }

                Column {
                    Layout.fillWidth: true
                    Layout.leftMargin: 8
                    Layout.rightMargin: 8
                    Layout.bottomMargin: 4
                    visible: popup.devicesOpen && audio.devices.length > 1
                    spacing: 2

                    Repeater {
                        model: audio.devices
                        delegate: Rectangle {
                            id: device

                            required property var modelData

                            width: parent.width
                            height: 34
                            radius: 4
                            color: modelData.current ? microphone.popupSelectedColor : deviceArea.containsMouse ? microphone.popupHoverColor : "transparent"
                            Accessible.role: Accessible.RadioButton
                            Accessible.name: modelData.name
                            Accessible.checked: modelData.current
                            Accessible.onPressAction: {
                                audio.setDevice(modelData.id)
                                popup.devicesOpen = false
                            }

                            Text {
                                x: 10
                                anchors.verticalCenter: parent.verticalCenter
                                text: microphone.icon
                                color: microphone.popupTextColor
                                opacity: device.modelData.current ? 1 : 0.75
                                font.family: microphone.iconFont.family
                                font.weight: microphone.iconFont.weight
                                font.variableAxes: microphone.iconFont.variableAxes
                                font.pixelSize: microphone.deviceIconSize
                            }

                            Text {
                                x: 36
                                width: parent.width - 72
                                anchors.verticalCenter: parent.verticalCenter
                                text: device.modelData.name
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                color: device.modelData.current ? microphone.popupTextColor : microphone.popupSecondaryTextColor
                                font: microphone.popupFont
                            }

                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                visible: device.modelData.current
                                text: "\ue73e"
                                color: microphone.accentColor
                                font.family: microphone.iconFont.family
                                font.weight: microphone.iconFont.weight
                                font.variableAxes: microphone.iconFont.variableAxes
                                font.pixelSize: microphone.checkIconSize
                            }

                            MouseArea {
                                id: deviceArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    audio.setDevice(device.modelData.id)
                                    popup.devicesOpen = false
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 10
                    Layout.rightMargin: 10
                    Layout.topMargin: 4
                    Layout.bottomMargin: 12
                    spacing: 4

                    IconButton {
                        glyph: microphone.currentIcon
                        iconSize: 16
                        enabled: audio.available
                        tip: audio.muted ? "Unmute" : "Mute"
                        onClicked: audio.toggleMute()
                        Accessible.name: audio.muted ? "Unmute" : "Mute"
                    }
                    Slider {
                        objectName: "level"
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        value: audio.volume
                        enabled: audio.available
                        onMoved: audio.setVolume(Math.round(value))
                        Accessible.name: "Microphone level"
                    }
                    Text {
                        Layout.preferredWidth: 28
                        horizontalAlignment: Text.AlignRight
                        text: audio.volume
                        color: microphone.popupTextColor
                        font: microphone.popupFont
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 1
                    Layout.rightMargin: 1
                    Layout.bottomMargin: 1
                    implicitHeight: 40
                    bottomLeftRadius: microphone.popupRadius - 1
                    bottomRightRadius: microphone.popupRadius - 1
                    color: footerArea.containsMouse ? Qt.tint(microphone.popupSecondaryBackgroundColor, microphone.popupHoverColor) : microphone.popupSecondaryBackgroundColor
                    Accessible.role: Accessible.Link
                    Accessible.name: "Sound settings"
                    Accessible.onPressAction: {
                        Qt.openUrlExternally("ms-settings:sound")
                        popup.close()
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: microphone.popupDividerColor
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Sound settings"
                        color: footerArea.containsMouse ? microphone.popupTextColor : microphone.popupSecondaryTextColor
                        font: microphone.popupSmallFont
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        text: "\ue76c"
                        color: microphone.popupTextColor
                        opacity: footerArea.containsMouse ? 1 : 0.75
                        font.family: microphone.iconFont.family
                        font.weight: microphone.iconFont.weight
                        font.variableAxes: microphone.iconFont.variableAxes
                        font.pixelSize: microphone.footerIconSize
                    }

                    MouseArea {
                        id: footerArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            Qt.openUrlExternally("ms-settings:sound")
                            popup.close()
                        }
                    }
                }
            }
        }
    }
}
