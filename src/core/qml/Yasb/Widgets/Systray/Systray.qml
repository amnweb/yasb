pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: systray

    component Settings: QtObject {
        required property Theme theme

        // Chevron glyph shown when the button has no label; rotated to point away from the bar edge.
        property string chevronIcon: "\ue972"
        // Button label; empty shows the chevron.
        property string labelCollapsed: ""
        property string labelExpanded: ""
        // Button side relative to pinned icons: left or right (top or bottom on a vertical bar).
        property string labelPosition: "left"
        property int iconSize: theme.bar.iconFont.pixelSize
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
        property color hoveredColor: theme.colors.hover
        // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
        property color textColor: theme.colors.text
        property font font
        // Glyphs take the theme's icon font, each part unless the widget file sets it
        property font iconFont
        iconFont.family: theme.bar.iconFont.family
        iconFont.weight: theme.bar.iconFont.weight
        iconFont.variableAxes: theme.bar.iconFont.variableAxes
        // The popup: the theme's, unless set here
        property color popupColor: theme.popup.background
        property color popupBorderColor: theme.popup.border
        property real popupRadius: theme.popup.radius
        property real popupGap: theme.popup.gap
        // Text in the popup: the theme's font family, in this widget's sizes
        property font popupFont
        popupFont.family: theme.popup.font.family
        popupFont.pixelSize: 13
        property font popupSmallFont
        popupSmallFont.family: theme.popup.font.family
        popupSmallFont.pixelSize: 12
        property int popupOpenDuration: theme.popup.openDuration
        property int popupCloseDuration: theme.popup.closeDuration
        // The right-click menu: the theme's, unless set here
        property color menuColor: theme.menu.background
        property color menuBorderColor: theme.menu.border
        property color menuTextColor: theme.colors.text
        property real menuRadius: theme.menu.radius
        property font menuFont: theme.menu.font
        // Milliseconds the right-click menu takes to fade in
        property int menuOpenDuration: theme.menu.openDuration
        property color popupTextColor: theme.colors.text
        property color popupTertiaryTextColor: theme.colors.textTertiary
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: systray.theme
    }

    readonly property bool dark: theme.dark
    readonly property string edge: bar.edge
    readonly property bool vertical: bar.vertical

    readonly property int pinKey: {
        switch (settings.pinModifier.toLowerCase()) {
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

    // Place the popup popupGap away from the bar, lined up with the button, and inside the screen.
    function placePopup() {
        const button = toggle.mapToGlobal(0, 0)
        const start = mapToGlobal(0, 0)
        const gap = settings.popupGap
        const margin = 8
        let x
        let y
        switch (edge) {
        case "bottom":
            x = alignedPopupX(button.x)
            y = start.y - popup.height - gap
            break
        case "left":
            x = start.x + width + gap
            y = button.y + (toggle.height - popup.height) / 2
            break
        case "right":
            x = start.x - popup.width - gap
            y = button.y + (toggle.height - popup.height) / 2
            break
        default:
            x = alignedPopupX(button.x)
            y = start.y + height + gap
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
        switch (settings.popupAlignment) {
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

        screenName: systray.bar.screenName
        showBattery: systray.settings.showBattery
        showVolume: systray.settings.showVolume
        showNetwork: systray.settings.showNetwork
        hideIcons: systray.settings.hideIcons
        useHook: systray.settings.useHook

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
        implicitWidth: systray.settings.iconSize + 2 * padding
        implicitHeight: systray.settings.iconSize + 2 * padding
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
        Drag.imageSourceSize: Qt.size(systray.settings.iconSize, systray.settings.iconSize)
        Drag.hotSpot: Qt.point(systray.settings.iconSize / 2, systray.settings.iconSize / 2)
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
                    return Qt.alpha(systray.settings.popupTextColor, 0.16)
                if (hover.hovered && !systray.dragging)
                    return systray.settings.hoveredColor
                return "transparent"
            }
        }

        Image {
            anchors.centerIn: parent
            width: systray.settings.iconSize
            height: systray.settings.iconSize
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
            visible: systray.settings.tooltip && hover.hovered && !systray.dragging && button.tip !== ""
            delay: 400
            text: button.tip
            // Away from the bar's edge
            y: systray.edge === "bottom" ? -implicitHeight - 6 : button.height + 6
        }
    }

    // Arrange the button and pinned icons along the bar; labelPosition controls their order.
    Item {
        id: layout

        readonly property Item first: systray.settings.labelPosition === "right" ? pinnedDrop : toggle
        readonly property Item second: systray.settings.labelPosition === "right" ? toggle : pinnedDrop

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

            readonly property string label: popup.visible ? systray.settings.labelExpanded : systray.settings.labelCollapsed
            readonly property bool showsLabel: label !== ""

            x: layout.xOf(toggle)
            y: layout.yOf(toggle)
            width: implicitWidth
            height: implicitHeight
            implicitWidth: Math.max(systray.settings.iconSize, showsLabel ? labelText.implicitWidth : 0) + 8
            implicitHeight: Math.max(systray.settings.iconSize, showsLabel ? labelText.implicitHeight : 0) + 8
            Accessible.role: Accessible.Button
            Accessible.name: popup.visible ? "Hide more icons" : "Show more icons"
            Accessible.onPressAction: systray.togglePopup()

            Rectangle {
                anchors.fill: parent
                radius: 4
                color: toggleHover.hovered ? systray.settings.hoveredColor : "transparent"
            }

            Label {
                id: labelText

                anchors.centerIn: parent
                visible: toggle.showsLabel
                text: toggle.label
                textFormat: Text.PlainText
                color: systray.settings.textColor
                font: systray.settings.font
            }

            Text {
                anchors.centerIn: parent
                visible: !toggle.showsLabel
                text: systray.settings.chevronIcon
                color: systray.settings.textColor
                font.family: systray.settings.iconFont.family
                font.weight: systray.settings.iconFont.weight
                font.variableAxes: systray.settings.iconFont.variableAxes
                font.pixelSize: systray.settings.iconSize
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
            readonly property int emptySize: systray.dragging ? systray.settings.iconSize + 8 : 0

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
                color: Qt.alpha(systray.settings.textColor, pinnedDrop.containsDrag ? 0.16 : 0.08)
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
                // Fades in when it opens, in place of the style's growing from a third of its height
                enter: Transition {
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: systray.settings.menuOpenDuration; easing.type: Easing.OutCubic }
                }
                onClosed: menuWindow.close()
                font: systray.settings.menuFont
                // Active and inactive only, so disabled controls keep the style's dimmed colours
                palette.active.text: systray.settings.menuTextColor
                palette.inactive.text: systray.settings.menuTextColor

                background: Rectangle {
                    implicitWidth: 180
                    radius: systray.settings.menuRadius
                    color: systray.settings.menuColor
                    border.color: systray.settings.menuBorderColor
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
        readonly property int cell: systray.settings.iconSize + 20
        readonly property int columns: Math.max(1, Math.min(systray.settings.iconsPerRow, iconCount))
        readonly property int rows: Math.max(1, Math.ceil(iconCount / columns))
        // Wide enough for "No icons" while there are none
        readonly property int gridWidth: iconCount > 0 ? columns * cell : 120
        // Drop area padding on both sides
        readonly property int frame: 2 * 4

        objectName: "menu"
        title: "Systray"
        width: gridWidth + frame
        height: rows * cell + frame
        anchor: toggle
        font: systray.settings.popupFont
        theme: systray.theme
        backdropItem: surface
        // Keep the popup open during a drag or while an icon's app shows its menu.
        pinned: systray.dragging || tray.menuOpen
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: systray.settings.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: systray.settings.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible)
                reveal = 0
        }

        Rectangle {
            id: surface

            anchors.fill: parent
            radius: systray.settings.popupRadius
            color: systray.settings.popupColor
            border.width: 1
            border.color: systray.settings.popupBorderColor
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
                    color: systray.settings.popupTertiaryTextColor
                    font: systray.settings.popupSmallFont
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
