import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: microphone

    property Item bar: null
    // Percentage points per wheel step
    property int scrollStep: 2
    property bool invertWheel: false
    property int popupWidth: 340
    // The microphone on the bar, drawn in iconFont and the text colour
    property int iconSize: 16
    property string icon: "\ue720"
    // Also shown when there is no microphone
    property string mutedIcon: "\uf781"

    readonly property bool dark: bar ? bar.dark : Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    // Glyphs take the family and weight of the bar's icon font unless the widget file sets them
    property font iconFont
    iconFont.family: bar?.iconFont?.family ?? "Segoe Fluent Icons"
    iconFont.weight: bar?.iconFont?.weight ?? Font.Normal
    readonly property color foreground: dark ? "#ebebeb" : "#1f1f1f"
    readonly property string edge: bar?.edge ?? "top"
    readonly property color accent: dark ? "#60cdff" : "#005fb8"
    readonly property string currentIcon: audio.available && !audio.muted ? icon : mutedIcon

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + 6
            : edge === "right" ? start.x - popup.width - 6 : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + 6
            : edge === "bottom" ? start.y - popup.height - 6 : start.y + (height - popup.height) / 2
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
            color: Qt.alpha(microphone.foreground, area.containsMouse ? 0.08 : button.checked ? 0.06 : 0)
        }

        Text {
            anchors.centerIn: parent
            text: button.glyph
            color: microphone.foreground
            opacity: button.checked || area.containsMouse ? 1 : 0.6
            font.family: microphone.iconFont.family
            font.weight: microphone.iconFont.weight
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
        height: content.implicitHeight + 16
        anchor: microphone
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            anchors.margins: 8
            radius: 8
            color: microphone.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: microphone.dark ? "#3A3A3A" : "#D9D9D9"
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: microphone.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: content
                width: parent.width
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 10
                    Layout.topMargin: 12
                    Layout.bottomMargin: 4
                    spacing: 2

                    Text {
                        objectName: "deviceName"
                        Layout.fillWidth: true
                        text: audio.deviceName || "No microphone"
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: microphone.foreground
                        font.pixelSize: 16
                        font.weight: Font.Bold
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
                            color: Qt.alpha(microphone.foreground, modelData.current ? 0.06 : deviceArea.containsMouse ? 0.04 : 0)
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
                                color: microphone.foreground
                                opacity: device.modelData.current ? 1 : 0.75
                                font.family: microphone.iconFont.family
                                font.weight: microphone.iconFont.weight
                                font.pixelSize: 14
                            }

                            Text {
                                x: 36
                                width: parent.width - 72
                                anchors.verticalCenter: parent.verticalCenter
                                text: device.modelData.name
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                color: Qt.alpha(microphone.foreground, device.modelData.current ? 1 : 0.85)
                                font.pixelSize: 13
                            }

                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                visible: device.modelData.current
                                text: "\ue73e"
                                color: microphone.accent
                                font.family: microphone.iconFont.family
                                font.weight: microphone.iconFont.weight
                                font.pixelSize: 12
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
                        color: microphone.foreground
                        font.pixelSize: 13
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 1
                    Layout.rightMargin: 1
                    Layout.bottomMargin: 1
                    implicitHeight: 40
                    bottomLeftRadius: 7
                    bottomRightRadius: 7
                    color: Qt.alpha("#000000", (microphone.dark ? 0.15 : 0.03) + (footerArea.containsMouse ? 0.05 : 0))
                    Accessible.role: Accessible.Link
                    Accessible.name: "Sound settings"
                    Accessible.onPressAction: {
                        Qt.openUrlExternally("ms-settings:sound")
                        popup.close()
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Qt.alpha(microphone.foreground, 0.08)
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Sound settings"
                        color: footerArea.containsMouse ? microphone.foreground : Qt.alpha(microphone.foreground, 0.75)
                        font.pixelSize: 12
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        text: "\ue76c"
                        color: microphone.foreground
                        opacity: footerArea.containsMouse ? 1 : 0.75
                        font.family: microphone.iconFont.family
                        font.weight: microphone.iconFont.weight
                        font.pixelSize: 10
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
