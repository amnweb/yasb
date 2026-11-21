pragma ComponentBehavior: Bound

import QtQuick
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

// Every open window in a row, front to back, to bring one to the front. A click on the glyph or the hotkey opens it.
Item {
    id: switcher

    component Settings: QtObject {
        required property Theme theme

        // Hotkey that opens the switcher, such as "alt+w". With a modifier it works like Alt+Tab: hold alt and press w
        // to move on, let go of alt to switch
        property string hotkey: ""
        // active, cursor or primary: which screen's widget opens on the hotkey
        property string hotkeyScreen: "active"
        // Pixels of each window's icon; with previews a small one sits beside the title instead
        property int appIconSize: 48
        property int previewIconSize: 16
        // The most windows side by side before the row scrolls, 1 or more; the row never takes more than 90% of the screen
        property int maxVisibleApps: 8
        // The selected window's title under the row
        property bool showTitle: true
        // A live picture of each window under its title
        property bool preview: false
        // Pixels of each picture's width, 100 to 360; its height is 9/16 of it
        property int previewWidth: 240
        // The glyph on the bar, drawn in iconFont and the text colour
        property string icon: "\uf156"
        property int iconSize: theme.bar.iconFont.pixelSize

        property color textColor: theme.colors.text
        // Glyphs take the theme's icon font, each part unless the widget file sets it
        property font iconFont
        iconFont.family: theme.bar.iconFont.family
        iconFont.weight: theme.bar.iconFont.weight
        iconFont.variableAxes: theme.bar.iconFont.variableAxes
        // The popup: the theme's, unless set here
        property color popupColor: theme.popup.background
        property color popupBorderColor: theme.popup.border
        property color popupTextColor: theme.colors.text
        property color popupDividerColor: theme.colors.divider
        property color popupSelectedColor: theme.colors.selected
        property color accentColor: theme.colors.accent
        property real popupRadius: theme.popup.radius
        property int popupOpenDuration: theme.popup.openDuration
        property int popupCloseDuration: theme.popup.closeDuration
        // Pixels around the row, around each window and inside it, and of the selected window's border
        property int popupPadding: 10
        property int itemSpacing: 5
        property int itemPadding: 10
        property real itemRadius: 8
        property int selectionBorderWidth: 2
        // Each window's title beside its icon when previews show, in the theme's font family
        property font popupFont
        popupFont.family: theme.popup.font.family
        popupFont.pixelSize: 13
        // The selected window's title under the row
        property font windowTitleFont
        windowTitleFont.family: theme.popup.font.family
        windowTitleFont.pixelSize: 12
        windowTitleFont.weight: 600
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: switcher.theme
    }

    // The windows shown, by hwnd, front to back as they were when the switcher opened
    property var order: []
    property int current: -1
    // The modifier keys held when the switcher opened, as with a hotkey like "alt+w": letting go of them switches
    property int holdModifiers: 0
    // Where the cursor last moved, so a popup opening under a cursor that stays still selects nothing
    property point cursor: Qt.point(-1, -1)

    readonly property var byHwnd: {
        const windows = {}
        for (const window of windowList.windows)
            windows[window.hwnd] = window
        return windows
    }
    readonly property real cellWidth: (settings.preview ? settings.previewWidth : settings.appIconSize) + 2 * (settings.itemPadding + settings.selectionBorderWidth + settings.itemSpacing)
    readonly property real cellHeight: (settings.preview ? Math.max(settings.previewIconSize, previewMetrics.height) + 6 + Math.round(settings.previewWidth * 9 / 16)
        : settings.appIconSize) + 2 * (settings.itemPadding + settings.selectionBorderWidth + settings.itemSpacing)
    readonly property int visibleCount: Math.max(1, Math.min(order.length, settings.maxVisibleApps,
        Math.floor((Screen.width * 0.95 - 2 * settings.popupPadding) / cellWidth)))

    implicitWidth: label.width
    implicitHeight: label.height

    function toggle() {
        if (popup.visible && !popup.closing) {
            if (holdModifiers && order.length)
                select((current + 1) % order.length, false)
            else
                popup.close()
            return
        }
        holdModifiers = windowList.keyboardModifiers()
        // A quick tap can let go of the modifiers before the popup has the keyboard and sees it
        if (open() && holdModifiers)
            Qt.callLater(switchIfReleased)
    }

    function open(): bool {
        const windows = windowList.windows
        if (!windows.length)
            return false
        order = windows.map(window => window.hwnd)
        // The window behind the one in front, read before the popup takes the foreground
        const start = order.length > 1 && windowList.inFront(order[0]) ? 1 : 0
        current = -1
        cursor = Qt.point(-1, -1)
        popup.open()
        windowList.takeFocus(popup.window)
        keys.forceActiveFocus()
        select(start, false)
        return true
    }

    function select(index: int, byMouse: bool) {
        if (index < 0 || index >= order.length)
            return
        current = index
        if (!byMouse) {
            row.forceLayout()
            row.positionViewAtIndex(index, ListView.Contain)
        }
    }

    function switchIfReleased() {
        if (!holdModifiers || windowList.keyboardModifiers() & holdModifiers)
            return
        if (current >= 0 && current < order.length)
            switchTo(order[current])
    }

    function switchTo(hwnd: int) {
        holdModifiers = 0
        popup.close()
        windowList.switchTo(hwnd)
    }

    function closeWindow(hwnd: int) {
        windowList.close(hwnd)
        const index = order.indexOf(hwnd)
        if (index >= 0)
            keep(order.filter(other => other !== hwnd), Math.min(index, order.length - 2))
    }

    // Shows only these windows and selects this place among them, or closes when none are left
    function keep(hwnds: var, index: int) {
        order = hwnds
        if (!hwnds.length)
            popup.close()
        else
            select(Math.max(0, index), false)
    }

    TextMetrics {
        id: previewMetrics

        font: switcher.settings.popupFont
        text: "Hg"
    }

    Text {
        id: label

        y: Math.round((parent.height - height) / 2)
        width: switcher.settings.iconSize
        height: switcher.settings.iconSize
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        text: switcher.settings.icon
        color: switcher.settings.textColor
        font.family: switcher.settings.iconFont.family
        font.weight: switcher.settings.iconFont.weight
        font.variableAxes: switcher.settings.iconFont.variableAxes
        font.pixelSize: switcher.settings.iconSize
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: switcher.toggle()
    }

    Hotkey {
        keys: switcher.settings.hotkey
        screen: switcher.settings.hotkeyScreen
        onActivated: switcher.toggle()
    }

    WindowList {
        id: windowList

        // A window that closed while the switcher shows leaves the row
        onWindowsChanged: {
            if (!popup.visible)
                return
            const live = new Set(windowList.windows.map(window => window.hwnd))
            const kept = switcher.order.filter(hwnd => live.has(hwnd))
            if (kept.length === switcher.order.length)
                return
            const selected = kept.indexOf(switcher.order[switcher.current])
            switcher.keep(kept, selected >= 0 ? selected : Math.min(switcher.current, kept.length - 1))
        }
    }

    Component.onDestruction: popup.hide()

    BackdropPopup {
        id: popup

        property real reveal: 0

        title: "Window Switcher"
        width: surface.implicitWidth
        height: surface.implicitHeight
        x: Math.round(switcher.Screen.virtualX + (switcher.Screen.width - width) / 2)
        y: Math.round(switcher.Screen.virtualY + (switcher.Screen.height - height) / 2)
        anchor: switcher
        font: switcher.settings.popupFont
        theme: switcher.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: switcher.settings.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: switcher.settings.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible) {
                reveal = 0
                switcher.holdModifiers = 0
                // Emptying the row drops the window thumbnails
                switcher.order = []
                switcher.current = -1
            }
        }

        Rectangle {
            id: surface

            anchors.fill: parent
            implicitWidth: content.implicitWidth + 2 * switcher.settings.popupPadding
            implicitHeight: content.implicitHeight + 2 * switcher.settings.popupPadding
            radius: switcher.settings.popupRadius
            color: switcher.settings.popupColor
            border.width: 1
            border.color: switcher.settings.popupBorderColor
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            // Nothing takes a key or click while the popup fades
            enabled: !popup.closing

            // A notch scrolls the row by one window
            WheelHandler {
                onWheel: event => {
                    const step = event.angleDelta.y < 0 ? switcher.cellWidth : -switcher.cellWidth
                    row.contentX = Math.max(0, Math.min(row.contentWidth - row.width, row.contentX + step))
                }
            }

            Item {
                id: keys

                focus: true
                Keys.onPressed: event => {
                    const last = switcher.order.length - 1
                    if (event.key === Qt.Key_Escape) {
                        switcher.holdModifiers = 0
                        popup.close()
                    } else if (event.key === Qt.Key_Right) {
                        switcher.select(Math.min(switcher.current + 1, last), false)
                    } else if (event.key === Qt.Key_Left) {
                        switcher.select(Math.max(switcher.current - 1, 0), false)
                    } else if (event.key === Qt.Key_Delete) {
                        if (switcher.current >= 0)
                            switcher.closeWindow(switcher.order[switcher.current])
                    } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) {
                        if (switcher.current >= 0)
                            switcher.switchTo(switcher.order[switcher.current])
                    } else {
                        return
                    }
                    event.accepted = true
                }
                Keys.onReleased: switcher.switchIfReleased()
            }

            Column {
                id: content

                x: switcher.settings.popupPadding
                y: switcher.settings.popupPadding

                ListView {
                    id: row

                    width: switcher.cellWidth * switcher.visibleCount
                    height: switcher.cellHeight
                    orientation: ListView.Horizontal
                    interactive: false
                    clip: true
                    model: switcher.order

                    delegate: Item {
                        id: cell

                        required property int modelData
                        required property int index
                        readonly property var window: switcher.byHwnd[modelData] ?? null
                        readonly property bool selected: index === switcher.current

                        width: switcher.cellWidth
                        height: switcher.cellHeight

                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: switcher.settings.itemSpacing
                            radius: switcher.settings.itemRadius
                            color: cell.selected ? switcher.settings.popupSelectedColor : "transparent"
                            border.width: switcher.settings.selectionBorderWidth
                            border.color: cell.selected ? switcher.settings.accentColor : "transparent"

                            Image {
                                visible: !switcher.settings.preview
                                anchors.centerIn: parent
                                width: switcher.settings.appIconSize
                                height: switcher.settings.appIconSize
                                sourceSize: Qt.size(switcher.settings.appIconSize, switcher.settings.appIconSize)
                                source: !switcher.settings.preview ? cell.window?.icon ?? "" : ""
                            }

                            Column {
                                visible: switcher.settings.preview
                                x: switcher.settings.itemPadding + switcher.settings.selectionBorderWidth
                                y: switcher.settings.itemPadding + switcher.settings.selectionBorderWidth
                                spacing: 6

                                Row {
                                    width: switcher.settings.previewWidth
                                    height: Math.max(switcher.settings.previewIconSize, previewMetrics.height)
                                    spacing: 6

                                    Image {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: switcher.settings.previewIconSize
                                        height: switcher.settings.previewIconSize
                                        sourceSize: Qt.size(switcher.settings.previewIconSize, switcher.settings.previewIconSize)
                                        source: switcher.settings.preview ? cell.window?.icon ?? "" : ""
                                    }

                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width - switcher.settings.previewIconSize - parent.spacing
                                        text: cell.window?.title ?? ""
                                        color: switcher.settings.popupTextColor
                                        font: switcher.settings.popupFont
                                        elide: Text.ElideRight
                                    }
                                }

                                Item {
                                    width: switcher.settings.previewWidth
                                    height: Math.round(switcher.settings.previewWidth * 9 / 16)

                                    WindowThumbnail {
                                        readonly property real aspect: sourceWidth > 0 && sourceHeight > 0
                                            ? sourceWidth / sourceHeight : parent.width / parent.height

                                        anchors.centerIn: parent
                                        width: Math.min(parent.width, parent.height * aspect)
                                        height: width / aspect
                                        hwnd: switcher.settings.preview ? cell.modelData : 0
                                    }
                                }
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            onPositionChanged: mouse => {
                                const point = mapToGlobal(mouse.x, mouse.y)
                                const moved = switcher.cursor.x >= 0 && (point.x !== switcher.cursor.x || point.y !== switcher.cursor.y)
                                switcher.cursor = point
                                if (moved && !cell.selected)
                                    switcher.select(cell.index, true)
                            }
                            onClicked: mouse => {
                                if (mouse.button === Qt.RightButton)
                                    switcher.closeWindow(cell.modelData)
                                else
                                    switcher.switchTo(cell.modelData)
                            }
                        }
                    }
                }

                Item {
                    visible: switcher.settings.showTitle
                    width: row.width
                    height: 10
                }

                Rectangle {
                    visible: switcher.settings.showTitle
                    width: row.width
                    height: 1
                    color: switcher.settings.popupDividerColor
                }

                Text {
                    visible: switcher.settings.showTitle
                    width: row.width
                    topPadding: 10
                    bottomPadding: 5
                    leftPadding: 10
                    rightPadding: 10
                    horizontalAlignment: Text.AlignHCenter
                    text: switcher.byHwnd[switcher.order[switcher.current]]?.title ?? " "
                    color: switcher.settings.popupTextColor
                    font: switcher.settings.windowTitleFont
                    elide: Text.ElideRight
                }
            }
        }
    }
}
