pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: quickLaunch

    required property BarBase bar
    readonly property Theme theme: bar.theme
    // Hotkey that opens the launcher, such as "alt+space"
    property string hotkey: ""
    // active, cursor or primary: which screen's widget opens on the hotkey
    property string hotkeyScreen: "active"
    // What each search provider does: on or off, the prefix typed before a space to use it ("*" for none),
    // its order among the others, and its own options. Apps, colour, file search and GitHub notifications are on;
    // turn another on with `calculator.enabled: true`.
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
    property int resultIconSize: 24
    // The popup shows only the search bar until something is typed or a prefix is picked
    property bool compactMode: false
    // One line per result: the title on the left and the description on the right, in at most half the row
    property bool compactText: false
    property int popupWidth: 720
    property int popupHeight: 480
    // The glyph on the bar, drawn in iconFont and the text colour
    property string icon: "\ue721"
    property int iconSize: theme.bar.iconFont.pixelSize

    readonly property bool dark: theme.dark
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
    property color popupSecondaryTextColor: theme.colors.textTertiary
    property real popupRadius: theme.popup.radius
    // Text in the popup: the theme's font family, in this widget's sizes
    property font popupFont
    popupFont.family: theme.popup.font.family
    popupFont.pixelSize: 14
    property font popupSmallFont
    popupSmallFont.family: theme.popup.font.family
    popupSmallFont.pixelSize: 12
    // Bold text in the preview, the search field and its glyph, each group's heading in the results, and the
    // colour's code under the picker's lens
    property font popupStrongFont
    popupStrongFont.family: theme.popup.font.family
    popupStrongFont.pixelSize: 13
    popupStrongFont.weight: Font.DemiBold
    property font searchFont
    searchFont.family: theme.popup.font.family
    searchFont.pixelSize: 16
    property int searchIconSize: 18
    property font sectionFont
    sectionFont.family: theme.popup.font.family
    sectionFont.pixelSize: 12
    sectionFont.weight: Font.DemiBold
    property font colorCodeFont
    colorCodeFont.family: theme.popup.font.family
    colorCodeFont.pointSize: 9
    colorCodeFont.weight: Font.Bold
    // Emoji shown in place of a result's icon
    property font emojiFont
    emojiFont.family: "Segoe UI Emoji"
    property int popupOpenDuration: theme.popup.openDuration
    property int popupCloseDuration: theme.popup.closeDuration
    // The right-click menu on a result: the theme's, unless set here
    property int menuWidth: 200
    property color menuColor: theme.menu.background
    property color menuBorderColor: theme.menu.border
    property color menuTextColor: theme.colors.text
    property real menuRadius: theme.menu.radius
    property font menuFont: theme.menu.font
    // Milliseconds the right-click menu takes to fade in
    property int menuOpenDuration: theme.menu.openDuration
    // The icons in the text fields' right-click menu
    property int menuIconSize: 16
    property color popupDividerColor: theme.colors.divider
    property color popupHoverColor: theme.colors.hover
    property color popupSelectedColor: theme.colors.selected

    property string prefix: ""
    property bool previewShown: false
    // In compactMode, while nothing is typed and no prefix is picked
    readonly property bool collapsed: compactMode && prefix === "" && field.text.trim() === ""

    implicitWidth: label.width
    implicitHeight: label.height

    function toggle() {
        if (popup.visible && !popup.closing)
            popup.close()
        else
            open()
    }

    function open() {
        popup.x = Math.round(quickLaunch.Screen.virtualX + (quickLaunch.Screen.width - popup.width) / 2)
        // From the full height, so the search bar stays where it is when the results show
        popup.y = Math.round(quickLaunch.Screen.virtualY + (quickLaunch.Screen.height - quickLaunch.popupHeight) / 3)
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
            if (!(list.itemAtIndex(row) as ResultRow)?.separator)
                break
        }
        list.currentIndex = row
    }

    function showMenu(row: int, item: Item) {
        const actions = search.contextActions(row)
        if (!actions.length)
            return
        list.currentIndex = row
        resultMenu.row = row
        resultMenu.actions = actions
        resultMenu.popup(item)
    }

    // An item of the text fields' right-click menu, its icon in menuIconSize
    component FieldMenuItem: MenuItem {
        icon.width: quickLaunch.menuIconSize
        icon.height: quickLaunch.menuIconSize
    }

    component SvgIcon: IconImage {
        sourceSize: Qt.size(width, height)
    }

    Text {
        id: label

        y: Math.round((parent.height - height) / 2)
        width: quickLaunch.iconSize
        height: quickLaunch.iconSize
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        text: quickLaunch.icon
        color: quickLaunch.textColor
        font.family: quickLaunch.iconFont.family
        font.weight: quickLaunch.iconFont.weight
        font.variableAxes: quickLaunch.iconFont.variableAxes
        font.pixelSize: quickLaunch.iconSize
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: quickLaunch.toggle()
    }

    Hotkey {
        keys: quickLaunch.hotkey
        screen: quickLaunch.hotkeyScreen
        onActivated: quickLaunch.toggle()
    }

    QuickLaunchSearch {
        id: search

        maxResults: quickLaunch.maxResults
        homePage: quickLaunch.homePage
        providers: ({
            apps: settingsOf(quickLaunch.apps),
            bookmarks: settingsOf(quickLaunch.bookmarks),
            calculator: settingsOf(quickLaunch.calculator),
            clipboard_history: settingsOf(quickLaunch.clipboardHistory),
            color: settingsOf(quickLaunch.color),
            binance: settingsOf(quickLaunch.binance),
            currency: settingsOf(quickLaunch.currency),
            dev_tools: settingsOf(quickLaunch.devTools),
            emoji: settingsOf(quickLaunch.emoji),
            file_search: settingsOf(quickLaunch.fileSearch),
            github_notifications: settingsOf(quickLaunch.githubNotifications),
            hacker_news: settingsOf(quickLaunch.hackerNews),
            ip_info: settingsOf(quickLaunch.ipInfo),
            kill_process: settingsOf(quickLaunch.killProcess),
            port_viewer: settingsOf(quickLaunch.portViewer),
            settings: settingsOf(quickLaunch.settings),
            snippets: settingsOf(quickLaunch.snippets),
            ssh: settingsOf(quickLaunch.ssh),
            system_commands: settingsOf(quickLaunch.systemCommands),
            unit_converter: settingsOf(quickLaunch.unitConverter),
            vscode: settingsOf(quickLaunch.vscode),
            web_search: settingsOf(quickLaunch.webSearch),
            window_switcher: settingsOf(quickLaunch.windowSwitcher),
            windows_terminal: settingsOf(quickLaunch.windowsTerminal),
            world_clock: settingsOf(quickLaunch.worldClock),
            wsl: settingsOf(quickLaunch.wsl)
        })

        function settingsOf(provider: Provider): var {
            return Object.assign({ enabled: provider.enabled, prefix: provider.prefix, priority: provider.priority },
                provider.options)
        }

        onCloseRequested: popup.close()
        onQueryRequested: text => quickLaunch.showQuery(text)
        onColorPickRequested: prefix => {
            popup.close()
            colorPicker.prefix = prefix
            colorPicker.start()
        }
    }

    ColorPicker {
        id: colorPicker

        property string prefix

        launcherSearch: search
        frameColor: quickLaunch.popupBorderColor
        labelColor: quickLaunch.popupColor
        textColor: quickLaunch.popupTextColor
        font: quickLaunch.colorCodeFont
        onPicked: color => quickLaunch.showQuery(prefix + color)
    }

    Component.onDestruction: popup.hide()

    BackdropPopup {
        id: popup

        property real reveal: 0

        title: "Quick Launch"
        width: quickLaunch.popupWidth
        // The search bar with its margins and the border
        height: quickLaunch.collapsed ? searchBar.implicitHeight + 2 * 12 + 2 : quickLaunch.popupHeight
        anchor: quickLaunch
        font: quickLaunch.popupFont
        theme: quickLaunch.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: quickLaunch.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: quickLaunch.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible) {
                reveal = 0
                search.deactivate()
            }
        }

        Rectangle {
            id: surface

            anchors.fill: parent
            radius: quickLaunch.popupRadius
            color: quickLaunch.popupColor
            border.width: 1
            border.color: quickLaunch.popupBorderColor      
            opacity: popup.reveal
            scale: 0.92 + popup.reveal * 0.08

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 1
                spacing: 0

                RowLayout {
                    id: searchBar

                    Layout.fillWidth: true
                    Layout.margins: 12
                    spacing: 0

                    TextField {
                        id: field

                        // Qt's own text menu is replaced by fieldMenu, which the right button opens
                        ContextMenu.menu: null

                        // A right-click opens the menu at the mouse cursor, on press or release as Windows sets it
                        TapHandler {
                            acceptedButtons: Qt.RightButton
                            onPressedChanged: {
                                if (pressed === (Application.styleHints.contextMenuTrigger === Qt.ContextMenuTrigger.Press))
                                    fieldMenu.popup(field)
                            }
                        }

                        Layout.fillWidth: true
                        Layout.preferredHeight: 40
                        leftPadding: prefixChip.visible ? prefixChip.x + prefixChip.width + 6 : 12
                        rightPadding: 32
                        background: Rectangle {
                            color: "transparent"
                            border.width: 0
                        }

                        Label {
                            id: prefixChip

                            // Its text starts where the prefix was typed, so it stays in place
                            x: 12 - leftPadding
                            anchors.verticalCenter: parent.verticalCenter
                            visible: quickLaunch.prefix !== ""
                            text: quickLaunch.prefix
                            font.pixelSize: field.font.pixelSize
                            leftPadding: 8
                            rightPadding: 8
                            topPadding: 3
                            bottomPadding: 3
                            background: Rectangle {
                                radius: 4
                                color: quickLaunch.popupSelectedColor
                            }
                        }

                        Text {
                            anchors.right: parent.right
                            anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            text: "\ue721"
                            color: quickLaunch.popupTextColor
                            font.family: quickLaunch.iconFont.family
                            font.weight: quickLaunch.iconFont.weight
                            font.variableAxes: quickLaunch.iconFont.variableAxes
                            font.pixelSize: quickLaunch.searchIconSize
                        }

                        placeholderText: quickLaunch.prefix
                            ? search.prefixes.find(p => p.prefix === quickLaunch.prefix)?.placeholder ?? ""
                            : quickLaunch.placeholder
                        font: quickLaunch.searchFont
                        verticalAlignment: TextInput.AlignVCenter

                        onTextEdited: {
                            const typed = search.prefixes.find(p => text.startsWith(`${p.prefix} `))
                            if (!quickLaunch.prefix && typed)
                                quickLaunch.setPrefix(typed.prefix, text.slice(typed.prefix.length + 1))
                            else
                                quickLaunch.runSearch()
                        }

                        Keys.onPressed: event => {
                            if (event.key === Qt.Key_Down || event.key === Qt.Key_Up) {
                                quickLaunch.select(event.key === Qt.Key_Down ? 1 : -1)
                            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                search.execute(list.currentIndex)
                            } else if (event.key === Qt.Key_Right && search.prediction && cursorPosition === text.length) {
                                text = search.prediction
                                quickLaunch.runSearch()
                            } else if (event.key === Qt.Key_Backspace && quickLaunch.prefix && cursorPosition === 0
                                       && selectedText === "") {
                                quickLaunch.prefix = ""
                                quickLaunch.runSearch()
                            } else if (event.key === Qt.Key_P && event.modifiers === Qt.AltModifier) {
                                quickLaunch.previewShown = !quickLaunch.previewShown
                            } else {
                                return
                            }
                            event.accepted = true
                        }

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

                LoadingLine {
                    Layout.fillWidth: true
                    visible: !quickLaunch.collapsed
                    running: search.loading
                    trackColor: quickLaunch.popupDividerColor
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: !quickLaunch.collapsed
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
                                Qt.callLater(quickLaunch.select, 1)
                            }
                        }

                        component ResultRow: Item {
                            id: row

                            required property int index
                            required property string title
                            required property string description
                            required property string icon
                            required property string iconText
                            required property bool separator
                            required property string path

                            width: ListView.view.width
                            height: separator ? 28 : Math.max(quickLaunch.showIcons ? quickLaunch.resultIconSize : 0, texts.implicitHeight) + 16

                            Rectangle {
                                anchors.fill: parent
                                radius: 6
                                visible: !row.separator
                                color: row.ListView.isCurrentItem ? quickLaunch.popupSelectedColor
                                    : mouse.containsMouse ? quickLaunch.popupHoverColor : "transparent"
                            }

                            Label {
                                anchors.left: parent.left
                                anchors.leftMargin: 10
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 4
                                visible: row.separator
                                text: row.title
                                color: quickLaunch.popupSecondaryTextColor
                                font: quickLaunch.sectionFont
                            }

                            Item {
                                id: iconBox

                                x: 10
                                anchors.verticalCenter: parent.verticalCenter
                                width: quickLaunch.resultIconSize
                                height: quickLaunch.resultIconSize
                                visible: quickLaunch.showIcons && !row.separator

                                Image {
                                    anchors.fill: parent
                                    visible: row.icon !== ""
                                    source: row.icon
                                    sourceSize: Qt.size(quickLaunch.resultIconSize, quickLaunch.resultIconSize)
                                    fillMode: Image.PreserveAspectFit
                                }

                                Text {
                                    anchors.centerIn: parent
                                    visible: row.icon === ""
                                    text: row.iconText
                                    font.family: quickLaunch.emojiFont.family
                                    font.pixelSize: quickLaunch.resultIconSize * 0.75
                                }
                            }

                            GridLayout {
                                id: texts

                                anchors.left: iconBox.visible ? iconBox.right : parent.left
                                anchors.leftMargin: iconBox.visible ? 12 : 10
                                anchors.right: parent.right
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                visible: !row.separator
                                columns: quickLaunch.compactText ? 2 : 1
                                columnSpacing: 12
                                rowSpacing: 2

                                Label {
                                    Layout.fillWidth: true
                                    text: row.title
                                    elide: Text.ElideRight
                                    textFormat: Text.PlainText
                                }

                                Label {
                                    Layout.fillWidth: !quickLaunch.compactText
                                    Layout.preferredWidth: quickLaunch.compactText ? Math.min(implicitWidth, texts.width / 2) : -1
                                    horizontalAlignment: quickLaunch.compactText ? Text.AlignRight : Text.AlignLeft
                                    visible: row.description !== ""
                                    text: row.description
                                    elide: Text.ElideRight
                                    textFormat: Text.PlainText
                                    color: quickLaunch.popupSecondaryTextColor
                                    font: quickLaunch.popupSmallFont
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
                                        quickLaunch.showMenu(row.index, row)
                                    else {
                                        list.currentIndex = row.index
                                        search.execute(row.index)
                                    }
                                }
                            }

                            Item {
                                id: dragItem

                                Drag.active: mouse.drag.active
                                Drag.dragType: Drag.Automatic
                                Drag.supportedActions: Qt.CopyAction | Qt.LinkAction
                                Drag.mimeData: ({ "text/uri-list": `file:///${row.path.replace(/\\/g, "/")}` })
                            }
                        }

                        delegate: ResultRow {}
                    }

                    Rectangle {
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        visible: preview.visible
                        color: quickLaunch.popupDividerColor
                    }

                    Preview {
                        id: preview

                        Layout.fillHeight: true
                        Layout.preferredWidth: Math.round(quickLaunch.popupWidth * 0.4)
                        textColor: quickLaunch.popupSecondaryTextColor
                        font: quickLaunch.popupSmallFont
                        strongFont: quickLaunch.popupStrongFont
                        editMenu: fieldMenu
                        content: list.currentIndex >= 0 ? search.preview(list.currentIndex) : ({})
                        forced: quickLaunch.previewShown
                        onAction: (id, values) => search.previewAction(list.currentIndex, id, values)
                        onCancelled: search.cancelEdit()
                    }
                }
            }

            Column {
                anchors.centerIn: parent
                anchors.verticalCenterOffset: 30
                spacing: 8
                visible: list.count === 0 && !search.loading && !quickLaunch.collapsed

                Image {
                    anchors.horizontalCenter: parent.horizontalCenter
                    source: Qt.resolvedUrl("icons/search-main.svg")
                    sourceSize: Qt.size(64, 64)
                }

                Label {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: field.text || quickLaunch.prefix ? "No results" : "Type to search..."
                    color: quickLaunch.popupSecondaryTextColor
                }
            }

            // The text fields' right-click menu: Qt's editing items and icons in the menu's look, acting on the field that
            // opened it
            Menu {
                id: fieldMenu

                // The field it opened on: a TextField, or the preview form's multi-line TextArea
                readonly property TextField line: parent as TextField
                readonly property TextArea area: parent as TextArea
                readonly property bool editable: !((line?.readOnly ?? area?.readOnly) ?? true)
                readonly property bool selected: ((line?.selectedText.length ?? area?.selectedText.length) ?? 0) > 0

                // A window of its own, so it opens where clicked even past the popup's edges
                popupType: Popup.Window
                // Its window is made once and reused, and Windows shows it again where it was, under the popup raised
                // since; raising it before it shows keeps it in front
                onAboutToShow: contentItem.Window.window?.raise()
                // Fades in when it opens, in place of the style's growing from a third of its height
                enter: Transition {
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: quickLaunch.menuOpenDuration; easing.type: Easing.OutCubic }
                }
                topInset: 0
                leftInset: 0
                rightInset: 0
                bottomInset: 0
                font: quickLaunch.menuFont
                // Active and inactive only, so disabled controls keep the style's dimmed colours
                palette.active.text: quickLaunch.menuTextColor
                palette.inactive.text: quickLaunch.menuTextColor

                background: Rectangle {
                    implicitWidth: quickLaunch.menuWidth
                    radius: quickLaunch.menuRadius
                    color: quickLaunch.menuColor
                    border.color: quickLaunch.menuBorderColor
                }

                FieldMenuItem {
                    text: qsTr("Undo")
                    icon.name: "edit-undo"
                    enabled: (fieldMenu.line?.canUndo ?? fieldMenu.area?.canUndo) ?? false
                    onTriggered: fieldMenu.line ? fieldMenu.line.undo() : fieldMenu.area?.undo()
                }
                FieldMenuItem {
                    text: qsTr("Redo")
                    icon.name: "edit-redo"
                    enabled: (fieldMenu.line?.canRedo ?? fieldMenu.area?.canRedo) ?? false
                    onTriggered: fieldMenu.line ? fieldMenu.line.redo() : fieldMenu.area?.redo()
                }
                MenuSeparator {}
                FieldMenuItem {
                    text: qsTr("Cut")
                    icon.name: "edit-cut"
                    enabled: fieldMenu.editable && fieldMenu.selected
                    onTriggered: fieldMenu.line ? fieldMenu.line.cut() : fieldMenu.area?.cut()
                }
                FieldMenuItem {
                    text: qsTr("Copy")
                    icon.name: "edit-copy"
                    enabled: fieldMenu.selected
                    onTriggered: fieldMenu.line ? fieldMenu.line.copy() : fieldMenu.area?.copy()
                }
                FieldMenuItem {
                    text: qsTr("Paste")
                    icon.name: "edit-paste"
                    enabled: fieldMenu.editable && ((fieldMenu.line?.canPaste ?? fieldMenu.area?.canPaste) ?? false)
                    onTriggered: fieldMenu.line ? fieldMenu.line.paste() : fieldMenu.area?.paste()
                }
                FieldMenuItem {
                    text: qsTr("Delete")
                    icon.name: "edit-delete"
                    enabled: fieldMenu.editable && fieldMenu.selected
                    onTriggered: fieldMenu.line ? fieldMenu.line.remove(fieldMenu.line.selectionStart, fieldMenu.line.selectionEnd)
                        : fieldMenu.area?.remove(fieldMenu.area.selectionStart, fieldMenu.area.selectionEnd)
                }
                MenuSeparator {}
                FieldMenuItem {
                    text: qsTr("Select All")
                    icon.name: "edit-select-all"
                    onTriggered: fieldMenu.line ? fieldMenu.line.selectAll() : fieldMenu.area?.selectAll()
                }
            }

            Menu {
                id: resultMenu

                property int row: -1
                property var actions: []

                popupType: Popup.Item
                // Fades in when it opens, in place of the style's growing from a third of its height
                enter: Transition {
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: quickLaunch.menuOpenDuration; easing.type: Easing.OutCubic }
                }
                topInset: 0
                leftInset: 0
                rightInset: 0
                bottomInset: 0
                font: quickLaunch.menuFont
                // Active and inactive only, so disabled controls keep the style's dimmed colours
                palette.active.text: quickLaunch.menuTextColor
                palette.inactive.text: quickLaunch.menuTextColor

                background: Rectangle {
                    implicitWidth: quickLaunch.menuWidth
                    radius: quickLaunch.menuRadius
                    color: quickLaunch.menuColor
                    border.color: quickLaunch.menuBorderColor
                }

                Instantiator {
                    model: resultMenu.actions

                    delegate: MenuItem {
                        required property var modelData

                        text: modelData.label
                        enabled: modelData.enabled
                        onTriggered: search.runContextAction(resultMenu.row, modelData.id)
                    }

                    onObjectAdded: (index, object) => resultMenu.insertItem(index, object)
                    onObjectRemoved: (index, object) => resultMenu.removeItem(object)
                }
            }
        }
    }
}
