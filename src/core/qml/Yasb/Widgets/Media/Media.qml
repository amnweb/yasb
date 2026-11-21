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
    id: media

    component PopupIcons: QtObject {
        property string volume
        property string muted
        property string app
        property string cover
        property string shuffle
        property string previous
        property string play
        property string pause
        property string next
        property string repeat
        property string repeatOne
    }

    component Settings: QtObject {
        required property Theme theme

        property bool hideEmpty: true
        // The album art on the bar, in a circle; the icon glyph, in iconFont, shows while there is none
        property bool showThumbnail: true
        property int thumbnailSize: 20
        property string icon: "\ue8d6"
        property int iconSize: theme.bar.iconFont.pixelSize
        property bool showArtist: false
        property bool showProgress: false
        // The title's widest size on the bar, in pixels
        property int maxLabelWidth: 150
        property int popupWidth: 280
        // The album art in the popup and its rounded corners
        property int imageSize: 160
        property int imageRadius: 12
        // The album art blurred behind the popup; artworkDim 0 shows it fully, 1 hides it
        property bool artworkBackground: true
        property real artworkDim: 0.85
        // Shuffle and repeat while they are on
        property color activeColor: theme.dark ? "#05ec4a" : "#0a8a3a"
        // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
        property color textColor: theme.colors.text
        property font font
        // Glyphs take the theme's icon font, each part unless the widget file sets it
        property font iconFont
        iconFont.family: theme.bar.iconFont.family
        iconFont.weight: theme.bar.iconFont.weight
        iconFont.variableAxes: theme.bar.iconFont.variableAxes
        // The glyph on the play button
        property color primaryGlyphColor: theme.colors.textOnAccent
        // The popup: the theme's, unless set here
        property color popupColor: theme.popup.background
        property color popupBorderColor: theme.popup.border
        property color popupTextColor: theme.colors.text
        property real popupRadius: theme.popup.radius
        property real popupGap: theme.popup.gap
        property int popupOpenDuration: theme.popup.openDuration
        property int popupCloseDuration: theme.popup.closeDuration
        // Text in the popup: the theme's font family, in this widget's sizes
        property font popupFont
        popupFont.family: theme.popup.font.family
        popupFont.pixelSize: 13
        property color popupDividerColor: theme.colors.divider
        readonly property PopupIcons popupIcons: PopupIcons {
            volume: "\ue767"
            muted: "\ue74f"
            // The player app's while it has no icon, and the album art's while there is none
            app: "\ue8d6"
            cover: "\ue8d6"
            shuffle: "\ue8b1"
            previous: "\uf8ac"
            play: "\uf5b0"
            pause: "\uf8ae"
            next: "\uf8ad"
            repeat: "\ue8ee"
            repeatOne: "\ue8ed"
        }
        property font popupIconFont
        popupIconFont.family: theme.popup.iconFont.family
        popupIconFont.weight: theme.popup.iconFont.weight
        popupIconFont.variableAxes: theme.popup.iconFont.variableAxes
        // Glyphs: the play button's, the other buttons', the player app's when it has no icon, and the one shown
        // without a cover
        property int playIconSize: 20
        property int controlIconSize: 16
        property int appIconSize: 16
        property int coverIconSize: 40
        // The track's title and artist, and the times beside the timeline
        property font trackTitleFont
        trackTitleFont.family: theme.popup.font.family
        trackTitleFont.pixelSize: 15
        trackTitleFont.weight: 600
        property font artistFont
        artistFont.family: theme.popup.font.family
        artistFont.pixelSize: 12
        artistFont.weight: 600
        property font timeFont
        timeFont.family: theme.popup.font.family
        timeFont.pixelSize: 11
        property color popupSecondaryTextColor: theme.colors.textSecondary
        property color popupTertiaryTextColor: theme.colors.textTertiary
        property color popupHoverColor: theme.colors.hover
        // The right-click menu: the theme's, unless set here
        property color menuColor: theme.menu.background
        property color menuBorderColor: theme.menu.border
        property color accentColor: theme.colors.accent
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: media.theme
    }

    readonly property bool dark: theme.dark
    readonly property string edge: bar.edge
    readonly property string label: player.title && media.settings.showArtist && player.artist
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
        let px = edge === "left" ? start.x + width + settings.popupGap
            : edge === "right" ? start.x - popup.width - settings.popupGap : start.x + (width - popup.width) / 2
        let py = edge === "top" ? start.y + height + settings.popupGap
            : edge === "bottom" ? start.y - popup.height - settings.popupGap : start.y + (height - popup.height) / 2
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

    readonly property bool shown: !settings.hideEmpty || player.available

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

    Row {
        id: row
        height: parent.height
        spacing: 6

        Item {
            id: cover
            y: Math.round((parent.height - height) / 2)
            width: media.settings.thumbnailSize
            height: media.settings.thumbnailSize
            visible: media.settings.showThumbnail && thumbnail.status === Image.Ready
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
                sourceSize: Qt.size(media.settings.thumbnailSize * 2, media.settings.thumbnailSize * 2)
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

        Text {
            anchors.verticalCenter: parent.verticalCenter
            visible: !cover.visible
            text: media.settings.icon
            color: media.settings.textColor
            font.family: media.settings.iconFont.family
            font.weight: media.settings.iconFont.weight
            font.variableAxes: media.settings.iconFont.variableAxes
            font.pixelSize: media.settings.iconSize
        }

        Label {
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(implicitWidth, media.settings.maxLabelWidth)
            visible: player.available
            text: media.label
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: media.settings.textColor
            font: media.settings.font
        }
    }

    Rectangle {
        anchors.bottom: parent.bottom
        width: player.duration > 0 ? parent.width * Math.min(1, player.position / player.duration) : 0
        height: 2
        radius: 1
        visible: media.settings.showProgress && player.duration > 0
        color: media.settings.accentColor
    }

    component PlayerButton: Item {
        id: button

        property string glyph
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
            color: button.primary && button.enabled ? media.settings.popupTextColor : area.containsMouse ? media.settings.popupHoverColor : "transparent"
        }

        Text {
            anchors.centerIn: parent
            text: button.glyph
            font.family: media.settings.popupIconFont.family
            font.weight: media.settings.popupIconFont.weight
            font.variableAxes: media.settings.popupIconFont.variableAxes
            font.pixelSize: button.primary ? media.settings.playIconSize : media.settings.controlIconSize
            color: button.primary && button.enabled ? media.settings.primaryGlyphColor
                : button.active ? media.settings.activeColor : media.settings.popupTextColor
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
        property bool volumeShown: false
        readonly property bool volumeHovered: volumeArea.containsMouse || volumeBoxHover.hovered
        title: "Now playing"
        width: media.settings.popupWidth
        height: popupContent.implicitHeight
        anchor: media
        font: media.settings.popupFont
        theme: media.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: media.settings.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: media.settings.popupCloseDuration; easing.type: Easing.InCubic }
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
            radius: media.settings.popupRadius
            color: media.settings.popupColor
            // Active and inactive only, so disabled controls keep the style's dimmed colours
            palette.active.accent: media.settings.accentColor
            palette.inactive.accent: media.settings.accentColor
            border.width: 1
            border.color: media.settings.popupBorderColor
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
                visible: media.settings.artworkBackground && media.settings.artworkDim < 1 && player.thumbnail !== ""
                opacity: 1 - media.settings.artworkDim
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
                id: popupContent
                width: parent.width
                spacing: 0

                Item {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 12
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

                        Text {
                            anchors.centerIn: parent
                            text: media.app?.muted ? media.settings.popupIcons.muted : media.settings.popupIcons.volume
                            color: media.settings.popupTextColor
                            font.family: media.settings.popupIconFont.family
                            font.weight: media.settings.popupIconFont.weight
                            font.variableAxes: media.settings.popupIconFont.variableAxes
                            font.pixelSize: media.settings.controlIconSize
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
                        color: media.settings.menuColor
                        border.width: 1
                        border.color: media.settings.menuBorderColor

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
                                color: Qt.alpha(media.settings.popupTextColor, 0.1)

                                Rectangle {
                                    anchors.bottom: parent.bottom
                                    width: parent.width
                                    height: volumeSlider.position * parent.height
                                    radius: 2
                                    color: media.settings.popupTextColor
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

                        Text {
                            anchors.centerIn: parent
                            visible: appIcon.status !== Image.Ready
                            text: media.settings.popupIcons.app
                            color: media.settings.popupTextColor
                            font.family: media.settings.popupIconFont.family
                            font.weight: media.settings.popupIconFont.weight
                            font.variableAxes: media.settings.popupIconFont.variableAxes
                            font.pixelSize: media.settings.appIconSize
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
                // The header's bottom line
                Rectangle {
                    Layout.fillWidth: true
                    Layout.topMargin: 10
                    Layout.bottomMargin: 8
                    implicitHeight: 1
                    color: media.settings.popupDividerColor
                }

                Item {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: media.settings.imageSize
                    Layout.preferredHeight: media.settings.imageSize
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
                        color: Qt.alpha(media.settings.popupTextColor, 0.06)

                        Text {
                            anchors.centerIn: parent
                            text: media.settings.popupIcons.cover
                            color: media.settings.popupTextColor
                            font.family: media.settings.popupIconFont.family
                            font.weight: media.settings.popupIconFont.weight
                            font.variableAxes: media.settings.popupIconFont.variableAxes
                            font.pixelSize: media.settings.coverIconSize
                            opacity: 0.5
                        }
                    }

                    Image {
                        id: art
                        anchors.fill: parent
                        source: player.thumbnail
                        sourceSize: Qt.size(media.settings.imageSize * 2, media.settings.imageSize * 2)
                        fillMode: Image.PreserveAspectCrop
                    }

                    Rectangle {
                        id: coverMask
                        anchors.fill: parent
                        radius: media.settings.imageRadius
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
                    color: media.settings.popupTextColor
                    font: media.settings.trackTitleFont
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
                    color: media.settings.popupSecondaryTextColor
                    font: media.settings.artistFont
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
                        color: Qt.alpha(media.settings.popupTextColor, thick ? 0.2 : 0.1)

                        Rectangle {
                            width: timeline.position * parent.width
                            height: parent.height
                            radius: 3
                            color: media.settings.popupTextColor
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
                        color: media.settings.popupTertiaryTextColor
                        font: media.settings.timeFont
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    Text {
                        text: media.time(player.duration)
                        color: media.settings.popupTertiaryTextColor
                        font: media.settings.timeFont
                    }
                }

                Row {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 4
                    Layout.bottomMargin: 36
                    spacing: 4

                    PlayerButton {
                        glyph: media.settings.popupIcons.shuffle
                        enabled: player.canShuffle
                        active: player.shuffle
                        onClicked: player.toggleShuffle()
                        Accessible.name: player.shuffle ? "Shuffle on" : "Shuffle"
                    }
                    PlayerButton {
                        glyph: media.settings.popupIcons.previous
                        enabled: player.canPrevious
                        onClicked: player.previous()
                        Accessible.name: "Previous"
                    }
                    PlayerButton {
                        primary: true
                        glyph: player.playing ? media.settings.popupIcons.pause : media.settings.popupIcons.play
                        enabled: player.canPlayPause
                        onClicked: player.playPause()
                        Accessible.name: player.playing ? "Pause" : "Play"
                    }
                    PlayerButton {
                        glyph: media.settings.popupIcons.next
                        enabled: player.canNext
                        onClicked: player.next()
                        Accessible.name: "Next"
                    }
                    PlayerButton {
                        glyph: player.repeat === "track" ? media.settings.popupIcons.repeatOne : media.settings.popupIcons.repeat
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
