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

    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
    color: "transparent"
    x: menuX + menu.leftInset
    y: menuY + menu.topInset
    width: menu.width - menu.leftInset - menu.rightInset
    height: menu.implicitHeight - menu.topInset - menu.bottomInset

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
        x: -leftInset
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
