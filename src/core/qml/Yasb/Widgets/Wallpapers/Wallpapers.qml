pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Shapes
import Yasb
import Yasb.Bar
import Yasb.Themes

Item {
    id: wallpapers

    required property BarBase bar
    readonly property Theme theme: bar.theme
    // Folders searched for wallpapers, subfolders included; empty for your Pictures folder
    property list<string> folders: []
    // Transition before a wallpaper is set on every screen: circle, slide_top, diamond, split or "" for none
    property string animation: ""
    // Commands run through cmd.exe, out of sight, once a wallpaper is set, after its transition. {image} becomes
    // the image's path, so 'matugen image "{image}"' themes the bar from it. A command still running from the last
    // wallpaper is not run again.
    property list<string> runAfter: []
    property string icon: "\ue7aa"
    property int iconSize: theme.bar.iconFont.pixelSize
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
    property color accentColor: theme.colors.accent
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
            // itemScale is a PathAttribute of the carousel's path; Qt attaches it by name, which qmllint can't see
            readonly property real growth: Number.isFinite(PathView.itemScale) ? PathView.itemScale : 1 // qmllint disable missing-property
            readonly property real nearness: Math.max(0, Math.min(1, (growth - 1) / Math.max(0.01, wallpapers.selectedScale - 1)))
            readonly property real pixelRatio: Screen.devicePixelRatio || 1

            width: wallpapers.thumbnailWidth
            height: wallpapers.thumbnailHeight
            scale: growth
            z: growth

            Rectangle {
                anchors.fill: parent
                radius: wallpapers.cornerRadius
                color: wallpapers.placeholderColor
                visible: picture.status !== Image.Ready
            }

            WallpaperThumbnail {
                id: made

                readonly property real ratio: card.pixelRatio * wallpapers.selectedScale

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
                    // Adjust for scaling using pixelRatio
                    fillTransform: PlanarTransform.fromScale(card.width * card.pixelRatio / Math.max(1, picture.implicitWidth),
                        card.height * card.pixelRatio / Math.max(1, picture.implicitHeight))

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

    readonly property bool dark: theme.dark
    property color textColor: theme.colors.text
    property font iconFont
    iconFont.family: theme.bar.iconFont.family
    iconFont.weight: theme.bar.iconFont.weight
    iconFont.variableAxes: theme.bar.iconFont.variableAxes
    // A thumbnail still loading, and the gallery's message while there are none
    property color placeholderColor: Qt.alpha("#808080", 0.3)
    property color galleryTextColor: "#ffffff"
    // The popup: the theme's, unless set here
    // Text in the popup: the theme's font family, in this widget's sizes
    property font popupFont
    popupFont.family: theme.popup.font.family
    popupFont.pixelSize: 13
    // The right-click menu: its width, and a look that is the theme's unless set here
    property int menuWidth: 200
    property color menuColor: theme.menu.background
    property color menuBorderColor: theme.menu.border
    property color menuTextColor: theme.colors.text
    property real menuRadius: theme.menu.radius
    property font menuFont: theme.menu.font
    // Milliseconds the right-click menu takes to fade in
    property int menuOpenDuration: theme.menu.openDuration

    // Held so the garbage collector doesn't destroy the open gallery
    property Gallery opened: null

    // A bar rebuild, such as for a new theme, replaces this widget; an open gallery would outlive it, stuck on screen
    Component.onDestruction: opened?.destroy()

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
        }) as Gallery
    }

    WallpaperLibrary {
        id: library

        folders: wallpapers.folders
        animation: wallpapers.animation
        onWallpaperSet: path => {
            for (let i = 0; i < runAfterCommands.count; i++) {
                const process = runAfterCommands.objectAt(i) as Process
                process.command = wallpapers.runAfter[i].split("{image}").join(path)
                process.run()
            }
        }
    }

    Instantiator {
        id: runAfterCommands

        model: wallpapers.runAfter

        // A process for each command in runAfter
        delegate: Process {}
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
        font.variableAxes: wallpapers.iconFont.variableAxes
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

        Gallery {}
    }

    // The gallery: a window across the screen, with the thumbnails in a carousel
    component Gallery: Window {
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
        // The right-click menu that is open, if one is
        property Window menu: null

        function openMenu(path: string, position: point) {
            menu?.close()
            const screen = carousel.Screen
            menu = menuComponent.createObject(null, {
                path: path,
                screens: library.screenCount(),
                position: position,
                area: Qt.rect(screen.virtualX, screen.virtualY, screen.width, screen.height)
            })
        }

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
            // Not set while a transition still plays: the gallery stays for another try
            if (screen < 0 ? library.setWallpaper(path) : library.setWallpaperOn(path, screen))
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

        // Its own menu takes the activation while it is open; closing the menu decides about the gallery
        onActiveChanged: {
            if (!active && !menu)
                dismiss()
        }

        onVisibleChanged: {
            if (visible)
                return
            wallpapers.opened = null
            destroy()
        }

        Component.onDestruction: menu?.destroy()

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
                    // The menu acts on the thumbnail where it is: sliding it to the centre while the menu's window
                    // opens makes the slide stutter
                    window.openMenu(library.images[index].path, carousel.mapToGlobal(mouse.x, mouse.y))
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
                color: wallpapers.galleryTextColor
                font: wallpapers.popupFont
            }
        }

        Component {
            id: menuComponent

            // The menu sits in a window of its own, as the bar's other menus do: a popup window Qt makes for it is
            // resized while the menu animates open
            Window {
                id: menuHost

                required property string path
                required property int screens
                required property point position
                required property rect area
                // Closing because the menu was used or closed with Escape, not for a click elsewhere
                property bool done: false

                flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
                color: "transparent"
                width: menu.width
                height: menu.implicitHeight
                // At the click, inside the screen
                x: Math.round(Math.max(area.x, Math.min(position.x, area.x + area.width - width)))
                y: Math.round(Math.max(area.y, Math.min(position.y, area.y + area.height - height)))

                Component.onCompleted: {
                    if (screens > 1) {
                        // Made with the menu as their parent, so the garbage collector leaves them while it is open
                        menu.addItem(separatorComponent.createObject(menu.contentItem))
                        for (let index = 0; index < screens; index++)
                            menu.addItem(screenItemComponent.createObject(menu.contentItem, { index: index }))
                    }
                    // Measured before the window shows, so it doesn't open at one size and then change
                    (menu.contentItem as ListView)?.forceLayout()
                    show()
                    requestActivate()
                    menu.open()
                }
                onActiveChanged: {
                    if (!active)
                        close()
                }
                onVisibleChanged: {
                    if (visible)
                        return
                    if (window.menu === menuHost)
                        window.menu = null
                    // A click elsewhere closes the gallery as well, as it would without the menu
                    if (!done && !window.active)
                        window.dismiss()
                    destroy()
                }

                Component {
                    id: separatorComponent

                    MenuSeparator {}
                }

                Component {
                    id: screenItemComponent

                    MenuItem {
                        required property int index

                        text: qsTr("Set on screen %1").arg(index + 1)
                        onTriggered: window.apply(menuHost.path, index)
                    }
                }

                // Looks like the bar's own right-click menu
                Menu {
                    id: menu

                    font: wallpapers.menuFont
                    // Active and inactive only, so disabled controls keep the style's dimmed colours
                    palette.active.text: wallpapers.menuTextColor
                    palette.inactive.text: wallpapers.menuTextColor
                    topInset: 0
                    leftInset: 0
                    rightInset: 0
                    bottomInset: 0
                    popupType: Popup.Item
                    // Fades in when it opens, in place of the style's growing from a third of its height
                    enter: Transition {
                        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: wallpapers.menuOpenDuration; easing.type: Easing.OutCubic }
                    }
                    onClosed: {
                        // Used, or closed with Escape: the gallery gets the focus back
                        if (menuHost.active) {
                            menuHost.done = true
                            window.requestActivate()
                        }
                        menuHost.close()
                    }

                    background: Rectangle {
                        implicitWidth: wallpapers.menuWidth
                        radius: wallpapers.menuRadius
                        color: wallpapers.menuColor
                        border.color: wallpapers.menuBorderColor
                    }

                    MenuItem {
                        text: qsTr("Set on all screens")
                        onTriggered: window.apply(menuHost.path, -1)
                    }
                }
            }
        }
    }
}
