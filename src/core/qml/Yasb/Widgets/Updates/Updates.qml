pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: widget

    property Item bar: null
    // Which sources are checked; winget and Scoop are left out where they are not installed
    property bool windowsUpdate: true
    property bool winget: true
    property bool scoop: true
    // How often Windows Update is checked, in milliseconds, from 1800000 to 604800000
    property int windowsInterval: 86400000
    // How often winget and Scoop are checked, in milliseconds, from 600000 to 604800000
    property int packageInterval: 14400000
    // Updates to leave out, by a name or id they contain, in any case, such as ["Microsoft.Edge", "Defender"]
    property list<string> exclude: []
    // Label placeholders: {count}, {windows}, {winget} and {scoop}
    property string label: "{count}"
    // The glyph in front of the label, in the icon font
    property string icon: "\ue896"
    // Hides the widget while there is nothing to update and no restart waiting
    property bool hideWhenNone: true
    property bool tooltip: true
    // Hotkey that opens the popup, such as "alt+shift+u"
    property string keys: ""
    property int popupWidth: 380
    // Popup alignment relative to the widget on a horizontal bar: left, right or center
    property string popupAlignment: "center"
    // The updates scroll when they exceed this height
    property int maxListHeight: 420
    property color accentColor: dark ? "#60CDFF" : "#005FB8"
    property color cautionColor: dark ? "#FCE100" : "#9D5D00"
    property color criticalColor: dark ? "#FF99A4" : "#C42B1C"
    property color successColor: dark ? "#6CCB5F" : "#0F7B0F"

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
    // Glyphs take the family and weight of the bar's icon font unless the widget file sets them
    property font iconFont
    iconFont.family: bar?.iconFont?.family ?? "Segoe Fluent Icons"
    iconFont.weight: bar?.iconFont?.weight ?? Font.Normal
    readonly property string edge: bar?.edge ?? "top"

    // The updates of each source by its id
    readonly property var bySource: {
        const found = { windows: 0, winget: 0, scoop: 0 }
        for (const update of updates.updates)
            found[update.source] = (found[update.source] ?? 0) + 1
        return found
    }
    readonly property string text: label.replace(/\{(\w+)\}/g,
        (match, key) => key === "count" ? String(updates.count) : String(bySource[key] ?? match))
    // When a source was last checked: the time today, the day and time before
    readonly property string checked: {
        const at = updates.checked
        if (!(at instanceof Date) || isNaN(at))
            return ""
        const time = Qt.formatTime(at, Qt.locale().timeFormat(Locale.ShortFormat))
        return at.toDateString() === new Date().toDateString() ? time
            : `${Qt.locale().dayName(at.getDay(), Locale.ShortFormat)} ${time}`
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        const gap = 6
        const margin = 8
        const screen = widget.Screen
        let px
        let py
        switch (edge) {
        case "left":
            px = start.x + width + gap
            py = start.y + (height - popup.height) / 2
            break
        case "right":
            px = start.x - popup.width - gap
            py = start.y + (height - popup.height) / 2
            break
        default:
            px = popupAlignment === "left" ? start.x
                : popupAlignment === "right" ? start.x + width - popup.width : start.x + (width - popup.width) / 2
            py = edge === "bottom" ? start.y - popup.height - gap : start.y + height + gap
            break
        }
        px = Math.max(screen.virtualX + margin, Math.min(px, screen.virtualX + screen.width - popup.width - margin))
        py = Math.max(screen.virtualY + margin, Math.min(py, screen.virtualY + screen.desktopAvailableHeight - popup.height - margin))
        popup.x = Math.round(px)
        popup.y = Math.round(py)
    }

    function togglePopup() {
        if (popup.visible) {
            popup.close()
            return
        }
        popup.showSkipped = false
        placePopup()
        popup.open()
    }

    // A hidden widget takes no room on the bar, as its slot keeps the size it asks for
    readonly property bool shown: !hideWhenNone || updates.count > 0 || updates.restartRequired

    implicitWidth: shown ? row.implicitWidth : 0
    implicitHeight: shown ? row.implicitHeight : 0
    visible: shown
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: qsTr("%n update(s) available", "", updates.count)
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    Component.onDestruction: popup.hide()

    AvailableUpdates {
        id: updates

        windowsUpdate: widget.windowsUpdate
        winget: widget.winget
        scoop: widget.scoop
        windowsInterval: widget.windowsInterval
        packageInterval: widget.packageInterval
        exclude: widget.exclude
    }

    Hotkey {
        keys: widget.keys
        onActivated: widget.togglePopup()
    }

    Connections {
        target: widget.Window.window

        function onVisibleChanged() {
            if (!widget.Window.window?.visible)
                popup.hide()
        }

        function onXChanged() {
            if (popup.visible)
                widget.placePopup()
        }

        function onYChanged() {
            if (popup.visible)
                widget.placePopup()
        }
    }

    // Keep the popup anchored when its height changes
    Connections {
        target: popup

        function onHeightChanged() {
            if (popup.visible)
                widget.placePopup()
        }
    }

    component Glyph: Text {
        textFormat: Text.PlainText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.family: widget.iconFont.family
        font.weight: widget.iconFont.weight
    }

    // Text in the popup: plain, in its ink or muted colour, cut short with an ellipsis rather than widening a row
    component Label: Text {
        property bool muted: false

        Layout.minimumWidth: 0
        textFormat: Text.PlainText
        elide: Text.ElideRight
        color: muted ? popup.muted : popup.ink
        font.pixelSize: 13
    }

    // A line between the popup's parts
    component Divider: Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: popup.line
    }

    // A WinUI card, holding a source's updates
    component Card: Rectangle {
        Layout.fillWidth: true
        Layout.leftMargin: 12
        Layout.rightMargin: 12
        radius: 8
        color: widget.dark ? Qt.alpha("#ffffff", 0.0512) : Qt.alpha("#ffffff", 0.7)
        border.width: 1
        border.color: Qt.alpha("#000000", widget.dark ? 0.1 : 0.0578)
    }

    // The line above a row in a card, after its first
    component RowSeparator: Rectangle {
        width: parent.width
        height: 1
        color: Qt.alpha(popup.ink, 0.06)
    }

    component Link: Text {
        id: link

        signal clicked

        color: linkArea.containsMouse ? popup.ink : popup.secondary
        font.pixelSize: 12
        Accessible.role: Accessible.Link
        Accessible.name: text
        Accessible.onPressAction: link.clicked()

        MouseArea {
            id: linkArea

            anchors.fill: parent
            anchors.margins: -8
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: link.clicked()
        }
    }

    // A small framed button, as WinUI's standard buttons are
    component SmallButton: Rectangle {
        id: button

        property string text
        signal clicked

        implicitWidth: buttonText.implicitWidth + 20
        implicitHeight: 26
        radius: 4
        color: Qt.alpha(popup.ink, buttonArea.pressed ? 0.04 : buttonArea.containsMouse ? 0.09 : 0.06)
        border.width: 1
        border.color: Qt.alpha(popup.ink, 0.08)
        Accessible.role: Accessible.Button
        Accessible.name: text
        Accessible.onPressAction: button.clicked()

        Text {
            id: buttonText

            anchors.centerIn: parent
            text: button.text
            textFormat: Text.PlainText
            color: popup.ink
            font.pixelSize: 12
        }

        MouseArea {
            id: buttonArea

            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: button.clicked()
        }
    }

    // A glyph button that shows on a row while the pointer is over it
    component RowAction: Item {
        id: action

        property string glyph
        property string tip
        property color tint: popup.secondary
        signal clicked

        implicitWidth: 26
        implicitHeight: 26
        Accessible.role: Accessible.Button
        Accessible.name: tip
        Accessible.onPressAction: action.clicked()
        ToolTip.visible: actionArea.containsMouse
        ToolTip.delay: 500
        ToolTip.text: tip

        Rectangle {
            anchors.fill: parent
            radius: 4
            color: Qt.alpha(popup.ink, actionArea.containsMouse ? 0.08 : 0)
        }

        Glyph {
            anchors.fill: parent
            text: action.glyph
            color: action.tint
            font.pixelSize: 14
        }

        MouseArea {
            id: actionArea

            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: action.clicked()
        }
    }

    Row {
        id: row

        height: parent.height
        spacing: 6

        Glyph {
            objectName: "icon"
            anchors.verticalCenter: parent.verticalCenter
            visible: widget.icon !== ""
            text: widget.icon
            color: widget.textColor
            font.pixelSize: widget.font.pixelSize + 1
        }

        Text {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: widget.text
            textFormat: Text.PlainText
            color: widget.textColor
            font: widget.font
        }
    }

    MouseArea {
        id: area

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                widget.togglePopup()
            else
                updates.check("")
        }
    }

    ToolTip {
        objectName: "tooltip"
        popupType: Popup.Window
        visible: widget.tooltip && area.containsMouse && !popup.visible
        delay: 400
        text: updates.count === 0 ? qsTr("Everything is up to date")
            : [qsTr("%n update(s)", "", updates.count),
                ...updates.sources.filter(source => source.count > 0).map(source => `${source.name}: ${source.count}`)]
                .join("\n")
        // Away from the bar's edge
        y: widget.edge === "bottom" ? -implicitHeight - 6 : widget.height + 6
    }

    BackdropPopup {
        id: popup

        property real reveal: 0
        // Whether the popup lists the versions skipped instead of the updates
        property bool showSkipped: false
        readonly property color ink: widget.dark ? "#ffffff" : "#000000"
        // Supporting text, and labels, times and other text to read last
        readonly property color secondary: Qt.alpha(ink, 0.786)
        readonly property color muted: Qt.alpha(ink, 0.544)
        // The lines between the parts
        readonly property color line: Qt.alpha(ink, 0.08)
        // The sources with something to show: updates, an error, or for Windows a restart waiting
        readonly property var shownSources: updates.sources.filter(source => source.installed
            && (source.count > 0 || source.error !== "" || source.installing
                || (source.id === "windows" && updates.restartRequired)))
        readonly property string subtitle: {
            // Every source still being checked, as "Windows Update, winget and Scoop"
            const checking = updates.sources.filter(source => source.checking).map(source => source.name)
            if (checking.length > 0) {
                const names = checking.length === 1 ? checking[0]
                    : qsTr("%1 and %2").arg(checking.slice(0, -1).join(", ")).arg(checking[checking.length - 1])
                return qsTr("Checking %1...").arg(names)
            }
            if (updates.count > 0)
                return qsTr("%n available", "", updates.count)
            return updates.sources.filter(source => source.installed).map(source => source.name).join(", ")
        }

        objectName: "popup"
        title: qsTr("Updates")
        width: widget.popupWidth
        // Never taller than the screen
        height: Math.min(popupContent.implicitHeight + 16, widget.Screen.desktopAvailableHeight - 24)
        anchor: widget
        backdropItem: surface
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
            color: widget.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: widget.dark ? "#3A3A3A" : "#D9D9D9"
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: widget.edge === "bottom" ? Item.Bottom : Item.Top
            clip: true

            ColumnLayout {
                id: popupContent

                anchors.left: parent.left
                anchors.right: parent.right
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 10
                    Layout.topMargin: 12
                    Layout.bottomMargin: 10
                    spacing: 8

                    Column {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 2

                        Label {
                            width: parent.width
                            text: popup.showSkipped ? qsTr("Skipped versions") : qsTr("Updates")
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }

                        Label {
                            objectName: "subtitle"
                            width: parent.width
                            visible: !popup.showSkipped && text !== ""
                            text: popup.subtitle
                            muted: true
                            font.pixelSize: 12
                        }
                    }

                    Item {
                        objectName: "refresh"
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        visible: !popup.showSkipped
                        enabled: !updates.checking
                        opacity: enabled ? 1 : 0.4
                        Accessible.role: Accessible.Button
                        Accessible.name: qsTr("Check again")
                        Accessible.onPressAction: updates.check("")
                        ToolTip.visible: refreshArea.containsMouse
                        ToolTip.delay: 500
                        ToolTip.text: qsTr("Check again")

                        Rectangle {
                            anchors.fill: parent
                            radius: 4
                            color: Qt.alpha(popup.ink, refreshArea.containsMouse ? 0.1 : 0)
                        }

                        Glyph {
                            anchors.fill: parent
                            text: "\ue72c"
                            color: refreshArea.containsMouse ? popup.ink : popup.muted
                            font.pixelSize: 14
                        }

                        MouseArea {
                            id: refreshArea

                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: updates.check("")
                        }
                    }
                }

                // The header's bottom line, which the loading bar runs along
                LoadingLine {
                    Layout.fillWidth: true
                    running: updates.checking || updates.sources.some(source => source.installing)
                    trackColor: popup.line
                }

                // Nothing to update
                ColumnLayout {
                    objectName: "upToDate"
                    Layout.fillWidth: true
                    Layout.topMargin: 28
                    Layout.bottomMargin: 28
                    visible: !popup.showSkipped && popup.shownSources.length === 0
                    spacing: 2

                    Glyph {
                        Layout.alignment: Qt.AlignHCenter
                        text: "\ue930"
                        color: widget.successColor
                        font.pixelSize: 28
                    }

                    Label {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 8
                        text: updates.checking && widget.checked === "" ? qsTr("Checking for updates...")
                            : qsTr("Everything is up to date")
                        font.pixelSize: 14
                    }

                    Label {
                        Layout.alignment: Qt.AlignHCenter
                        visible: widget.checked !== ""
                        text: qsTr("Checked %1").arg(widget.checked)
                        muted: true
                        font.pixelSize: 12
                    }
                }

                // Each source with updates: its name, count and button, then its updates
                Flickable {
                    id: list

                    objectName: "sources"
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(contentHeight, widget.maxListHeight)
                    visible: !popup.showSkipped && popup.shownSources.length > 0
                    clip: true
                    contentHeight: sourceColumn.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}

                    ColumnLayout {
                        id: sourceColumn

                        width: list.width
                        spacing: 0

                        Repeater {
                            model: popup.shownSources

                            delegate: ColumnLayout {
                                id: section

                                required property var modelData
                                required property int index
                                readonly property var items: updates.updates.filter(update => update.source === modelData.id)
                                readonly property bool failed: modelData.error !== ""
                                readonly property bool restart: modelData.id === "windows" && updates.restartRequired

                                Layout.fillWidth: true
                                // Long names are cut short instead of widening the popup
                                Layout.minimumWidth: 0
                                spacing: 0

                                // The source's name, count and button, above its card
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 16
                                    Layout.rightMargin: 12
                                    Layout.topMargin: section.index > 0 ? 16 : 12
                                    Layout.bottomMargin: 8
                                    spacing: 8

                                    // Shrinks with an ellipsis when the row is short, but never grows past its text
                                    Label {
                                        Layout.fillWidth: true
                                        Layout.maximumWidth: implicitWidth
                                        text: section.modelData.name
                                        font.pixelSize: 14
                                        font.weight: Font.DemiBold
                                    }

                                    Rectangle {
                                        visible: section.modelData.count > 0
                                        implicitWidth: Math.max(implicitHeight, countText.implicitWidth + 12)
                                        implicitHeight: 18
                                        radius: 9
                                        color: Qt.alpha(popup.ink, 0.08)

                                        Text {
                                            id: countText

                                            anchors.centerIn: parent
                                            text: String(section.modelData.count)
                                            textFormat: Text.PlainText
                                            color: popup.secondary
                                            font.pixelSize: 11
                                            font.weight: Font.DemiBold
                                        }
                                    }

                                    Item { Layout.fillWidth: true }

                                    Label {
                                        visible: section.modelData.installing
                                        text: qsTr("Updating...")
                                        muted: true
                                        font.pixelSize: 12
                                    }

                                    SmallButton {
                                        visible: !section.modelData.installing
                                            && (section.modelData.id === "windows" || section.items.length > 0)
                                        text: section.modelData.id === "windows" ? qsTr("Open settings") : qsTr("Update all")
                                        onClicked: updates.install(section.modelData.id, section.items.map(update => update.id))
                                    }
                                }

                                Card {
                                    visible: section.failed || section.restart || section.items.length > 0
                                    implicitHeight: cardColumn.implicitHeight

                                    ColumnLayout {
                                        id: cardColumn

                                        width: parent.width
                                        spacing: 0

                                        // A check that failed, keeping the updates found before
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Layout.margins: 12
                                            visible: section.failed
                                            spacing: 8

                                            Label {
                                                Layout.fillWidth: true
                                                text: section.modelData.error
                                                wrapMode: Text.WordWrap
                                                color: widget.criticalColor
                                                font.pixelSize: 12
                                            }

                                            Link {
                                                text: qsTr("Try again")
                                                onClicked: updates.check(section.modelData.id)
                                            }
                                        }

                                        // Windows waits for a restart to finish installing updates
                                        Item {
                                            objectName: "restart"
                                            Layout.fillWidth: true
                                            implicitHeight: restartRow.implicitHeight + 24
                                            visible: section.restart

                                            RowSeparator { visible: section.failed }

                                            RowLayout {
                                                id: restartRow

                                                anchors.left: parent.left
                                                anchors.right: parent.right
                                                anchors.margins: 12
                                                anchors.verticalCenter: parent.verticalCenter
                                                spacing: 8

                                                Glyph {
                                                    text: "\ue777"
                                                    color: widget.cautionColor
                                                    font.pixelSize: 14
                                                }

                                                Label {
                                                    Layout.fillWidth: true
                                                    text: qsTr("Restart your PC to finish installing Windows updates")
                                                    wrapMode: Text.WordWrap
                                                    color: popup.secondary
                                                    font.pixelSize: 12
                                                }
                                            }
                                        }

                                        Repeater {
                                            model: section.items

                                            delegate: Item {
                                                id: updateRow

                                                required property var modelData
                                                required property int index
                                                readonly property bool packaged: modelData.source !== "windows"
                                                readonly property string details: packaged
                                                    ? `${modelData.installedVersion || qsTr("Unknown")} → ${modelData.availableVersion}`
                                                    : [modelData.category, modelData.kb, modelData.severity,
                                                        modelData.downloaded ? qsTr("Downloaded") : ""].filter(part => part).join(" · ")

                                                Layout.fillWidth: true
                                                implicitHeight: rowContent.implicitHeight + 16
                                                Accessible.role: Accessible.StaticText
                                                Accessible.name: `${modelData.name}, ${details}`

                                                RowSeparator { visible: updateRow.index > 0 || section.failed || section.restart }

                                                Rectangle {
                                                    anchors.fill: parent
                                                    anchors.margins: 3
                                                    radius: 4
                                                    color: Qt.alpha(popup.ink, rowHover.hovered ? 0.04 : 0)
                                                }

                                                // Stays hovered over the row's buttons too; a MouseArea would lose the hover to them
                                                // and hide them again, which flashes the row
                                                HoverHandler {
                                                    id: rowHover
                                                }

                                                RowLayout {
                                                    id: rowContent

                                                    anchors.left: parent.left
                                                    anchors.right: parent.right
                                                    anchors.leftMargin: 12
                                                    anchors.rightMargin: 8
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    spacing: 4

                                                    Column {
                                                        Layout.fillWidth: true
                                                        Layout.minimumWidth: 0

                                                        Label {
                                                            width: parent.width
                                                            text: updateRow.modelData.name
                                                            font.pixelSize: 13
                                                            font.weight: Font.DemiBold
                                                        }

                                                        // The installed version, then the new one in the accent colour
                                                        Row {
                                                            width: parent.width
                                                            visible: updateRow.packaged

                                                            Label {
                                                                text: `${updateRow.modelData.installedVersion || qsTr("Unknown")} · `
                                                                muted: true
                                                                font.pixelSize: 12
                                                            }

                                                            Label {
                                                                text: updateRow.modelData.availableVersion
                                                                muted: true
                                                                font.pixelSize: 12
                                                            }
                                                        }

                                                        Label {
                                                            width: parent.width
                                                            visible: !updateRow.packaged && text !== ""
                                                            text: updateRow.details
                                                            muted: true
                                                            font.pixelSize: 12
                                                        }
                                                    }

                                                    RowAction {
                                                        visible: updateRow.packaged && rowHover.hovered
                                                        glyph: "\ued1a"
                                                        tip: qsTr("Skip this version")
                                                        onClicked: updates.skip(updateRow.modelData.source, updateRow.modelData.id)
                                                    }

                                                    RowAction {
                                                        visible: updateRow.packaged && rowHover.hovered && !section.modelData.installing
                                                        glyph: "\ue896"
                                                        tip: qsTr("Update")
                                                        tint: widget.accentColor
                                                        onClicked: updates.install(updateRow.modelData.source, [updateRow.modelData.id])
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Item { implicitHeight: 12 }
                    }
                }

                // The versions skipped, each shown again by a click
                Flickable {
                    id: skippedList

                    objectName: "skipped"
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(contentHeight, widget.maxListHeight)
                    visible: popup.showSkipped
                    clip: true
                    contentHeight: skippedColumn.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}

                    ColumnLayout {
                        id: skippedColumn

                        width: skippedList.width
                        spacing: 0

                        Label {
                            Layout.fillWidth: true
                            Layout.margins: 16
                            visible: updates.skipped.length === 0
                            text: qsTr("No versions are skipped.")
                            horizontalAlignment: Text.AlignHCenter
                            muted: true
                        }

                        Card {
                            Layout.topMargin: 12
                            Layout.bottomMargin: 12
                            visible: updates.skipped.length > 0
                            implicitHeight: skippedRows.implicitHeight

                            ColumnLayout {
                                id: skippedRows

                                width: parent.width
                                spacing: 0

                                Repeater {
                                    model: updates.skipped

                                    delegate: Item {
                                        id: skippedRow

                                        required property var modelData
                                        required property int index

                                        Layout.fillWidth: true
                                        implicitHeight: skippedContent.implicitHeight + 16

                                        RowSeparator { visible: skippedRow.index > 0 }

                                        RowLayout {
                                            id: skippedContent

                                            anchors.left: parent.left
                                            anchors.right: parent.right
                                            anchors.leftMargin: 12
                                            anchors.rightMargin: 12
                                            anchors.verticalCenter: parent.verticalCenter
                                            spacing: 8

                                            Column {
                                                Layout.fillWidth: true
                                                Layout.minimumWidth: 0

                                                Label {
                                                    width: parent.width
                                                    text: skippedRow.modelData.name
                                                    font.pixelSize: 14
                                                }

                                                Label {
                                                    width: parent.width
                                                    text: [skippedRow.modelData.version, skippedRow.modelData.source].filter(part => part).join(" · ")
                                                    muted: true
                                                    font.pixelSize: 12
                                                }
                                            }

                                            Link {
                                                text: qsTr("Show again")
                                                onClicked: updates.restore(skippedRow.modelData.source, skippedRow.modelData.id)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // A darker strip, as in the GitHub popup
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 1
                    Layout.rightMargin: 1
                    Layout.bottomMargin: 1
                    implicitHeight: 40
                    bottomLeftRadius: 7
                    bottomRightRadius: 7
                    color: Qt.alpha("#000000", widget.dark ? 0.15 : 0.03)

                    Divider { width: parent.width }

                    Link {
                        objectName: "skippedLink"
                        x: 16
                        anchors.verticalCenter: parent.verticalCenter
                        visible: popup.showSkipped || updates.skipped.length > 0
                        text: popup.showSkipped ? qsTr("Back") : qsTr("Skipped (%1)").arg(updates.skipped.length)
                        onClicked: popup.showSkipped = !popup.showSkipped
                    }

                    Label {
                        objectName: "checked"
                        anchors.right: parent.right
                        anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !popup.showSkipped && widget.checked !== "" && popup.shownSources.length > 0
                        text: qsTr("Checked %1").arg(widget.checked)
                        muted: true
                        font.pixelSize: 12
                    }
                }
            }
        }
    }
}
