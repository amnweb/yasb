import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl
import QtQuick.Effects
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: volume

    property Item bar: null
    // Percentage points per wheel step
    property int scrollStep: 2
    property bool invertWheel: false
    // Windows' default sound when a slider is let go, to hear the new level
    property bool beepOnRelease: true
    property int popupWidth: 340
    // The speaker on the bar, an SVG from icons/ in the text colour
    property int iconSize: 16
    // Volumes of the apps playing, under the master slider; appsExpanded opens them with the popup
    property bool showApps: true
    property bool appsExpanded: false

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
    readonly property color foreground: dark ? "#ebebeb" : "#1f1f1f"
    readonly property string edge: bar?.edge ?? "top"
    readonly property color accent: dark ? "#60cdff" : "#005fb8"

    function icon(level: int, muted: bool): url {
        const name = muted ? "mute" : level === 0 ? "0" : level < 34 ? "1" : level < 67 ? "2" : "3"
        return Qt.resolvedUrl(`icons/speaker-${name}.svg`)
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + 6
            : edge === "right" ? start.x - popup.width - 6 : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + 6
            : edge === "bottom" ? start.y - popup.height - 6 : start.y + (height - popup.height) / 2
        const screen = volume.Screen
        px = Math.max(screen.virtualX + 8, Math.min(px, screen.virtualX + screen.width - popup.width - 8))
        py = Math.max(screen.virtualY + 8, Math.min(py, screen.virtualY + screen.desktopAvailableHeight - popup.height - 8))
        popup.x = Math.round(px)
        popup.y = Math.round(py)
    }

    function togglePopup() {
        if (popup.visible)
            popup.close()
        else {
            audio.refreshApps()
            popup.devicesOpen = false
            popup.appsOpen = appsExpanded
            placePopup()
            popup.open()
        }
    }

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: audio.muted ? "Volume, muted" : `Volume ${audio.volume}%`
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    Component.onDestruction: popup.hide()

    AudioOutput { id: audio }

    Connections {
        target: volume.Window.window
        function onVisibleChanged() {
            if (!volume.Window.window?.visible)
                popup.hide()
        }
        function onXChanged() { if (popup.visible) volume.placePopup() }
        function onYChanged() { if (popup.visible) volume.placePopup() }
    }

    component SvgIcon: IconImage {
        sourceSize: Qt.size(width, height)
    }

    Row {
        id: label
        height: parent.height
        spacing: 6
        SvgIcon {
            y: Math.round((parent.height - height) / 2)
            width: volume.iconSize
            height: volume.iconSize
            source: volume.icon(audio.volume, audio.muted)
            color: volume.textColor
        }
        // Text {
        //     anchors.verticalCenter: parent.verticalCenter
        //     text: audio.available ? `${audio.volume}%` : "--"
        //     color: volume.textColor
        //     font: volume.font
        // }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                volume.togglePopup()
            else
                audio.toggleMute()
        }
        onWheel: wheel => {
            const delta = wheel.angleDelta.y || wheel.angleDelta.x
            if (delta !== 0)
                audio.setVolume(audio.volume + ((delta > 0) !== volume.invertWheel ? volume.scrollStep : -volume.scrollStep))
        }
    }

    component IconButton: Item {
        id: button

        property url source
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
            color: Qt.alpha(volume.foreground, area.containsMouse ? 0.08 : button.checked ? 0.06 : 0)
        }

        SvgIcon {
            anchors.centerIn: parent
            width: button.iconSize
            height: button.iconSize
            source: button.source
            color: volume.foreground
            opacity: button.checked || area.containsMouse ? 1 : 0.6
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
        property bool appsOpen: false
        title: "Volume"
        width: volume.popupWidth
        height: content.implicitHeight + 16
        anchor: volume
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            anchors.margins: 8
            radius: 8
            color: volume.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: volume.dark ? Qt.alpha("#3A3A3A", 1) : Qt.alpha("#D9D9D9", 1)
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: volume.edge === "bottom" ? Item.Bottom : Item.Top

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
                        Layout.fillWidth: true
                        text: audio.deviceName || "No output device"
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: volume.foreground
                        font.family: "Segoe UI"
                        font.pixelSize: 16
                        font.weight: Font.Bold
                    }
                    IconButton {
                        visible: audio.devices.length > 1
                        source: Qt.resolvedUrl(popup.devicesOpen ? "icons/chevron-up.svg" : "icons/chevron-down.svg")
                        iconSize: 12
                        checked: popup.devicesOpen
                        tip: "Output devices"
                        onClicked: popup.devicesOpen = !popup.devicesOpen
                        Accessible.name: popup.devicesOpen ? "Hide output devices" : "Choose output device"
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
                            color: Qt.alpha(volume.foreground, modelData.current ? 0.06 : deviceArea.containsMouse ? 0.04 : 0)
                            Accessible.role: Accessible.RadioButton
                            Accessible.name: modelData.name
                            Accessible.checked: modelData.current
                            Accessible.onPressAction: {
                                audio.setDevice(modelData.id)
                                popup.devicesOpen = false
                            }

                            SvgIcon {
                                x: 10
                                anchors.verticalCenter: parent.verticalCenter
                                width: 14
                                height: 14
                                source: Qt.resolvedUrl("icons/device.svg")
                                color: volume.foreground
                                opacity: device.modelData.current ? 1 : 0.75
                            }

                            Text {
                                x: 36
                                width: parent.width - 72
                                anchors.verticalCenter: parent.verticalCenter
                                text: device.modelData.name
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                color: Qt.alpha(volume.foreground, device.modelData.current ? 1 : 0.85)
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                            }

                            SvgIcon {
                                anchors.right: parent.right
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                width: 12
                                height: 12
                                visible: device.modelData.current
                                source: Qt.resolvedUrl("icons/check.svg")
                                color: volume.accent
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
                        source: volume.icon(audio.volume, audio.muted)
                        iconSize: 16
                        enabled: audio.available
                        tip: audio.muted ? "Unmute" : "Mute"
                        onClicked: audio.toggleMute()
                        Accessible.name: audio.muted ? "Unmute" : "Mute"
                    }
                    Slider {
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        value: audio.volume
                        enabled: audio.available
                        onMoved: audio.setVolume(Math.round(value))
                        onPressedChanged: {
                            if (!pressed && volume.beepOnRelease)
                                audio.beep()
                        }
                        Accessible.name: "Volume"
                    }
                    Text {
                        Layout.preferredWidth: 28
                        horizontalAlignment: Text.AlignRight
                        text: audio.volume
                        color: volume.foreground
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                    }
                    IconButton {
                        visible: volume.showApps && audio.apps.length > 0
                        source: Qt.resolvedUrl(popup.appsOpen ? "icons/chevron-up.svg" : "icons/chevron-down.svg")
                        iconSize: 12
                        checked: popup.appsOpen
                        tip: "App volumes"
                        onClicked: popup.appsOpen = !popup.appsOpen
                        Accessible.name: popup.appsOpen ? "Hide app volumes" : "Show app volumes"
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 12
                    Layout.rightMargin: 12
                    Layout.bottomMargin: 12
                    visible: popup.appsOpen && volume.showApps && audio.apps.length > 0
                    implicitHeight: apps.implicitHeight + 12
                    radius: 8
                    color: Qt.alpha(volume.foreground, 0.03)
                    border.width: 1
                    border.color: Qt.alpha(volume.foreground, 0.04)

                    Column {
                        id: apps
                        x: 8
                        y: 6
                        width: parent.width - 22

                        Repeater {
                            model: audio.apps
                            delegate: RowLayout {
                                id: app

                                required property var modelData

                                width: apps.width
                                spacing: 8

                                Rectangle {
                                    Layout.preferredWidth: 36
                                    Layout.preferredHeight: 36
                                    radius: 6
                                    color: Qt.alpha(volume.foreground, iconArea.containsMouse ? 0.08 : 0)
                                    Accessible.role: Accessible.Button
                                    Accessible.name: app.modelData.muted ? `Unmute ${app.modelData.name}` : `Mute ${app.modelData.name}`
                                    Accessible.onPressAction: audio.setAppMuted(app.modelData.key, !app.modelData.muted)
                                    ToolTip.visible: iconArea.containsMouse
                                    ToolTip.delay: 500
                                    ToolTip.text: app.modelData.muted ? "Unmute" : "Mute"

                                    Image {
                                        anchors.centerIn: parent
                                        width: 20
                                        height: 20
                                        source: app.modelData.icon
                                        sourceSize: Qt.size(40, 40)
                                        opacity: app.modelData.muted ? 0.5 : 1
                                        layer.enabled: app.modelData.muted
                                        layer.effect: MultiEffect {
                                            saturation: -1
                                        }
                                    }

                                    MouseArea {
                                        id: iconArea
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: audio.setAppMuted(app.modelData.key, !app.modelData.muted)
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Layout.topMargin: 6

                                        Text {
                                            Layout.fillWidth: true
                                            text: app.modelData.name
                                            textFormat: Text.PlainText
                                            elide: Text.ElideRight
                                            color: Qt.alpha(volume.foreground, app.modelData.muted ? 0.5 : 0.85)
                                            font.family: "Segoe UI"
                                            font.pixelSize: 12
                                        }
                                        Text {
                                            text: app.modelData.muted ? "Muted" : Math.round(appSlider.value)
                                            color: Qt.alpha(volume.foreground, 0.5)
                                            font.family: "Segoe UI"
                                            font.pixelSize: 12
                                        }
                                    }
                                    Slider {
                                        id: appSlider
                                        Layout.fillWidth: true
                                        Layout.leftMargin: -(leftPadding + handle.width / 2)
                                        Layout.rightMargin: -(rightPadding + handle.width / 2)
                                        from: 0
                                        to: 100
                                        value: app.modelData.volume
                                        opacity: app.modelData.muted ? 0.5 : 1
                                        onMoved: audio.setAppVolume(app.modelData.key, Math.round(value))
                                        onPressedChanged: {
                                            if (!pressed && volume.beepOnRelease)
                                                audio.beep()
                                        }
                                        Accessible.name: `${app.modelData.name} volume`
                                    }
                                }
                            }
                        }
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
                    color: Qt.alpha("#000000", (volume.dark ? 0.15 : 0.03) + (footerArea.containsMouse ? 0.05 : 0))
                    Accessible.role: Accessible.Link
                    Accessible.name: "Sound settings"
                    Accessible.onPressAction: {
                        Qt.openUrlExternally("ms-settings:sound")
                        popup.close()
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Qt.alpha(volume.foreground, 0.08)
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Sound settings"
                        color: footerArea.containsMouse ? volume.foreground : Qt.alpha(volume.foreground, 0.75)
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                    }

                    SvgIcon {
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        width: 10
                        height: 10
                        source: Qt.resolvedUrl("icons/chevron-right.svg")
                        color: volume.foreground
                        opacity: footerArea.containsMouse ? 1 : 0.75
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
