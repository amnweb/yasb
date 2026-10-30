import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: launcher

    property Item bar: null
    property string hotkey: "alt+space"
    // active, cursor or primary: which screen's widget opens on the hotkey
    property string hotkeyScreen: "active"
    // What each search provider does: on or off, the prefix typed before a space to use it ("*" for none),
    // its order among the others, and its own options. Only apps is on; turn one on with `calculator.enabled: true`.
    component Provider: QtObject {
        property bool enabled: false
        property string prefix: "*"
        property int priority: 0
        property var options: ({})
    }

    property Provider apps: Provider {
        enabled: true
        options: ({ show_recent: true, max_recent: 10, show_description: true })
    }

    property Provider bookmarks: Provider {
        enabled: false
        options: ({ browser: "all", profile: "Default" })
    }

    property Provider calculator: Provider {
        enabled: false
        prefix: "="
    }

    property Provider clipboardHistory: Provider {
        enabled: false
        prefix: "cb"
        options: ({ max_items: 30, show_preview: true })
    }

    property Provider color: Provider {
        enabled: true
        prefix: "c:"
    }

    property Provider binance: Provider {
        enabled: false
        prefix: "crypto"
        options: ({ pairs: ["BTC/USDT"], round: 2, open_url: false, domain: "api-gcp.binance.com" })
    }

    property Provider currency: Provider {
        enabled: false
        prefix: "$"
    }

    property Provider devTools: Provider {
        enabled: false
        prefix: "dev"
    }

    property Provider emoji: Provider {
        enabled: false
        prefix: ":"
    }

    property Provider fileSearch: Provider {
        enabled: true
        prefix: "/"
        options: ({ backend: "disk", show_path: true, show_preview: false })
    }

    property Provider githubNotifications: Provider {
        enabled: true
        prefix: "gh"
        options: ({ token: "env" })
    }

    property Provider hackerNews: Provider {
        enabled: false
        prefix: "hn"
        options: ({ cache_ttl: 300, max_items: 30 })
    }

    property Provider ipInfo: Provider {
        enabled: false
        prefix: "ip"
    }

    property Provider killProcess: Provider {
        enabled: false
        prefix: "!"
    }

    property Provider portViewer: Provider {
        enabled: false
        prefix: "pv"
        options: ({ tcp_listening_only: true, include_established: false })
    }

    property Provider settings: Provider {
        enabled: false
        prefix: "@"
    }

    property Provider snippets: Provider {
        enabled: false
        prefix: ";"
        options: ({ type_delay: 200 })
    }

    property Provider ssh: Provider {
        enabled: false
        prefix: "ssh"
        options: ({ ssh_config_path: "" })
    }

    property Provider systemCommands: Provider {
        enabled: false
        prefix: ">"
    }

    property Provider unitConverter: Provider {
        enabled: false
        prefix: "~"
    }

    property Provider vscode: Provider {
        enabled: false
        prefix: "vsc"
        options: ({ state_storage_path: "" })
    }

    property Provider webSearch: Provider {
        enabled: false
        prefix: "?"
        options: ({ engine: "google", custom_engines: [], remove_engines: [] })
    }

    property Provider windowSwitcher: Provider {
        enabled: false
        prefix: "win"
    }

    property Provider windowsTerminal: Provider {
        enabled: false
        prefix: "wt"
    }

    property Provider worldClock: Provider {
        enabled: false
        prefix: "tz"
    }

    property Provider wsl: Provider {
        enabled: false
        prefix: "wsl"
        options: ({ show_online: true })
    }

    // The most results the launcher lists, and the most each provider looks for
    property int maxResults: 50
    // With nothing typed, list the providers that have a prefix instead of the apps
    property bool homePage: false
    property string placeholder: "Search applications..."
    property bool rememberLastQuery: false
    property bool showIcons: true
    property int iconSize: 24
    property int popupWidth: 720
    property int popupHeight: 480

    readonly property bool dark: bar ? bar.dark : Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color foreground: dark ? "#f3f3f3" : "#1b1b1b"
    readonly property color secondary: dark ? "#9a9a9a" : "#5f5f5f"
    readonly property color hover: Qt.alpha(foreground, 0.06)
    readonly property color selected: Qt.alpha(foreground, 0.1)

    // The provider prefix shown as a chip in front of the search text
    property string prefix: ""
    property bool previewShown: false

    implicitWidth: label.implicitWidth + 16
    implicitHeight: 30

    function toggle() {
        if (popup.visible && !popup.closing)
            popup.close()
        else
            open()
    }

    function open() {
        // Centered on the bar's screen, a third of the way down
        popup.x = Math.round(launcher.Screen.virtualX + (launcher.Screen.width - popup.width) / 2)
        popup.y = Math.round(launcher.Screen.virtualY + (launcher.Screen.height - popup.height) / 3)
        if (!rememberLastQuery) {
            prefix = ""
            field.text = ""
        }
        popup.open()
        search.activate(popup.window)
        field.forceActiveFocus()
        field.selectAll()
        runSearch()
    }

    // Opens with this text; a provider prefix in front of it becomes the chip
    function showQuery(text: string) {
        if (!popup.visible || popup.closing)
            open()
        const typed = search.prefixes.find(p => text.startsWith(`${p.prefix} `))
        if (typed) {
            setPrefix(typed.prefix, text.slice(typed.prefix.length + 1))
        } else {
            prefix = ""
            field.text = text
            runSearch()
        }
    }

    function runSearch() {
        search.search(prefix ? `${prefix} ${field.text}` : field.text)
    }

    function setPrefix(value: string, text: string) {
        prefix = value
        field.text = text
        field.forceActiveFocus()
        runSearch()
    }

    function select(step: int) {
        let row = list.currentIndex
        for (let i = 0; i < list.count; i++) {
            row = Math.max(0, Math.min(list.count - 1, row + step))
            if (!list.itemAtIndex(row)?.separator)
                break
        }
        list.currentIndex = row
    }

    function showMenu(row: int, item: Item) {
        const actions = search.contextActions(row)
        if (!actions.length)
            return
        list.currentIndex = row
        menu.row = row
        menu.actions = actions
        menu.popup(item)
    }

    Image {
        id: label

        anchors.centerIn: parent
        source: Qt.resolvedUrl("icons/search.svg")
        sourceSize: Qt.size(16, 16)
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: launcher.toggle()
    }

    Hotkey {
        keys: launcher.hotkey
        screen: launcher.hotkeyScreen
        onActivated: launcher.toggle()
    }

    QuickLaunchSearch {
        id: search

        maxResults: launcher.maxResults
        homePage: launcher.homePage
        providers: ({
            apps: settingsOf(launcher.apps),
            bookmarks: settingsOf(launcher.bookmarks),
            calculator: settingsOf(launcher.calculator),
            clipboard_history: settingsOf(launcher.clipboardHistory),
            color: settingsOf(launcher.color),
            binance: settingsOf(launcher.binance),
            currency: settingsOf(launcher.currency),
            dev_tools: settingsOf(launcher.devTools),
            emoji: settingsOf(launcher.emoji),
            file_search: settingsOf(launcher.fileSearch),
            github_notifications: settingsOf(launcher.githubNotifications),
            hacker_news: settingsOf(launcher.hackerNews),
            ip_info: settingsOf(launcher.ipInfo),
            kill_process: settingsOf(launcher.killProcess),
            port_viewer: settingsOf(launcher.portViewer),
            settings: settingsOf(launcher.settings),
            snippets: settingsOf(launcher.snippets),
            ssh: settingsOf(launcher.ssh),
            system_commands: settingsOf(launcher.systemCommands),
            unit_converter: settingsOf(launcher.unitConverter),
            vscode: settingsOf(launcher.vscode),
            web_search: settingsOf(launcher.webSearch),
            window_switcher: settingsOf(launcher.windowSwitcher),
            windows_terminal: settingsOf(launcher.windowsTerminal),
            world_clock: settingsOf(launcher.worldClock),
            wsl: settingsOf(launcher.wsl)
        })

        function settingsOf(provider: Provider): var {
            return Object.assign({ enabled: provider.enabled, prefix: provider.prefix, priority: provider.priority },
                provider.options)
        }

        onCloseRequested: popup.close()
        onPrefixRequested: value => launcher.setPrefix(value, "")
        onQueryRequested: text => launcher.showQuery(text)
        onColorPickRequested: prefix => {
            popup.close()
            colorPicker.prefix = prefix
            colorPicker.start()
        }
    }

    ColorPicker {
        id: colorPicker

        // The colour provider's prefix, so a picked colour opens on its results
        property string prefix

        quickLaunch: search
        onPicked: color => launcher.showQuery(prefix + color)
    }

    Component.onDestruction: popup.hide()

    BackdropPopup {
        id: popup

        property real reveal: 0

        title: "Quick Launch"
        width: launcher.popupWidth
        height: launcher.popupHeight
        anchor: launcher
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 120; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 90; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible) {
                reveal = 0
                search.deactivate()
            }
        }

        Rectangle {
            id: surface

            anchors.fill: parent
            radius: 16
            color: launcher.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#f3f3f3", 0.85)
            border.width: 1
            border.color: launcher.dark ? Qt.alpha("#ffffff", 0.1) : "#22000000"
            opacity: popup.reveal
            scale: 0.75 + popup.reveal * 0.25

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 1
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.margins: 12
                    spacing: 8

                    Label {
                        visible: launcher.prefix !== ""
                        text: launcher.prefix
                        leftPadding: 8
                        rightPadding: 8
                        topPadding: 3
                        bottomPadding: 3
                        background: Rectangle {
                            radius: 4
                            color: launcher.selected
                        }
                    }

                    TextField {
                        id: field

                        Layout.fillWidth: true
                        placeholderText: launcher.prefix
                            ? search.prefixes.find(p => p.prefix === launcher.prefix)?.placeholder ?? ""
                            : launcher.placeholder
                        font.pixelSize: 16

                        onTextEdited: {
                            const typed = search.prefixes.find(p => text.startsWith(`${p.prefix} `))
                            if (!launcher.prefix && typed)
                                launcher.setPrefix(typed.prefix, text.slice(typed.prefix.length + 1))
                            else
                                launcher.runSearch()
                        }

                        Keys.onPressed: event => {
                            if (event.key === Qt.Key_Down || event.key === Qt.Key_Up) {
                                launcher.select(event.key === Qt.Key_Down ? 1 : -1)
                            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                search.execute(list.currentIndex)
                            } else if (event.key === Qt.Key_Right && search.prediction && cursorPosition === text.length) {
                                text = search.prediction
                                launcher.runSearch()
                            } else if (event.key === Qt.Key_Backspace && launcher.prefix && cursorPosition === 0
                                       && selectedText === "") {
                                launcher.prefix = ""
                                launcher.runSearch()
                            } else if (event.key === Qt.Key_P && event.modifiers === Qt.AltModifier) {
                                launcher.previewShown = !launcher.previewShown
                            } else {
                                return
                            }
                            event.accepted = true
                        }

                        // The rest of the first app's name, after what is typed
                        Label {
                            x: field.leftPadding + field.contentWidth
                            anchors.verticalCenter: parent.verticalCenter
                            visible: search.prediction !== "" && field.cursorPosition === field.text.length
                            text: search.prediction.slice(field.text.length)
                            font: field.font
                            opacity: 0.4
                        }
                    }
                }

                ProgressBar {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    indeterminate: true
                    visible: search.loading
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    visible: !search.loading
                    color: launcher.dark ? "#1affffff" : "#14000000"
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 0

                    ListView {
                        id: list

                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.margins: 6
                        clip: true
                        model: search.results
                        boundsBehavior: Flickable.StopAtBounds
                        highlightMoveDuration: 0
                        ScrollBar.vertical: ScrollBar {}

                        Connections {
                            target: search.results

                            function onModelReset() {
                                list.currentIndex = -1
                                // The list handles the reset after this handler, so until then it still has the old rows
                                Qt.callLater(launcher.select, 1)
                            }
                        }

                        delegate: Item {
                            id: row

                            required property int index
                            required property string title
                            required property string description
                            required property string icon
                            required property string iconText
                            required property bool separator
                            required property string path

                            width: ListView.view.width
                            height: separator ? 28 : Math.max(launcher.showIcons ? launcher.iconSize : 0, texts.implicitHeight) + 16

                            Rectangle {
                                anchors.fill: parent
                                radius: 6
                                visible: !row.separator
                                color: row.ListView.isCurrentItem ? launcher.selected
                                    : mouse.containsMouse ? launcher.hover : "transparent"
                            }

                            Label {
                                anchors.left: parent.left
                                anchors.leftMargin: 10
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 4
                                visible: row.separator
                                text: row.title
                                color: launcher.secondary
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                            }

                            Item {
                                id: iconBox

                                x: 10
                                anchors.verticalCenter: parent.verticalCenter
                                width: launcher.iconSize
                                height: launcher.iconSize
                                visible: launcher.showIcons && !row.separator

                                Image {
                                    anchors.fill: parent
                                    visible: row.icon !== ""
                                    source: row.icon
                                    sourceSize: Qt.size(launcher.iconSize, launcher.iconSize)
                                    fillMode: Image.PreserveAspectFit
                                }

                                Text {
                                    anchors.centerIn: parent
                                    visible: row.icon === ""
                                    text: row.iconText
                                    font.family: "Segoe UI Emoji"
                                    font.pixelSize: launcher.iconSize * 0.75
                                }
                            }

                            ColumnLayout {
                                id: texts

                                anchors.left: iconBox.visible ? iconBox.right : parent.left
                                anchors.leftMargin: iconBox.visible ? 12 : 10
                                anchors.right: parent.right
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                visible: !row.separator
                                spacing: 2

                                Label {
                                    Layout.fillWidth: true
                                    text: row.title
                                    elide: Text.ElideRight
                                    textFormat: Text.PlainText
                                }

                                Label {
                                    Layout.fillWidth: true
                                    visible: row.description !== ""
                                    text: row.description
                                    elide: Text.ElideRight
                                    textFormat: Text.PlainText
                                    color: launcher.secondary
                                    font.pixelSize: 12
                                }
                            }

                            MouseArea {
                                id: mouse

                                anchors.fill: parent
                                enabled: !row.separator
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                cursorShape: Qt.PointingHandCursor
                                drag.target: row.path ? dragItem : null

                                onClicked: event => {
                                    if (event.button === Qt.RightButton)
                                        launcher.showMenu(row.index, row)
                                    else {
                                        list.currentIndex = row.index
                                        search.execute(row.index)
                                    }
                                }
                            }

                            // Files can be dragged out to other apps
                            Item {
                                id: dragItem

                                Drag.active: mouse.drag.active
                                Drag.dragType: Drag.Automatic
                                Drag.supportedActions: Qt.CopyAction | Qt.LinkAction
                                Drag.mimeData: ({ "text/uri-list": `file:///${row.path.replace(/\\/g, "/")}` })
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        visible: preview.visible
                        color: launcher.dark ? "#1affffff" : "#14000000"
                    }

                    Preview {
                        id: preview

                        Layout.fillHeight: true
                        Layout.preferredWidth: Math.round(launcher.popupWidth * 0.4)
                        dark: launcher.dark
                        secondary: launcher.secondary
                        content: list.currentIndex >= 0 ? search.preview(list.currentIndex) : ({})
                        forced: launcher.previewShown
                        onAction: (id, values) => search.previewAction(list.currentIndex, id, values)
                        onCancelled: search.cancelEdit()
                    }
                }
            }

            Column {
                anchors.centerIn: parent
                anchors.verticalCenterOffset: 30
                spacing: 8
                visible: list.count === 0 && !search.loading

                Image {
                    anchors.horizontalCenter: parent.horizontalCenter
                    source: Qt.resolvedUrl("icons/search-main.svg")
                    sourceSize: Qt.size(64, 64)
                }

                Label {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: field.text || launcher.prefix ? "No results" : "Type to search..."
                    color: launcher.secondary
                }
            }

            Menu {
                id: menu

                property int row: -1
                property var actions: []

                Instantiator {
                    model: menu.actions

                    delegate: MenuItem {
                        required property var modelData

                        text: modelData.label
                        enabled: modelData.enabled
                        onTriggered: search.runContextAction(menu.row, modelData.id)
                    }

                    onObjectAdded: (index, object) => menu.insertItem(index, object)
                    onObjectRemoved: (index, object) => menu.removeItem(object)
                }
            }
        }
    }
}
