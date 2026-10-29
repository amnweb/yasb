import QtQuick
import Yasb

// A popup in a window of its own, blurred behind `backdropItem` when its bar has a backdrop. `x`, `y`,
// `width` and `height` are the popup on screen. It closes on Escape, when it loses focus and when the bar is
// pressed outside `anchor`.
QtObject {
    id: popup

    property real x: 0
    property real y: 0
    property real width: 0
    property real height: 0
    // The item that opens the popup, usually the widget; pressing it toggles instead of closing
    property Item anchor: null
    // The item the blur follows, with its position, size, rounded corners and opacity
    property Item backdropItem: null
    // Animations a widget can set; the popup runs `enter` after it shows and `exit` before it hides
    property Animation enter: null
    property Animation exit: null
    // While `exit` runs
    property bool closing: false
    // Windows can take focus away for a moment while the popup shows
    property bool opening: false
    property alias visible: window.visible
    property alias title: window.title
    property alias color: window.color

    default property alias content: body.data

    // Keep spare backing space so small content animations do not resize the native windows.
    // Retain allocated space through contractions and reopenings; only the visible body shrinks.
    property real windowWidth: 0
    property real windowHeight: 0
    // Where the popup sits next to its anchor, which is the side the room grows away from
    property string side: "below"

    // The bar window the anchor sits in
    readonly property QtObject bar: anchor?.Window.window ?? null

    readonly property Backdrop backdrop: Backdrop {
        bar: popup.bar
        item: popup.backdropItem
    }

    readonly property Window window: Window {
        id: window

        readonly property real roomX: Math.round(popup.side === "left" ? popup.windowWidth - popup.width
            : popup.side === "right" ? 0 : (popup.windowWidth - popup.width) / 2)
        readonly property real roomY: Math.round(popup.side === "above" ? popup.windowHeight - popup.height
            : popup.side === "below" ? 0 : (popup.windowHeight - popup.height) / 2)

        // A window owned by the bar would be destroyed by Windows together with it, before QML cleans up
        transientParent: null
        flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
        color: "transparent"
        x: Math.round(popup.x) - roomX
        y: Math.round(popup.y) - roomY
        width: Math.ceil(Math.max(popup.windowWidth, popup.width))
        height: Math.ceil(Math.max(popup.windowHeight, popup.height))

        onActiveChanged: {
            if (!active && !popup.opening) {
                Qt.callLater(() => {
                    if (window.visible && !window.active && !popup.opening && !popup.bar?.active)
                        popup.close()
                })
            }
        }
        // Qt's close() would destroy the native window, and the blur with it
        onClosing: event => {
            event.accepted = false
            popup.close()
        }
        onVisibleChanged: {
            if (!visible)
                popup.closing = false
        }

        // A press in the room around the popup counts as a press outside it
        MouseArea {
            anchors.fill: parent
            onPressed: mouse => {
                mouse.accepted = false
                if (!body.contains(mapToItem(body, mouse.x, mouse.y)))
                    popup.close()
            }
        }

        Item {
            id: body

            x: window.roomX
            y: window.roomY
            width: popup.width
            height: popup.height
        }

        Shortcut {
            sequence: "Escape"
            enabled: window.visible
            onActivated: popup.close()
        }
    }

    function open() {
        exit?.stop()
        closing = false
        opening = true
        side = sideOfAnchor()
        makeRoom()
        window.show()
        window.requestActivate()
        enter?.restart()
        Qt.callLater(() => opening = false)
    }

    function close() {
        if (!window.visible || closing)
            return
        enter?.stop()
        if (exit) {
            closing = true
            exit.restart()
        } else {
            window.hide()
        }
    }


    function hide() {
        window.hide()
    }

    function sideOfAnchor(): string {
        if (!anchor)
            return "below"
        const start = anchor.mapToGlobal(0, 0)
        if (y >= start.y + anchor.height)
            return "below"
        if (y + height <= start.y)
            return "above"
        return x >= start.x + anchor.width ? "right" : "left"
    }

    function makeRoom() {
        const screen = anchor ? anchor.Screen : window.screen
        const paddedWidth = Math.max(width, Math.min(width + 100, screen ? screen.width : width + 100))
        const paddedHeight = Math.max(height, Math.min(height + 100, screen ? screen.height : height + 100))
        if (!window.visible) {
            windowWidth = Math.max(windowWidth, paddedWidth)
            windowHeight = Math.max(windowHeight, paddedHeight)
            return
        }
        if (width > windowWidth)
            windowWidth = Math.max(paddedWidth, Math.min(windowWidth * 2, screen ? screen.width : paddedWidth))
        if (height > windowHeight)
            windowHeight = Math.max(paddedHeight, Math.min(windowHeight * 2, screen ? screen.height : paddedHeight))
    }

    onWidthChanged: makeRoom()
    onHeightChanged: makeRoom()

    property Connections exitFinished: Connections {
        target: popup.exit

        function onFinished() {
            if (popup.closing)
                window.hide()
        }
    }

    // The bar never takes focus, so presses on it come from the bar window instead of onActiveChanged
    property Connections barPressed: Connections {
        target: popup.bar
        ignoreUnknownSignals: true

        function onPressed(position: point) {
            const anchor = popup.anchor
            if (window.visible && !(anchor && anchor.contains(anchor.mapFromItem(null, position))))
                popup.close()
        }
    }
}
