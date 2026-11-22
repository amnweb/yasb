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

    component PopupIcons: QtObject {
        property string check
        property string open
        property string expand
        property string collapse
        property string device
    }

    component Settings: QtObject {
        required property Theme theme

        // Label placeholders: {level}, the microphone level as 30%, or mutedText while muted and noDeviceText without a
        // microphone; {device}, the microphone's name. Empty shows only the icon
        property string label: ""
        property string mutedText: "mute"
        property string noDeviceText: "No Device"
        // Percentage points per wheel step
        property int scrollStep: 2
        property bool invertWheel: false
        property int popupWidth: 324
        // The microphone on the bar, drawn in iconFont and the text colour
        property int iconSize: theme.bar.iconFont.pixelSize
        property string icon: "\ue720"
        // Also shown when there is no microphone
        property string mutedIcon: "\uf781"
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
        property font popupTitleFont
        popupTitleFont.family: theme.popup.font.family
        popupTitleFont.pixelSize: 16
        popupTitleFont.weight: 600
        // Popup icons; device is the microphone on each input device
        readonly property PopupIcons popupIcons: PopupIcons {
            check: "\ue73e"
            open: "\ue76c"
            expand: "\ue70d"
            collapse: "\ue70e"
            device: "\ue720"
        }
        property font popupIconFont
        popupIconFont.family: theme.popup.iconFont.family
        popupIconFont.weight: theme.popup.iconFont.weight
        popupIconFont.variableAxes: theme.popup.iconFont.variableAxes
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
        property color accentColor: theme.colors.accent
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: microphone.theme
    }

    readonly property bool dark: theme.dark
    readonly property string edge: bar.edge

    readonly property string currentIcon: audio.available && !audio.muted ? settings.icon : settings.mutedIcon
    readonly property string text: format(settings.label)

    function format(template: string): string {
        const level = !audio.available ? settings.noDeviceText : audio.muted ? settings.mutedText : `${audio.volume}%`
        return template.replace(/\{level\}/g, () => level).replace(/\{device\}/g, () => audio.deviceName)
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + settings.popupGap
            : edge === "right" ? start.x - popup.width - settings.popupGap : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + settings.popupGap
            : edge === "bottom" ? start.y - popup.height - settings.popupGap : start.y + (height - popup.height) / 2
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

    implicitWidth: row.implicitWidth
    implicitHeight: row.implicitHeight
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

    // Keep the popup anchored when its height changes
    Connections {
        target: popup
        function onHeightChanged() { if (popup.visible) microphone.placePopup() }
    }

    Row {
        id: row
        height: parent.height
        spacing: 6
        Text {
            objectName: "icon"
            anchors.verticalCenter: parent.verticalCenter
            text: microphone.currentIcon
            color: microphone.settings.textColor
            font.family: microphone.settings.iconFont.family
            font.weight: microphone.settings.iconFont.weight
            font.variableAxes: microphone.settings.iconFont.variableAxes
            font.pixelSize: microphone.settings.iconSize
        }

        Label {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: microphone.text
            textFormat: Text.PlainText
            color: microphone.settings.textColor
            font: microphone.settings.font
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
                audio.setVolume(audio.volume + ((delta > 0) !== microphone.settings.invertWheel ? microphone.settings.scrollStep : -microphone.settings.scrollStep))
        }
    }

    component IconButton: Item {
        id: button

        property string glyph
        property int iconSize: 14
        property font iconFont: microphone.settings.popupIconFont
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
            color: area.containsMouse ? microphone.settings.popupHoverColor : button.checked ? microphone.settings.popupSelectedColor : "transparent"
        }

        Text {
            anchors.centerIn: parent
            text: button.glyph
            color: microphone.settings.popupTextColor
            opacity: button.checked || area.containsMouse ? 1 : 0.6
            font.family: button.iconFont.family
            font.weight: button.iconFont.weight
            font.variableAxes: button.iconFont.variableAxes
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
        width: microphone.settings.popupWidth
        height: popupContent.implicitHeight
        anchor: microphone
        font: microphone.settings.popupFont
        theme: microphone.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: microphone.settings.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: microphone.settings.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            radius: microphone.settings.popupRadius
            color: microphone.settings.popupColor
            // Active and inactive only, so disabled controls keep the style's dimmed colours
            palette.active.accent: microphone.settings.accentColor
            palette.inactive.accent: microphone.settings.accentColor
            border.width: 1
            border.color: microphone.settings.popupBorderColor
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
                        color: microphone.settings.popupTextColor
                        font: microphone.settings.popupTitleFont
                    }
                    IconButton {
                        visible: audio.devices.length > 1
                        glyph: popup.devicesOpen ? microphone.settings.popupIcons.collapse : microphone.settings.popupIcons.expand
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
                    color: microphone.settings.popupDividerColor
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
                            color: modelData.current ? microphone.settings.popupSelectedColor : deviceArea.containsMouse ? microphone.settings.popupHoverColor : "transparent"
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
                                text: microphone.settings.popupIcons.device
                                color: microphone.settings.popupTextColor
                                opacity: device.modelData.current ? 1 : 0.75
                                font.family: microphone.settings.popupIconFont.family
                                font.weight: microphone.settings.popupIconFont.weight
                                font.variableAxes: microphone.settings.popupIconFont.variableAxes
                                font.pixelSize: microphone.settings.deviceIconSize
                            }

                            Text {
                                x: 36
                                width: parent.width - 72
                                anchors.verticalCenter: parent.verticalCenter
                                text: device.modelData.name
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                color: device.modelData.current ? microphone.settings.popupTextColor : microphone.settings.popupSecondaryTextColor
                                font: microphone.settings.popupFont
                            }

                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                visible: device.modelData.current
                                text: microphone.settings.popupIcons.check
                                color: microphone.settings.accentColor
                                font.family: microphone.settings.popupIconFont.family
                                font.weight: microphone.settings.popupIconFont.weight
                                font.variableAxes: microphone.settings.popupIconFont.variableAxes
                                font.pixelSize: microphone.settings.checkIconSize
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
                        // The bar's microphone icon, so the bar's icon font
                        iconFont: microphone.settings.iconFont
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
                        color: microphone.settings.popupTextColor
                        font: microphone.settings.popupFont
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 1
                    Layout.rightMargin: 1
                    Layout.bottomMargin: 1
                    implicitHeight: 40
                    bottomLeftRadius: microphone.settings.popupRadius - 1
                    bottomRightRadius: microphone.settings.popupRadius - 1
                    color: footerArea.containsMouse ? Qt.tint(microphone.settings.popupSecondaryBackgroundColor, microphone.settings.popupHoverColor) : microphone.settings.popupSecondaryBackgroundColor
                    Accessible.role: Accessible.Link
                    Accessible.name: "Sound settings"
                    Accessible.onPressAction: {
                        Qt.openUrlExternally("ms-settings:sound")
                        popup.close()
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: microphone.settings.popupDividerColor
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Sound settings"
                        color: footerArea.containsMouse ? microphone.settings.popupTextColor : microphone.settings.popupSecondaryTextColor
                        font: microphone.settings.popupSmallFont
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        text: microphone.settings.popupIcons.open
                        color: microphone.settings.popupTextColor
                        opacity: footerArea.containsMouse ? 1 : 0.75
                        font.family: microphone.settings.popupIconFont.family
                        font.weight: microphone.settings.popupIconFont.weight
                        font.variableAxes: microphone.settings.popupIconFont.variableAxes
                        font.pixelSize: microphone.settings.footerIconSize
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
