import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Themes

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
    // The widget's theme; the controls in the popup take their accent and text colours from it
    required property Theme theme
    // The font every Label and control in the popup takes, the widget's popupFont
    property font font
    // The item the blur follows, with its position, size, rounded corners and opacity
    property Item backdropItem: null
    // Animations a widget can set; the popup runs `enter` after it shows and `exit` before it hides
    property Animation enter: null
    property Animation exit: null
    // A pinned popup stays open when it loses focus or the bar is pressed; close() and Escape still close it
    property bool pinned: false
    // While `exit` runs
    property bool closing: false
    // Windows can take focus away for a moment while the popup shows
    property bool opening: false
    // Frames left until the window hides, so the closed state is drawn first
    property int framesUntilHidden: 0
    property alias visible: popupWindow.visible
    property alias title: popupWindow.title
    property alias color: popupWindow.color

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

    readonly property PopupGraphics graphics: PopupGraphics {
        window: popup.window
    }

    readonly property Window window: Window {
        id: popupWindow

        readonly property real roomX: Math.round(popup.side === "left" ? popup.windowWidth - popup.width
            : popup.side === "right" ? 0 : (popup.windowWidth - popup.width) / 2)
        readonly property real roomY: Math.round(popup.side === "above" ? popup.windowHeight - popup.height
            : popup.side === "below" ? 0 : (popup.windowHeight - popup.height) / 2)
        readonly property rect frame: Qt.rect(Math.round(popup.x) - roomX, Math.round(popup.y) - roomY,
            Math.ceil(Math.max(popup.windowWidth, popup.width)), Math.ceil(Math.max(popup.windowHeight, popup.height)))

        // A window owned by the bar would be destroyed by Windows together with it, before QML cleans up
        transientParent: null
        flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
        color: "transparent"
        // Active and inactive only, so disabled controls keep the style's dimmed colours
        palette.active.accent: popup.theme.colors.accent
        palette.active.text: popup.theme.colors.text
        palette.active.windowText: popup.theme.colors.text
        palette.active.buttonText: popup.theme.colors.text
        palette.inactive.accent: popup.theme.colors.accent
        palette.inactive.text: popup.theme.colors.text
        palette.inactive.windowText: popup.theme.colors.text
        palette.inactive.buttonText: popup.theme.colors.text
        x: frame.x
        y: frame.y
        width: frame.width
        height: frame.height

        onActiveChanged: {
            if (!active && !popup.opening && !popup.pinned) {
                Qt.callLater(() => {
                    if (popupWindow.visible && !popupWindow.active && !popup.opening && !popup.pinned && !popup.anchor?.Window.active)
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
        // Windows shows a window's last drawn frame again when it reopens
        onAfterAnimating: {
            if (popup.framesUntilHidden === 0)
                return
            if (--popup.framesUntilHidden === 0) {
                // Hidden after this signal: giving back the graphics inside it hangs the app
                Qt.callLater(() => {
                    if (popup.closing)
                        popupWindow.hide()
                })
            } else {
                popupWindow.update()
            }
        }

        // A press in the room around the popup counts as a press outside it
        MouseArea {
            anchors.fill: parent
            onPressed: mouse => {
                mouse.accepted = false
                if (!popup.pinned && !body.contains(mapToItem(body, mouse.x, mouse.y)))
                    popup.close()
            }
        }

        // A Control, so every Label and control in the popup takes the popup's font
        Control {
            id: body

            font: popup.font
            x: popupWindow.roomX
            y: popupWindow.roomY
            width: popup.width
            height: popup.height
        }

        Shortcut {
            sequence: "Escape"
            enabled: popupWindow.visible
            onActivated: popup.close()
        }
    }

    function open() {
        exit?.stop()
        closing = false
        framesUntilHidden = 0
        opening = true
        side = sideOfAnchor()
        makeRoom()
        // Windows rescales only visible windows, so one hidden during a scale change is sized again here
        popupWindow.setWidth(popupWindow.frame.width)
        popupWindow.setHeight(popupWindow.frame.height)
        popupWindow.setX(popupWindow.frame.x)
        popupWindow.setY(popupWindow.frame.y)
        popupWindow.show()
        popupWindow.requestActivate()
        enter?.restart()
        Qt.callLater(() => opening = false)
    }

    function close() {
        if (!popupWindow.visible || closing)
            return
        enter?.stop()
        if (exit) {
            closing = true
            exit.restart()
        } else {
            popupWindow.hide()
        }
    }


    function hide() {
        popupWindow.hide()
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
        const screen = anchor ? anchor.Screen : popupWindow.screen
        const paddedWidth = Math.max(width, Math.min(width + 100, screen ? screen.width : width + 100))
        const paddedHeight = Math.max(height, Math.min(height + 100, screen ? screen.height : height + 100))
        if (!popupWindow.visible) {
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
            if (popup.closing) {
                popup.framesUntilHidden = 2
                popupWindow.update()
            }
        }
    }

    // The bar never takes focus, so presses on it come from the bar window instead of onActiveChanged
    property Connections barPressed: Connections {
        target: popup.bar
        ignoreUnknownSignals: true

        function onPressed(position: point) {
            const anchor = popup.anchor
            if (popupWindow.visible && !popup.pinned && !(anchor && anchor.contains(anchor.mapFromItem(null, position))))
                popup.close()
        }
    }
}
