pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: widget

    property Item bar: null
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
    // Hotkeys, such as "alt+shift+r"
    property string keys: ""
    property string recordKeys: ""
    property string pauseKeys: ""
    property string streamKeys: ""
    property string virtualCamKeys: ""
    property string studioModeKeys: ""
    property int popupWidth: 300
    // Popup alignment relative to the widget on a horizontal bar: left, right or center
    property string popupAlignment: "center"
    property color liveColor: "#E81123"
    property color pausedColor: "#FFB900"

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
    readonly property string edge: bar?.edge ?? "top"

    readonly property bool recording: obs.recording.active
    readonly property bool paused: obs.recording.paused
    readonly property bool streaming: obs.streaming.active

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
        const gap = 6
        const margin = 8
        const screen = widget.Screen
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
    readonly property bool shown: !(hideWhenDisconnected && !obs.connected) && !(hideWhenIdle && !recording && !streaming)

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
        id: obs

        host: widget.host
        port: widget.port
        password: widget.password
    }

    Hotkey {
        keys: widget.keys
        onActivated: widget.togglePopup()
    }

    Hotkey {
        keys: widget.recordKeys
        onActivated: obs.toggleRecord()
    }

    Hotkey {
        keys: widget.pauseKeys
        onActivated: obs.toggleRecordPause()
    }

    Hotkey {
        keys: widget.streamKeys
        onActivated: obs.toggleStream()
    }

    Hotkey {
        keys: widget.virtualCamKeys
        onActivated: obs.toggleVirtualCam()
    }

    Hotkey {
        keys: widget.studioModeKeys
        onActivated: obs.toggleStudioMode()
    }

    Connections {
        target: widget.Window.window

        function onVisibleChanged() {
            if (!widget.Window.window?.visible)
                popup.hide()
        }

        function onXChanged() {
            if (popup.visible)
                widget.placePopup()
        }

        function onYChanged() {
            if (popup.visible)
                widget.placePopup()
        }
    }

    // Keep the popup anchored when its height changes
    Connections {
        target: popup

        function onHeightChanged() {
            if (popup.visible)
                widget.placePopup()
        }
    }

    component Glyph: Text {
        textFormat: Text.PlainText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.family: widget.iconFont.family
        font.weight: widget.iconFont.weight
    }

    // The red dot of a recording; it blinks while it records, unless blinkingIcon is off
    component RecordDot: Rectangle {
        id: dot

        property bool blinking: false

        implicitWidth: 9
        implicitHeight: 9
        radius: 4.5
        color: widget.liveColor

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
    component Label: Text {
        property bool muted: false

        Layout.minimumWidth: 0
        textFormat: Text.PlainText
        elide: Text.ElideRight
        color: muted ? popup.muted : popup.ink
        font.pixelSize: 13
    }

    component Card: Rectangle {
        Layout.fillWidth: true
        Layout.leftMargin: 12
        Layout.rightMargin: 12
        radius: 8
        color: widget.dark ? Qt.alpha("#ffffff", 0.0512) : Qt.alpha("#ffffff", 0.7)
        border.width: 1
        border.color: Qt.alpha("#000000", widget.dark ? 0.1 : 0.0578)
    }

    // The line above a row in a card, after its first
    component RowSeparator: Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: Qt.alpha(popup.ink, 0.06)
    }

    // A small framed button, as WinUI's standard buttons are; a strong one is filled in the live colour
    component SmallButton: Rectangle {
        id: button

        property string text
        property bool strong: false
        signal clicked

        implicitWidth: buttonText.implicitWidth + 20
        implicitHeight: 26
        radius: 4
        color: strong ? Qt.darker(widget.liveColor, buttonArea.pressed ? 1.2 : buttonArea.containsMouse ? 1.1 : 1)
            : Qt.alpha(popup.ink, buttonArea.pressed ? 0.04 : buttonArea.containsMouse ? 0.09 : 0.06)
        border.width: 1
        border.color: strong ? "transparent" : Qt.alpha(popup.ink, 0.08)
        Accessible.role: Accessible.Button
        Accessible.name: text
        Accessible.onPressAction: button.clicked()

        Text {
            id: buttonText

            anchors.centerIn: parent
            text: button.text
            textFormat: Text.PlainText
            color: button.strong ? "#ffffff" : popup.ink
            font.pixelSize: 12
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
            visible: !widget.recording && !widget.streaming
            text: "\ue7c8"
            color: widget.textColor
            opacity: obs.connected ? 1 : 0.4
            font.pixelSize: widget.font.pixelSize + 1
        }

        Row {
            objectName: "recording"
            anchors.verticalCenter: parent.verticalCenter
            visible: widget.recording
            spacing: 6

            RecordDot {
                anchors.verticalCenter: parent.verticalCenter
                visible: !widget.paused
                blinking: widget.blinkingIcon && widget.recording && !widget.paused
            }

            Glyph {
                anchors.verticalCenter: parent.verticalCenter
                visible: widget.paused
                text: "\ue769"
                color: widget.pausedColor
                font.pixelSize: widget.font.pixelSize
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                visible: widget.showRecordTime
                text: widget.clock(obs.recording.duration)
                textFormat: Text.PlainText
                color: widget.textColor
                opacity: widget.paused ? 0.7 : 1
                font: widget.font
            }
        }

        Row {
            objectName: "streaming"
            anchors.verticalCenter: parent.verticalCenter
            visible: widget.streaming
            spacing: 6

            Glyph {
                anchors.verticalCenter: parent.verticalCenter
                text: "\ue93e"
                color: widget.liveColor
                font.pixelSize: widget.font.pixelSize + 1
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                visible: widget.showStreamTime
                text: widget.clock(obs.streaming.duration)
                textFormat: Text.PlainText
                color: widget.textColor
                font: widget.font
            }
        }

        Glyph {
            anchors.verticalCenter: parent.verticalCenter
            visible: widget.showVirtualCam && obs.virtualCam
            text: "\ue714"
            color: widget.textColor
            font.pixelSize: widget.font.pixelSize + 1
        }

        Glyph {
            anchors.verticalCenter: parent.verticalCenter
            visible: widget.showStudioMode && obs.studioMode
            text: "\ue7f4"
            color: widget.textColor
            font.pixelSize: widget.font.pixelSize + 1
        }

        Text {
            objectName: "scene"
            anchors.verticalCenter: parent.verticalCenter
            visible: widget.showSceneName && obs.scene !== ""
            text: obs.scene
            textFormat: Text.PlainText
            color: widget.textColor
            opacity: 0.7
            font: widget.font
        }
    }

    MouseArea {
        id: area

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: widget.togglePopup()
    }

    ToolTip {
        popupType: Popup.Window
        visible: widget.tooltip && area.containsMouse && !popup.visible
        delay: 400
        text: !obs.connected ? qsTr("OBS is not connected")
            : [widget.recording ? (widget.paused ? qsTr("Recording paused") : qsTr("Recording")) : qsTr("Not recording"),
                widget.streaming ? qsTr("Streaming") : "",
                obs.scene !== "" ? qsTr("Scene: %1").arg(obs.scene) : ""].filter(line => line).join("\n")
        // Away from the bar's edge
        y: widget.edge === "bottom" ? -implicitHeight - 6 : widget.height + 6
    }

    BackdropPopup {
        id: popup

        property real reveal: 0
        readonly property color ink: widget.dark ? "#ffffff" : "#000000"
        readonly property color muted: Qt.alpha(ink, 0.544)
        readonly property color line: Qt.alpha(ink, 0.08)

        objectName: "popup"
        title: qsTr("OBS Studio")
        width: widget.popupWidth
        height: popupContent.implicitHeight + 16
        anchor: widget
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible)
                reveal = 0
        }

        Rectangle {
            id: surface

            anchors.fill: parent
            anchors.margins: 8
            radius: 8
            color: widget.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: widget.dark ? "#3A3A3A" : "#D9D9D9"
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: widget.edge === "bottom" ? Item.Bottom : Item.Top
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

                    Label {
                        Layout.fillWidth: true
                        text: qsTr("OBS Studio")
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                    }

                    Label {
                        Layout.fillWidth: true
                        visible: text !== ""
                        text: obs.connected ? (obs.scene !== "" ? qsTr("Scene: %1").arg(obs.scene) : "")
                            : qsTr("Not connected")
                        muted: true
                        font.pixelSize: 12
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 1
                    color: popup.line
                }

                // OBS is not running, its server is off, or the password is wrong
                Label {
                    objectName: "disconnected"
                    Layout.fillWidth: true
                    Layout.margins: 16
                    visible: !obs.connected
                    text: obs.error !== "" ? obs.error
                        : qsTr("Start OBS and turn on its WebSocket server under Tools > WebSocket Server Settings.")
                    wrapMode: Text.WordWrap
                    elide: Text.ElideNone
                    muted: obs.error === ""
                    color: obs.error !== "" ? widget.liveColor : popup.muted
                    font.pixelSize: 12
                }

                // Recording and streaming
                Card {
                    Layout.topMargin: 12
                    visible: obs.connected
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
                                    visible: widget.recording && !widget.paused
                                    blinking: false
                                }

                                Glyph {
                                    anchors.centerIn: parent
                                    visible: !widget.recording || widget.paused
                                    text: widget.paused ? "\ue769" : "\ue7c8"
                                    color: widget.paused ? widget.pausedColor : popup.muted
                                    font.pixelSize: 15
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 0

                                Label {
                                    Layout.fillWidth: true
                                    text: !widget.recording ? qsTr("Not recording")
                                        : widget.paused ? qsTr("Recording paused") : qsTr("Recording")
                                }

                                Label {
                                    Layout.fillWidth: true
                                    visible: widget.recording
                                    text: widget.clock(obs.recording.duration)
                                    muted: true
                                    font.pixelSize: 12
                                }
                            }

                            SmallButton {
                                visible: widget.recording
                                text: widget.paused ? qsTr("Resume") : qsTr("Pause")
                                onClicked: obs.toggleRecordPause()
                            }

                            SmallButton {
                                text: widget.recording ? qsTr("Stop") : qsTr("Start")
                                strong: widget.recording
                                onClicked: obs.toggleRecord()
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
                                text: "\ue93e"
                                color: widget.streaming ? widget.liveColor : popup.muted
                                font.pixelSize: 15
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 0

                                Label {
                                    Layout.fillWidth: true
                                    text: !widget.streaming ? qsTr("Not streaming")
                                        : obs.streaming.reconnecting ? qsTr("Reconnecting...") : qsTr("Streaming")
                                }

                                Label {
                                    Layout.fillWidth: true
                                    visible: widget.streaming
                                    text: [widget.clock(obs.streaming.duration),
                                        obs.streaming.skippedFrames === 1 ? qsTr("1 dropped frame")
                                            : obs.streaming.skippedFrames > 1
                                            ? qsTr("%1 dropped frames").arg(obs.streaming.skippedFrames) : ""]
                                        .filter(part => part).join(" · ")
                                    muted: true
                                    font.pixelSize: 12
                                }
                            }

                            SmallButton {
                                text: widget.streaming ? qsTr("Stop") : qsTr("Start")
                                strong: widget.streaming
                                onClicked: obs.toggleStream()
                            }
                        }
                    }
                }

                // The virtual camera and studio mode
                Card {
                    Layout.topMargin: 8
                    visible: obs.connected
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
                                text: "\ue714"
                                color: popup.muted
                                font.pixelSize: 15
                            }

                            Label {
                                Layout.fillWidth: true
                                text: qsTr("Virtual camera")
                            }

                            Switch {
                                objectName: "virtualCam"
                                checked: obs.virtualCam
                                Accessible.name: qsTr("Virtual camera")
                                onToggled: {
                                    obs.toggleVirtualCam()
                                    checked = Qt.binding(() => obs.virtualCam)
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
                                text: "\ue7f4"
                                color: popup.muted
                                font.pixelSize: 15
                            }

                            Label {
                                Layout.fillWidth: true
                                text: qsTr("Studio mode")
                            }

                            Switch {
                                objectName: "studioMode"
                                checked: obs.studioMode
                                Accessible.name: qsTr("Studio mode")
                                onToggled: {
                                    obs.toggleStudioMode()
                                    checked = Qt.binding(() => obs.studioMode)
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
                    bottomLeftRadius: 7
                    bottomRightRadius: 7
                    color: Qt.alpha("#000000", widget.dark ? 0.15 : 0.03)

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: popup.line
                    }

                    Label {
                        x: 16
                        anchors.verticalCenter: parent.verticalCenter
                        text: `${widget.host}:${widget.port}`
                        muted: true
                        font.pixelSize: 12
                    }

                    Label {
                        anchors.right: parent.right
                        anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        text: obs.connected ? qsTr("Connected") : qsTr("Not connected")
                        muted: true
                        font.pixelSize: 12
                    }
                }
            }
        }
    }
}
