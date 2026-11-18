pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: volume

    // Label placeholders: {level}, the volume as 30%, or mutedText while muted and noDeviceText without an output
    // device; {device}, the output device's name. Empty shows only the icon
    property string label: ""
    property string mutedText: "mute"
    property string noDeviceText: "No Device"
    required property BarBase bar
    readonly property Theme theme: bar.theme
    // Percentage points per wheel step
    property int scrollStep: 2
    property bool invertWheel: false
    // Windows' default sound when a slider is let go, to hear the new level
    property bool beepOnRelease: true
    property int popupWidth: 324
    // The speaker on the bar: the first of icons at 0%, the rest spread over 1 to 100% from quietest to loudest, the
    // last also drawn faint behind; mutedIcon while muted
    property list<string> icons: ["\ue992", "\ue993", "\ue994", "\ue995"]
    property string mutedIcon: "\ue74f"
    property int iconSize: theme.bar.iconFont.pixelSize
    // Volumes of the apps playing, under the master slider; appsExpanded opens them with the popup
    property bool showApps: true
    property bool appsExpanded: false

    readonly property bool dark: theme.dark
    // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
    property color textColor: theme.colors.text
    property font font
    // The faint full-volume waves behind the speaker's lit ones
    property color iconTrackColor: theme.colors.textDisabled
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
    property color popupTertiaryTextColor: theme.colors.textTertiary
    property color popupHoverColor: theme.colors.hover
    property color popupSelectedColor: theme.colors.selected
    property color popupCardColor: theme.colors.card
    property color popupCardBorderColor: theme.colors.cardBorder
    // Text and accent in the popup
    property color accentColor: theme.colors.accent
    readonly property string edge: bar.edge
    readonly property string text: format(label)

    function format(template: string): string {
        const level = !audio.available ? noDeviceText : audio.muted ? mutedText : `${audio.volume}%`
        return template.replace(/\{level\}/g, () => level).replace(/\{device\}/g, () => audio.deviceName)
    }

    function icon(level: int, muted: bool): string {
        if (muted)
            return mutedIcon
        if (level === 0 || icons.length < 2)
            return icons[0] ?? ""
        return icons[1 + Math.min(icons.length - 2, Math.floor(level * (icons.length - 1) / 100))]
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        const gap = popupGap
        let px = edge === "left" ? start.x + width + gap
            : edge === "right" ? start.x - popup.width - gap : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + gap
            : edge === "bottom" ? start.y - popup.height - gap : start.y + (height - popup.height) / 2
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

    implicitWidth: row.implicitWidth
    implicitHeight: row.implicitHeight
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

    // Keep the popup anchored when its height changes
    Connections {
        target: popup
        function onHeightChanged() { if (popup.visible) volume.placePopup() }
    }

    Row {
        id: row
        height: parent.height
        spacing: 6
        Item {
            anchors.verticalCenter: parent.verticalCenter
            implicitWidth: levelIcon.implicitWidth
            implicitHeight: levelIcon.implicitHeight

            Text {
                visible: !audio.muted
                text: volume.icons[volume.icons.length - 1] ?? ""
                color: volume.iconTrackColor
                font: levelIcon.font
            }

            Text {
                id: levelIcon
                objectName: "icon"
                text: volume.icon(audio.volume, audio.muted)
                color: volume.textColor
                font.family: volume.iconFont.family
                font.weight: volume.iconFont.weight
                font.variableAxes: volume.iconFont.variableAxes
                font.pixelSize: volume.iconSize
            }
        }

        Label {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: volume.text
            textFormat: Text.PlainText
            color: volume.textColor
            font: volume.font
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
            color: area.containsMouse ? volume.popupHoverColor : button.checked ? volume.popupSelectedColor : "transparent"
        }

        Text {
            anchors.centerIn: parent
            text: button.glyph
            color: volume.popupTextColor
            opacity: button.checked || area.containsMouse ? 1 : 0.6
            font.family: volume.iconFont.family
            font.weight: volume.iconFont.weight
            font.variableAxes: volume.iconFont.variableAxes
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
        property bool appsOpen: false
        title: "Volume"
        width: volume.popupWidth
        height: popupContent.implicitHeight
        anchor: volume
        font: volume.popupFont
        theme: volume.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: volume.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: volume.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            radius: volume.popupRadius
            color: volume.popupColor
            border.width: 1
            border.color: volume.popupBorderColor
            // The sliders draw with the palette's accent
            // Active and inactive only, so disabled controls keep the style's dimmed colours
            palette.active.accent: volume.accentColor
            palette.inactive.accent: volume.accentColor
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: volume.edge === "bottom" ? Item.Bottom : Item.Top

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
                        Layout.fillWidth: true
                        text: audio.deviceName || "No output device"
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: volume.popupTextColor
                        font: volume.popupTitleFont
                    }
                    IconButton {
                        visible: audio.devices.length > 1
                        glyph: popup.devicesOpen ? "\ue70e" : "\ue70d"
                        iconSize: 12
                        checked: popup.devicesOpen
                        tip: "Output devices"
                        onClicked: popup.devicesOpen = !popup.devicesOpen
                        Accessible.name: popup.devicesOpen ? "Hide output devices" : "Choose output device"
                    }
                }
                // The header's bottom line
                Rectangle {
                    Layout.fillWidth: true
                    Layout.bottomMargin: 8
                    implicitHeight: 1
                    color: volume.popupDividerColor
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
                            color: modelData.current ? volume.popupSelectedColor : deviceArea.containsMouse ? volume.popupHoverColor : "transparent"
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
                                text: "\ue7f5"
                                color: volume.popupTextColor
                                opacity: device.modelData.current ? 1 : 0.75
                                font.family: volume.iconFont.family
                                font.weight: volume.iconFont.weight
                                font.variableAxes: volume.iconFont.variableAxes
                                font.pixelSize: volume.deviceIconSize
                            }

                            Text {
                                x: 36
                                width: parent.width - 72
                                anchors.verticalCenter: parent.verticalCenter
                                text: device.modelData.name
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                color: device.modelData.current ? volume.popupTextColor : volume.popupSecondaryTextColor
                                font: volume.popupFont
                            }

                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                visible: device.modelData.current
                                text: "\ue73e"
                                color: volume.accentColor
                                font.family: volume.iconFont.family
                                font.weight: volume.iconFont.weight
                                font.variableAxes: volume.iconFont.variableAxes
                                font.pixelSize: volume.checkIconSize
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
                        glyph: volume.icon(audio.volume, audio.muted)
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
                        color: volume.popupTextColor
                        font: volume.popupFont
                    }
                    IconButton {
                        visible: volume.showApps && audio.apps.length > 0
                        glyph: popup.appsOpen ? "\ue70e" : "\ue70d"
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
                    color: volume.popupCardColor
                    border.width: 1
                    border.color: volume.popupCardBorderColor

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
                                    color: iconArea.containsMouse ? volume.popupHoverColor : "transparent"
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
                                            color: app.modelData.muted ? volume.popupTertiaryTextColor : volume.popupSecondaryTextColor
                                            font: volume.popupSmallFont
                                        }
                                        Text {
                                            text: app.modelData.muted ? "Muted" : Math.round(appSlider.value)
                                            color: volume.popupTertiaryTextColor
                                            font: volume.popupSmallFont
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
                    bottomLeftRadius: volume.popupRadius - 1
                    bottomRightRadius: volume.popupRadius - 1
                    color: footerArea.containsMouse ? Qt.tint(volume.popupSecondaryBackgroundColor, volume.popupHoverColor) : volume.popupSecondaryBackgroundColor
                    Accessible.role: Accessible.Link
                    Accessible.name: "Sound settings"
                    Accessible.onPressAction: {
                        Qt.openUrlExternally("ms-settings:sound")
                        popup.close()
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: volume.popupDividerColor
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 15
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Sound settings"
                        color: footerArea.containsMouse ? volume.popupTextColor : volume.popupSecondaryTextColor
                        font: volume.popupSmallFont
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        text: "\ue76c"
                        color: volume.popupTextColor
                        opacity: footerArea.containsMouse ? 1 : 0.75
                        font.family: volume.iconFont.family
                        font.weight: volume.iconFont.weight
                        font.variableAxes: volume.iconFont.variableAxes
                        font.pixelSize: volume.footerIconSize
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
