import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl
import QtQuick.Effects
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: media

    property Item bar: null
    property bool hideEmpty: true
    // The album art on the bar, in a circle; the icon shows while there is none
    property bool showThumbnail: true
    property int thumbnailSize: 20
    property url icon: Qt.resolvedUrl("icons/music.svg")
    property int iconSize: 16
    property bool showArtist: false
    property bool showProgress: false
    // The title's widest size on the bar, in pixels
    property int maxLabelWidth: 150
    property int popupWidth: 296
    // The album art in the popup and its rounded corners
    property int imageSize: 160
    property int imageRadius: 12
    // The album art blurred behind the popup; artworkDim 0 shows it fully, 1 hides it
    property bool artworkBackground: true
    property real artworkDim: 0.85
    // Shuffle and repeat while they are on
    property color activeColor: dark ? "#05ec4a" : "#0a8a3a"

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
    readonly property color accent: dark ? "#60cdff" : "#005fb8"
    readonly property string edge: bar?.edge ?? "top"
    readonly property string label: player.title && media.showArtist && player.artist
        ? `${player.title} - ${player.artist}` : player.title || player.appName
    readonly property var app: audio.apps.find(entry => (player.appId !== "" && entry.appId === player.appId)
        || (player.process !== "" && entry.process.toLowerCase() === player.process.toLowerCase())) ?? null

    function time(seconds: real): string {
        const total = Math.max(0, Math.floor(seconds))
        const pad = value => String(value).padStart(2, "0")
        const hours = Math.floor(total / 3600)
        const minutes = Math.floor(total % 3600 / 60)
        return hours > 0 ? `${hours}:${pad(minutes)}:${pad(total % 60)}` : `${minutes}:${pad(total % 60)}`
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + 6
            : edge === "right" ? start.x - popup.width - 6 : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + 6
            : edge === "bottom" ? start.y - popup.height - 6 : start.y + (height - popup.height) / 2
        const screen = media.Screen
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
            placePopup()
            popup.open()
        }
    }

    readonly property bool shown: !hideEmpty || player.available

    implicitWidth: shown ? row.implicitWidth : 0
    implicitHeight: shown ? row.implicitHeight : 0
    visible: shown
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: player.available ? `${player.appName}: ${player.title}` : "Nothing playing"
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    Component.onDestruction: popup.hide()

    NowPlaying {
        id: player
        positionInterval: popup.visible ? 250 : 1000
    }

    AudioOutput { id: audio }

    Connections {
        target: media.Window.window
        function onVisibleChanged() {
            if (!media.Window.window?.visible)
                popup.hide()
        }
        function onXChanged() { if (popup.visible) media.placePopup() }
        function onYChanged() { if (popup.visible) media.placePopup() }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: media.togglePopup()
        onWheel: wheel => {
            const delta = wheel.angleDelta.y || wheel.angleDelta.x
            if (delta !== 0)
                player.switchSession(delta > 0 ? -1 : 1)
        }
    }

    component SvgIcon: IconImage {
        sourceSize: Qt.size(width, height)
    }

    Row {
        id: row
        height: parent.height
        spacing: 6

        Item {
            id: cover
            y: Math.round((parent.height - height) / 2)
            width: media.thumbnailSize
            height: media.thumbnailSize
            visible: media.showThumbnail && thumbnail.status === Image.Ready
            layer.enabled: visible
            layer.effect: MultiEffect {
                maskEnabled: true
                maskSource: coverCircle
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1
            }

            Image {
                id: thumbnail
                anchors.fill: parent
                source: player.thumbnail
                sourceSize: Qt.size(media.thumbnailSize * 2, media.thumbnailSize * 2)
                fillMode: Image.PreserveAspectCrop
            }

            Rectangle {
                id: coverCircle
                anchors.fill: parent
                radius: width / 2
                visible: false
                layer.enabled: true
            }
        }

        SvgIcon {
            y: Math.round((parent.height - height) / 2)
            width: media.iconSize
            height: media.iconSize
            visible: !cover.visible
            source: media.icon
            color: media.textColor
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(implicitWidth, media.maxLabelWidth)
            visible: player.available
            text: media.label
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: media.textColor
            font: media.font
        }
    }

    Rectangle {
        anchors.bottom: parent.bottom
        width: player.duration > 0 ? parent.width * Math.min(1, player.position / player.duration) : 0
        height: 2
        radius: 1
        visible: media.showProgress && player.duration > 0
        color: media.accent
    }

    component PlayerButton: Item {
        id: button

        property url source
        property bool active: false
        property bool primary: false

        signal clicked

        width: 40
        height: 40
        opacity: area.pressed ? 0.5 : 1
        Accessible.role: Accessible.Button
        Accessible.onPressAction: button.clicked()

        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: button.primary && button.enabled ? popup.ink : Qt.alpha(popup.ink, area.containsMouse ? 0.1 : 0)
        }

        SvgIcon {
            anchors.centerIn: parent
            width: button.primary ? 20 : 16
            height: button.primary ? 20 : 16
            source: button.source
            color: button.primary && button.enabled ? (media.dark ? "#000000" : "#ffffff")
                : button.active ? media.activeColor : popup.ink
            opacity: button.enabled ? 1 : 0.35
        }

        MouseArea {
            id: area
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: button.clicked()
        }
    }

    BackdropPopup {
        id: popup
        property real reveal: 0
        readonly property color ink: media.dark ? "#ffffff" : "#000000"
        property bool volumeShown: false
        readonly property bool volumeHovered: volumeArea.containsMouse || volumeBoxHover.hovered
        title: "Now playing"
        width: media.popupWidth
        height: content.implicitHeight + 16
        anchor: media
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible) {
                reveal = 0
                volumeShown = false
            }
        }
        onVolumeHoveredChanged: volumeTimer.restart()

        Rectangle {
            id: surface
            anchors.fill: parent
            anchors.margins: 8
            radius: 8
            color: media.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: media.dark ? Qt.alpha("#3A3A3A", 1) : Qt.alpha("#D9D9D9", 1)
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: media.edge === "bottom" ? Item.Bottom : Item.Top

            WheelHandler {
                onWheel: event => {
                    const delta = event.angleDelta.y || event.angleDelta.x
                    if (delta !== 0)
                        player.switchSession(delta > 0 ? -1 : 1)
                }
            }

            Timer {
                id: volumeTimer
                interval: popup.volumeHovered ? 150 : 350
                onTriggered: popup.volumeShown = popup.volumeHovered && media.app !== null
            }

            Item {
                id: artwork
                anchors.fill: parent
                anchors.margins: 1
                visible: media.artworkBackground && media.artworkDim < 1 && player.thumbnail !== ""
                opacity: 1 - media.artworkDim
                layer.enabled: visible
                layer.effect: MultiEffect {
                    maskEnabled: true
                    maskSource: artworkMask
                    maskThresholdMin: 0.5
                    maskSpreadAtMin: 1
                }

                Image {
                    anchors.fill: parent
                    anchors.margins: -48
                    source: player.thumbnail
                    sourceSize: Qt.size(96, 96)
                    fillMode: Image.PreserveAspectCrop
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        blurEnabled: true
                        blur: 1
                        blurMax: 48
                    }
                }

                Rectangle {
                    id: artworkMask
                    anchors.fill: parent
                    radius: surface.radius - 1
                    visible: false
                    layer.enabled: true
                }
            }

            ColumnLayout {
                id: content
                width: parent.width
                spacing: 0

                Item {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 16
                    implicitHeight: 24
                    z: 1

                    Item {
                        id: volumeIcon
                        width: 24
                        height: 24
                        Accessible.role: Accessible.Button
                        Accessible.name: media.app?.muted ? `Unmute ${player.appName}` : `Mute ${player.appName}`
                        Accessible.onPressAction: {
                            if (media.app)
                                audio.setAppMuted(media.app.key, !media.app.muted)
                        }

                        SvgIcon {
                            anchors.centerIn: parent
                            width: 16
                            height: 16
                            source: Qt.resolvedUrl(media.app?.muted ? "icons/speaker-mute.svg" : "icons/speaker.svg")
                            color: popup.ink
                            opacity: !media.app ? 0.3 : media.app.muted ? 0.6 : 1
                        }

                        MouseArea {
                            id: volumeArea
                            anchors.fill: parent
                            enabled: media.app !== null
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: audio.setAppMuted(media.app.key, !media.app.muted)
                            onWheel: wheel => {
                                const delta = wheel.angleDelta.y || wheel.angleDelta.x
                                if (delta !== 0)
                                    audio.setAppVolume(media.app.key, Math.max(0, Math.min(100, media.app.volume + (delta > 0 ? 5 : -5))))
                            }
                        }
                    }

                    Rectangle {
                        x: (volumeIcon.width - width) / 2
                        y: volumeIcon.height
                        width: 32
                        height: 144
                        radius: 10
                        visible: popup.volumeShown
                        color: media.dark ? "#202020" : "#f9f9f9"
                        border.width: 1
                        border.color: media.dark ? "#363636" : "#e5e5e5"

                        HoverHandler {
                            id: volumeBoxHover
                        }

                        Slider {
                            id: volumeSlider
                            anchors.fill: parent
                            topPadding: 12
                            bottomPadding: 12
                            leftPadding: 8
                            rightPadding: 8
                            orientation: Qt.Vertical
                            from: 0
                            to: 100
                            wheelEnabled: true
                            value: media.app?.volume ?? 0
                            onMoved: audio.setAppVolume(media.app.key, Math.round(value))
                            Accessible.name: `${player.appName} volume`
                            background: Rectangle {
                                x: volumeSlider.leftPadding + (volumeSlider.availableWidth - width) / 2
                                y: volumeSlider.topPadding
                                width: 3
                                height: volumeSlider.availableHeight
                                radius: 2
                                color: Qt.alpha(popup.ink, 0.1)

                                Rectangle {
                                    anchors.bottom: parent.bottom
                                    width: parent.width
                                    height: volumeSlider.position * parent.height
                                    radius: 2
                                    color: popup.ink
                                }
                            }
                            handle: Item {}
                        }
                    }

                    Item {
                        anchors.right: parent.right
                        width: 16
                        height: 16
                        ToolTip.visible: sourceArea.containsMouse && player.appName !== ""
                        ToolTip.delay: 500
                        ToolTip.text: player.appName

                        Image {
                            id: appIcon
                            anchors.fill: parent
                            source: media.app?.icon ?? ""
                            sourceSize: Qt.size(32, 32)
                        }

                        SvgIcon {
                            anchors.fill: parent
                            visible: appIcon.status !== Image.Ready
                            source: Qt.resolvedUrl("icons/music.svg")
                            color: popup.ink
                            opacity: 0.65
                        }

                        MouseArea {
                            id: sourceArea
                            anchors.fill: parent
                            enabled: player.available
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                player.openApp()
                                popup.close()
                            }
                        }
                    }
                }

                Item {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: media.imageSize
                    Layout.preferredHeight: media.imageSize
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        maskEnabled: true
                        maskSource: coverMask
                        maskThresholdMin: 0.5
                        maskSpreadAtMin: 1
                    }

                    Rectangle {
                        anchors.fill: parent
                        visible: art.status !== Image.Ready
                        color: Qt.alpha(popup.ink, 0.06)

                        SvgIcon {
                            anchors.centerIn: parent
                            width: 40
                            height: 40
                            source: Qt.resolvedUrl("icons/music-large.svg")
                            color: popup.ink
                            opacity: 0.5
                        }
                    }

                    Image {
                        id: art
                        anchors.fill: parent
                        source: player.thumbnail
                        sourceSize: Qt.size(media.imageSize * 2, media.imageSize * 2)
                        fillMode: Image.PreserveAspectCrop
                    }

                    Rectangle {
                        id: coverMask
                        anchors.fill: parent
                        radius: media.imageRadius
                        visible: false
                        layer.enabled: true
                    }

                    MouseArea {
                        anchors.fill: parent
                        enabled: player.available
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            player.openApp()
                            popup.close()
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 32
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    horizontalAlignment: Text.AlignHCenter
                    text: player.available ? player.title || "Unknown Title" : "Nothing playing"
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                    color: popup.ink
                    font.family: "Segoe UI"
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                }

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    horizontalAlignment: Text.AlignHCenter
                    text: player.available ? player.artist || "Unknown Artist" : ""
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                    color: Qt.alpha(popup.ink, 0.65)
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                }

                Slider {
                    id: timeline
                    Layout.fillWidth: true
                    Layout.topMargin: 18
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    implicitHeight: 10
                    padding: 0
                    from: 0
                    to: Math.max(player.duration, 1)
                    enabled: player.canSeek && player.duration > 0
                    onPressedChanged: {
                        if (!pressed)
                            player.seek(value)
                    }
                    Accessible.name: "Position"
                    background: Rectangle {
                        readonly property bool thick: timeline.hovered || timeline.pressed

                        y: (timeline.height - height) / 2
                        width: timeline.width
                        height: thick ? 6 : 2
                        radius: 3
                        color: Qt.alpha(popup.ink, thick ? 0.2 : 0.1)

                        Rectangle {
                            width: timeline.position * parent.width
                            height: parent.height
                            radius: 3
                            color: popup.ink
                        }
                    }
                    handle: Item {}
                }
                Binding {
                    target: timeline
                    property: "value"
                    value: player.position
                    when: !timeline.pressed
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 2
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16

                    Text {
                        text: media.time(player.duration > 0 ? Math.min(timeline.pressed ? timeline.value : player.position, player.duration) : 0)
                        color: Qt.alpha(popup.ink, 0.5)
                        font.family: "Segoe UI"
                        font.pixelSize: 11
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    Text {
                        text: media.time(player.duration)
                        color: Qt.alpha(popup.ink, 0.5)
                        font.family: "Segoe UI"
                        font.pixelSize: 11
                    }
                }

                Row {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 4
                    Layout.bottomMargin: 36
                    spacing: 4

                    PlayerButton {
                        source: Qt.resolvedUrl("icons/shuffle.svg")
                        enabled: player.canShuffle
                        active: player.shuffle
                        onClicked: player.toggleShuffle()
                        Accessible.name: player.shuffle ? "Shuffle on" : "Shuffle"
                    }
                    PlayerButton {
                        source: Qt.resolvedUrl("icons/previous.svg")
                        enabled: player.canPrevious
                        onClicked: player.previous()
                        Accessible.name: "Previous"
                    }
                    PlayerButton {
                        primary: true
                        source: Qt.resolvedUrl(player.playing ? "icons/pause.svg" : "icons/play.svg")
                        enabled: player.canPlayPause
                        onClicked: player.playPause()
                        Accessible.name: player.playing ? "Pause" : "Play"
                    }
                    PlayerButton {
                        source: Qt.resolvedUrl("icons/next.svg")
                        enabled: player.canNext
                        onClicked: player.next()
                        Accessible.name: "Next"
                    }
                    PlayerButton {
                        source: Qt.resolvedUrl(player.repeat === "track" ? "icons/repeat-one.svg" : "icons/repeat.svg")
                        enabled: player.canRepeat
                        active: player.repeat !== "none"
                        onClicked: player.cycleRepeat()
                        Accessible.name: `Repeat: ${player.repeat}`
                    }
                }
            }
        }
    }
}
