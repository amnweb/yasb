pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar
import Yasb.Common

Item {
    id: systray

    // Chevron glyph shown when the button has no label; rotated to point away from the bar edge.
    property string chevronIcon: ""
    // Button label; empty shows the chevron.
    property string labelCollapsed: ""
    property string labelExpanded: ""
    // Button side relative to pinned icons: left or right (top or bottom on a vertical bar).
    property string labelPosition: "left"
    property int iconSize: 16
    // Modifier used to pin or unpin an icon: ctrl, alt, or shift.
    property string pinModifier: "alt"
    property int iconsPerRow: 5
    // Popup alignment relative to the button: left, right, or center.
    property string popupAlignment: "center"
    // Windows' own battery, volume and network icons
    property bool showBattery: false
    property bool showVolume: false
    property bool showNetwork: false
    // Process names without .exe, matched case-insensitively (for example, ["discord"]).
    property list<string> hideIcons: []
    property bool tooltip: true
    // Use the Explorer hook instead of the legacy tray window; the first widget sets this for all bars.
    property bool useHook: true
    property color hoveredColor: dark ? Qt.alpha("#ffffff", 0.1) : Qt.alpha("#000000", 0.1)
    property BarBase bar: null

    readonly property bool dark: bar ? bar.dark : Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    // Inherit the bar's text color and font unless overridden here.
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    property font font
    font.family: bar?.font.family ?? Application.font.family
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
    readonly property color foreground: dark ? "#ebebeb" : "#1f1f1f"
    readonly property string edge: bar?.edge ?? "top"
    readonly property bool vertical: bar?.vertical ?? false

    readonly property int pinKey: {
        switch (pinModifier.toLowerCase()) {
        case "ctrl":
            return Qt.ControlModifier
        case "shift":
            return Qt.ShiftModifier
        default:
            return Qt.AltModifier
        }
    }
    readonly property string mimeType: "application/x-yasb-systray-icon"
    // While an icon is dragged, from the bar or the popup
    property bool dragging: false

    function clamp(value: real, low: real, high: real): real {
        return Math.max(low, Math.min(value, high))
    }

    // Place the popup beside the button, away from the bar edge and inside the screen.
    function placePopup() {
        const button = toggle.mapToGlobal(0, 0)
        const gap = 6
        const margin = 8
        let x
        let y
        switch (edge) {
        case "bottom":
            x = alignedPopupX(button.x)
            y = button.y - popup.height - gap
            break
        case "left":
            x = button.x + toggle.width + gap
            y = button.y + (toggle.height - popup.height) / 2
            break
        case "right":
            x = button.x - popup.width - gap
            y = button.y + (toggle.height - popup.height) / 2
            break
        default:
            x = alignedPopupX(button.x)
            y = button.y + toggle.height + gap
            break
        }
        const screen = systray.Screen
        const right = screen.virtualX + screen.width - popup.width - margin
        const bottom = screen.virtualY + screen.desktopAvailableHeight - popup.height - margin
        popup.x = Math.round(clamp(x, screen.virtualX + margin, right))
        popup.y = Math.round(clamp(y, screen.virtualY + margin, bottom))
    }

    // Where the popup starts along a horizontal bar, by popupAlignment
    function alignedPopupX(buttonX: real): real {
        switch (popupAlignment) {
        case "left":
            return buttonX
        case "center":
            return buttonX + (toggle.width - popup.width) / 2
        default:
            return buttonX + toggle.width - popup.width
        }
    }

    function togglePopup() {
        if (popup.visible)
            popup.close()
        else
            openPopup()
    }

    function openPopup() {
        placePopup()
        popup.open()
    }

    function openMenu(position: point) {
        const screen = systray.Screen
        toggleMenu.createObject(null, {
            position: position,
            area: Qt.rect(screen.virtualX, screen.virtualY, screen.width, screen.height)
        })
    }

    // Return the drop index in repeater order, including the dragged icon. Icons run by row or column.
    function dropIndex(repeater: Repeater, area: Item, x: real, y: real, inColumns: bool): int {
        for (let index = 0; index < repeater.count; ++index) {
            const icon = repeater.itemAt(index)
            if (!icon)
                continue
            const point = icon.mapFromItem(area, x, y)
            const along = inColumns ? point.y : point.x
            const across = inColumns ? point.x : point.y
            const length = inColumns ? icon.height : icon.width
            const thickness = inColumns ? icon.width : icon.height

            const beforeLine = across < 0
            const onLine = across < thickness
            if (beforeLine || (onLine && along < length / 2))
                return index
        }
        return repeater.count
    }

    function dropIcon(drop: var, pinned: bool, repeater: Repeater, area: Item, inColumns: bool) {
        const iconId = parseInt(drop.getDataAsString(mimeType))
        tray.moveIcon(iconId, pinned, dropIndex(repeater, area, drop.x, drop.y, inColumns))
        drop.accept(Qt.MoveAction)
        // Moving to the other list destroys the dragged delegate before its Drag.onDragFinished runs
        dragging = false
    }

    implicitWidth: layout.implicitWidth
    implicitHeight: layout.implicitHeight

    Component.onDestruction: popup.hide()

    // Restore popup focus after a drop so clicks elsewhere can close it.
    onDraggingChanged: {
        if (!dragging && popup.visible)
            popup.window.requestActivate()
    }

    SystrayModel {
        id: tray

        screenName: systray.bar?.screenName ?? ""
        showBattery: systray.showBattery
        showVolume: systray.showVolume
        showNetwork: systray.showNetwork
        hideIcons: systray.hideIcons
        useHook: systray.useHook

        // Close the popup when the menu ends unless the popup has focus.
        onMenuOpenChanged: {
            if (!menuOpen && popup.visible && !popup.window.active)
                popup.close()
        }
    }

    Connections {
        target: systray.Window.window

        function onVisibleChanged() {
            if (!systray.Window.window?.visible)
                popup.hide()
        }

        function onXChanged() {
            if (popup.visible)
                systray.placePopup()
        }

        function onYChanged() {
            if (popup.visible)
                systray.placePopup()
        }
    }

    // Icons that come or go while the popup is open change its size, which moves it away from the button
    Connections {
        target: popup

        function onWidthChanged() {
            if (popup.visible)
                systray.placePopup()
        }

        function onHeightChanged() {
            if (popup.visible)
                systray.placePopup()
        }
    }

    // One tray icon, on the bar or in the popup
    component TrayButton: Item {
        id: button

        required property int index
        required property int iconId
        required property string tip
        required property string source
        // Drop area used to detect drags over this icon.
        property DropArea dropArea: null
        property int padding: 4
        // Open the popup on drag start so it can receive the icon.
        property bool opensPopup: false
        readonly property bool dragOver: {
            if (!dropArea || !dropArea.containsDrag)
                return false
            return contains(mapFromItem(dropArea, dropArea.drag.x, dropArea.drag.y))
        }

        objectName: "trayIcon"
        implicitWidth: systray.iconSize + 2 * padding
        implicitHeight: systray.iconSize + 2 * padding
        opacity: Drag.active ? 0.3 : 1
        Accessible.role: Accessible.Button
        Accessible.name: tip
        Accessible.onPressAction: tray.click(iconId, Qt.LeftButton)

        Drag.active: dragHandler.active
        Drag.dragType: Drag.Automatic
        Drag.supportedActions: Qt.MoveAction
        Drag.keys: [systray.mimeType]
        Drag.mimeData: ({ [systray.mimeType]: String(button.iconId) })
        Drag.imageSource: button.source
        Drag.imageSourceSize: Qt.size(systray.iconSize, systray.iconSize)
        Drag.hotSpot: Qt.point(systray.iconSize / 2, systray.iconSize / 2)
        Drag.onDragStarted: {
            systray.dragging = true
            if (opensPopup && !popup.visible)
                systray.openPopup()
        }
        Drag.onDragFinished: systray.dragging = false

        Rectangle {
            anchors.fill: parent
            radius: 4
            color: {
                if (button.dragOver)
                    return Qt.alpha(systray.foreground, 0.16)
                if (hover.hovered && !systray.dragging)
                    return systray.hoveredColor
                return "transparent"
            }
        }

        Image {
            anchors.centerIn: parent
            width: systray.iconSize
            height: systray.iconSize
            sourceSize: Qt.size(width, height)
            source: button.source
            smooth: true
        }

        HoverHandler {
            id: hover
        }

        TapHandler {
            id: tap

            acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
            onTapped: (point, mouseButton) => {
                const leftClick = mouseButton === Qt.LeftButton
                if (leftClick && (tap.point.modifiers & systray.pinKey))
                    tray.togglePinned(button.iconId)
                else if (leftClick && tap.tapCount === 2)
                    tray.doubleClick(button.iconId)
                else
                    tray.click(button.iconId, mouseButton)
            }
        }

        DragHandler {
            id: dragHandler

            target: null
            acceptedButtons: Qt.LeftButton
        }

        ToolTip {
            popupType: Popup.Window
            visible: systray.tooltip && hover.hovered && !systray.dragging && button.tip !== ""
            delay: 400
            text: button.tip
            // Away from the bar's edge
            y: systray.edge === "bottom" ? -implicitHeight - 6 : button.height + 6
        }
    }

    // Arrange the button and pinned icons along the bar; labelPosition controls their order.
    Item {
        id: layout

        readonly property Item first: systray.labelPosition === "right" ? pinnedDrop : toggle
        readonly property Item second: systray.labelPosition === "right" ? toggle : pinnedDrop

        function xOf(item: Item): real {
            if (systray.vertical)
                return Math.round((width - item.width) / 2)
            return item === second ? first.width : 0
        }

        function yOf(item: Item): real {
            if (systray.vertical)
                return item === second ? first.height : 0
            return Math.round((height - item.height) / 2)
        }

        anchors.verticalCenter: systray.vertical ? undefined : parent.verticalCenter
        anchors.horizontalCenter: systray.vertical ? parent.horizontalCenter : undefined
        implicitWidth: systray.vertical ? Math.max(toggle.width, pinnedDrop.width) : toggle.width + pinnedDrop.width
        implicitHeight: systray.vertical ? toggle.height + pinnedDrop.height : Math.max(toggle.height, pinnedDrop.height)

        // Opens the popup with the unpinned icons
        Item {
            id: toggle

            readonly property string label: popup.visible ? systray.labelExpanded : systray.labelCollapsed
            readonly property bool showsLabel: label !== ""

            x: layout.xOf(toggle)
            y: layout.yOf(toggle)
            width: implicitWidth
            height: implicitHeight
            implicitWidth: Math.max(systray.iconSize, showsLabel ? labelText.implicitWidth : 0) + 8
            implicitHeight: Math.max(systray.iconSize, showsLabel ? labelText.implicitHeight : 0) + 8
            Accessible.role: Accessible.Button
            Accessible.name: popup.visible ? "Hide more icons" : "Show more icons"
            Accessible.onPressAction: systray.togglePopup()

            Rectangle {
                anchors.fill: parent
                radius: 4
                color: toggleHover.hovered ? systray.hoveredColor : "transparent"
            }

            Text {
                id: labelText

                anchors.centerIn: parent
                visible: toggle.showsLabel
                text: toggle.label
                textFormat: Text.PlainText
                color: systray.textColor
                font: systray.font
            }

            Text {
                anchors.centerIn: parent
                visible: !toggle.showsLabel
                text: systray.chevronIcon
                color: systray.textColor
                font.family: systray.iconFont.family
                font.weight: systray.iconFont.weight
                font.pixelSize: systray.iconSize
                // Point away from the bar edge while closed, and toward it while open.
                rotation: {
                    const away = { top: 0, bottom: 180, left: -90, right: 90 }[systray.edge]
                    return popup.visible ? away + 180 : away
                }

                Behavior on rotation {
                    NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
                }
            }

            HoverHandler {
                id: toggleHover

                cursorShape: Qt.PointingHandCursor
            }

            TapHandler {
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onTapped: (point, mouseButton) => {
                    if (mouseButton === Qt.LeftButton)
                        systray.togglePopup()
                    else
                        systray.openMenu(toggle.mapToGlobal(point.position))
                }
            }
        }

        // Pinned icons and their drop area.
        DropArea {
            id: pinnedDrop

            readonly property bool empty: pinnedRepeater.count === 0
            // Keep an empty drop target available during a drag.
            readonly property int emptySize: systray.dragging ? systray.iconSize + 8 : 0

            x: layout.xOf(pinnedDrop)
            y: layout.yOf(pinnedDrop)
            width: implicitWidth
            height: implicitHeight
            implicitWidth: empty ? emptySize : pinned.implicitWidth
            implicitHeight: empty ? emptySize : pinned.implicitHeight
            keys: [systray.mimeType]
            onDropped: drop => systray.dropIcon(drop, true, pinnedRepeater, pinnedDrop, systray.vertical)

            Rectangle {
                anchors.fill: parent
                radius: 4
                visible: pinnedDrop.empty && systray.dragging
                color: Qt.alpha(systray.textColor, pinnedDrop.containsDrag ? 0.16 : 0.08)
            }

            Flow {
                id: pinned

                flow: systray.vertical ? Flow.TopToBottom : Flow.LeftToRight

                Repeater {
                    id: pinnedRepeater

                    model: tray.pinnedIcons

                    delegate: TrayButton {
                        dropArea: pinnedDrop
                        opensPopup: true
                    }
                }
            }
        }
    }

    // Opened by a right-click on the button
    Component {
        id: toggleMenu

        Window {
            id: menuWindow

            required property point position
            required property rect area

            // Open at the click, away from the bar edge and within the screen.
            readonly property real wantedX: systray.edge === "right" ? position.x - width : position.x
            readonly property real wantedY: systray.edge === "bottom" ? position.y - height : position.y

            flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
            color: "transparent"
            x: systray.clamp(wantedX, area.x, area.x + area.width - width)
            y: systray.clamp(wantedY, area.y, area.y + area.height - height)
            width: menu.width
            height: menu.implicitHeight

            Component.onCompleted: {
                show()
                requestActivate()
                menu.open()
            }

            onActiveChanged: {
                if (!active)
                    close()
            }

            onVisibleChanged: {
                if (!visible)
                    destroy()
            }

            Menu {
                id: menu

                topInset: 0
                leftInset: 0
                rightInset: 0
                bottomInset: 0
                popupType: Popup.Item
                onClosed: menuWindow.close()

                background: Rectangle {
                    implicitWidth: 180
                    radius: 8
                    color: "#222222"
                    border.color: "#363636"
                }

                MenuItem {
                    text: "Refresh Systray"
                    onTriggered: tray.refresh()
                }
            }
        }
    }

    BackdropPopup {
        id: popup

        property real reveal: 0
        readonly property int iconCount: unpinnedRepeater.count
        readonly property int cell: systray.iconSize + 20
        readonly property int columns: Math.max(1, Math.min(systray.iconsPerRow, iconCount))
        readonly property int rows: Math.max(1, Math.ceil(iconCount / columns))
        // Wide enough for "No icons" while there are none
        readonly property int gridWidth: iconCount > 0 ? columns * cell : 120
        // Surface margins and drop area padding on both sides.
        readonly property int frame: 2 * 8 + 2 * 4

        objectName: "menu"
        title: "Systray"
        width: gridWidth + frame
        height: rows * cell + frame
        anchor: toggle
        backdropItem: surface
        // Keep the popup open during a drag or while an icon's app shows its menu.
        pinned: systray.dragging || tray.menuOpen
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
            color: systray.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: systray.dark ? "#3A3A3A" : "#D9D9D9"
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: systray.edge === "bottom" ? Item.Bottom : Item.Top

            DropArea {
                id: unpinnedDrop

                anchors.fill: parent
                anchors.margins: 4
                keys: [systray.mimeType]
                onDropped: drop => systray.dropIcon(drop, false, unpinnedRepeater, unpinnedDrop, false)

                Text {
                    anchors.centerIn: parent
                    visible: popup.iconCount === 0
                    text: systray.dragging ? "Drop here" : "No icons"
                    color: Qt.alpha(systray.foreground, 0.5)
                    font.pixelSize: 12
                }

                Grid {
                    columns: popup.columns

                    Repeater {
                        id: unpinnedRepeater

                        model: tray.unpinnedIcons

                        delegate: TrayButton {
                            dropArea: unpinnedDrop
                            padding: 10
                        }
                    }
                }
            }
        }
    }
}
