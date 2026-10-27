import QtQuick
import QtQuick.Controls
import Yasb

// The bar's right-click menu. Qt keeps its popup windows inside the screen's work area, under the bar's
// always-on-top window and resizes them while they animate, so the menu sits in a window of its own.
Window {
    id: barMenu

    required property Item bar
    required property point position
    required property rect area

    // At the click, opening away from the bar's edge, and inside the screen
    readonly property real menuX: Math.max(area.x, Math.min(bar.edge === "right" ? position.x - menu.width : position.x,
        area.x + area.width - menu.width))
    readonly property real menuY: Math.max(area.y, Math.min(bar.edge === "bottom" ? position.y - menu.implicitHeight : position.y,
        area.y + area.height - menu.implicitHeight))
    // Submenus are drawn in this window too. It has room for one beside the menu, on the side the screen has space,
    // and below it, because Qt moves a submenu that doesn't fit on every frame of its open animation.
    readonly property real submenuWidth: backdropMenu.width - backdropMenu.leftInset - backdropMenu.rightInset
    readonly property real submenuHeight: backdropMenu.implicitHeight - backdropMenu.topInset - backdropMenu.bottomInset
    readonly property bool submenuOnLeft: menuX + menu.width + submenuWidth > area.x + area.width

    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
    color: "transparent"
    x: menuX + menu.leftInset - (submenuOnLeft ? submenuWidth : 0)
    y: menuY + menu.topInset
    width: menu.width - menu.leftInset - menu.rightInset + submenuWidth
    height: Math.min(menu.implicitHeight - menu.topInset - menu.bottomInset + submenuHeight, area.y + area.height - y)

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

    Commands {
        id: commands
    }

    Menu {
        id: menu
        
        // Custom menu colors
        topInset: 0
        leftInset: 0
        rightInset: 0
        bottomInset: 0

        background: Rectangle {
            implicitWidth: 200
            radius: 8
            color: "#222222"
            border.color: "#363636"
        }

        popupType: Popup.Item
        x: (barMenu.submenuOnLeft ? barMenu.submenuWidth : 0) - leftInset
        y: -topInset
        onClosed: barMenu.close()

        MenuItem {
            text: `Bar: ${barMenu.bar.name}`
            enabled: false
        }

        MenuSeparator {}

        MenuItem {
            text: "Task Manager"
            onTriggered: commands.execute("taskmgr")
        }

        MenuItem {
            text: "Take Screenshot"
            onTriggered: barMenu.bar.context.screenshot()
        }

        MenuSeparator {}

        Menu {
            id: backdropMenu

            title: "Backdrop"
            // Qt keeps the submenu inside this window, these keep its shadow inside too
            topMargin: -topInset
            bottomMargin: -bottomInset
            // cascade: true
            // Custom menu colors
            topInset: 0
            leftInset: 0
            rightInset: 0
            bottomInset: 0

            background: Rectangle {
                implicitWidth: 200
                radius: 8
                color: "#222222"
                border.color: "#363636"
            }
            MenuItem {
                text: "None"
                checkable: true
                autoExclusive: true
                checked: barMenu.bar.context.backdrop === "none"
                onTriggered: barMenu.bar.context.backdrop = "none"
            }

            MenuItem {
                text: "Blur"
                checkable: true
                autoExclusive: true
                checked: barMenu.bar.context.backdrop === "blur"
                onTriggered: barMenu.bar.context.backdrop = "blur"
            }

            MenuItem {
                text: "Acrylic"
                checkable: true
                autoExclusive: true
                checked: barMenu.bar.context.backdrop === "acrylic"
                onTriggered: barMenu.bar.context.backdrop = "acrylic"
            }

            MenuItem {
                text: "Mica"
                checkable: true
                autoExclusive: true
                checked: barMenu.bar.context.backdrop === "mica"
                onTriggered: barMenu.bar.context.backdrop = "mica"
            }

            MenuItem {
                text: "Mica Alt"
                checkable: true
                autoExclusive: true
                checked: barMenu.bar.context.backdrop === "mica-alt"
                onTriggered: barMenu.bar.context.backdrop = "mica-alt"
            }
        }

        MenuItem {
            text: barMenu.bar.context.autoHide ? "Disable Auto Hide" : "Enable Auto Hide"
            onTriggered: barMenu.bar.context.autoHide = !barMenu.bar.context.autoHide
        }

        MenuItem {
            text: "Reload Bar"
            onTriggered: barMenu.bar.context.reload()
        }

        MenuItem {
            text: "Exit"
            onTriggered: barMenu.bar.context.exit()
        }
    }
}
