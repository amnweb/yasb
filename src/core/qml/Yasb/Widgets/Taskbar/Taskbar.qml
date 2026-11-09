pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb

Item {
    id: taskbar

    property Item bar: null
    property int iconSize: 16
    // One button per app holding all its windows, or one per window
    property bool grouping: true
    // The number of windows on a grouped button, from two
    property bool showCount: true
    // The running-window indicator along each button's edge
    property bool showIndicator: true
    // Window titles beside the icons: never, focused (the window in front) or always
    property string titles: "never"
    property int titleMaxWidth: 64
    property bool tooltip: true
    // What a middle click on a button does: launch (a new window of the app), close (its window) or none
    property string middleClick: "launch"
    property bool animation: true
    property int animationDuration: 300
    // Only windows on the bar's own screen
    property bool onlyThisScreen: false
    // Leaves out cloaked windows, such as those on other virtual desktops
    property bool onlyVisible: false
    // Leaves out windows that cannot be minimized, such as some dialogs
    property bool strictFiltering: true
    // Windows to leave out, by their exact class, process or title, such as ["Notepad.exe"]
    property list<string> ignoreClasses: []
    property list<string> ignoreProcesses: []
    property list<string> ignoreTitles: []
    // Live previews of a button's windows while the pointer rests on it, after previewDelay milliseconds
    property bool preview: true
    property int previewDelay: 400
    property int previewWidth: 240
    // Fades every other window while the pointer rests on a preview, showing that one on the desktop
    property bool peek: true
    // Hides the widget while there is nothing pinned or open
    property bool hideWhenEmpty: false
    property int spacing: 4
    // Space before and after a button's icon and title, or above and below its icon on a vertical bar
    property int buttonPadding: 8
    // Space between a button and the bar's top and bottom edges, or its sides on a vertical bar; the button's
    // height is the bar's less this at both edges
    property int buttonMargin: 2
    property int buttonRadius: 5
    property color accentColor: dark ? "#60CDFF" : "#005FB8"
    // A window asking for attention
    property color attentionColor: "#ff99a4"

    readonly property bool dark: bar ? bar.dark : Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    property font font
    font.family: bar?.font.family ?? Qt.application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})
    readonly property string edge: bar?.edge ?? "top"
    readonly property bool vertical: bar?.vertical ?? false
    readonly property color ink: dark ? "#ffffff" : "#000000"

    // The buttons in order, each {key, app, windows}: a whole app when grouping, else a window, or a pinned app
    // with no window open. Pinned apps come first; the others follow in the order they were dragged to, then as they
    // opened
    readonly property var buttons: {
        const pinned = []
        const others = []
        for (const app of apps.apps) {
            const into = app.pinned ? pinned : others
            if (grouping || app.windows.length === 0)
                into.push({ key: app.id, app: app, windows: app.windows })
            else
                for (const window of app.windows)
                    into.push({ key: `window:${window.hwnd}`, app: app, windows: [window] })
        }
        const rank = button => {
            const index = order.indexOf(button.key)
            return index === -1 ? order.length + others.indexOf(button) : index
        }
        return pinned.concat(others.slice().sort((a, b) => rank(a) - rank(b)))
    }
    readonly property var buttonsByKey: {
        const byKey = {}
        for (const button of buttons)
            byKey[button.key] = button
        return byKey
    }
    // The buttons of apps that are not pinned, by key, in the order they were dragged to on this taskbar
    property var order: []
    // Animations wait for the first buttons, so the bar does not animate every window at start
    property bool ready: false
    readonly property string mimeType: "application/x-yasb-taskbar-button"
    // The button being dragged to a new place, by key; the buttons follow the pointer until it is dropped
    property string draggedKey: ""

    // The buttons' keys in their place on the bar, and each button's length along it once its own animations end.
    // Every button is placed from these rather than from the others' current sizes, so a button that grows or
    // shrinks while others move can never leave them overlapping
    property var placed: []
    property var lengths: ({})
    // Where each button starts along the bar, by key, and the length of them all
    readonly property var layout: {
        const at = {}
        let offset = 0
        for (const key of placed) {
            at[key] = offset
            const length = lengths[key] ?? 0
            // A button shrinking away takes its gap with it
            offset += length > 0 ? length + spacing : 0
        }
        return { offsets: at, extent: Math.max(0, offset - spacing) }
    }
    readonly property var offsets: layout.offsets
    readonly property real extent: layout.extent
    // The widget's own length on the bar follows its buttons as they animate, so the bar moves what is beside it, or
    // centres it, smoothly rather than at once
    property real shownExtent: extent
    Behavior on shownExtent {
        enabled: taskbar.animation && taskbar.ready
        NumberAnimation { duration: taskbar.animationDuration; easing.type: Easing.OutCubic }
    }
    // The buttons of closed apps, by key, kept while they shrink and fade away, until when in milliseconds
    property var leaving: ({})

    function setLength(key: string, length: real) {
        if (lengths[key] === length)
            return
        const changed = Object.assign({}, lengths)
        changed[key] = length
        lengths = changed
    }

    // Keeps a list model's entries, each {key}, in step with these keys, moving and inserting rather than resetting,
    // so what shows each entry stays
    function syncModel(model: ListModel, keys: var) {
        const wanted = new Set(keys)
        for (let i = model.count - 1; i >= 0; i--) {
            if (!wanted.has(model.get(i).key))
                model.remove(i)
        }
        for (let i = 0; i < keys.length; i++) {
            const found = modelIndex(model, keys[i], i)
            if (found === -1)
                model.insert(i, { key: keys[i] })
            else if (found !== i)
                model.move(found, i, 1)
        }
    }

    function modelIndex(model: ListModel, key: string, from: int): int {
        for (let i = from; i < model.count; i++) {
            if (model.get(i).key === key)
                return i
        }
        return -1
    }

    function modelKeys(model: ListModel): var {
        const keys = []
        for (let i = 0; i < model.count; i++)
            keys.push(model.get(i).key)
        return keys
    }

    function sync() {
        if (draggedKey !== "")
            return
        // From the buttons themselves: buttonsByKey can still hold the old ones when this runs
        const live = buttons.map(button => button.key)
        const liveSet = new Set(live)
        const now = Date.now()
        const stillLeaving = {}
        for (const key of Object.keys(leaving)) {
            if (!liveSet.has(key) && leaving[key] > now)
                stillLeaving[key] = leaving[key]
        }
        // A closed app's button stays in its place, after the button before it, while it shrinks away
        const current = modelKeys(buttonModel)
        const after = {}
        current.forEach((key, i) => {
            if (liveSet.has(key))
                return
            if (!(key in stillLeaving)) {
                if (!(key in leaving) && animation && ready)
                    stillLeaving[key] = now + animationDuration
                else
                    return
            }
            let before = ""
            for (let j = i - 1; j >= 0; j--) {
                if (liveSet.has(current[j])) {
                    before = current[j]
                    break
                }
            }
            after[key] = before
        })
        leaving = stillLeaving
        const keys = []
        const placeLeaving = before => {
            for (const key of Object.keys(after)) {
                if (after[key] === before)
                    keys.push(key)
            }
        }
        placeLeaving("")
        for (const key of live) {
            keys.push(key)
            placeLeaving(key)
        }
        syncModel(buttonModel, keys)
        placed = keys
        const soonest = Math.min(...Object.values(stillLeaving))
        if (Number.isFinite(soonest)) {
            leaveTimer.interval = Math.max(1, soonest - now)
            leaveTimer.restart()
        }
        const kept = {}
        for (const key of keys) {
            if (key in lengths)
                kept[key] = lengths[key]
        }
        lengths = kept
    }

    // The button at a point along the bar, by key; a button shrinking away is never one
    function keyAt(x: real, y: real): string {
        const along = vertical ? y : x
        for (const key of placed) {
            const start = offsets[key]
            const length = lengths[key] ?? 0
            if (length > 0 && along >= start && along < start + length + spacing)
                return key
        }
        return ""
    }

    // Moves the dragged button to the place of the one under the pointer
    function dragTo(x: real, y: real) {
        const over = keyAt(x, y)
        const from = modelIndex(buttonModel, draggedKey, 0)
        const to = modelIndex(buttonModel, over, 0)
        if (over !== "" && from !== -1 && to !== -1 && to !== from) {
            buttonModel.move(from, to, 1)
            placed = modelKeys(buttonModel)
        }
    }

    // Keeps the place the dragged button was dropped at: a pinned app moves among the pinned ones, another app dropped
    // before the last pinned one is pinned there, and one dropped after them keeps its place on this taskbar
    function drop() {
        const entry = buttonsByKey[draggedKey]
        if (!entry)
            return
        const keys = modelKeys(buttonModel)
        const index = keys.indexOf(draggedKey)
        let lastPinned = -1
        const pinnedBefore = new Set()
        keys.forEach((key, i) => {
            const other = buttonsByKey[key]
            if (key === draggedKey || !other?.app.pinned || other.app.id === entry.app.id)
                return
            lastPinned = i
            if (i < index)
                pinnedBefore.add(other.app.id)
        })
        if (entry.app.pinned)
            apps.move(entry.app.id, pinnedBefore.size)
        else if (index < lastPinned)
            apps.pin(entry.app.id, pinnedBefore.size)
        else
            order = keys.filter(key => !(buttonsByKey[key]?.app.pinned ?? true))
    }

    function endDrag() {
        draggedKey = ""
        sync()
    }

    onButtonsChanged: sync()
    Component.onCompleted: {
        sync()
        ready = true
    }
    Component.onDestruction: previewPopup.dismiss()

    // A hidden widget takes no room on the bar, as its slot keeps the size it asks for
    readonly property bool shown: !hideWhenEmpty || buttons.length > 0

    implicitWidth: !shown ? 0 : vertical ? (bar?.width ?? iconSize + 12) : shownExtent
    implicitHeight: !shown ? 0 : vertical ? shownExtent : iconSize + 12

    // Takes away the buttons of closed apps once they have shrunk
    Timer {
        id: leaveTimer

        onTriggered: taskbar.sync()
    }
    visible: shown

    TaskbarApps {
        id: apps

        screenName: taskbar.onlyThisScreen ? (taskbar.bar?.screenName ?? "") : ""
        onlyVisible: taskbar.onlyVisible
        strictFiltering: taskbar.strictFiltering
        ignoreClasses: taskbar.ignoreClasses
        ignoreProcesses: taskbar.ignoreProcesses
        ignoreTitles: taskbar.ignoreTitles
    }

    ListModel {
        id: buttonModel
    }

    // The right-click menu: what the app offers, then the app itself, pinning and closing; each entry {type, text,
    // icon, iconText, glyph, iconSize, action, target, arguments}, type item, label (shown, not chosen) or separator
    function menuEntries(button: Item): var {
        const app = button.app
        const offered = apps.jumpList(app.id)
        const entries = []
        const glyphs = {
            window: "\ue78b", private: "\ue727", profile: "\ue756", folder: "\ue8b7", explorer: "\ue8b7"
        }
        const bin = offered.items.find(item => item.kind === "recycleBin")
        if (bin) {
            if (bin.items > 0) {
                entries.push({ type: "label", text: qsTr("%n item(s), %1", "", bin.items)
                    .arg(Qt.locale().formattedDataSize(bin.bytes)) })
                entries.push({ type: "item", glyph: "\ue74d", text: qsTr("Empty Recycle Bin"), action: "emptyBin" })
            }
        } else {
            const folders = offered.items.filter(item => item.kind === "folder")
            if (folders.length > 0)
                entries.push({ type: "label", text: qsTr("Pinned") })
            for (const item of folders.concat(offered.items.filter(item => item.kind !== "folder")))
                entries.push({ type: "item", text: item.text, action: "launch", target: item.target,
                    arguments: item.arguments, glyph: glyphs[item.kind], icon: item.icon, iconText: item.iconText })
        }
        if (entries.length > 0)
            entries.push({ type: "separator" })
        // Apps found only by their window cannot be started again or pinned
        const known = !app.id.startsWith("window:")
        if (known)
            entries.push({ type: "item", icon: button.icon, text: offered.name || button.window?.title || app.name,
                action: "launch", target: app.id, arguments: "" })
        if (app.pinned)
            entries.push({ type: "item", glyph: "\ue77a", text: qsTr("Unpin from taskbar"), action: "unpin" })
        else if (known)
            entries.push({ type: "item", glyph: "\ue718", text: qsTr("Pin to taskbar"), action: "pin" })
        if (button.running) {
            entries.push({ type: "separator" })
            entries.push({ type: "item", glyph: "\ue8bb", iconSize: 11, action: "close",
                text: button.windows.length > 1 ? qsTr("Close all %1 windows").arg(button.windows.length)
                    : qsTr("Close window") })
        }
        return entries
    }

    function runEntry(entry: var, button: var) {
        switch (entry.action) {
        case "launch":
            apps.launch(entry.target, entry.arguments)
            break
        case "emptyBin":
            apps.emptyRecycleBin()
            break
        case "pin":
            apps.pin(button.app.id)
            break
        case "unpin":
            apps.unpin(button.app.id)
            break
        case "close":
            for (const window of button.windows)
                apps.close(window.hwnd)
            break
        }
    }

    function openMenu(button: Item) {
        menu?.close()
        const start = button.mapToGlobal(0, 0)
        const screen = taskbar.Screen
        menu = menuComponent.createObject(null, {
            entries: menuEntries(button),
            button: { app: button.app, windows: button.windows },
            anchor: Qt.rect(start.x, start.y, button.width, button.height),
            // This screen; desktopAvailableHeight would be the height of all screens together
            area: Qt.rect(screen.virtualX, screen.virtualY, screen.width, screen.height)
        })
    }

    // The menu that is open, if one is
    property Window menu: null

    Component {
        id: menuComponent

        // The menu sits in a window of its own, as the bar's other menus do: Qt keeps popup windows inside the work
        // area and under the bar's always-on-top window
        Window {
            id: menuHost

            required property var entries
            // The app and windows the menu is about, kept as they were when it opened
            required property var button
            required property rect anchor
            required property rect area
            readonly property int gap: 6
            readonly property int iconSize: 16
            readonly property string iconFamily: Qt.fontFamilies().includes("Segoe Fluent Icons")
                ? "Segoe Fluent Icons" : "Segoe MDL2 Assets"

            flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
            color: "transparent"
            width: menu.width
            height: menu.implicitHeight
            // Beside the button, away from the bar's edge, and inside the screen
            x: {
                const wanted = taskbar.edge === "left" ? anchor.x + anchor.width + gap
                    : taskbar.edge === "right" ? anchor.x - width - gap : anchor.x + (anchor.width - width) / 2
                return Math.round(Math.max(area.x, Math.min(wanted, area.x + area.width - width)))
            }
            y: {
                const wanted = taskbar.edge === "bottom" ? anchor.y - height - gap
                    : taskbar.edge === "top" ? anchor.y + anchor.height + gap : anchor.y
                return Math.round(Math.max(area.y, Math.min(wanted, area.y + area.height - height)))
            }

            Component.onCompleted: {
                for (const entry of entries) {
                    // Made with the menu as their parent: without one, JavaScript's garbage collector can delete
                    // them while the menu is open, leaving an empty menu a pixel or two tall
                    const item = entry.type === "separator" ? separatorComponent.createObject(menu.contentItem)
                        : itemComponent.createObject(menu.contentItem, { entry: entry })
                    menu.addItem(item)
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
                if (!visible) {
                    if (taskbar.menu === menuHost)
                        taskbar.menu = null
                    destroy()
                }
            }

            Component {
                id: itemComponent

                MenuItem {
                    id: menuItem

                    required property var entry
                    readonly property int iconSize: entry.iconSize ?? menuHost.iconSize

                    text: entry.text
                    enabled: entry.type === "item"

                    contentItem: RowLayout {
                        spacing: 8
                        layoutDirection: menuItem.mirrored ? Qt.RightToLeft : Qt.LeftToRight

                        Item {
                            visible: menuItem.enabled
                            Layout.preferredWidth: menuHost.iconSize
                            Layout.preferredHeight: menuHost.iconSize

                            Image {
                                id: image

                                anchors.centerIn: parent
                                width: menuItem.iconSize
                                height: menuItem.iconSize
                                // An icon from the icon service asks again with the latest revision, so one still
                                // loading when the menu opened shows as soon as it is ready
                                source: (menuItem.entry.icon ?? "").startsWith("image://icon/")
                                    ? menuItem.entry.icon.replace(/\/\d+$/, "/" + apps.iconRevision)
                                    : (menuItem.entry.icon ?? "")
                                sourceSize: Qt.size(menuItem.iconSize, menuItem.iconSize)
                                asynchronous: menuItem.entry.icon?.startsWith("file:") ?? false
                                fillMode: Image.PreserveAspectFit
                            }

                            Text {
                                anchors.centerIn: parent
                                visible: image.status !== Image.Ready
                                text: menuItem.entry.iconText ?? menuItem.entry.glyph ?? ""
                                textFormat: Text.PlainText
                                font.family: menuItem.entry.iconText ? "Segoe UI Emoji" : menuHost.iconFamily
                                font.pixelSize: menuItem.iconSize
                                color: menuItem.palette.text
                                Accessible.ignored: true
                            }
                        }

                        Label {
                            Layout.fillWidth: true
                            text: menuItem.text
                            textFormat: Text.PlainText
                            font: menuItem.font
                            color: menuItem.palette.text
                            elide: Text.ElideRight
                            Accessible.ignored: true
                        }
                    }

                    // A native action can process window events while the menu is closing.
                    onTriggered: Qt.callLater(taskbar.runEntry, entry, menuHost.button)
                }
            }

            Component {
                id: separatorComponent

                MenuSeparator {}
            }

            // Looks like the bar's own right-click menu
            Menu {
                id: menu

                font: taskbar.font
                topInset: 0
                leftInset: 0
                rightInset: 0
                bottomInset: 0
                popupType: Popup.Item
                // The items take their text colour from this, so it matches the background in light and dark
                palette.text: taskbar.ink
                palette.windowText: taskbar.ink
                palette.buttonText: taskbar.ink
                onClosed: menuHost.close()

                background: Rectangle {
                    implicitWidth: 260
                    radius: 8
                    color: taskbar.dark ? "#222222" : "#f9f9f9"
                    border.color: taskbar.dark ? "#363636" : "#e5e5e5"
                }
            }
        }
    }

    TaskbarPreview {
        id: previewPopup

        host: taskbar
        backend: apps
        buttonsByKey: taskbar.buttonsByKey
        syncModel: taskbar.syncModel
        allowed: taskbar.preview && taskbar.draggedKey === "" && taskbar.menu === null
        peek: taskbar.peek
        previewDelay: taskbar.previewDelay
        previewWidth: taskbar.previewWidth
        animation: taskbar.animation
        animationDuration: taskbar.animationDuration
        edge: taskbar.edge
        vertical: taskbar.vertical
        dark: taskbar.dark
        tint: taskbar.bar?.color ?? (dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85))
        attentionColor: taskbar.attentionColor
        fontFamily: taskbar.font.family
        iconFontFamily: taskbar.bar?.iconFont?.family ?? "Segoe Fluent Icons"
    }

    // Takes this taskbar's own buttons to new places, and brings a window to the front while a file is held over its
    // button, so the file can be dropped in it
    DropArea {
        id: dropArea

        // The button a file is held over, by key
        property string fileOver: ""

        anchors.fill: strip
        onEntered: drag => {
            const key = drag.formats.includes(taskbar.mimeType) ? drag.getDataAsString(taskbar.mimeType) : ""
            if (key !== "" && !(key in taskbar.buttonsByKey))
                drag.accepted = false
        }
        onPositionChanged: drag => {
            if (taskbar.draggedKey !== "") {
                taskbar.dragTo(drag.x, drag.y)
                return
            }
            const key = taskbar.keyAt(drag.x, drag.y)
            if (key !== fileOver) {
                fileOver = key
                fileTimer.restart()
            }
        }
        onExited: {
            fileOver = ""
            fileTimer.stop()
        }
        onDropped: drop => {
            fileOver = ""
            fileTimer.stop()
            if (taskbar.draggedKey === "") {
                drop.accepted = false
                return
            }
            taskbar.drop()
            drop.accept(Qt.MoveAction)
            taskbar.endDrag()
        }

        Timer {
            id: fileTimer

            interval: 600
            onTriggered: {
                const windows = taskbar.buttonsByKey[dropArea.fileOver]?.windows ?? []
                const window = windows.find(window => window.active) ?? windows[0]
                if (window)
                    apps.focus(window.hwnd)
            }
        }
    }

    // The buttons, each placed along the bar from the lengths of those before it
    Item {
        id: strip

        objectName: "buttons"
        // The buttons shown, without those shrinking away
        readonly property int count: taskbar.buttons.length

        width: taskbar.vertical ? taskbar.width : taskbar.extent
        height: taskbar.vertical ? taskbar.extent : taskbar.height

        Repeater {
            model: buttonModel

            delegate: Item {
                id: button

                required property string key
                readonly property var current: taskbar.buttonsByKey[key] ?? null
                // What it last showed, kept while it shrinks away once its app has closed
                property var kept: null
                readonly property var entry: current ?? kept
                readonly property bool leaving: key in taskbar.leaving
                readonly property var app: entry?.app ?? null
                readonly property var windows: entry?.windows ?? []
                readonly property bool running: windows.length > 0
                readonly property var activeWindow: windows.find(window => window.active) ?? null
                readonly property bool active: activeWindow !== null && !activeWindow.minimized
                readonly property bool flashing: windows.some(window => window.flashing)
                readonly property bool minimized: running && windows.every(window => window.minimized)
                // The window a title or click is about: the one in front, else the first
                readonly property var window: activeWindow ?? windows[0] ?? null
                readonly property bool titled: !taskbar.vertical && running
                    && (taskbar.titles === "always" || (taskbar.titles === "focused" && active))
                readonly property string icon: app?.pinned || !window ? (app?.icon ?? "") : window.icon
                // The button's length along the bar once its title has opened or shut
                readonly property real length: leaving ? 0 : taskbar.iconSize + 2 * taskbar.buttonPadding
                    + (titled ? title.width + 6 : 0)
                // Fades and grows in when it comes after the bar first filled
                property real shown: 1
                // The first place it is given is taken at once; moves after that animate
                property bool placedOnce: false

                // Activates the window, cycles through a group's windows in turn, or starts a pinned app
                function click() {
                    if (!running) {
                        apps.launch(app.id)
                        return
                    }
                    if (windows.length === 1) {
                        apps.activate(windows[0].hwnd)
                        return
                    }
                    const index = windows.findIndex(window => window.active)
                    apps.activate(windows[(index + 1) % windows.length].hwnd)
                }

                // Moves animate once the button has its first place
                function place() {
                    placedOnce = true
                }

                onCurrentChanged: {
                    if (current)
                        kept = current
                }
                onLeavingChanged: {
                    if (leaving) {
                        appear.stop()
                        fade.start()
                    } else {
                        fade.stop()
                        shown = 1
                    }
                }
                onLengthChanged: taskbar.setLength(key, length)
                Component.onCompleted: {
                    kept = current
                    taskbar.setLength(key, length)
                    if (taskbar.animation && taskbar.ready) {
                        shown = 0
                        appear.start()
                    }
                    // Qt drops the call if the button is destroyed first, as when the bar closes
                    Qt.callLater(button.place)
                }

                // Where it starts along the bar and how long it is there, animated; x, y, width and height follow
                // them on either kind of bar. It grows and shrinks as a whole when its title opens or shuts, in step
                // with the buttons after it
                property real along: taskbar.offsets[key] ?? 0
                property real size: length
                x: taskbar.vertical ? 0 : along
                y: taskbar.vertical ? along : 0
                width: taskbar.vertical ? strip.width : size
                height: taskbar.vertical ? size : strip.height
                enabled: !leaving
                clip: true
                Accessible.role: Accessible.Button
                Accessible.name: window?.title ?? app?.name ?? ""
                Accessible.onPressAction: click()
                // The dragged button stays faint in the place it would be dropped
                opacity: (taskbar.draggedKey === key ? 0.3 : 1) * shown
                scale: 0.5 + shown / 2

                Behavior on along {
                    enabled: taskbar.animation && button.placedOnce
                    NumberAnimation { duration: taskbar.animationDuration; easing.type: Easing.OutCubic }
                }
                Behavior on size {
                    enabled: taskbar.animation && button.placedOnce
                    NumberAnimation { duration: taskbar.animationDuration; easing.type: Easing.OutCubic }
                }

                NumberAnimation {
                    id: fade

                    target: button
                    property: "shown"
                    to: 0
                    duration: taskbar.animationDuration
                    easing.type: Easing.OutCubic
                }

                NumberAnimation {
                    id: appear

                    target: button
                    property: "shown"
                    to: 1
                    duration: taskbar.animationDuration
                    easing.type: Easing.OutCubic
                }

                Drag.active: dragHandler.active
                Drag.dragType: Drag.Automatic
                Drag.supportedActions: Qt.MoveAction
                Drag.mimeData: ({ [taskbar.mimeType]: button.key })
                Drag.imageSource: button.icon
                Drag.imageSourceSize: Qt.size(taskbar.iconSize, taskbar.iconSize)
                Drag.hotSpot: Qt.point(taskbar.iconSize / 2, taskbar.iconSize / 2)
                Drag.onDragStarted: {
                    previewPopup.dismiss()
                    taskbar.draggedKey = button.key
                }
                Drag.onDragFinished: taskbar.endDrag()

                Rectangle {
                    anchors.fill: parent
                    anchors.topMargin: taskbar.vertical ? 0 : taskbar.buttonMargin
                    anchors.bottomMargin: taskbar.vertical ? 0 : taskbar.buttonMargin
                    anchors.leftMargin: taskbar.vertical ? taskbar.buttonMargin : 0
                    anchors.rightMargin: taskbar.vertical ? taskbar.buttonMargin : 0
                    radius: taskbar.buttonRadius
                    color: button.flashing ? "transparent"
                        : button.active ? Qt.alpha(taskbar.ink, tap.pressed ? 0.05 : 0.08)
                        : Qt.alpha(taskbar.ink, tap.pressed ? 0.03 : hover.hovered && taskbar.draggedKey === "" ? 0.05 : 0)

                    Behavior on color {
                        enabled: taskbar.animation
                        ColorAnimation { duration: 120 }
                    }

                    Rectangle {
                        id: attentionHighlight

                        anchors.fill: parent
                        radius: taskbar.buttonRadius
                        visible: button.flashing
                        color: Qt.alpha(taskbar.attentionColor, 0.28)

                        SequentialAnimation on opacity {
                            running: button.flashing && !button.leaving
                                && taskbar.animation && taskbar.animationDuration > 0
                            NumberAnimation { from: 0; to: 1; duration: 500; easing.type: Easing.InOutSine }
                            SequentialAnimation {
                                loops: 5
                                PauseAnimation { duration: 500 }
                                NumberAnimation { from: 1; to: 0; duration: 800; easing.type: Easing.InOutSine }
                                PauseAnimation { duration: 200 }
                                NumberAnimation { from: 0; to: 1; duration: 200; easing.type: Easing.InOutSine }
                            }
                            onStopped: attentionHighlight.opacity = 1
                        }
                    }
                }

                // The icon keeps its place at the button's start, and the title beside it shows as the button grows
                Image {
                    x: taskbar.vertical ? (parent.width - width) / 2 : taskbar.buttonPadding
                    y: (parent.height - height) / 2
                    source: button.icon
                    width: taskbar.iconSize
                    height: taskbar.iconSize
                    sourceSize: Qt.size(taskbar.iconSize, taskbar.iconSize)
                }

                Text {
                    id: title

                    objectName: "title"
                    x: taskbar.buttonPadding + taskbar.iconSize + 6
                    y: (parent.height - height) / 2
                    visible: !taskbar.vertical && taskbar.titles !== "never"
                    width: Math.min(implicitWidth, taskbar.titleMaxWidth)
                    text: button.window?.title ?? ""
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                    color: taskbar.textColor
                    opacity: button.titled ? (button.minimized ? 0.6 : 1) : 0
                    font: taskbar.font

                    Behavior on opacity {
                        enabled: taskbar.animation && button.placedOnce
                        NumberAnimation { duration: taskbar.animationDuration; easing.type: Easing.OutCubic }
                    }
                }

                // The line along the button's edge: short while open, long for the window in front or one asking for
                // attention
                Rectangle {
                    objectName: "indicator"
                    readonly property real length: button.active || button.flashing ? 16 : 6

                    visible: taskbar.showIndicator && button.running
                    x: taskbar.edge === "left" ? taskbar.buttonMargin
                        : taskbar.edge === "right" ? parent.width - width - taskbar.buttonMargin
                        : (parent.width - width) / 2
                    y: taskbar.vertical ? (parent.height - height) / 2 : parent.height - height - taskbar.buttonMargin
                    width: taskbar.vertical ? 3 : length
                    height: taskbar.vertical ? length : 3
                    radius: 1.5
                    color: button.flashing ? taskbar.attentionColor : button.active ? taskbar.accentColor
                        : Qt.alpha(taskbar.ink, button.minimized ? 0.35 : 0.55)

                    Behavior on width {
                        enabled: taskbar.animation
                        NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
                    }
                    Behavior on height {
                        enabled: taskbar.animation
                        NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
                    }
                }

                // The number of windows a grouped button holds
                Rectangle {
                    objectName: "count"
                    visible: taskbar.grouping && taskbar.showCount && button.windows.length > 1
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 3
                    width: Math.max(height, countText.implicitWidth + 4)
                    height: 11
                    radius: 5.5
                    color: taskbar.dark ? "#3A3A3A" : "#E0E0E0"

                    Text {
                        id: countText

                        anchors.centerIn: parent
                        text: String(button.windows.length)
                        textFormat: Text.PlainText
                        color: Qt.alpha(taskbar.ink, 0.85)
                        font.pixelSize: 9
                    }
                }

                HoverHandler {
                    id: hover

                    onHoveredChanged: previewPopup.hoverButton(button, hovered)
                }

                TapHandler {
                    id: tap

                    acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
                    onTapped: (point, mouseButton) => {
                        previewPopup.pressButton(button)
                        if (mouseButton === Qt.LeftButton)
                            button.click()
                        else if (mouseButton === Qt.RightButton)
                            taskbar.openMenu(button)
                        else if (taskbar.middleClick === "launch")
                            apps.launch(button.app.id)
                        else if (taskbar.middleClick === "close" && button.window)
                            apps.close(button.window.hwnd)
                    }
                }

                DragHandler {
                    id: dragHandler

                    target: null
                    acceptedButtons: Qt.LeftButton
                }

                ToolTip {
                    popupType: Popup.Window
                    visible: taskbar.tooltip && hover.hovered && taskbar.draggedKey === "" && taskbar.menu === null
                        && !(taskbar.preview && button.running)
                    delay: 500
                    text: button.running ? button.windows.map(window => window.title).join("\n")
                        : (button.app?.name ?? "")
                    // Away from the bar's edge
                    y: taskbar.edge === "bottom" ? -implicitHeight - 6 : button.height + 6
                }
            }
        }
    }
}
