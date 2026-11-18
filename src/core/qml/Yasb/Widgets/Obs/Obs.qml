pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: obs

    required property BarBase bar
    readonly property Theme theme: bar.theme
    // obs-websocket's server, in OBS under Tools > WebSocket Server Settings
    property string host: "localhost"
    property int port: 4455
    // Its password; it can come from an environment variable, such as Environment.value("OBS_PASSWORD")
    property string password: ""
    // Hides the widget while OBS is not running or its server is off
    property bool hideWhenDisconnected: true
    // Hides the widget while nothing is recorded or streamed
    property bool hideWhenIdle: false
    property bool blinkingIcon: true
    property bool showRecordTime: true
    property bool showStreamTime: true
    property bool showSceneName: false
    // Shows a glyph on the bar while the virtual camera or studio mode is on
    property bool showVirtualCam: false
    property bool showStudioMode: false
    property bool tooltip: true
    // Glyphs on the bar and in the popup; icon is OBS's record glyph, shown while idle
    property string icon: "\ue7c8"
    property string pausedIcon: "\ue769"
    property string streamIcon: "\ue93e"
    property string virtualCamIcon: "\ue714"
    property string studioModeIcon: "\ue7f4"
    // Hotkeys, such as "alt+shift+r"
    property string hotkey: ""
    property string recordHotkey: ""
    property string pauseHotkey: ""
    property string streamHotkey: ""
    property string virtualCamHotkey: ""
    property string studioModeHotkey: ""
    property int popupWidth: 284
    // Popup alignment relative to the widget on a horizontal bar: left, right or center
    property string popupAlignment: "center"
    property color liveColor: "#E81123"
    property color pausedColor: "#FFB900"

    readonly property bool dark: theme.dark
    // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
    property color textColor: theme.colors.text
    property font font
    // Glyphs take the theme's icon font, each part unless the widget file sets it
    property int iconSize: theme.bar.iconFont.pixelSize
    property font iconFont
    iconFont.family: theme.bar.iconFont.family
    iconFont.weight: theme.bar.iconFont.weight
    iconFont.variableAxes: theme.bar.iconFont.variableAxes
    // The text of a button that starts or stops something
    property color strongTextColor: "#ffffff"
    // The popup: the theme's, unless set here
    property color popupColor: theme.popup.background
    property color popupBorderColor: theme.popup.border
    property color popupTextColor: theme.colors.text
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
    property color popupSecondaryBackgroundColor: theme.colors.backgroundSecondary
    property color popupCardColor: theme.colors.card
    property color popupCardBorderColor: theme.colors.cardBorder
    property color popupDividerColor: theme.colors.divider
    property color popupTertiaryTextColor: theme.colors.textTertiary
    property color popupControlColor: theme.colors.control
    property color popupControlHoverColor: theme.colors.controlHover
    property color popupControlPressedColor: theme.colors.controlPressed
    property color popupControlBorderColor: theme.colors.controlBorder
    property font popupTitleFont
    popupTitleFont.family: theme.popup.font.family
    popupTitleFont.pixelSize: 16
    popupTitleFont.weight: Font.DemiBold
    // The glyphs beside the recording, streaming and other rows
    property int popupIconSize: 15
    readonly property string edge: bar.edge

    readonly property bool recording: studio.recording.active
    readonly property bool paused: studio.recording.paused
    readonly property bool streaming: studio.streaming.active

    // A duration in milliseconds as 12:48, or 1:04:10 from an hour
    function clock(ms: real): string {
        const seconds = Math.floor(ms / 1000)
        const hours = Math.floor(seconds / 3600)
        const pad = value => String(value).padStart(2, "0")
        const minutes = pad(Math.floor(seconds / 60) % 60)
        return hours > 0 ? `${hours}:${minutes}:${pad(seconds % 60)}` : `${minutes}:${pad(seconds % 60)}`
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        const gap = popupGap
        const margin = 8
        const screen = obs.Screen
        let px
        let py
        switch (edge) {
        case "left":
            px = start.x + width + gap
            py = start.y + (height - popup.height) / 2
            break
        case "right":
            px = start.x - popup.width - gap
            py = start.y + (height - popup.height) / 2
            break
        default:
            px = popupAlignment === "left" ? start.x
                : popupAlignment === "right" ? start.x + width - popup.width : start.x + (width - popup.width) / 2
            py = edge === "bottom" ? start.y - popup.height - gap : start.y + height + gap
            break
        }
        px = Math.max(screen.virtualX + margin, Math.min(px, screen.virtualX + screen.width - popup.width - margin))
        py = Math.max(screen.virtualY + margin, Math.min(py, screen.virtualY + screen.desktopAvailableHeight - popup.height - margin))
        popup.x = Math.round(px)
        popup.y = Math.round(py)
    }

    function togglePopup() {
        if (popup.visible) {
            popup.close()
            return
        }
        placePopup()
        popup.open()
    }

    // A hidden widget takes no room on the bar, as its slot keeps the size it asks for
    readonly property bool shown: !(hideWhenDisconnected && !studio.connected) && !(hideWhenIdle && !recording && !streaming)

    implicitWidth: shown ? row.implicitWidth : 0
    implicitHeight: shown ? row.implicitHeight : 0
    visible: shown
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: qsTr("OBS Studio")
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    Component.onDestruction: popup.hide()

    ObsStudio {
        id: studio

        host: obs.host
        port: obs.port
        password: obs.password
    }

    Hotkey {
        keys: obs.hotkey
        onActivated: obs.togglePopup()
    }

    Hotkey {
        keys: obs.recordHotkey
        onActivated: studio.toggleRecord()
    }

    Hotkey {
        keys: obs.pauseHotkey
        onActivated: studio.toggleRecordPause()
    }

    Hotkey {
        keys: obs.streamHotkey
        onActivated: studio.toggleStream()
    }

    Hotkey {
        keys: obs.virtualCamHotkey
        onActivated: studio.toggleVirtualCam()
    }

    Hotkey {
        keys: obs.studioModeHotkey
        onActivated: studio.toggleStudioMode()
    }

    Connections {
        target: obs.Window.window

        function onVisibleChanged() {
            if (!obs.Window.window?.visible)
                popup.hide()
        }

        function onXChanged() {
            if (popup.visible)
                obs.placePopup()
        }

        function onYChanged() {
            if (popup.visible)
                obs.placePopup()
        }
    }

    // Keep the popup anchored when its height changes
    Connections {
        target: popup

        function onHeightChanged() {
            if (popup.visible)
                obs.placePopup()
        }
    }

    component Glyph: Text {
        textFormat: Text.PlainText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.family: obs.iconFont.family
        font.weight: obs.iconFont.weight
        font.variableAxes: obs.iconFont.variableAxes
    }

    // The red dot of a recording; it blinks while it records, unless blinkingIcon is off
    component RecordDot: Rectangle {
        id: dot

        property bool blinking: false

        implicitWidth: 9
        implicitHeight: 9
        radius: 4.5
        color: obs.liveColor

        SequentialAnimation on opacity {
            running: dot.blinking
            loops: Animation.Infinite
            onRunningChanged: {
                if (!running)
                    dot.opacity = 1
            }
            NumberAnimation { to: 0.25; duration: 600; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1; duration: 600; easing.type: Easing.InOutSine }
        }
    }

    // Text in the popup, in its ink or muted colour
    component PopupText: Text {
        property bool muted: false

        Layout.minimumWidth: 0
        textFormat: Text.PlainText
        elide: Text.ElideRight
        color: muted ? obs.popupTertiaryTextColor : obs.popupTextColor
        font: obs.popupFont
    }

    component Card: Rectangle {
        Layout.fillWidth: true
        Layout.leftMargin: 12
        Layout.rightMargin: 12
        radius: 8
        color: obs.popupCardColor
        border.width: 1
        border.color: obs.popupCardBorderColor
    }

    // The line above a row in a card, after its first
    component RowSeparator: Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: obs.popupDividerColor
    }

    // A small framed button; a strong one is filled in the live colour
    component SmallButton: Rectangle {
        id: button

        property string text
        property bool strong: false
        signal clicked

        implicitWidth: buttonText.implicitWidth + 20
        implicitHeight: 26
        radius: 4
        color: strong ? Qt.darker(obs.liveColor, buttonArea.pressed ? 1.2 : buttonArea.containsMouse ? 1.1 : 1)
            : buttonArea.pressed ? obs.popupControlPressedColor : buttonArea.containsMouse ? obs.popupControlHoverColor : obs.popupControlColor
        border.width: 1
        border.color: strong ? "transparent" : obs.popupControlBorderColor
        Accessible.role: Accessible.Button
        Accessible.name: text
        Accessible.onPressAction: button.clicked()

        Text {
            id: buttonText

            anchors.centerIn: parent
            text: button.text
            textFormat: Text.PlainText
            color: button.strong ? obs.strongTextColor : obs.popupTextColor
            font: obs.popupSmallFont
        }

        MouseArea {
            id: buttonArea

            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: button.clicked()
        }
    }

    Row {
        id: row

        height: parent.height
        spacing: 10

        // Nothing is recorded or streamed: OBS's own record glyph, faint while OBS is not connected
        Glyph {
            objectName: "idle"
            anchors.verticalCenter: parent.verticalCenter
            visible: !obs.recording && !obs.streaming
            text: obs.icon
            color: obs.textColor
            opacity: studio.connected ? 1 : 0.4
            font.pixelSize: obs.iconSize
        }

        Row {
            objectName: "recording"
            anchors.verticalCenter: parent.verticalCenter
            visible: obs.recording
            spacing: 6

            RecordDot {
                anchors.verticalCenter: parent.verticalCenter
                visible: !obs.paused
                blinking: obs.blinkingIcon && obs.recording && !obs.paused
            }

            Glyph {
                anchors.verticalCenter: parent.verticalCenter
                visible: obs.paused
                text: obs.pausedIcon
                color: obs.pausedColor
                font.pixelSize: sceneLabel.font.pixelSize
            }

            Label {
                anchors.verticalCenter: parent.verticalCenter
                visible: obs.showRecordTime
                text: obs.clock(studio.recording.duration)
                textFormat: Text.PlainText
                color: obs.textColor
                font: obs.font
                opacity: obs.paused ? 0.7 : 1
            }
        }

        Row {
            objectName: "streaming"
            anchors.verticalCenter: parent.verticalCenter
            visible: obs.streaming
            spacing: 6

            Glyph {
                anchors.verticalCenter: parent.verticalCenter
                text: obs.streamIcon
                color: obs.liveColor
                font.pixelSize: obs.iconSize
            }

            Label {
                anchors.verticalCenter: parent.verticalCenter
                visible: obs.showStreamTime
                text: obs.clock(studio.streaming.duration)
                textFormat: Text.PlainText
                color: obs.textColor
                font: obs.font
            }
        }

        Glyph {
            anchors.verticalCenter: parent.verticalCenter
            visible: obs.showVirtualCam && studio.virtualCam
            text: obs.virtualCamIcon
            color: obs.textColor
            font.pixelSize: obs.iconSize
        }

        Glyph {
            anchors.verticalCenter: parent.verticalCenter
            visible: obs.showStudioMode && studio.studioMode
            text: obs.studioModeIcon
            color: obs.textColor
            font.pixelSize: obs.iconSize
        }

        Label {
            id: sceneLabel

            objectName: "scene"
            anchors.verticalCenter: parent.verticalCenter
            visible: obs.showSceneName && studio.scene !== ""
            text: studio.scene
            textFormat: Text.PlainText
            color: obs.textColor
            font: obs.font
            opacity: 0.7
        }
    }

    MouseArea {
        id: area

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: obs.togglePopup()
    }

    ToolTip {
        popupType: Popup.Window
        visible: obs.tooltip && area.containsMouse && !popup.visible
        delay: 400
        text: !studio.connected ? qsTr("OBS is not connected")
            : [obs.recording ? (obs.paused ? qsTr("Recording paused") : qsTr("Recording")) : qsTr("Not recording"),
                obs.streaming ? qsTr("Streaming") : "",
                studio.scene !== "" ? qsTr("Scene: %1").arg(studio.scene) : ""].filter(line => line).join("\n")
        // Away from the bar's edge
        y: obs.edge === "bottom" ? -implicitHeight - 6 : obs.height + 6
    }

    BackdropPopup {
        id: popup

        property real reveal: 0

        objectName: "popup"
        title: qsTr("OBS Studio")
        width: obs.popupWidth
        height: popupContent.implicitHeight
        anchor: obs
        font: obs.popupFont
        theme: obs.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: obs.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: obs.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible)
                reveal = 0
        }

        Rectangle {
            id: surface

            anchors.fill: parent
            radius: obs.popupRadius
            color: obs.popupColor
            border.width: 1
            border.color: obs.popupBorderColor
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: obs.edge === "bottom" ? Item.Bottom : Item.Top
            clip: true

            ColumnLayout {
                id: popupContent

                anchors.left: parent.left
                anchors.right: parent.right
                spacing: 0

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 12
                    Layout.bottomMargin: 10
                    spacing: 2

                    PopupText {
                        Layout.fillWidth: true
                        text: qsTr("OBS Studio")
                        font: obs.popupTitleFont
                    }

                    PopupText {
                        Layout.fillWidth: true
                        visible: text !== ""
                        text: studio.connected ? (studio.scene !== "" ? qsTr("Scene: %1").arg(studio.scene) : "")
                            : qsTr("Not connected")
                        muted: true
                        font: obs.popupSmallFont
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 1
                    color: obs.popupDividerColor
                }

                // OBS is not running, its server is off, or the password is wrong
                PopupText {
                    objectName: "disconnected"
                    Layout.fillWidth: true
                    Layout.margins: 16
                    visible: !studio.connected
                    text: studio.error !== "" ? studio.error
                        : qsTr("Start OBS and turn on its WebSocket server under Tools > WebSocket Server Settings.")
                    wrapMode: Text.WordWrap
                    elide: Text.ElideNone
                    muted: studio.error === ""
                    color: studio.error !== "" ? obs.liveColor : obs.popupTertiaryTextColor
                    font: obs.popupSmallFont
                }

                // Recording and streaming
                Card {
                    Layout.topMargin: 12
                    visible: studio.connected
                    implicitHeight: outputs.implicitHeight

                    ColumnLayout {
                        id: outputs

                        width: parent.width
                        spacing: 0

                        RowLayout {
                            objectName: "recordRow"
                            Layout.fillWidth: true
                            Layout.margins: 12
                            spacing: 10

                            Item {
                                implicitWidth: 16
                                implicitHeight: 16

                                RecordDot {
                                    anchors.centerIn: parent
                                    visible: obs.recording && !obs.paused
                                    blinking: false
                                }

                                Glyph {
                                    anchors.centerIn: parent
                                    visible: !obs.recording || obs.paused
                                    text: obs.paused ? obs.pausedIcon : obs.icon
                                    color: obs.paused ? obs.pausedColor : obs.popupTertiaryTextColor
                                    font.pixelSize: obs.popupIconSize
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 0

                                PopupText {
                                    Layout.fillWidth: true
                                    text: !obs.recording ? qsTr("Not recording")
                                        : obs.paused ? qsTr("Recording paused") : qsTr("Recording")
                                }

                                PopupText {
                                    Layout.fillWidth: true
                                    visible: obs.recording
                                    text: obs.clock(studio.recording.duration)
                                    muted: true
                                    font: obs.popupSmallFont
                                }
                            }

                            SmallButton {
                                visible: obs.recording
                                text: obs.paused ? qsTr("Resume") : qsTr("Pause")
                                onClicked: studio.toggleRecordPause()
                            }

                            SmallButton {
                                text: obs.recording ? qsTr("Stop") : qsTr("Start")
                                strong: obs.recording
                                onClicked: studio.toggleRecord()
                            }
                        }

                        RowSeparator {}

                        RowLayout {
                            objectName: "streamRow"
                            Layout.fillWidth: true
                            Layout.margins: 12
                            spacing: 10

                            Glyph {
                                Layout.preferredWidth: 16
                                text: obs.streamIcon
                                color: obs.streaming ? obs.liveColor : obs.popupTertiaryTextColor
                                font.pixelSize: obs.popupIconSize
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 0

                                PopupText {
                                    Layout.fillWidth: true
                                    text: !obs.streaming ? qsTr("Not streaming")
                                        : studio.streaming.reconnecting ? qsTr("Reconnecting...") : qsTr("Streaming")
                                }

                                PopupText {
                                    Layout.fillWidth: true
                                    visible: obs.streaming
                                    text: [obs.clock(studio.streaming.duration),
                                        studio.streaming.skippedFrames === 1 ? qsTr("1 dropped frame")
                                            : studio.streaming.skippedFrames > 1
                                            ? qsTr("%1 dropped frames").arg(studio.streaming.skippedFrames) : ""]
                                        .filter(part => part).join(" · ")
                                    muted: true
                                    font: obs.popupSmallFont
                                }
                            }

                            SmallButton {
                                text: obs.streaming ? qsTr("Stop") : qsTr("Start")
                                strong: obs.streaming
                                onClicked: studio.toggleStream()
                            }
                        }
                    }
                }

                // The virtual camera and studio mode
                Card {
                    Layout.topMargin: 8
                    visible: studio.connected
                    implicitHeight: switches.implicitHeight

                    ColumnLayout {
                        id: switches

                        width: parent.width
                        spacing: 0

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.leftMargin: 12
                            Layout.rightMargin: 8
                            Layout.topMargin: 6
                            Layout.bottomMargin: 6
                            spacing: 10

                            Glyph {
                                Layout.preferredWidth: 16
                                text: obs.virtualCamIcon
                                color: obs.popupTertiaryTextColor
                                font.pixelSize: obs.popupIconSize
                            }

                            PopupText {
                                Layout.fillWidth: true
                                text: qsTr("Virtual camera")
                            }

                            Switch {
                                objectName: "virtualCam"
                                checked: studio.virtualCam
                                Accessible.name: qsTr("Virtual camera")
                                onToggled: {
                                    studio.toggleVirtualCam()
                                    checked = Qt.binding(() => studio.virtualCam)
                                }
                            }
                        }

                        RowSeparator {}

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.leftMargin: 12
                            Layout.rightMargin: 8
                            Layout.topMargin: 6
                            Layout.bottomMargin: 6
                            spacing: 10

                            Glyph {
                                Layout.preferredWidth: 16
                                text: obs.studioModeIcon
                                color: obs.popupTertiaryTextColor
                                font.pixelSize: obs.popupIconSize
                            }

                            PopupText {
                                Layout.fillWidth: true
                                text: qsTr("Studio mode")
                            }

                            Switch {
                                objectName: "studioMode"
                                checked: studio.studioMode
                                Accessible.name: qsTr("Studio mode")
                                onToggled: {
                                    studio.toggleStudioMode()
                                    checked = Qt.binding(() => studio.studioMode)
                                }
                            }
                        }
                    }
                }

                // A darker strip, as in the other popups
                Rectangle {
                    Layout.fillWidth: true
                    Layout.topMargin: 12
                    Layout.leftMargin: 1
                    Layout.rightMargin: 1
                    Layout.bottomMargin: 1
                    implicitHeight: 40
                    bottomLeftRadius: obs.popupRadius - 1
                    bottomRightRadius: obs.popupRadius - 1
                    color: obs.popupSecondaryBackgroundColor

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: obs.popupDividerColor
                    }

                    PopupText {
                        x: 16
                        anchors.verticalCenter: parent.verticalCenter
                        text: `${obs.host}:${obs.port}`
                        muted: true
                        font: obs.popupSmallFont
                    }

                    PopupText {
                        anchors.right: parent.right
                        anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        text: studio.connected ? qsTr("Connected") : qsTr("Not connected")
                        muted: true
                        font: obs.popupSmallFont
                    }
                }
            }
        }
    }
}
