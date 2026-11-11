pragma ComponentBehavior: Bound

import QtQuick
import Yasb

// Live thumbnails in a window that never takes focus from the app in front.
Window {
    id: previewWindow

    objectName: "previewWindow"

    required property Item host
    required property TaskbarApps backend
    required property var buttonsByKey
    required property var syncModel
    required property bool allowed
    required property bool peek
    required property int previewDelay
    required property int previewWidth
    required property bool animation
    required property int animationDuration
    required property string edge
    required property bool vertical
    required property bool dark
    required property color tint
    required property color attentionColor
    required property string fontFamily
    required property string iconFontFamily

    readonly property QtObject barWindow: host.Window.window
    readonly property color ink: dark ? "#ffffff" : "#000000"

    // The button whose previews show, by key, and the button the pointer is on
    property string previewKey: ""
    property Item hovered: null
    // The button whose previews wait to show, and one clicked, whose previews wait until the pointer leaves it
    property Item previewPending: null
    property Item clicked: null
    property rect previewAnchor
    property rect previewArea
    // The window peek shows, and the one it waits to show while the pointer settles on a preview
    property int peeking: 0
    property int peekPending: 0
    property real reveal: 0
    property real blend: 1
    property string outgoingKey: ""
    property size fromSize
    property size reservedSize
    // Waiting for a frame without the cards before hiding
    property bool hiding: false

    function hoverButton(button: Item, entered: bool) {
        if (entered) {
            hovered = button
        } else {
            // The pointer can reach the next button before it leaves this one
            if (hovered === button)
                hovered = null
            if (clicked === button)
                clicked = null
        }
        if (!allowed)
            return
        if (entered && button.running && clicked !== button) {
            previewHide.stop()
            previewPending = button
            // Moving between buttons while previews show switches without the hover delay.
            if (previewWindow.visible)
                showPreview()
            else
                previewShow.restart()
        } else if (hovered === null || !hovered.running) {
            previewShow.stop()
            if (previewWindow.visible)
                previewHide.restart()
        }
    }

    function showPreview() {
        const button = previewPending
        if (!button || !button.running || button !== hovered)
            return
        const start = button.mapToGlobal(0, 0)
        const screen = host.Screen
        previewAnchor = Qt.rect(start.x, start.y, button.width, button.height)
        // This screen; desktopAvailableHeight would be the height of all screens together
        previewArea = Qt.rect(screen.virtualX, screen.virtualY, screen.width, screen.height)
        previewWindow.setCards(button.key)
        previewWindow.revealCards()
    }

    function pressButton(button: Item) {
        // Its previews wait until the pointer leaves the button.
        clicked = button
        fadeOut()
    }

    // Hides the previews with their animation, as when the pointer leaves the button
    function fadeOut() {
        previewShow.stop()
        previewHide.stop()
        previewPending = null
        if (!previewWindow.visible || previewWindow.hiding) {
            dismiss()
            return
        }
        stopPeek()
        previewAnimation.to = 0
        previewAnimation.restart()
    }

    function dismiss() {
        previewShow.stop()
        previewHide.stop()
        previewPending = null
        stopPeek()
        previewAnimation.stop()
        previewWindow.reveal = 0
        previewWindow.setCards("")
        if (!previewWindow.visible) {
            hiding = false
            return
        }
        // Windows shows a window's last frame again when it shows, so it hides once a frame without the cards is on
        // screen; without that, the old previews flash before the new ones animate in
        hiding = true
        hideFallback.restart()
        previewWindow.requestUpdate()
    }

    function finishHiding() {
        if (!hiding)
            return
        hiding = false
        hideFallback.stop()
        previewWindow.hide()
    }

    // Peeks at a window once the pointer rests on its preview, and moves straight to another while peeking
    function peekCard(hwnd: int, entered: bool) {
        if (!peek || !backend.peekAvailable)
            return
        if (!entered) {
            if (hwnd === peekPending) {
                peekOn.stop()
                peekPending = 0
            }
            if (hwnd === peeking)
                peekOff.restart()
        } else if (peeking !== 0) {
            peekOff.stop()
            setPeek(hwnd)
        } else {
            peekOff.stop()
            peekPending = hwnd
            peekOn.restart()
        }
    }

    function setPeek(hwnd: int) {
        if (hwnd === peeking)
            return
        // The first window is the one DWM should keep above the app during Peek.
        backend.peek(hwnd, [previewWindow, barWindow])
        peeking = hwnd
    }

    function stopPeek() {
        peekOn.stop()
        peekOff.stop()
        peekPending = 0
        setPeek(0)
    }

    Timer {
        id: previewShow

        interval: previewWindow.previewDelay
        onTriggered: previewWindow.showPreview()
    }

    // Leaving a button for its previews crosses a gap, so they wait a moment before hiding
    Timer {
        id: previewHide

        interval: 300
        onTriggered: {
            if (previewWindow.visible && previewAnimation.to === 1 && !previewHover.hovered
                    && !(previewWindow.hovered?.running && previewWindow.hovered !== previewWindow.clicked)) {
                previewWindow.stopPeek()
                previewAnimation.to = 0
                previewAnimation.restart()
            }
        }
    }

    Timer {
        id: peekOn

        interval: 400
        onTriggered: {
            if (previewWindow.visible)
                previewWindow.setPeek(previewWindow.peekPending)
            previewWindow.peekPending = 0
        }
    }

    // Restoring the desktop waits a moment, so moving between previews does not bounce it back
    Timer {
        id: peekOff

        interval: 60
        onTriggered: previewWindow.setPeek(0)
    }

    // Hides the window even when no frame comes, such as while the bar is hidden
    Timer {
        id: hideFallback

        interval: 100
        onTriggered: previewWindow.finishHiding()
    }

    onFrameSwapped: finishHiding()

    Connections {
        target: previewWindow.barWindow

        function onVisibleChanged() {
            if (!previewWindow.barWindow?.visible)
                previewWindow.dismiss()
        }
    }

    ListModel {
        id: previewGroups
    }

    // Move along the bar, then clamp the preview's position using its current size.
    property real anchorPosition: previewWindow.vertical ? previewWindow.previewAnchor.y
        : previewWindow.previewAnchor.x + previewWindow.previewAnchor.width / 2
    Behavior on anchorPosition {
        enabled: previewWindow.visible && previewWindow.animation
        NumberAnimation { duration: Math.min(150, previewWindow.animationDuration); easing.type: Easing.OutCubic }
    }
    readonly property var windows: previewWindow.buttonsByKey[previewWindow.previewKey]?.windows ?? []
    readonly property int gap: 8
    readonly property int cardWidth: previewWindow.previewWidth
    readonly property int thumbHeight: Math.round(cardWidth * 9 / 16)
    readonly property int cardHeight: thumbHeight + 42
    // As many previews in a row as fit on the screen, then more rows
    readonly property int columns: columnsFor(windows.length)
    readonly property int rows: Math.max(1, Math.ceil(windows.length / columns))
    readonly property int targetWidth: columns * (cardWidth + 4) + 8
    readonly property int targetHeight: rows * (cardHeight + 4) + 8

    function columnsFor(count: int): int {
        return Math.max(1, Math.min(count, Math.floor((previewWindow.previewArea.width - 40) / (cardWidth + 4))))
    }

    function setCards(key: string) {
        if (key === previewWindow.previewKey)
            return
        switchAnimation.stop()
        const animated = key !== "" && previewWindow.animation && previewWindow.animationDuration > 0
        if (visible && animated) {
            previewWindow.stopPeek()
            fromSize = Qt.size(surface.width, surface.height)
            reservedSize = Qt.size(width, height)
            if (!outgoingKey || blend >= 0.5 || outgoingKey === key)
                outgoingKey = previewWindow.previewKey
            blend = 0
            previewWindow.previewKey = key
            previewWindow.syncModel(previewGroups, [outgoingKey, key])
            switchAnimation.start()
        } else {
            if (animated) {
                // Allocate before showing so a wider group can expand inside the same native window.
                const count = Object.values(previewWindow.buttonsByKey).reduce((largest, button) => Math.max(largest, button.windows.length), 1)
                const columns = columnsFor(count)
                const rows = Math.ceil(count / columns)
                reservedSize = Qt.size(columns * (cardWidth + 4) + 8,
                    Math.min(rows * (cardHeight + 4) + 8, previewWindow.previewArea.height - 16))
            }
            previewWindow.previewKey = key
            finishSwitch()
        }
    }

    function finishSwitch() {
        blend = 1
        outgoingKey = ""
        if (previewWindow.previewKey === "")
            reservedSize = Qt.size(0, 0)
        previewWindow.syncModel(previewGroups, previewWindow.previewKey ? [previewWindow.previewKey] : [])
    }

    function revealCards() {
        if (visible && previewAnimation.to === 1 && !hiding)
            return
        // A preview asked for again before the window hid keeps it
        hiding = false
        hideFallback.stop()
        previewAnimation.to = 1
        show()
        previewAnimation.restart()
    }

    // Hides the previews once their app has no windows left, unless one came back meanwhile
    function dismissIfEmpty() {
        if (visible && windows.length === 0)
            dismiss()
    }

    onWindowsChanged: {
        // Qt drops the call if the preview is destroyed first, as when the bar closes
        if (visible && windows.length === 0)
            Qt.callLater(previewWindow.dismissIfEmpty)
    }

    transientParent: null
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
        | Qt.WindowDoesNotAcceptFocus
    color: "transparent"
    // Keep enough native space for both previews until the window hides.
    width: Math.max(targetWidth, reservedSize.width)
    height: Math.max(targetHeight, reservedSize.height)
    x: leftFor(width)
    y: topFor(height)

    function leftFor(size: real): int {
        const anchor = previewWindow.previewAnchor
        const area = previewWindow.previewArea
        const wanted = previewWindow.edge === "left" ? anchor.x + anchor.width + gap
            : previewWindow.edge === "right" ? anchor.x - size - gap : anchorPosition - size / 2
        return Math.round(Math.max(area.x + 8, Math.min(wanted, area.x + area.width - size - 8)))
    }

    function topFor(size: real): int {
        const anchor = previewWindow.previewAnchor
        const area = previewWindow.previewArea
        const wanted = previewWindow.edge === "bottom" ? anchor.y - size - gap
            : previewWindow.edge === "top" ? anchor.y + anchor.height + gap : anchorPosition
        return Math.round(Math.max(area.y + 8, Math.min(wanted, area.y + area.height - size - 8)))
    }

    NumberAnimation {
        id: previewAnimation

        target: previewWindow
        property: "reveal"
        to: 1
        duration: previewWindow.animation ? Math.min(to === 1 ? 180 : 140, previewWindow.animationDuration) : 0
        easing.type: to === 1 ? Easing.OutCubic : Easing.InCubic
        onFinished: { if (to === 0) previewWindow.dismiss() }
    }

    NumberAnimation {
        id: switchAnimation

        target: previewWindow
        property: "blend"
        to: 1
        duration: Math.min(150, previewWindow.animationDuration)
        easing.type: Easing.OutCubic
        onFinished: previewWindow.finishSwitch()
    }

    Backdrop {
        // Attach after the preview has opened with its topmost, non-activating flags.
        bar: previewWindow.visible ? previewWindow.barWindow : null
        item: surface
    }

    Rectangle {
        id: surface

        width: Math.round(previewWindow.fromSize.width * (1 - previewWindow.blend)
            + previewWindow.targetWidth * previewWindow.blend)
        height: Math.round(previewWindow.fromSize.height * (1 - previewWindow.blend)
            + previewWindow.targetHeight * previewWindow.blend)
        x: previewWindow.leftFor(width) - previewWindow.x
        y: previewWindow.topFor(height) - previewWindow.y
        clip: true
        radius: 8
        color: previewWindow.tint
        opacity: previewWindow.reveal
        scale: 0.85 + previewWindow.reveal * 0.15
        transformOrigin: previewWindow.edge === "bottom" ? Item.Bottom : previewWindow.edge === "left" ? Item.Left
            : previewWindow.edge === "right" ? Item.Right : Item.Top

        // Hover reaches an item and its parents only, so the cards sit inside this to keep it hovered
        HoverHandler {
            id: previewHover

            onHoveredChanged: {
                if (hovered) {
                    previewHide.stop()
                    previewWindow.revealCards()
                } else {
                    previewHide.restart()
                }
            }
        }

        Repeater {
            model: previewGroups
            delegate: PreviewCards {}
        }

        component PreviewCards: Flow {
            id: group

            required property string key
            readonly property var windows: previewWindow.buttonsByKey[key]?.windows ?? []
            readonly property var byHwnd: {
                const found = {}
                for (const window of windows)
                    found[String(window.hwnd)] = window
                return found
            }

            objectName: enabled ? "previewCards" : "outgoingPreviewCards"
            enabled: key === previewWindow.previewKey
            opacity: enabled ? previewWindow.blend : 1 - previewWindow.blend
            readonly property int columns: previewWindow.columnsFor(windows.length)
            width: columns * (previewWindow.cardWidth + 4) - 4
            height: Math.max(1, Math.ceil(windows.length / columns)) * (previewWindow.cardHeight + 4) - 4
            x: 6
            y: 6
            spacing: 4
            // Keep each group's card layout and stretch it with the panel during the crossfade.
            transform: Scale {
                xScale: (surface.width - 12) / group.width
                yScale: (surface.height - 12) / group.height
            }

            onWindowsChanged: previewWindow.syncModel(cards, windows.map(window => String(window.hwnd)))
            Component.onCompleted: previewWindow.syncModel(cards, windows.map(window => String(window.hwnd)))

            ListModel {
                id: cards
            }

            Repeater {
                model: cards

                delegate: Item {
                    id: card

                    required property string key
                    readonly property var info: group.byHwnd[key] ?? null
                    readonly property int hwnd: Number(key)

                    objectName: "preview"
                    width: previewWindow.cardWidth
                    height: previewWindow.cardHeight
                    Accessible.role: Accessible.Button
                    Accessible.name: info?.title ?? ""

                    Rectangle {
                        anchors.fill: parent
                        radius: 6
                        color: card.info?.flashing ? Qt.alpha(previewWindow.attentionColor, 0.28)
                            : Qt.alpha(previewWindow.ink, cardTap.pressed ? 0.04 : cardHover.hovered ? 0.0605 : 0)
                    }

                    Image {
                        x: 6
                        y: 9
                        source: card.info?.icon ?? ""
                        width: 16
                        height: 16
                        sourceSize: Qt.size(16, 16)
                    }

                    Text {
                        x: 30
                        width: card.width - 30 - 34
                        height: 34
                        verticalAlignment: Text.AlignVCenter
                        text: card.info?.title ?? ""
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: Qt.alpha(previewWindow.ink, 0.9)
                        font.family: previewWindow.fontFamily
                        font.pixelSize: 12
                    }

                    Rectangle {
                        id: closeButton

                        readonly property bool hovered: cardHover.hovered
                            && contains(mapFromItem(card, cardHover.point.position))

                        x: card.width - 28
                        y: 6
                        width: 22
                        height: 22
                        radius: 4
                        visible: cardHover.hovered
                        color: hovered ? "#C42B1C" : "transparent"

                        Text {
                            anchors.centerIn: parent
                            text: "\ue8bb"
                            color: closeButton.hovered ? "#ffffff" : Qt.alpha(previewWindow.ink, 0.786)
                            font.family: previewWindow.iconFontFamily
                            font.pixelSize: 10
                        }
                    }

                    Item {
                        x: 6
                        y: 34
                        width: card.width - 12
                        height: previewWindow.thumbHeight

                        WindowThumbnail {
                            readonly property real aspect: sourceWidth > 0 && sourceHeight > 0
                                ? sourceWidth / sourceHeight : parent.width / parent.height

                            anchors.centerIn: parent
                            width: Math.min(parent.width, parent.height * aspect)
                            height: width / aspect
                            hwnd: card.hwnd
                        }
                    }

                    HoverHandler {
                        id: cardHover

                        onHoveredChanged: previewWindow.peekCard(card.hwnd, hovered)
                    }

                    TapHandler {
                        id: cardTap

                        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                        onTapped: (point, mouseButton) => {
                            if (mouseButton === Qt.MiddleButton || closeButton.hovered) {
                                previewWindow.backend.close(card.hwnd)
                            } else {
                                previewWindow.dismiss()
                                previewWindow.backend.focus(card.hwnd)
                            }
                        }
                    }
                }
            }
        }
    }
}
