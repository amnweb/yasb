import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: desktops

    property Item bar: null
    // Button text can be {name} or {index}
    property string label: "{name}"
    property string activeLabel: "{name}"
    // For desktops other than the active one that have windows open, empty to use label
    property string populatedLabel: ""
    // What each mouse button does on a desktop's button. Actions: activate_workspace, toggle_context_menu,
    // move_window_here, delete_workspace, create_desktop, switch_desktop N, move_window_to N,
    // delete_desktop or delete_desktop N, rename_desktop or rename_desktop N, next_desktop, prev_desktop and do_nothing.
    // Without N, delete_desktop deletes the current desktop, and rename_desktop renames the clicked one, or the
    // current one from a hotkey
    property string leftClick: "activate_workspace"
    property string middleClick: "do_nothing"
    property string rightClick: "toggle_context_menu"
    // Scroll over the widget to switch desktops: down for the next one, up for the previous one
    property bool scrollSwitching: true
    property bool reverseScroll: false
    // Global hotkeys, with the actions that need no button. Set to [] for none
    property var keybindings: []
    // Example below, with the default hotkeys for switching and moving windows.
    // property var keybindings: [
    //     { keys: "alt+1", action: "switch_desktop 1" },
    //     { keys: "alt+2", action: "switch_desktop 2" },
    //     { keys: "alt+3", action: "switch_desktop 3" },
    //     { keys: "alt+4", action: "switch_desktop 4" },
    //     { keys: "alt+5", action: "switch_desktop 5" },
    //     { keys: "alt+6", action: "switch_desktop 6" },
    //     { keys: "alt+7", action: "switch_desktop 7" },
    //     { keys: "alt+8", action: "switch_desktop 8" },
    //     { keys: "alt+9", action: "switch_desktop 9" },
    //     { keys: "alt+shift+1", action: "move_window_to 1" },
    //     { keys: "alt+shift+2", action: "move_window_to 2" },
    //     { keys: "alt+shift+3", action: "move_window_to 3" },
    //     { keys: "alt+shift+4", action: "move_window_to 4" },
    //     { keys: "alt+shift+5", action: "move_window_to 5" },
    //     { keys: "alt+shift+6", action: "move_window_to 6" },
    //     { keys: "alt+shift+7", action: "move_window_to 7" },
    //     { keys: "alt+shift+8", action: "move_window_to 8" },
    //     { keys: "alt+shift+9", action: "move_window_to 9" },
    //     { keys: "alt+pagedown", action: "next_desktop" },
    //     { keys: "alt+pageup", action: "prev_desktop" },
    //     { keys: "alt+shift+n", action: "create_desktop" },
    //     { keys: "alt+shift+d", action: "delete_desktop" },
    //     { keys: "alt+shift+r", action: "rename_desktop" }
    // ]
    // active, cursor or primary: which screen's widget runs a hotkey when several bars have one
    property string hotkeyScreen: "active"
    property int spacing: 4
    property int buttonPadding: 8

    readonly property bool dark: bar ? bar.dark : Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    // Text on the bar takes the bar's colour and font, each part unless the widget file sets it
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    property font font
    font.family: bar?.font.family ?? Qt.application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})
    // The active desktop's button background, and how strongly desktops without windows are dimmed
    property color activeBackground: Qt.alpha(textColor, 0.16)
    property real emptyOpacity: 0.5
    readonly property color foreground: dark ? "#ebebeb" : "#1f1f1f"
    readonly property color secondary: dark ? "#9d9d9d" : "#616161"
    readonly property string edge: bar?.edge ?? "top"

    readonly property alias service: service
    property real scrolled: 0
    // Held so the garbage collector doesn't destroy the open menu
    property Window openedMenu: null

    implicitWidth: row.implicitWidth
    implicitHeight: row.implicitHeight

    function labelFor(desktop: var): string {
        const format = desktop.number === service.current ? activeLabel
            : desktop.populated && populatedLabel !== "" ? populatedLabel : label
        return format.replace(/\{index\}/g, desktop.number).replace(/\{name\}/g, desktop.name || desktop.number)
    }

    // Runs an action for the button of desktop number, or for no button when number is 0
    function run(action: string, number: int) {
        const [name, argument] = action.trim().split(/\s+/)
        const target = argument ? parseInt(argument) : number
        switch (name) {
        case "activate_workspace":
        case "switch_desktop":
            service.switchTo(target)
            break
        case "move_window_here":
        case "move_window_to":
            service.moveFrontWindowTo(target)
            break
        case "delete_workspace":
            service.remove(number)
            break
        case "delete_desktop":
            service.remove(argument ? target : 0)
            break
        case "create_desktop":
            service.create()
            break
        case "rename_desktop":
            openRename(argument ? target : number || service.current)
            break
        case "toggle_context_menu":
            openMenu(number)
            break
        case "next_desktop":
            service.step(1)
            break
        case "prev_desktop":
            service.step(-1)
            break
        case "do_nothing":
        case undefined:
        case "":
            break
        default:
            console.warn(`Windows desktops: unknown action "${action}"`)
        }
    }

    function openMenu(number: int) {
        // Before the menu takes focus from the window its entries act on
        service.readForeground()
        openedMenu?.close()
        const index = service.desktops.findIndex(desktop => desktop.number === (number || service.current))
        const button = desktopButtons.itemAt(index) ?? desktops
        const start = button.mapToGlobal(0, 0)
        const screen = desktops.Screen
        openedMenu = menuWindow.createObject(null, {
            number: number,
            anchor: Qt.rect(start.x, start.y, button.width, button.height),
            area: Qt.rect(screen.virtualX, screen.virtualY, screen.width, screen.desktopAvailableHeight)
        })
    }

    function openRename(number: int) {
        const desktop = service.desktops.find(item => item.number === number)
        if (!desktop)
            return
        renamePopup.number = number
        nameField.text = desktop.name || `Desktop ${number}`
        placePopup()
        renamePopup.open()
        nameField.forceActiveFocus()
        nameField.selectAll()
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + 6
            : edge === "right" ? start.x - renamePopup.width - 6 : start.x + (width - renamePopup.width) / 2
        let py = edge === "top" ? start.y + height + 6
            : edge === "bottom" ? start.y - renamePopup.height - 6 : start.y + (height - renamePopup.height) / 2
        const screen = desktops.Screen
        px = Math.max(screen.virtualX + 8, Math.min(px, screen.virtualX + screen.width - renamePopup.width - 8))
        py = Math.max(screen.virtualY + 8, Math.min(py, screen.virtualY + screen.desktopAvailableHeight - renamePopup.height - 8))
        renamePopup.x = Math.round(px)
        renamePopup.y = Math.round(py)
    }

    function chooseWallpaper(number: int) {
        wallpaperDialog.number = number
        wallpaperDialog.open()
    }

    VirtualDesktops {
        id: service
    }

    Instantiator {
        model: desktops.keybindings

        delegate: Hotkey {
            required property var modelData

            keys: modelData.keys ?? ""
            screen: desktops.hotkeyScreen
            onActivated: desktops.run(modelData.action ?? "", 0)
        }
    }

    WheelHandler {
        enabled: desktops.scrollSwitching
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: event => {
            desktops.scrolled += event.angleDelta.y
            if (Math.abs(desktops.scrolled) < 120)
                return
            const up = desktops.scrolled > 0
            desktops.scrolled = 0
            service.step(up !== desktops.reverseScroll ? -1 : 1)
        }
    }

    Row {
        id: row

        spacing: desktops.spacing

        Repeater {
            id: desktopButtons

            model: service.desktops

            delegate: Item {
                id: button

                required property var modelData
                readonly property bool active: modelData.number === service.current
                readonly property string caption: caption.text

                objectName: `desktop-${modelData.number}`
                width: Math.ceil(caption.implicitWidth) + 2 * desktops.buttonPadding
                height: Math.max(desktops.height, Math.ceil(caption.implicitHeight) + 8)
                Accessible.role: Accessible.Button
                Accessible.name: `Desktop ${modelData.name || modelData.number}`
                Accessible.onPressAction: desktops.run(desktops.leftClick, modelData.number)

                Rectangle {
                    y: Math.round((parent.height - height) / 2)
                    width: parent.width
                    height: Math.round(Math.min(parent.height, caption.implicitHeight + 8))
                    radius: 4
                    color: button.active ? desktops.activeBackground
                        : area.containsMouse ? Qt.alpha(desktops.textColor, 0.08) : "transparent"
                }

                Text {
                    id: caption

                    anchors.centerIn: parent
                    text: desktops.labelFor(button.modelData)
                    textFormat: Text.PlainText
                    color: desktops.textColor
                    font: desktops.font
                    opacity: button.active || button.modelData.populated ? 1 : desktops.emptyOpacity
                }

                MouseArea {
                    id: area

                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
                    onClicked: mouse => desktops.run(mouse.button === Qt.LeftButton ? desktops.leftClick
                        : mouse.button === Qt.MiddleButton ? desktops.middleClick : desktops.rightClick,
                        button.modelData.number)
                }
            }
        }
    }

    FileDialog {
        id: wallpaperDialog

        // 0 for every desktop
        property int number: 0

        title: qsTr("Select wallpaper image")
        nameFilters: [qsTr("Images (*.png *.jpg *.jpeg *.bmp *.gif)")]
        onAccepted: {
            if (number)
                service.setWallpaper(number, selectedFile)
            else
                service.setWallpaperAll(selectedFile)
        }
    }

    // The menu sits in a window of its own: Qt keeps popup windows inside the work area and under the bar's
    // always-on-top window. The window leaves room for the submenu to open inside it, beside the menu
    Component {
        id: menuWindow

        Window {
            id: menuHost

            required property int number
            required property rect anchor
            required property rect area
            // Room beside the menu for the window submenu, which only exists when a window was in front
            readonly property bool withSubmenu: service.hasWindow
            readonly property int gap: 6
            readonly property string iconFamily: Qt.fontFamilies().includes("Segoe Fluent Icons")
                ? "Segoe Fluent Icons" : "Segoe MDL2 Assets"
            readonly property int menuX: {
                const wanted = desktops.edge === "left" ? anchor.x + anchor.width + gap
                    : desktops.edge === "right" ? anchor.x - menu.width - gap : anchor.x + (anchor.width - menu.width) / 2
                return Math.round(Math.max(area.x, Math.min(wanted, area.x + area.width - menu.width)))
            }
            readonly property int menuY: {
                const wanted = desktops.edge === "bottom" ? anchor.y - menu.implicitHeight - gap
                    : desktops.edge === "top" ? anchor.y + anchor.height + gap : anchor.y
                return Math.round(Math.max(area.y, Math.min(wanted, area.y + area.height - menu.implicitHeight)))
            }

            flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
            color: "transparent"
            // Keep the submenu's room on screen without shifting the main menu away from the button.
            x: Math.min(menuX, Math.max(area.x, area.x + area.width - width))
            y: Math.min(menuY, Math.max(area.y, area.y + area.height - height))
            width: menu.width + (withSubmenu ? moveMenu.width : 0)
            height: menu.implicitHeight + (withSubmenu ? moveMenu.implicitHeight : 0)

            // Entries that don't apply are taken out, not hidden: Menu still lays out a hidden entry
            Component.onCompleted: {
                if (service.desktops.length < 2)
                    menu.removeItem(deleteItem)
                if (!service.hasWindow) {
                    for (const item of [windowSeparator, moveHereItem, windowPinItem, appPinItem])
                        menu.removeItem(item)
                    menu.removeMenu(moveMenu)
                }
                if (!service.wallpaperSupported) {
                    for (const item of [wallpaperSeparator, wallpaperItem, wallpaperAllItem])
                        menu.removeItem(item)
                }
                // Measured before the window shows, so it doesn't open at the old size and then shrink
                menu.contentItem.forceLayout?.()
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

            component ActionItem: MenuItem {
                id: actionItem

                property string glyph: ""
                property int iconSize: 14
                leftPadding: mirrored ? 12 : Math.max(34, iconSize + 18)
                rightPadding: mirrored ? Math.max(34, iconSize + 18) : 12

                Text {
                    x: actionItem.mirrored ? actionItem.width - width - 10 : 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: actionItem.glyph
                    font.family: menuHost.iconFamily
                    font.pixelSize: actionItem.iconSize
                    color: actionItem.palette.text
                    Accessible.ignored: true
                }
            }

            // Looks like the bar's own right-click menu
            component BarLikeMenu: Menu {
                topInset: 0
                leftInset: 0
                rightInset: 0
                bottomInset: 0

                background: Rectangle {
                    implicitWidth: 260
                    radius: 8
                    color: "#222222"
                    border.color: "#363636"
                }
            }

            BarLikeMenu {
                id: menu

                x: menuHost.menuX - menuHost.x
                y: menuHost.menuY - menuHost.y
                popupType: Popup.Item
                onClosed: menuHost.close()

                delegate: ActionItem {
                    glyph: subMenu ? "\ue7c2" : ""
                }

                ActionItem {
                    glyph: "\ue70f"
                    text: qsTr("Rename")
                    onTriggered: desktops.openRename(menuHost.number)
                }

                ActionItem {
                    id: deleteItem

                    glyph: "\ue74d"
                    text: qsTr("Delete")
                    onTriggered: service.remove(menuHost.number)
                }

                MenuSeparator {}

                ActionItem {
                    glyph: "\ue710"
                    text: qsTr("Create new desktop")
                    onTriggered: service.create()
                }

                MenuSeparator {
                    id: windowSeparator
                }

                ActionItem {
                    id: moveHereItem

                    glyph: "\ue7c2"
                    text: qsTr("Move window here")
                    onTriggered: service.moveWindowTo(menuHost.number)
                }

                BarLikeMenu {
                    id: moveMenu

                    title: qsTr("Move window to")
                    popupType: Popup.Item

                    Instantiator {
                        model: service.desktops

                        delegate: MenuItem {
                            required property var modelData

                            text: modelData.name || qsTr("Desktop %1").arg(modelData.number)
                            onTriggered: service.moveWindowTo(modelData.number)
                        }

                        onObjectAdded: (index, object) => moveMenu.insertItem(index, object)
                        onObjectRemoved: (index, object) => moveMenu.removeItem(object)
                    }
                }

                ActionItem {
                    id: windowPinItem

                    glyph: service.windowPinned ? "\ue77a" : "\ue718"
                    text: service.windowPinned ? qsTr("Unpin window from all desktops") : qsTr("Pin window to all desktops")
                    onTriggered: service.toggleWindowPin()
                }

                ActionItem {
                    id: appPinItem

                    glyph: service.appPinned ? "\ue77a" : "\ue718"
                    text: service.appPinned ? qsTr("Unpin app from all desktops") : qsTr("Pin app to all desktops")
                    onTriggered: service.toggleAppPin()
                }

                MenuSeparator {
                    id: wallpaperSeparator
                }

                ActionItem {
                    id: wallpaperItem

                    glyph: "\ue8b9"
                    text: qsTr("Set wallpaper on this desktop")
                    onTriggered: desktops.chooseWallpaper(menuHost.number)
                }

                ActionItem {
                    id: wallpaperAllItem

                    glyph: "\ue8b9"
                    text: qsTr("Set wallpaper on all desktops")
                    onTriggered: desktops.chooseWallpaper(0)
                }
            }
        }
    }

    BackdropPopup {
        id: renamePopup
        objectName: "rename"

        property int number: 0
        property real reveal: 0

        function save() {
            service.rename(number, nameField.text)
            close()
        }

        title: qsTr("Rename desktop")
        width: 320
        height: content.implicitHeight + 16
        anchor: desktops
        backdropItem: surface
        enter: NumberAnimation { target: renamePopup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: renamePopup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface

            anchors.fill: parent
            anchors.margins: 8
            radius: 8
            color: desktops.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#f3f3f3", 0.85)
            border.width: 1
            border.color: desktops.dark ? "#3a3a3a" : "#d9d9d9"
            opacity: renamePopup.reveal
            scale: 0.85 + renamePopup.reveal * 0.15
            transformOrigin: desktops.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: content

                width: parent.width
                spacing: 0

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.margins: 16
                    spacing: 8

                    Text {
                        text: qsTr("Rename desktop")
                        color: desktops.foreground
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                    }

                    Text {
                        Layout.fillWidth: true
                        text: qsTr("Enter a new name for this desktop.")
                        color: desktops.secondary
                        font.pixelSize: 12
                        wrapMode: Text.Wrap
                    }

                    TextField {
                        id: nameField

                        Layout.fillWidth: true
                        placeholderText: qsTr("Desktop name")
                        onAccepted: renamePopup.save()
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    color: desktops.dark ? Qt.alpha("#ffffff", 0.08) : Qt.alpha("#000000", 0.08)
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.margins: 12
                    spacing: 8

                    Button {
                        Layout.fillWidth: true
                        text: qsTr("Rename")
                        highlighted: true
                        onClicked: renamePopup.save()
                    }

                    Button {
                        Layout.fillWidth: true
                        text: qsTr("Cancel")
                        onClicked: renamePopup.close()
                    }
                }
            }
        }
    }
}
