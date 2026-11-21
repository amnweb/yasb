pragma ComponentBehavior: Bound

import QtQml.Models
import QtQuick
import QtQuick.Controls
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

// Every app from Start's All apps in one grid, in your own order. Drag an app to move it, hold it over another app to
// make a group, click a group to open it and drag an app out of it to take it out. Ctrl+click, Shift+click and Ctrl+A
// select tiles, and right-click hides or groups them; right-click outside the tiles to show the hidden apps.
Item {
    id: launchpad

    component PopupIcons: QtObject {
        property string search
        property string hidden
    }

    component Settings: QtObject {
        required property Theme theme

        // Hotkey that opens the launchpad, such as "alt+l"
        property string hotkey: "alt+l"
        // active, cursor or primary: which screen's widget opens on the hotkey
        property string hotkeyScreen: "active"
        // Pixels of the popup; it never takes more than 90% of the screen
        property int popupWidth: 860
        property int popupHeight: 600
        // Pixels of each app's icon, and of the room inside each tile around its icon and name
        property int appIconSize: 48
        property int tilePadding: 32
        // The most apps side by side in an open group
        property int groupColumns: 4
        property string searchPlaceholder: qsTr("Search apps")
        // The glyph on the bar, drawn in iconFont and the text colour
        property string icon: "\ue8a9"
        property int iconSize: theme.bar.iconFont.pixelSize
        property int searchIconSize: 16
        readonly property PopupIcons popupIcons: PopupIcons {
            search: "\ue721"
            // The mark on a hidden app's tile
            hidden: "\ued1a"
        }
        property font popupIconFont
        popupIconFont.family: theme.popup.iconFont.family
        popupIconFont.weight: theme.popup.iconFont.weight
        popupIconFont.variableAxes: theme.popup.iconFont.variableAxes

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
        property color popupSecondaryTextColor: theme.colors.textSecondary
        property color popupHoverColor: theme.colors.hover
        property color popupSelectedColor: theme.colors.selected
        // Behind a group's icons on its tile
        property color popupCardColor: theme.colors.card
        property color accentColor: theme.colors.accent
        property real popupRadius: theme.popup.radius
        property int popupOpenDuration: theme.popup.openDuration
        property int popupCloseDuration: theme.popup.closeDuration
        // Milliseconds apps take to slide to their new place, and a group to open or close
        property int moveDuration: 220
        property int groupDuration: 220
        // An open group, and the shade laid over the grid behind it
        property color groupColor: theme.colors.background
        property color groupBorderColor: theme.popup.border
        property color smokeColor: theme.colors.smoke
        property real groupRadius: 12
        // Text in the popup: the theme's font family, in this widget's sizes
        property font popupFont
        popupFont.family: theme.popup.font.family
        popupFont.pixelSize: 12
        property font searchFont
        searchFont.family: theme.popup.font.family
        searchFont.pixelSize: 16
        property font groupNameFont
        groupNameFont.family: theme.popup.font.family
        groupNameFont.pixelSize: 16
        groupNameFont.weight: 600
        // The right-click menus: the theme's, unless set here
        property int menuWidth: 200
        property color menuColor: theme.menu.background
        property color menuBorderColor: theme.menu.border
        property color menuTextColor: theme.colors.text
        property real menuRadius: theme.menu.radius
        property font menuFont: theme.menu.font
        property int menuOpenDuration: theme.menu.openDuration
        // The icons in the text fields' right-click menu
        property int menuIconSize: 16
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: launchpad.theme
    }

    implicitWidth: label.width
    implicitHeight: label.height

    onQueryChanged: {
        closeGroup()
        current = query.trim() ? 0 : -1
        selection = []
    }
    // Each move of the dragged tile aims it again; one dragged past the edge of the open group leaves it
    onDragPointChanged: {
        if (dragging?.from === "group" && !leftGroup && openGroup >= 0 && dragPoint.x >= 0 && !insideGroup)
            leaveGroup()
        retarget()
    }

    function iconOf(app: var): string {
        return app ? app.icon.replace(/\/\d+$/, "/" + library.iconRevision) : ""
    }

    function toggle() {
        if (popup.visible && !popup.closing)
            popup.close()
        else
            open()
    }

    function open() {
        query = ""
        field.text = ""
        closeGroupNow()
        current = -1
        popup.open()
        library.takeFocus(popup.window)
        field.forceActiveFocus()
    }

    function launch(id: string) {
        library.launch(id)
        popup.close()
    }

    function openGroupAt(row: int, rename: bool) {
        const tile = grid.itemAtIndex(row)
        groupOrigin = tile ? tile.mapToItem(surfaceItem, tile.width / 2, tile.height / 2)
            : Qt.point(surfaceItem.width / 2, surfaceItem.height / 2)
        openGroup = row
        openApps = layout.appsOf(row)
        groupName.text = layout.nameOf(row)
        groupAnimation.to = 1
        groupAnimation.restart()
        if (rename) {
            groupName.forceActiveFocus()
            groupName.selectAll()
        }
    }

    // Folds the open group back into its tile
    function closeGroup() {
        if (openGroup < 0 || groupAnimation.to === 0)
            return
        renameOpenGroup()
        groupAnimation.to = 0
        groupAnimation.restart()
        field.forceActiveFocus()
    }

    function closeGroupNow() {
        renameOpenGroup()
        groupAnimation.stop()
        groupAnimation.to = 0
        groupReveal = 0
        openGroup = -1
        openApps = []
        field.forceActiveFocus()
    }

    function renameOpenGroup() {
        if (openGroup >= 0 && layout.isGroup(openGroup))
            layout.renameGroup(openGroup, groupName.text)
    }

    function step(dx: int, dy: int) {
        const count = query.trim() ? results.length : layout.count
        if (!count)
            return
        current = current < 0 ? 0 : Math.max(0, Math.min(count - 1, current + dx + dy * columns))
        const view = query.trim() ? resultsGrid : grid
        view.positionViewAtIndex(current, GridView.Contain)
    }

    function activateCurrent() {
        if (query.trim()) {
            const app = results[Math.max(0, current)]
            if (app)
                launch(app.id)
        } else if (current >= 0) {
            if (layout.isGroup(current))
                openGroupAt(current, false)
            else if ((grid.itemAtIndex(current) as Tile)?.appId)
                launch((grid.itemAtIndex(current) as Tile).appId)
        }
    }

    // The keys of the tiles in sight, in their order: app:<id> for an app, group:<row> for a group
    function shownKeys(): var {
        if (query.trim())
            return results.map(app => "app:" + app.id)
        const keys = []
        for (let row = 0; row < layout.count; row++)
            keys.push(layout.isGroup(row) ? "group:" + row : "app:" + layout.appAt(row))
        if (showHidden) {
            for (const id of layout.hidden)
                keys.push("app:" + id)
        }
        return keys
    }

    // Ctrl+click adds a tile to the selection or takes it out; Shift+click selects the tiles from the one clicked last
    function pick(key: string, range: bool) {
        const keys = shownKeys()
        const from = keys.indexOf(anchorKey)
        const to = keys.indexOf(key)
        if (range && from >= 0 && to >= 0) {
            selection = keys.slice(Math.min(from, to), Math.max(from, to) + 1)
            return
        }
        selection = selection.includes(key) ? selection.filter(other => other !== key) : selection.concat([key])
        anchorKey = key
    }

    function isHiddenKey(key: string): bool {
        return key.startsWith("app:") && hiddenIds[key.slice(4)] === true
    }

    // The app ids behind these keys, a group's apps for a group
    function appsOfKeys(keys: var): var {
        let ids = []
        for (const key of keys)
            ids = ids.concat(key.startsWith("group:") ? layout.appsOf(Number(key.slice(6))) : [key.slice(4)])
        return ids
    }

    // A right-click on a tile: one not selected is selected alone first, and the menu acts on the whole selection.
    // In the open group it acts on the app clicked
    function showMenu(tile: Tile) {
        if (tile.from === "group") {
            tileMenu.show(tile.appId, -1, [])
            return
        }
        if (!selection.includes(tile.key)) {
            selection = [tile.key]
            anchorKey = tile.key
        }
        const single = selection.length === 1
        tileMenu.show(single && !tile.group ? tile.appId : "", single && tile.group ? tile.index : -1, selection)
    }

    function runMenu(action: string) {
        const appId = tileMenu.appId
        const keys = tileMenu.keys
        const shown = keys.filter(key => !isHiddenKey(key))
        if (action === "open") {
            if (tileMenu.groupRow >= 0)
                openGroupAt(tileMenu.groupRow, false)
            else
                launch(appId)
        } else if (action === "hide") {
            layout.hide(appId ? [appId] : appsOfKeys(shown))
            // Hiding an app shrinks the open group, or dissolves it once one app is left
            if (openGroup >= 0) {
                if (layout.isGroup(openGroup))
                    openApps = layout.appsOf(openGroup)
                else
                    closeGroupNow()
            }
        } else if (action === "unhide") {
            layout.unhide(appId ? [appId] : appsOfKeys(keys.filter(key => isHiddenKey(key))))
        } else if (action === "group") {
            const row = layout.groupApps(appsOfKeys(shown.filter(key => key.startsWith("app:"))))
            if (row >= 0)
                openGroupAt(row, true)
        } else if (action === "ungroup") {
            layout.ungroup(tileMenu.groupRow)
        } else {
            library.run(appId, action)
            popup.close()
        }
        selection = []
    }

    // The row the dragged app or group is at in the grid, -1 while it is still in the open group
    function dragRow(): int {
        if (!dragging || (dragging.from === "group" && !leftGroup))
            return -1
        return dragging.group ? (dragging.tile as Tile).index : layout.rowOf(dragging.appId)
    }

    function startDrag(info: var) {
        selection = []
        leftGroup = false
        mergeRow = -1
        groupDrop = -1
        dragging = info
    }

    // Aims the drag from where the dragged tile's middle is, by the grid's cells rather than the tiles in them,
    // which slide while apps make room
    function retarget() {
        if (!dragging || dragPoint.x < 0)
            return
        if (dragging.from === "group" && !leftGroup) {
            const inGroup = groupGrid.mapFromItem(surfaceItem, dragPoint.x, dragPoint.y)
            const groupColumn = Math.max(0, Math.min(groupAcross - 1, Math.floor(inGroup.x / cellWidth)))
            const groupCell = Math.max(0, Math.floor(inGroup.y / cellHeight)) * groupAcross + groupColumn
            groupDrop = groupCell >= openApps.length ? openApps.length
                : inGroup.x / cellWidth - groupColumn < 0.5 ? groupCell : groupCell + 1
            return
        }
        const point = grid.mapFromItem(surfaceItem, dragPoint.x, dragPoint.y)
        if (point.x < 0 || point.x >= grid.width || point.y < 0 || point.y >= grid.height) {
            mergeRow = -1
            return
        }
        const column = Math.floor(point.x / grid.cellWidth)
        const cell = Math.floor((point.y + grid.contentY - grid.originY) / grid.cellHeight) * columns + column
        aim(cell, point.x / grid.cellWidth - column)
    }

    // A drag over the grid's cell, across that far into it: the middle half makes a group with the app there, the
    // sides put the dragged one before or after it, and past the last cell it goes to the end
    function aim(cell: int, across: real) {
        const source = dragRow()
        if (source < 0)
            return
        if (cell >= layout.count) {
            mergeRow = -1
            layout.move(source, layout.count)
        } else if (across >= 0.25 && across <= 0.75) {
            mergeRow = cell !== source && !dragging.group ? cell : -1
        } else {
            mergeRow = -1
            layout.move(source, across < 0.25 ? cell : cell + 1)
        }
    }

    function leaveGroup() {
        leftGroup = true
        groupDrop = -1
        layout.takeOut(openGroup, dragging.appId, openGroup + 1)
    }

    function endDrag() {
        const info = dragging
        if (!info)
            return
        if (info.from === "group" && !leftGroup) {
            if (groupDrop >= 0)
                layout.moveInGroup(openGroup, info.appId, groupDrop)
            openApps = layout.appsOf(openGroup)
        } else if (mergeRow >= 0) {
            // Read before the change, which moves the rows
            const ontoApp = !layout.isGroup(mergeRow)
            const row = layout.group(dragRow(), mergeRow)
            if (info.from === "group")
                closeGroupNow()
            if (row >= 0 && ontoApp)
                openGroupAt(row, true)
        } else {
            layout.commit()
            if (info.from === "group")
                closeGroupNow()
        }
        dragging = null
        leftGroup = false
        mergeRow = -1
        groupDrop = -1
        dragPoint = Qt.point(-1, -1)
    }

    // An app or group tile. from: grid, results, hidden (after the grid) or group (inside the open group)
    component Tile: Item {
        id: tile

        required property int index
        required property bool group
        required property string appId
        required property string name
        required property var apps
        property string from: "grid"
        readonly property var app: group ? null : launchpad.byId[appId] ?? null
        readonly property var members: group ? apps.map(id => launchpad.byId[id]).filter(member => member) : []
        readonly property string key: group ? "group:" + index : "app:" + appId
        readonly property bool current: (from === "grid" || from === "results") && launchpad.current === index
            && (from === "results") === (launchpad.query.trim() !== "")
        readonly property bool chosen: from !== "group" && launchpad.selection.includes(key)
        readonly property bool hiddenApp: !group && launchpad.hiddenIds[appId] === true
        readonly property bool merging: from === "grid" && launchpad.mergeRow === index
        // The place an app dragged out of the open group keeps in the grid until it is dropped
        readonly property bool placeholder: from === "grid" && !group && launchpad.leftGroup
            && launchpad.dragging?.appId === appId
        // Where a drop inside the open group would put the dragged app: before this one, or after the last of a row
        readonly property string zone: from !== "group" || !launchpad.dragging || launchpad.leftGroup
            || launchpad.dragging.appId === appId ? ""
            : launchpad.groupDrop === index ? "before"
            : launchpad.groupDrop === index + 1 && (index === launchpad.openApps.length - 1
                || (index + 1) % launchpad.groupAcross === 0) ? "after" : ""

        width: launchpad.cellWidth
        height: launchpad.cellHeight

        // Where a dropped app goes in between, inside the open group
        Rectangle {
            visible: tile.zone !== ""
            x: tile.zone === "before" ? 0 : tile.width - width
            y: 8
            width: 3
            height: tile.height - 16
            radius: 1.5
            color: launchpad.settings.accentColor
        }

        // The part that follows the mouse while the tile is dragged
        Item {
            id: face

            width: tile.width
            height: tile.height
            opacity: tile.placeholder ? 0 : 1
            onXChanged: if (mouse.drag.active) launchpad.dragPoint = mapToItem(launchpad.surface, width / 2, height / 2)
            onYChanged: if (mouse.drag.active) launchpad.dragPoint = mapToItem(launchpad.surface, width / 2, height / 2)

            states: State {
                name: "dragged"
                when: mouse.drag.active

                ParentChange {
                    target: face
                    parent: launchpad.dragLayer
                }
                PropertyChanges {
                    face.scale: 1.08
                }
            }
            // A dropped tile glides into its place
            transitions: Transition {
                to: ""

                ParentAnimation {
                    NumberAnimation { properties: "x,y"; duration: launchpad.settings.moveDuration; easing.type: Easing.OutCubic }
                }
                NumberAnimation { property: "scale"; duration: launchpad.settings.moveDuration; easing.type: Easing.OutCubic }
            }

            // The tile's own look, which a dragged tile takes with it; the whole tile lights up while a dragged app is
            // held over it to make a group
            Rectangle {
                anchors.fill: parent
                radius: 10
                color: tile.current || tile.chosen || tile.merging ? launchpad.settings.popupSelectedColor
                    : mouse.drag.active || (mouse.containsMouse && !launchpad.dragging) ? launchpad.settings.popupHoverColor
                    : "transparent"
                border.width: tile.current || tile.chosen || tile.merging ? 2 : 0
                border.color: launchpad.settings.accentColor
                Behavior on color {
                    ColorAnimation { duration: 80 }
                }
            }

            Item {
                x: Math.round((parent.width - width) / 2)
                y: launchpad.settings.tilePadding
                width: launchpad.settings.appIconSize
                height: launchpad.settings.appIconSize
                opacity: tile.hiddenApp ? 0.45 : 1

                Image {
                    visible: !tile.group
                    anchors.fill: parent
                    sourceSize: Qt.size(launchpad.settings.appIconSize, launchpad.settings.appIconSize)
                    source: launchpad.iconOf(tile.app)
                }

                Rectangle {
                    visible: tile.group
                    anchors.fill: parent
                    radius: 12
                    color: launchpad.settings.popupCardColor

                    Grid {
                        anchors.centerIn: parent
                        columns: 2
                        spacing: 3

                        Repeater {
                            model: tile.members.slice(0, 4)

                            Image {
                                required property var modelData

                                readonly property int size: Math.floor((launchpad.settings.appIconSize - 15) / 2)

                                width: size
                                height: size
                                sourceSize: Qt.size(size, size)
                                source: launchpad.iconOf(modelData)
                            }
                        }
                    }
                }
            }

            Text {
                x: 6
                y: launchpad.settings.tilePadding + launchpad.settings.appIconSize + 6
                width: parent.width - 12
                height: launchpad.nameHeight
                horizontalAlignment: Text.AlignHCenter
                text: tile.group ? tile.name : tile.app?.name ?? ""
                color: launchpad.settings.popupTextColor
                opacity: tile.hiddenApp ? 0.45 : 1
                font: launchpad.settings.popupFont
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }

            Text {
                visible: tile.hiddenApp
                x: parent.width - width - 10
                y: 10
                text: launchpad.settings.popupIcons.hidden
                color: launchpad.settings.popupSecondaryTextColor
                font.family: launchpad.settings.popupIconFont.family
                font.weight: launchpad.settings.popupIconFont.weight
                font.variableAxes: launchpad.settings.popupIconFont.variableAxes
                font.pixelSize: 14
            }
        }

        MouseArea {
            id: mouse

            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            // Search results keep their order and hidden apps have none, so they are not dragged
            drag.target: tile.from === "results" || tile.from === "hidden" ? null : face
            drag.onActiveChanged: {
                if (drag.active)
                    launchpad.startDrag({ appId: tile.appId, group: tile.group, from: tile.from, tile: tile })
            }
            onReleased: {
                if (launchpad.dragging)
                    Qt.callLater(launchpad.endDrag)
            }
            // As when the launchpad loses the mouse in the middle of a drag
            onCanceled: Qt.callLater(launchpad.endDrag)
            onClicked: event => {
                if (event.button === Qt.RightButton) {
                    launchpad.showMenu(tile)
                } else if (tile.from !== "group" && (event.modifiers & (Qt.ControlModifier | Qt.ShiftModifier))) {
                    launchpad.pick(tile.key, (event.modifiers & Qt.ShiftModifier) !== 0)
                } else {
                    launchpad.selection = []
                    if (tile.group)
                        launchpad.openGroupAt(tile.index, false)
                    else
                        launchpad.launch(tile.appId)
                }
            }
        }
    }

    // An item of the text fields' right-click menu, its icon in menuIconSize
    component FieldMenuItem: MenuItem {
        icon.width: launchpad.settings.menuIconSize
        icon.height: launchpad.settings.menuIconSize
    }

    // A text field with its right-click menu in the widget's look
    component Field: TextField {
        id: textField

        // Qt's own text menu is replaced by fieldMenu, which the right button opens
        ContextMenu.menu: null

        // A right-click opens the menu at the mouse cursor, on press or release as Windows sets it
        TapHandler {
            acceptedButtons: Qt.RightButton
            onPressedChanged: {
                if (pressed === (Application.styleHints.contextMenuTrigger === Qt.ContextMenuTrigger.Press))
                    fieldMenu.popup(textField)
            }
        }
    }

    // A menu in the widget's look
    component WidgetMenu: Menu {
        popupType: Popup.Item
        // Fades in when it opens, in place of the style's growing from a third of its height
        enter: Transition {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: launchpad.settings.menuOpenDuration; easing.type: Easing.OutCubic }
        }
        topInset: 0
        leftInset: 0
        rightInset: 0
        bottomInset: 0
        font: launchpad.settings.menuFont
        // Active and inactive only, so disabled controls keep the style's dimmed colours
        palette.active.text: launchpad.settings.menuTextColor
        palette.inactive.text: launchpad.settings.menuTextColor

        background: Rectangle {
            implicitWidth: launchpad.settings.menuWidth
            radius: launchpad.settings.menuRadius
            color: launchpad.settings.menuColor
            border.color: launchpad.settings.menuBorderColor
        }
    }

    Text {
        id: label

        y: Math.round((parent.height - height) / 2)
        width: launchpad.settings.iconSize
        height: launchpad.settings.iconSize
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        text: launchpad.settings.icon
        color: launchpad.settings.textColor
        font.family: launchpad.settings.iconFont.family
        font.weight: launchpad.settings.iconFont.weight
        font.variableAxes: launchpad.settings.iconFont.variableAxes
        font.pixelSize: launchpad.settings.iconSize
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: launchpad.toggle()
    }

    Hotkey {
        keys: launchpad.settings.hotkey
        screen: launchpad.settings.hotkeyScreen
        onActivated: launchpad.toggle()
    }

    LaunchpadApps {
        id: appLibrary
    }

    // Rows change when apps are installed or removed, and a group's key would point at another row
    Connections {
        target: launchpad.layout

        function onModelReset() {
            launchpad.selection = []
        }
    }

    FontMetrics {
        id: nameMetrics

        font: launchpad.settings.popupFont
    }

    NumberAnimation {
        id: groupAnimation

        target: launchpad
        property: "groupReveal"
        duration: launchpad.settings.groupDuration
        easing.type: Easing.OutCubic
        onFinished: {
            if (launchpad.groupReveal === 0) {
                launchpad.openGroup = -1
                launchpad.openApps = []
            }
        }
    }

    Component.onDestruction: popup.hide()

    BackdropPopup {
        id: popup

        property real reveal: 0

        title: "Launchpad"
        width: Math.min(launchpad.settings.popupWidth, Math.round(launchpad.Screen.width * 0.9))
        height: Math.min(launchpad.settings.popupHeight, Math.round(launchpad.Screen.height * 0.9))
        x: Math.round(launchpad.Screen.virtualX + (launchpad.Screen.width - width) / 2)
        y: Math.round(launchpad.Screen.virtualY + (launchpad.Screen.height - height) / 2)
        anchor: launchpad
        font: launchpad.settings.popupFont
        theme: launchpad.theme
        backdropItem: surfaceItem
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: launchpad.settings.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: launchpad.settings.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible) {
                reveal = 0
                // The menus live in the popup's window and would show again with it
                tileMenu.close()
                gridMenu.close()
                fieldMenu.close()
                launchpad.closeGroupNow()
                launchpad.query = ""
                launchpad.selection = []
                launchpad.showHidden = false
            }
        }

        Rectangle {
            id: surfaceItem

            anchors.fill: parent
            radius: launchpad.settings.popupRadius
            color: launchpad.settings.popupColor
            border.width: 1
            border.color: launchpad.settings.popupBorderColor
            opacity: popup.reveal
            scale: 0.86 + popup.reveal * 0.14
            // Nothing takes a click while the popup fades
            enabled: !popup.closing

            // Under every other part, so it gets only clicks outside the tiles and the search field: a click clears the
            // selection, a right-click opens the hidden apps menu
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: event => {
                    launchpad.selection = []
                    if (event.button === Qt.RightButton)
                        gridMenu.popup()
                }
            }

            Field {
                id: field

                x: 16
                y: 16
                width: parent.width - 32
                height: 40
                leftPadding: 12 + launchpad.settings.searchIconSize + 10
                placeholderText: launchpad.settings.searchPlaceholder
                color: launchpad.settings.popupTextColor
                font: launchpad.settings.searchFont
                background: Rectangle {
                    radius: 6
                    color: launchpad.settings.popupCardColor
                    border.width: field.activeFocus ? 1 : 0
                    border.color: launchpad.settings.accentColor
                }
                onTextChanged: launchpad.query = text
                Keys.onShortcutOverride: event => event.accepted = event.key === Qt.Key_Escape
                    && (launchpad.openGroup >= 0 || launchpad.selection.length > 0)
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Left)
                        launchpad.step(-1, 0)
                    else if (event.key === Qt.Key_Right)
                        launchpad.step(1, 0)
                    else if (event.key === Qt.Key_Up)
                        launchpad.step(0, -1)
                    else if (event.key === Qt.Key_Down)
                        launchpad.step(0, 1)
                    else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                        launchpad.activateCurrent()
                    else if (event.matches(StandardKey.SelectAll))
                        launchpad.selection = launchpad.shownKeys()
                    else if (event.key === Qt.Key_Escape && launchpad.selection.length > 0)
                        launchpad.selection = []
                    else if (event.key === Qt.Key_Escape && launchpad.openGroup >= 0)
                        launchpad.closeGroup()
                    else
                        return
                    event.accepted = true
                }

                Text {
                    x: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: launchpad.settings.popupIcons.search
                    color: launchpad.settings.popupSecondaryTextColor
                    font.family: launchpad.settings.popupIconFont.family
                    font.weight: launchpad.settings.popupIconFont.weight
                    font.variableAxes: launchpad.settings.popupIconFont.variableAxes
                    font.pixelSize: launchpad.settings.searchIconSize
                }
            }

            Text {
                visible: (launchpad.query.trim() ? launchpad.results.length : launchpad.layout.count) === 0
                anchors.horizontalCenter: parent.horizontalCenter
                y: field.y + field.height + 32
                text: launchpad.query.trim() ? qsTr("No apps found")
                    : launchpad.library.loading ? qsTr("Loading apps...") : qsTr("No apps")
                color: launchpad.settings.popupSecondaryTextColor
                font: launchpad.settings.popupFont
            }

            GridView {
                id: grid

                x: Math.round((parent.width - width) / 2)
                y: field.y + field.height + 12
                width: Math.max(1, Math.floor((parent.width - 32) / launchpad.cellWidth)) * launchpad.cellWidth
                height: parent.height - y - 12
                visible: !launchpad.query.trim()
                cellWidth: launchpad.cellWidth
                cellHeight: launchpad.cellHeight
                clip: true
                // Dragging moves tiles, so the grid scrolls by the wheel and its scroll bar only
                interactive: false
                model: launchpad.layout
                ScrollBar.vertical: ScrollBar {}

                delegate: Tile {}

                footer: Column {
                    width: grid.width
                    visible: launchpad.showHidden && launchpad.layout.hidden.length > 0
                    height: visible ? implicitHeight : 0
                    topPadding: 16

                    Text {
                        x: 6
                        bottomPadding: 6
                        text: qsTr("Hidden apps")
                        color: launchpad.settings.popupSecondaryTextColor
                        font: launchpad.settings.popupFont
                    }

                    Grid {
                        columns: launchpad.columns

                        Repeater {
                            model: launchpad.showHidden ? launchpad.layout.hidden : []

                            Tile {
                                required property var modelData

                                group: false
                                appId: modelData
                                name: ""
                                apps: []
                                from: "hidden"
                            }
                        }
                    }
                }

                // Apps slide aside to make room, and into the place a moved one left. Each slide also brings opacity
                // and scale back to full, as one can cut an app's fade-in short and leave it half shown
                displaced: Transition {
                    NumberAnimation { properties: "x,y"; duration: launchpad.settings.moveDuration; easing.type: Easing.OutCubic }
                    NumberAnimation { property: "opacity"; to: 1; duration: launchpad.settings.moveDuration }
                    NumberAnimation { property: "scale"; to: 1; duration: launchpad.settings.moveDuration }
                }
                move: Transition {
                    NumberAnimation { properties: "x,y"; duration: launchpad.settings.moveDuration; easing.type: Easing.OutCubic }
                    NumberAnimation { property: "opacity"; to: 1; duration: launchpad.settings.moveDuration }
                    NumberAnimation { property: "scale"; to: 1; duration: launchpad.settings.moveDuration }
                }
                add: Transition {
                    NumberAnimation { property: "scale"; from: 0.6; to: 1; duration: launchpad.settings.moveDuration; easing.type: Easing.OutCubic }
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: launchpad.settings.moveDuration }
                }
                remove: Transition {
                    NumberAnimation { property: "scale"; to: 0.6; duration: launchpad.settings.moveDuration; easing.type: Easing.InCubic }
                    NumberAnimation { property: "opacity"; to: 0; duration: launchpad.settings.moveDuration }
                }

                WheelHandler {
                    onWheel: event => {
                        grid.contentY = Math.max(grid.originY, Math.min(grid.originY + grid.contentHeight - grid.height,
                            grid.contentY - event.angleDelta.y / 120 * launchpad.cellHeight))
                    }
                }
            }

            GridView {
                id: resultsGrid

                x: grid.x
                y: grid.y
                width: grid.width
                height: grid.height
                visible: launchpad.query.trim() !== ""
                cellWidth: launchpad.cellWidth
                cellHeight: launchpad.cellHeight
                clip: true
                interactive: false
                model: launchpad.results
                ScrollBar.vertical: ScrollBar {}

                WheelHandler {
                    onWheel: event => {
                        resultsGrid.contentY = Math.max(resultsGrid.originY, Math.min(
                            resultsGrid.originY + resultsGrid.contentHeight - resultsGrid.height,
                            resultsGrid.contentY - event.angleDelta.y / 120 * launchpad.cellHeight))
                    }
                }

                delegate: Tile {
                    required property var modelData

                    group: false
                    appId: modelData.id
                    name: ""
                    apps: []
                    from: "results"
                }
            }

            // Scrolls the grid while a tile is dragged near its top or bottom
            FrameAnimation {
                readonly property real edge: launchpad.dragPoint.y < 0 ? 0 : launchpad.dragPoint.y < grid.y + 40 ? -1
                    : launchpad.dragPoint.y > grid.y + grid.height - 40 ? 1 : 0

                running: launchpad.dragging !== null && (launchpad.openGroup < 0 || launchpad.leftGroup) && edge !== 0
                onTriggered: {
                    grid.contentY = Math.max(grid.originY, Math.min(grid.originY + grid.contentHeight - grid.height,
                        grid.contentY + edge * 12))
                    launchpad.retarget()
                }
            }

            // The open group over the grid, grown out of its tile. An app dragged out of it hands the drag to the grid
            Item {
                id: groupLayer

                anchors.fill: parent
                visible: launchpad.openGroup >= 0

                // Fades the group away as soon as an app leaves it
                property real shown: launchpad.leftGroup ? 0 : 1
                Behavior on shown {
                    NumberAnimation { duration: 150 }
                }

                Rectangle {
                    anchors.fill: parent
                    radius: launchpad.settings.popupRadius
                    color: launchpad.settings.smokeColor
                    opacity: launchpad.groupReveal * groupLayer.shown

                    MouseArea {
                        anchors.fill: parent
                        enabled: !launchpad.dragging
                        onClicked: launchpad.closeGroup()
                    }
                }

                Rectangle {
                    id: groupCard

                    readonly property real startX: launchpad.groupOrigin.x - width / 2
                    readonly property real startY: launchpad.groupOrigin.y - height / 2

                    width: launchpad.groupAcross * launchpad.cellWidth + 32
                    height: groupName.height + Math.ceil(launchpad.openApps.length / launchpad.groupAcross) * launchpad.cellHeight
                        + 42
                    x: startX + (Math.round((parent.width - width) / 2) - startX) * launchpad.groupReveal
                    y: startY + (Math.round((parent.height - height) / 2) - startY) * launchpad.groupReveal
                    scale: 0.2 + 0.8 * launchpad.groupReveal
                    opacity: Math.min(1, launchpad.groupReveal * 1.5) * groupLayer.shown
                    radius: launchpad.settings.groupRadius
                    color: launchpad.settings.groupColor
                    border.width: 1
                    border.color: launchpad.settings.groupBorderColor

                    // Takes clicks and drops on the group, so they do not reach the grid behind
                    MouseArea {
                        anchors.fill: parent
                    }

                    Field {
                        id: groupName

                        x: 16
                        y: 14
                        width: parent.width - 32
                        horizontalAlignment: TextInput.AlignHCenter
                        color: launchpad.settings.popupTextColor
                        font: launchpad.settings.groupNameFont
                        background: Rectangle {
                            radius: 6
                            color: groupName.activeFocus ? launchpad.settings.popupCardColor : "transparent"
                            border.width: groupName.activeFocus ? 1 : 0
                            border.color: launchpad.settings.accentColor
                        }
                        onEditingFinished: launchpad.renameOpenGroup()
                        Keys.onShortcutOverride: event => event.accepted = event.key === Qt.Key_Escape
                        Keys.onPressed: event => {
                            if (event.key === Qt.Key_Escape) {
                                launchpad.closeGroup()
                                event.accepted = true
                            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                launchpad.renameOpenGroup()
                                field.forceActiveFocus()
                                event.accepted = true
                            }
                        }
                    }

                    Grid {
                        id: groupGrid

                        x: 16
                        y: groupName.y + groupName.height + 12
                        columns: launchpad.groupAcross

                        Repeater {
                            model: launchpad.openApps

                            Tile {
                                required property var modelData

                                group: false
                                appId: modelData
                                name: ""
                                apps: []
                                from: "group"
                            }
                        }
                    }
                }
            }

            // Dragged tiles move here, above the grid and an open group
            Item {
                id: dragLayerItem

                anchors.fill: parent
            }

            // A tile's menu: for one app, one group, or the selection
            WidgetMenu {
                id: tileMenu

                // The one app or the row of the one group it is about, else the selection's keys it acts on
                property string appId: ""
                property int groupRow: -1
                property var keys: []
                property var entries: []

                function show(id: string, row: int, chosen: var) {
                    // A current item left from the menu still open would shift as the items are replaced, and the
                    // style's list and the menu would keep setting each other's currentIndex
                    tileMenu.currentIndex = -1
                    appId = id
                    groupRow = row
                    keys = chosen
                    const hiddenCount = chosen.filter(key => launchpad.isHiddenKey(key)).length
                    const shownCount = chosen.length - hiddenCount
                    const apps = chosen.filter(key => key.startsWith("app:") && !launchpad.isHiddenKey(key)).length
                    const labels = {
                        run_as_admin: qsTr("Run as administrator"),
                        open_file_location: qsTr("Open file location"),
                        uninstall: qsTr("Uninstall")
                    }
                    let list = []
                    if (id && launchpad.hiddenIds[id] === true) {
                        list = [{ id: "open", text: qsTr("Open") }, { id: "unhide", text: qsTr("Unhide") }]
                    } else if (id) {
                        const actions = launchpad.library.actions(id)
                        const separator = { kind: "separator" }
                        list = [{ id: "open", text: qsTr("Open") }]
                            .concat(actions.filter(action => action !== "uninstall")
                                .map(action => ({ id: action, text: labels[action] })))
                            .concat([separator, { id: "hide", text: qsTr("Hide") }])
                            .concat(actions.includes("uninstall") ? [separator, { id: "uninstall", text: labels.uninstall }] : [])
                    } else if (row >= 0) {
                        list = [
                            { id: "open", text: qsTr("Open") },
                            { id: "ungroup", text: qsTr("Ungroup") },
                            { id: "hide", text: qsTr("Hide group") }
                        ]
                    } else {
                        if (shownCount)
                            list.push({ id: "hide", text: shownCount === 1 ? qsTr("Hide") : qsTr("Hide %1 items").arg(shownCount) })
                        if (hiddenCount)
                            list.push({ id: "unhide", text: hiddenCount === 1 ? qsTr("Unhide") : qsTr("Unhide %1 apps").arg(hiddenCount) })
                        if (apps > 1)
                            list.push({ id: "group", text: qsTr("Group %1 apps").arg(apps) })
                    }
                    entries = list
                    tileMenu.popup()
                }

                Instantiator {
                    model: tileMenu.entries

                    // An entry of kind separator is a line, any other an item
                    delegate: DelegateChooser {
                        role: "kind"

                        DelegateChoice {
                            roleValue: "separator"

                            MenuSeparator {}
                        }
                        DelegateChoice {
                            MenuItem {
                                required property var modelData

                                text: modelData.text
                                onTriggered: launchpad.runMenu(modelData.id)
                            }
                        }
                    }

                    onObjectAdded: (index, object) => tileMenu.insertItem(index, object)
                    onObjectRemoved: (index, object) => tileMenu.removeItem(object)
                }
            }

            // The menu outside the tiles
            WidgetMenu {
                id: gridMenu

                // Qt checks the item itself when it is clicked, which would leave it apart from showHidden
                onAboutToShow: showHiddenItem.checked = launchpad.showHidden

                MenuItem {
                    id: showHiddenItem

                    text: qsTr("Show hidden apps (%1)").arg(launchpad.layout.hidden.length)
                    checkable: true
                    enabled: launchpad.layout.hidden.length > 0 || launchpad.showHidden
                    onTriggered: launchpad.showHidden = checked
                }
            }

            // The text fields' right-click menu: Qt's editing items and icons in the menu's look, acting on the field that
            // opened it
            WidgetMenu {
                id: fieldMenu

                readonly property TextField line: parent as TextField
                readonly property bool editable: !(line?.readOnly ?? true)
                readonly property bool selected: (line?.selectedText.length ?? 0) > 0

                // A window of its own, so it opens where clicked even past the popup's edges
                popupType: Popup.Window
                // Its window is made once and reused, and Windows shows it again where it was, under the popup raised
                // since; raising it before it shows keeps it in front
                onAboutToShow: contentItem.Window.window?.raise()

                FieldMenuItem {
                    text: qsTr("Undo")
                    icon.name: "edit-undo"
                    enabled: fieldMenu.line?.canUndo ?? false
                    onTriggered: fieldMenu.line?.undo()
                }
                FieldMenuItem {
                    text: qsTr("Redo")
                    icon.name: "edit-redo"
                    enabled: fieldMenu.line?.canRedo ?? false
                    onTriggered: fieldMenu.line?.redo()
                }
                MenuSeparator {}
                FieldMenuItem {
                    text: qsTr("Cut")
                    icon.name: "edit-cut"
                    enabled: fieldMenu.editable && fieldMenu.selected
                    onTriggered: fieldMenu.line?.cut()
                }
                FieldMenuItem {
                    text: qsTr("Copy")
                    icon.name: "edit-copy"
                    enabled: fieldMenu.selected
                    onTriggered: fieldMenu.line?.copy()
                }
                FieldMenuItem {
                    text: qsTr("Paste")
                    icon.name: "edit-paste"
                    enabled: fieldMenu.editable && (fieldMenu.line?.canPaste ?? false)
                    onTriggered: fieldMenu.line?.paste()
                }
                FieldMenuItem {
                    text: qsTr("Delete")
                    icon.name: "edit-delete"
                    enabled: fieldMenu.editable && fieldMenu.selected
                    onTriggered: fieldMenu.line?.remove(fieldMenu.line.selectionStart, fieldMenu.line.selectionEnd)
                }
                MenuSeparator {}
                FieldMenuItem {
                    text: qsTr("Select All")
                    icon.name: "edit-select-all"
                    onTriggered: fieldMenu.line?.selectAll()
                }
            }
        }
    }

    // State while the launchpad is used, and values worked out from it; none of this is an option
    readonly property LaunchpadApps library: appLibrary
    readonly property LaunchpadLayout layout: appLibrary.layout
    // The text typed in the search field
    property string query: ""
    // The row of the open group, -1 when none is; its apps, kept as they were while one of them is dragged out
    property int openGroup: -1
    property var openApps: []
    // 0 while the open group is folded into its tile, 1 once it is open; where its tile is in the popup
    property real groupReveal: 0
    property point groupOrigin: Qt.point(0, 0)
    // The tile the keyboard is on: its row in the grid, or its place in the search results
    property int current: -1
    // The tiles selected with Ctrl, Shift and Ctrl+A, by key: app:<id> or group:<row>; the one Shift selects from
    property var selection: []
    property string anchorKey: ""
    // The hidden apps show dimmed after the grid and in search, until the launchpad closes
    property bool showHidden: false
    // What is being dragged: {appId, group, from, tile}, from grid or group, group true for a group's tile
    property var dragging: null
    // An app dragged out of the open group, now in the grid
    property bool leftGroup: false
    // The row a dragged app would make a group with, and its place in the open group when dragged inside it
    property int mergeRow: -1
    property int groupDrop: -1
    // The middle of the dragged tile, in the popup's surface
    property point dragPoint: Qt.point(-1, -1)

    readonly property var byId: {
        const known = {}
        for (const app of library.apps)
            known[app.id] = app
        return known
    }
    readonly property var hiddenIds: {
        const ids = {}
        for (const id of layout.hidden)
            ids[id] = true
        return ids
    }
    readonly property var results: {
        const text = query.trim().toLowerCase()
        if (!text)
            return []
        const starting = []
        const containing = []
        for (const app of library.apps) {
            if (hiddenIds[app.id] === true && !showHidden)
                continue
            const name = app.name.toLowerCase()
            if (name.startsWith(text))
                starting.push(app)
            else if (name.includes(text))
                containing.push(app)
        }
        return starting.concat(containing)
    }
    // Every tile holds its icon and two lines of name, as Start does. It is twelve average letters of popupFont wide,
    // never narrower than the icon, plus tilePadding on each side, and the name may run across all of it
    readonly property real nameHeight: Math.ceil(nameMetrics.height * 2)
    readonly property real cellWidth: Math.max(settings.appIconSize, Math.ceil(nameMetrics.averageCharacterWidth * 12)) + 2 * settings.tilePadding
    readonly property real cellHeight: settings.appIconSize + 6 + nameHeight + 2 * settings.tilePadding
    readonly property int columns: Math.max(1, Math.floor(grid.width / cellWidth))
    readonly property int groupAcross: Math.max(1, Math.min(settings.groupColumns, openApps.length))
    readonly property bool insideGroup: groupCard.contains(groupCard.mapFromItem(surfaceItem, dragPoint.x, dragPoint.y))
    readonly property Item surface: surfaceItem
    readonly property Item dragLayer: dragLayerItem
}
