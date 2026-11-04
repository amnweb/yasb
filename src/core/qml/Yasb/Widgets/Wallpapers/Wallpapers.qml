import QtQuick
import QtQuick.Controls
import QtQuick.Shapes
import Yasb

Item {
    id: wallpapers

    property Item bar: null
    // Folders searched for wallpapers, subfolders included; empty for your Pictures folder
    property list<string> folders: []
    // Transition before a wallpaper is set on every screen: circle, slide_top, diamond, split or "" for none
    property string animation: ""
    property string icon: "\ue7aa"
    property int iconSize: 16
    // Hotkey that opens the gallery, such as "alt+w", and its screen: active, cursor or primary
    property string keys: ""
    property string hotkeyScreen: "active"

    property int thumbnailWidth: 200
    // landscape or portrait
    property string orientation: "portrait"
    readonly property int thumbnailHeight: Math.round(orientation === "portrait" ? thumbnailWidth * 16 / 9 : thumbnailWidth * 9 / 16)
    property real selectedScale: 1.4
    property int spacing: 6
    property int cornerRadius: 0
    property color accentColor: palette.active.accent
    property int animationDuration: 120
    // How long the thumbnails take to fan out from behind the current wallpaper when the gallery opens
    property int openDuration: 450
    property real slideSpeed: 8
    // One thumbnail: gets modelData ({path, name}) and index; PathView.itemScale is 1 at the sides, selectedScale in the centre
    property Component thumbnail: Component {
        Item {
            id: card

            required property var modelData
            required property int index
            readonly property real growth: Number.isFinite(PathView.itemScale) ? PathView.itemScale : 1
            readonly property real nearness: Math.max(0, Math.min(1, (growth - 1) / Math.max(0.01, wallpapers.selectedScale - 1)))

            width: wallpapers.thumbnailWidth
            height: wallpapers.thumbnailHeight
            scale: growth
            z: growth

            Rectangle {
                anchors.fill: parent
                radius: wallpapers.cornerRadius
                color: Qt.alpha("#808080", 0.3)
                visible: picture.status !== Image.Ready
            }

            WallpaperThumbnail {
                id: made

                readonly property real ratio: (card.Screen.devicePixelRatio || 1) * wallpapers.selectedScale

                path: card.modelData.path
                size: Qt.size(Math.round(card.width * made.ratio), Math.round(card.height * made.ratio))
            }

            Image {
                id: picture

                anchors.fill: parent
                visible: false
                source: made.source
                asynchronous: true
            }

            Shape {
                anchors.fill: parent
                opacity: picture.status === Image.Ready ? 1 : 0
                visible: opacity > 0
                preferredRendererType: Shape.CurveRenderer

                Behavior on opacity {
                    NumberAnimation {
                        duration: 150
                    }
                }

                ShapePath {
                    strokeColor: "transparent"
                    fillItem: picture
                    // The fill takes the picture's pixels one to one; scaled to the card, the whole thumbnail shows
                    fillTransform: PlanarTransform.fromScale(card.width / Math.max(1, picture.implicitWidth),
                        card.height / Math.max(1, picture.implicitHeight))

                    PathRectangle {
                        width: card.width
                        height: card.height
                        radius: wallpapers.cornerRadius
                    }
                }
            }

            Rectangle {
                anchors.fill: parent
                radius: wallpapers.cornerRadius
                color: Qt.alpha("#000000", 0.45 * (1 - card.nearness))
            }

            Rectangle {
                anchors.fill: parent
                radius: wallpapers.cornerRadius
                color: "transparent"
                border.width: 2
                border.color: wallpapers.accentColor
                opacity: card.nearness
            }
        }
    }

    readonly property bool dark: Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    property font iconFont
    iconFont.family: bar?.iconFont?.family ?? "Segoe Fluent Icons"
    iconFont.weight: bar?.iconFont?.weight ?? Font.Normal

    // Held so the garbage collector doesn't destroy the open gallery
    property Window opened: null

    implicitWidth: label.width
    implicitHeight: label.height
    Accessible.role: Accessible.Button
    Accessible.name: qsTr("Wallpapers")
    Accessible.onPressAction: toggleGallery()

    function toggleGallery() {
        if (opened) {
            opened.dismiss()
            return
        }
        library.refresh()
        const screen = wallpapers.Screen
        const height = Math.round(wallpapers.thumbnailHeight * wallpapers.selectedScale) + 48
        opened = gallery.createObject(null, {
            screenName: screen.name,
            area: Qt.rect(screen.virtualX, screen.virtualY + Math.round((screen.height - height) / 2), screen.width, height)
        })
    }

    WallpaperLibrary {
        id: library

        folders: wallpapers.folders
        animation: wallpapers.animation
    }

    Hotkey {
        keys: wallpapers.keys
        screen: wallpapers.hotkeyScreen
        onActivated: wallpapers.toggleGallery()
    }

    Text {
        id: label

        y: Math.round((parent.height - height) / 2)
        width: wallpapers.iconSize
        height: wallpapers.iconSize
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        text: wallpapers.icon
        color: wallpapers.textColor
        font.family: wallpapers.iconFont.family
        font.weight: wallpapers.iconFont.weight
        font.pixelSize: wallpapers.iconSize
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                wallpapers.toggleGallery()
            else
                library.setRandomWallpaper()
        }
    }

    Component {
        id: gallery

        Window {
            id: window

            required property string screenName
            required property rect area
            property real reveal: 0
            // 0 with every thumbnail behind the current wallpaper, 1 with them in their places
            property real spread: 0
            property bool sliding: false
            property bool moved: false
            // Animations start with the first frame on screen, which a new window takes a moment to show
            property bool shown: false

            function fanOutOnce() {
                if (shown && spread === 0 && carousel.count > 0 && !fanOut.running && !fadeOut.running)
                    fanOut.start()
            }

            function dismiss() {
                if (fadeOut.running)
                    return
                fadeIn.stop()
                fanOut.stop()
                fadeOut.start()
            }

            function apply(path: string, screen: int) {
                if (screen < 0)
                    library.setWallpaper(path)
                else
                    library.setWallpaperOn(path, screen)
                dismiss()
            }

            function showCurrent() {
                sliding = false
                carousel.target = Math.max(0, library.currentIndex(screenName))
                carousel.place()
                Qt.callLater(() => sliding = true)
                fanOutOnce()
            }

            flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            color: "transparent"
            x: area.x
            y: area.y
            width: area.width
            height: area.height

            Component.onCompleted: {
                visible = true
                requestActivate()
                if (library.images.length > 0)
                    showCurrent()
            }

            onFrameSwapped: {
                if (shown)
                    return
                shown = true
                fadeIn.start()
                fanOutOnce()
            }

            onActiveChanged: {
                if (!active && !menu.opened)
                    dismiss()
            }

            onVisibleChanged: {
                if (visible)
                    return
                wallpapers.opened = null
                destroy()
            }

            Connections {
                target: library
                // Again once the carousel has taken the new list, which resets its offset
                function onImagesChanged() {
                    window.showCurrent()
                    Qt.callLater(window.showCurrent)
                }
                function onCurrentChanged() {
                    if (!window.moved)
                        window.showCurrent()
                }
            }

            NumberAnimation {
                id: fadeIn

                target: window
                property: "reveal"
                to: 1
                duration: wallpapers.animationDuration
            }

            NumberAnimation {
                id: fanOut

                target: window
                property: "spread"
                to: 1
                duration: wallpapers.openDuration
                easing.type: Easing.OutCubic
            }

            SequentialAnimation {
                id: fadeOut

                ParallelAnimation {
                    NumberAnimation {
                        target: window
                        property: "spread"
                        to: 0
                        duration: wallpapers.animationDuration * 2
                        easing.type: Easing.InCubic
                    }

                    NumberAnimation {
                        target: window
                        property: "reveal"
                        to: 0
                        duration: wallpapers.animationDuration * 2
                        easing.type: Easing.InQuad
                    }
                }

                ScriptAction {
                    script: window.close()
                }
            }

            // Windows clicks through fully clear pixels
            Rectangle {
                anchors.fill: parent
                color: Qt.alpha("#000000", 0.01)
            }

            Item {
                anchors.fill: parent
                opacity: window.reveal

                PathView {
                    id: carousel

                    readonly property real step: wallpapers.thumbnailWidth + wallpapers.spacing
                    readonly property real near: wallpapers.thumbnailWidth * (wallpapers.selectedScale + 1) / 2 + wallpapers.spacing
                    readonly property int fits: 2 * Math.ceil(Math.max(0, width / 2 - near) / step) + 5
                    readonly property real side: Math.max(0, 0.5 - 1 / Math.max(1, pathItemCount))
                    readonly property real reach: Math.max(0, pathItemCount / 2 - 1) * step
                    readonly property int page: Math.max(1, Math.floor((width / 2 - near) / step) + 1)
                    // Never quite 0, since a path without length gives the thumbnails no scale
                    readonly property real open: Math.max(0.001, window.spread)
                    // Counted on past the last wallpaper, so the carousel slides the short way round
                    property real target: 0
                    property real position: target
                    readonly property int selected: count > 0 ? (Math.round(target) % count + count) % count : -1

                    Behavior on position {
                        enabled: window.sliding

                        SmoothedAnimation {
                            velocity: wallpapers.slideSpeed
                        }
                    }

                    function selectedPath(): string {
                        return selected >= 0 ? library.images[selected].path : ""
                    }

                    // A held key stays at most one step ahead, so the carousel slides evenly and stops on key release
                    function move(steps: int, held: bool) {
                        window.moved = true
                        if (count > 0 && !(held && Math.abs(target - position) >= 1))
                            target += steps
                    }

                    function select(index: int) {
                        window.moved = true
                        if (count === 0)
                            return
                        const ahead = ((index - selected) % count + count) % count
                        target += ahead > count / 2 ? ahead - count : ahead
                    }

                    // PathView puts wallpaper i at (i + offset) / pathItemCount along the path
                    function place() {
                        if (count > 0)
                            offset = ((pathItemCount / 2 - position) % count + count) % count
                    }

                    onPositionChanged: place()
                    onPathItemCountChanged: place()

                    objectName: "wallpapers"
                    anchors.fill: parent
                    focus: true
                    interactive: false
                    model: library.images
                    delegate: wallpapers.thumbnail
                    pathItemCount: Math.min(count, fits)
                    highlightRangeMode: PathView.NoHighlightRange

                    path: Path {
                        startX: carousel.width / 2 - (carousel.near + carousel.reach) * carousel.open
                        startY: carousel.height / 2

                        PathAttribute { name: "itemScale"; value: 1 }
                        PathLine { x: carousel.width / 2 - carousel.near * carousel.open; y: carousel.height / 2 }
                        PathPercent { value: carousel.side }
                        PathAttribute { name: "itemScale"; value: 1 }
                        PathLine { x: carousel.width / 2; y: carousel.height / 2 }
                        PathPercent { value: 0.5 }
                        PathAttribute { name: "itemScale"; value: wallpapers.selectedScale }
                        PathLine { x: carousel.width / 2 + carousel.near * carousel.open; y: carousel.height / 2 }
                        PathPercent { value: 1 - carousel.side }
                        PathAttribute { name: "itemScale"; value: 1 }
                        PathLine { x: carousel.width / 2 + (carousel.near + carousel.reach) * carousel.open; y: carousel.height / 2 }
                        PathAttribute { name: "itemScale"; value: 1 }
                    }

                    Keys.onEscapePressed: window.dismiss()
                    Keys.onReturnPressed: if (selectedPath()) window.apply(selectedPath(), -1)
                    Keys.onEnterPressed: if (selectedPath()) window.apply(selectedPath(), -1)
                    Keys.onPressed: event => {
                        if (event.key === Qt.Key_Left)
                            move(-1, event.isAutoRepeat)
                        else if (event.key === Qt.Key_Right)
                            move(1, event.isAutoRepeat)
                        else if (event.key === Qt.Key_PageUp)
                            move(-page, event.isAutoRepeat)
                        else if (event.key === Qt.Key_PageDown)
                            move(page, event.isAutoRepeat)
                        else if (event.key === Qt.Key_Home)
                            select(0)
                        else if (event.key === Qt.Key_End)
                            select(count - 1)
                        else
                            return
                        event.accepted = true
                    }
                }

                // Only a double click or the menu acts, on the thumbnail pointed at
                MouseArea {
                    anchors.fill: carousel
                    acceptedButtons: Qt.LeftButton | Qt.RightButton

                    onDoubleClicked: mouse => {
                        const index = carousel.indexAt(mouse.x, mouse.y)
                        if (mouse.button === Qt.LeftButton && index >= 0)
                            window.apply(library.images[index].path, -1)
                    }
                    onClicked: mouse => {
                        const index = carousel.indexAt(mouse.x, mouse.y)
                        if (mouse.button !== Qt.RightButton || index < 0)
                            return
                        carousel.select(index)
                        menu.path = library.images[index].path
                        menu.screens = library.screenCount()
                        menu.popup()
                    }
                    onWheel: wheel => {
                        const delta = wheel.angleDelta.y || wheel.angleDelta.x
                        if (delta !== 0)
                            carousel.move(delta > 0 ? -1 : 1, true)
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: carousel.count === 0
                    text: library.scanning ? qsTr("Looking for wallpapers...") : qsTr("No wallpapers found")
                    color: "#ffffff"
                    font.pixelSize: 13
                }
            }

            Menu {
                id: menu

                property string path
                property int screens: 0

                popupType: Popup.Window
                onClosed: {
                    if (!window.active)
                        window.dismiss()
                }

                MenuItem {
                    text: qsTr("Set on all screens")
                    onTriggered: window.apply(menu.path, -1)
                }

                MenuSeparator {
                    visible: menu.screens > 1
                }

                Instantiator {
                    model: menu.screens > 1 ? menu.screens : 0
                    onObjectAdded: (index, item) => menu.insertItem(index + 2, item)
                    onObjectRemoved: (index, item) => menu.removeItem(item)

                    MenuItem {
                        required property int index

                        text: qsTr("Set on screen %1").arg(index + 1)
                        onTriggered: window.apply(menu.path, index)
                    }
                }
            }
        }
    }
}
