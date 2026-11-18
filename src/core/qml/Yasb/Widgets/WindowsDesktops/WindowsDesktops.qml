pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: windowsDesktops

    required property BarBase bar
    readonly property Theme theme: bar.theme
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
    // The popup that renames a desktop
    property int popupWidth: 304
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

    readonly property bool dark: theme.dark
    // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
    property color textColor: theme.colors.text
    property font font
    // The popup: the theme's, unless set here
    property color popupColor: theme.popup.background
    property color popupBorderColor: theme.popup.border
    property color popupTextColor: theme.colors.text
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
    property color popupDividerColor: theme.colors.divider
    property font popupTitleFont
    popupTitleFont.family: theme.popup.font.family
    popupTitleFont.pixelSize: 16
    popupTitleFont.weight: Font.DemiBold
    // The right-click menu: its width, and a look that is the theme's unless set here
    property int menuWidth: 260
    property color menuColor: theme.menu.background
    property color menuBorderColor: theme.menu.border
    property color menuTextColor: theme.colors.text
    property real menuRadius: theme.menu.radius
    property font menuFont: theme.menu.font
    // Milliseconds the right-click menu takes to fade in
    property int menuOpenDuration: theme.menu.openDuration
    // The icons in the text fields' right-click menu
    property int menuIconSize: 16
    // Glyphs in the right-click menu take the theme's icon font, each part unless the widget file sets it
    property font menuIconFont
    menuIconFont.family: theme.bar.iconFont.family
    menuIconFont.weight: theme.bar.iconFont.weight
    menuIconFont.variableAxes: theme.bar.iconFont.variableAxes
    // The background of the active desktop's button and of a hovered one, and how strongly desktops without windows
    // are dimmed
    property color activeBackground: theme.colors.selected
    property color hoverColor: theme.colors.hover
    property real emptyOpacity: 0.5
    property color popupSecondaryTextColor: theme.colors.textSecondary
    readonly property string edge: bar.edge

    readonly property alias service: virtualDesktops
    property real scrolled: 0
    // Held so the garbage collector doesn't destroy the open menu
    property Window openedMenu: null

    implicitWidth: row.implicitWidth
    implicitHeight: row.implicitHeight

    function labelFor(desktop: var): string {
        const format = desktop.number === virtualDesktops.current ? activeLabel
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
            virtualDesktops.switchTo(target)
            break
        case "move_window_here":
        case "move_window_to":
            virtualDesktops.moveFrontWindowTo(target)
            break
        case "delete_workspace":
            virtualDesktops.remove(number)
            break
        case "delete_desktop":
            virtualDesktops.remove(argument ? target : 0)
            break
        case "create_desktop":
            virtualDesktops.create()
            break
        case "rename_desktop":
            openRename(argument ? target : number || virtualDesktops.current)
            break
        case "toggle_context_menu":
            openMenu(number)
            break
        case "next_desktop":
            virtualDesktops.step(1)
            break
        case "prev_desktop":
            virtualDesktops.step(-1)
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
        virtualDesktops.readForeground()
        openedMenu?.close()
        const index = virtualDesktops.desktops.findIndex(desktop => desktop.number === (number || virtualDesktops.current))
        const button = desktopButtons.itemAt(index) ?? windowsDesktops
        const start = button.mapToGlobal(0, 0)
        const screen = windowsDesktops.Screen
        openedMenu = menuWindow.createObject(null, {
            number: number,
            anchor: Qt.rect(start.x, start.y, button.width, button.height),
            area: Qt.rect(screen.virtualX, screen.virtualY, screen.width, screen.desktopAvailableHeight)
        })
    }

    function openRename(number: int) {
        const desktop = virtualDesktops.desktops.find(item => item.number === number)
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
        let px = edge === "left" ? start.x + width + popupGap
            : edge === "right" ? start.x - renamePopup.width - popupGap : start.x + (width - renamePopup.width) / 2
        let py = edge === "top" ? start.y + height + popupGap
            : edge === "bottom" ? start.y - renamePopup.height - popupGap : start.y + (height - renamePopup.height) / 2
        const screen = windowsDesktops.Screen
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
        id: virtualDesktops
    }

    Instantiator {
        model: windowsDesktops.keybindings

        delegate: Hotkey {
            required property var modelData

            keys: modelData.keys ?? ""
            screen: windowsDesktops.hotkeyScreen
            onActivated: windowsDesktops.run(modelData.action ?? "", 0)
        }
    }

    WheelHandler {
        enabled: windowsDesktops.scrollSwitching
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: event => {
            windowsDesktops.scrolled += event.angleDelta.y
            if (Math.abs(windowsDesktops.scrolled) < 120)
                return
            const up = windowsDesktops.scrolled > 0
            windowsDesktops.scrolled = 0
            virtualDesktops.step(up !== windowsDesktops.reverseScroll ? -1 : 1)
        }
    }

    Row {
        id: row

        spacing: windowsDesktops.spacing

        Repeater {
            id: desktopButtons

            model: virtualDesktops.desktops

            delegate: Item {
                id: button

                required property var modelData
                readonly property bool active: modelData.number === virtualDesktops.current
                readonly property string caption: captionLabel.text

                objectName: `desktop-${modelData.number}`
                width: Math.ceil(captionLabel.implicitWidth) + 2 * windowsDesktops.buttonPadding
                height: Math.max(windowsDesktops.height, Math.ceil(captionLabel.implicitHeight) + 8)
                Accessible.role: Accessible.Button
                Accessible.name: `Desktop ${modelData.name || modelData.number}`
                Accessible.onPressAction: windowsDesktops.run(windowsDesktops.leftClick, modelData.number)

                Rectangle {
                    y: Math.round((parent.height - height) / 2)
                    width: parent.width
                    height: Math.round(Math.min(parent.height, captionLabel.implicitHeight + 8))
                    radius: 4
                    color: button.active ? windowsDesktops.activeBackground
                        : area.containsMouse ? windowsDesktops.hoverColor : "transparent"
                }

                Label {
                    id: captionLabel

                    anchors.centerIn: parent
                    text: windowsDesktops.labelFor(button.modelData)
                    textFormat: Text.PlainText
                    color: windowsDesktops.textColor
                    font: windowsDesktops.font
                    opacity: button.active || button.modelData.populated ? 1 : windowsDesktops.emptyOpacity
                }

                MouseArea {
                    id: area

                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
                    onClicked: mouse => windowsDesktops.run(mouse.button === Qt.LeftButton ? windowsDesktops.leftClick
                        : mouse.button === Qt.MiddleButton ? windowsDesktops.middleClick : windowsDesktops.rightClick,
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
                virtualDesktops.setWallpaper(number, selectedFile)
            else
                virtualDesktops.setWallpaperAll(selectedFile)
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
            readonly property bool withSubmenu: virtualDesktops.hasWindow
            readonly property int gap: 6
            readonly property int menuX: {
                const wanted = windowsDesktops.edge === "left" ? anchor.x + anchor.width + gap
                    : windowsDesktops.edge === "right" ? anchor.x - menu.width - gap : anchor.x + (anchor.width - menu.width) / 2
                return Math.round(Math.max(area.x, Math.min(wanted, area.x + area.width - menu.width)))
            }
            readonly property int menuY: {
                const wanted = windowsDesktops.edge === "bottom" ? anchor.y - menu.implicitHeight - gap
                    : windowsDesktops.edge === "top" ? anchor.y + anchor.height + gap : anchor.y
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
                if (virtualDesktops.desktops.length < 2)
                    menu.removeItem(deleteItem)
                if (!virtualDesktops.hasWindow) {
                    for (const item of [windowSeparator, moveHereItem, windowPinItem, appPinItem])
                        menu.removeItem(item)
                    menu.removeMenu(moveMenu)
                }
                if (!virtualDesktops.wallpaperSupported) {
                    for (const item of [wallpaperSeparator, wallpaperItem, wallpaperAllItem])
                        menu.removeItem(item)
                }
                // Measured before the window shows, so it doesn't open at the old size and then shrink
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
                    font.family: windowsDesktops.menuIconFont.family
                    font.weight: windowsDesktops.menuIconFont.weight
                    font.variableAxes: windowsDesktops.menuIconFont.variableAxes
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
                font: windowsDesktops.menuFont
                // Active and inactive only, so disabled controls keep the style's dimmed colours
                palette.active.text: windowsDesktops.menuTextColor
                palette.inactive.text: windowsDesktops.menuTextColor
                // Fades in when it opens, in place of the style's growing from a third of its height
                enter: Transition {
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: windowsDesktops.menuOpenDuration; easing.type: Easing.OutCubic }
                }

                background: Rectangle {
                    implicitWidth: windowsDesktops.menuWidth
                    radius: windowsDesktops.menuRadius
                    color: windowsDesktops.menuColor
                    border.color: windowsDesktops.menuBorderColor
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
                    onTriggered: windowsDesktops.openRename(menuHost.number)
                }

                ActionItem {
                    id: deleteItem

                    glyph: "\ue74d"
                    text: qsTr("Delete")
                    onTriggered: virtualDesktops.remove(menuHost.number)
                }

                MenuSeparator {}

                ActionItem {
                    glyph: "\ue710"
                    text: qsTr("Create new desktop")
                    onTriggered: virtualDesktops.create()
                }

                MenuSeparator {
                    id: windowSeparator
                }

                ActionItem {
                    id: moveHereItem

                    glyph: "\ue7c2"
                    text: qsTr("Move window here")
                    onTriggered: virtualDesktops.moveWindowTo(menuHost.number)
                }

                BarLikeMenu {
                    id: moveMenu

                    title: qsTr("Move window to")
                    popupType: Popup.Item

                    Instantiator {
                        model: virtualDesktops.desktops

                        delegate: MenuItem {
                            required property var modelData

                            text: modelData.name || qsTr("Desktop %1").arg(modelData.number)
                            onTriggered: virtualDesktops.moveWindowTo(modelData.number)
                        }

                        onObjectAdded: (index, object) => moveMenu.insertItem(index, object)
                        onObjectRemoved: (index, object) => moveMenu.removeItem(object)
                    }
                }

                ActionItem {
                    id: windowPinItem

                    glyph: virtualDesktops.windowPinned ? "\ue77a" : "\ue718"
                    text: virtualDesktops.windowPinned ? qsTr("Unpin window from all desktops") : qsTr("Pin window to all desktops")
                    onTriggered: virtualDesktops.toggleWindowPin()
                }

                ActionItem {
                    id: appPinItem

                    glyph: virtualDesktops.appPinned ? "\ue77a" : "\ue718"
                    text: virtualDesktops.appPinned ? qsTr("Unpin app from all desktops") : qsTr("Pin app to all desktops")
                    onTriggered: virtualDesktops.toggleAppPin()
                }

                MenuSeparator {
                    id: wallpaperSeparator
                }

                ActionItem {
                    id: wallpaperItem

                    glyph: "\ue8b9"
                    text: qsTr("Set wallpaper on this desktop")
                    onTriggered: windowsDesktops.chooseWallpaper(menuHost.number)
                }

                ActionItem {
                    id: wallpaperAllItem

                    glyph: "\ue8b9"
                    text: qsTr("Set wallpaper on all desktops")
                    onTriggered: windowsDesktops.chooseWallpaper(0)
                }
            }
        }
    }

    // An item of the text fields' right-click menu, its icon in menuIconSize
    component FieldMenuItem: MenuItem {
        icon.width: windowsDesktops.menuIconSize
        icon.height: windowsDesktops.menuIconSize
    }

    BackdropPopup {
        id: renamePopup
        objectName: "rename"

        property int number: 0
        property real reveal: 0

        function save() {
            virtualDesktops.rename(number, nameField.text)
            close()
        }

        title: qsTr("Rename desktop")
        width: windowsDesktops.popupWidth
        height: popupContent.implicitHeight
        anchor: windowsDesktops
        font: windowsDesktops.popupFont
        theme: windowsDesktops.theme
        backdropItem: surface
        enter: NumberAnimation { target: renamePopup; property: "reveal"; to: 1; duration: windowsDesktops.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: renamePopup; property: "reveal"; to: 0; duration: windowsDesktops.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface

            anchors.fill: parent
            radius: windowsDesktops.popupRadius
            color: windowsDesktops.popupColor
            border.width: 1
            border.color: windowsDesktops.popupBorderColor
            opacity: renamePopup.reveal
            scale: 0.85 + renamePopup.reveal * 0.15
            transformOrigin: windowsDesktops.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: popupContent

                width: parent.width
                spacing: 0

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.margins: 16
                    spacing: 8

                    Text {
                        text: qsTr("Rename desktop")
                        font: windowsDesktops.popupTitleFont
                        color: windowsDesktops.popupTextColor
                    }

                    Text {
                        Layout.fillWidth: true
                        text: qsTr("Enter a new name for this desktop.")
                        color: windowsDesktops.popupSecondaryTextColor
                        font: windowsDesktops.popupSmallFont
                        wrapMode: Text.Wrap
                    }

                    // The text fields' right-click menu: Qt's editing items and icons in the menu's look, acting on the field that
                    // opened it
                    Menu {
                        id: fieldMenu

                        readonly property TextField editor: parent as TextField
                        readonly property bool editable: !(editor?.readOnly ?? true)
                        readonly property bool selected: (editor?.selectedText.length ?? 0) > 0

                        // A window of its own, so it opens where clicked even past the popup's edges
                        popupType: Popup.Window
                        // Its window is made once and reused, and Windows shows it again where it was, under the popup raised
                        // since; raising it before it shows keeps it in front
                        onAboutToShow: contentItem.Window.window?.raise()
                        // Fades in when it opens, in place of the style's growing from a third of its height
                        enter: Transition {
                            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: windowsDesktops.menuOpenDuration; easing.type: Easing.OutCubic }
                        }
                        topInset: 0
                        leftInset: 0
                        rightInset: 0
                        bottomInset: 0
                        font: windowsDesktops.menuFont
                        // Active and inactive only, so disabled controls keep the style's dimmed colours
                        palette.active.text: windowsDesktops.menuTextColor
                        palette.inactive.text: windowsDesktops.menuTextColor

                        background: Rectangle {
                            implicitWidth: windowsDesktops.menuWidth
                            radius: windowsDesktops.menuRadius
                            color: windowsDesktops.menuColor
                            border.color: windowsDesktops.menuBorderColor
                        }

                        FieldMenuItem {
                            text: qsTr("Undo")
                            icon.name: "edit-undo"
                            enabled: fieldMenu.editor?.canUndo ?? false
                            onTriggered: fieldMenu.editor.undo()
                        }
                        FieldMenuItem {
                            text: qsTr("Redo")
                            icon.name: "edit-redo"
                            enabled: fieldMenu.editor?.canRedo ?? false
                            onTriggered: fieldMenu.editor.redo()
                        }
                        MenuSeparator {}
                        FieldMenuItem {
                            text: qsTr("Cut")
                            icon.name: "edit-cut"
                            enabled: fieldMenu.editable && fieldMenu.selected
                            onTriggered: fieldMenu.editor.cut()
                        }
                        FieldMenuItem {
                            text: qsTr("Copy")
                            icon.name: "edit-copy"
                            enabled: fieldMenu.selected
                            onTriggered: fieldMenu.editor.copy()
                        }
                        FieldMenuItem {
                            text: qsTr("Paste")
                            icon.name: "edit-paste"
                            enabled: fieldMenu.editable && (fieldMenu.editor?.canPaste ?? false)
                            onTriggered: fieldMenu.editor.paste()
                        }
                        FieldMenuItem {
                            text: qsTr("Delete")
                            icon.name: "edit-delete"
                            enabled: fieldMenu.editable && fieldMenu.selected
                            onTriggered: fieldMenu.editor.remove(fieldMenu.editor.selectionStart, fieldMenu.editor.selectionEnd)
                        }
                        MenuSeparator {}
                        FieldMenuItem {
                            text: qsTr("Select All")
                            icon.name: "edit-select-all"
                            onTriggered: fieldMenu.editor.selectAll()
                        }
                    }

                    TextField {
                        id: nameField

                        // Qt's own text menu is replaced by fieldMenu, which the right button opens
                        ContextMenu.menu: null

                        // A right-click opens the menu at the mouse cursor, on press or release as Windows sets it
                        TapHandler {
                            acceptedButtons: Qt.RightButton
                            onPressedChanged: {
                                if (pressed === (Application.styleHints.contextMenuTrigger === Qt.ContextMenuTrigger.Press))
                                    fieldMenu.popup(nameField)
                            }
                        }

                        Layout.fillWidth: true
                        placeholderText: qsTr("Desktop name")
                        onAccepted: renamePopup.save()
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    color: windowsDesktops.popupDividerColor
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
