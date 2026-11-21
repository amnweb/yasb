pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    // Not updates: the id would hide AvailableUpdates' updates property
    id: updatesWidget

    component PopupIcons: QtObject {
        property string refresh
        property string upToDate
        property string restart
        property string skip
        property string update
    }

    component Settings: QtObject {
        required property Theme theme

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
        property string label: ""
        // The glyph in front of the label, in the icon font
        property string icon: "\ue896"
        // Hides the widget while there is nothing to update and no restart waiting
        property bool hideWhenNone: true
        property bool tooltip: true
        // Hotkey that opens the popup, such as "alt+shift+u"
        property string hotkey: ""
        property int popupWidth: 364
        // Popup alignment relative to the widget on a horizontal bar: left, right or center
        property string popupAlignment: "center"
        // The updates scroll when they exceed this height
        property int maxListHeight: 420
        property color accentColor: theme.colors.accent
        property color cautionColor: theme.colors.warning
        property color criticalColor: theme.colors.critical
        property color successColor: theme.colors.success
        // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
        property color textColor: theme.colors.text
        property font font
        // Glyphs take the theme's icon font, each part unless the widget file sets it
        property int iconSize: theme.bar.iconFont.pixelSize
        property font iconFont
        iconFont.family: theme.bar.iconFont.family
        iconFont.weight: theme.bar.iconFont.weight
        iconFont.variableAxes: theme.bar.iconFont.variableAxes
        // The popup: the theme's, unless set here
        property color popupColor: theme.popup.background
        property color popupBorderColor: theme.popup.border
        property color popupTextColor: theme.colors.text
        property color popupSecondaryTextColor: theme.colors.textSecondary
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
        property color popupSecondaryBackgroundColor: theme.colors.backgroundSecondary
        property color popupCardColor: theme.colors.card
        property color popupCardBorderColor: theme.colors.cardBorder
        property color popupDividerColor: theme.colors.divider
        property color popupTertiaryTextColor: theme.colors.textTertiary
        property color popupHoverColor: theme.colors.hover
        property color popupControlColor: theme.colors.control
        property color popupControlHoverColor: theme.colors.controlHover
        property color popupControlPressedColor: theme.colors.controlPressed
        property color popupControlBorderColor: theme.colors.controlBorder
        property font popupTitleFont
        popupTitleFont.family: theme.popup.font.family
        popupTitleFont.pixelSize: 16
        popupTitleFont.weight: 600
        readonly property PopupIcons popupIcons: PopupIcons {
            refresh: "\ue72c"
            upToDate: "\ue930"
            restart: "\ue777"
            skip: "\ued1a"
            update: "\ue896"
        }
        property font popupIconFont
        popupIconFont.family: theme.popup.iconFont.family
        popupIconFont.weight: theme.popup.iconFont.weight
        popupIconFont.variableAxes: theme.popup.iconFont.variableAxes
        // Glyphs: the popup's buttons and warnings, and the one shown when everything is up to date
        property int popupIconSize: 14
        property int statusIconSize: 28
        // The message when everything is up to date, each source's name and count, each update's name, and each
        // skipped update's name
        property font statusFont
        statusFont.family: theme.popup.font.family
        statusFont.pixelSize: 14
        property font sectionFont
        sectionFont.family: theme.popup.font.family
        sectionFont.pixelSize: 14
        sectionFont.weight: 600
        property font countFont
        countFont.family: theme.popup.font.family
        countFont.pixelSize: 11
        countFont.weight: 600
        property font updateNameFont
        updateNameFont.family: theme.popup.font.family
        updateNameFont.pixelSize: 13
        updateNameFont.weight: 600
        property font skippedNameFont
        skippedNameFont.family: theme.popup.font.family
        skippedNameFont.pixelSize: 14
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: updatesWidget.theme
    }

    readonly property bool dark: theme.dark
    readonly property string edge: bar.edge

    // The updates of each source by its id
    readonly property var bySource: {
        const found = { windows: 0, winget: 0, scoop: 0 }
        for (const update of available.updates)
            found[update.source] = (found[update.source] ?? 0) + 1
        return found
    }
    readonly property string text: settings.label.replace(/\{(\w+)\}/g,
        (match, key) => key === "count" ? String(available.count) : String(bySource[key] ?? match))
    // When a source was last checked: the time today, the day and time before
    readonly property string checked: {
        const at = available.checked
        if (!(at instanceof Date) || isNaN(at))
            return ""
        const time = Qt.formatTime(at, Qt.locale().timeFormat(Locale.ShortFormat))
        return at.toDateString() === new Date().toDateString() ? time
            : `${Qt.locale().dayName(at.getDay(), Locale.ShortFormat)} ${time}`
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        const gap = settings.popupGap
        const margin = 8
        const screen = updatesWidget.Screen
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
            px = settings.popupAlignment === "left" ? start.x
                : settings.popupAlignment === "right" ? start.x + width - popup.width : start.x + (width - popup.width) / 2
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
    readonly property bool shown: !settings.hideWhenNone || available.count > 0 || available.restartRequired

    implicitWidth: shown ? row.implicitWidth : 0
    implicitHeight: shown ? row.implicitHeight : 0
    visible: shown
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: qsTr("%n update(s) available", "", available.count)
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    Component.onDestruction: popup.hide()

    AvailableUpdates {
        id: available

        windowsUpdate: updatesWidget.settings.windowsUpdate
        winget: updatesWidget.settings.winget
        scoop: updatesWidget.settings.scoop
        windowsInterval: updatesWidget.settings.windowsInterval
        packageInterval: updatesWidget.settings.packageInterval
        exclude: updatesWidget.settings.exclude
    }

    Hotkey {
        keys: updatesWidget.settings.hotkey
        onActivated: updatesWidget.togglePopup()
    }

    Connections {
        target: updatesWidget.Window.window

        function onVisibleChanged() {
            if (!updatesWidget.Window.window?.visible)
                popup.hide()
        }

        function onXChanged() {
            if (popup.visible)
                updatesWidget.placePopup()
        }

        function onYChanged() {
            if (popup.visible)
                updatesWidget.placePopup()
        }
    }

    // Keep the popup anchored when its height changes
    Connections {
        target: popup

        function onHeightChanged() {
            if (popup.visible)
                updatesWidget.placePopup()
        }
    }

    component Glyph: Text {
        id: glyph

        property font iconFont: updatesWidget.settings.iconFont

        textFormat: Text.PlainText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.family: glyph.iconFont.family
        font.weight: glyph.iconFont.weight
        font.variableAxes: glyph.iconFont.variableAxes
    }

    // Text in the popup: plain, in its ink or muted colour, cut short with an ellipsis rather than widening a row
    component PopupText: Text {
        property bool muted: false

        Layout.minimumWidth: 0
        textFormat: Text.PlainText
        elide: Text.ElideRight
        color: muted ? updatesWidget.settings.popupTertiaryTextColor : updatesWidget.settings.popupTextColor
        font: updatesWidget.settings.popupFont
    }

    // A line between the popup's parts
    component Divider: Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: updatesWidget.settings.popupDividerColor
    }

    // A card holding a source's updates
    component Card: Rectangle {
        Layout.fillWidth: true
        Layout.leftMargin: 12
        Layout.rightMargin: 12
        radius: 8
        color: updatesWidget.settings.popupCardColor
        border.width: 1
        border.color: updatesWidget.settings.popupCardBorderColor
    }

    // The line above a row in a card, after its first
    component RowSeparator: Rectangle {
        width: parent.width
        height: 1
        color: updatesWidget.settings.popupDividerColor
    }

    component Link: Text {
        id: link

        signal clicked

        color: linkArea.containsMouse ? updatesWidget.settings.popupTextColor : updatesWidget.settings.popupSecondaryTextColor
        font: updatesWidget.settings.popupSmallFont
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

    // A small framed button
    component SmallButton: Rectangle {
        id: button

        property string text
        signal clicked

        implicitWidth: buttonText.implicitWidth + 20
        implicitHeight: 26
        radius: 4
        color: buttonArea.pressed ? updatesWidget.settings.popupControlPressedColor : buttonArea.containsMouse ? updatesWidget.settings.popupControlHoverColor : updatesWidget.settings.popupControlColor
        border.width: 1
        border.color: updatesWidget.settings.popupControlBorderColor
        Accessible.role: Accessible.Button
        Accessible.name: text
        Accessible.onPressAction: button.clicked()

        Text {
            id: buttonText

            anchors.centerIn: parent
            text: button.text
            textFormat: Text.PlainText
            color: updatesWidget.settings.popupTextColor
            font: updatesWidget.settings.popupSmallFont
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
        property color tint: updatesWidget.settings.popupSecondaryTextColor
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
            color: actionArea.containsMouse ? updatesWidget.settings.popupHoverColor : "transparent"
        }

        Glyph {
            anchors.fill: parent
            text: action.glyph
            color: action.tint
            iconFont: updatesWidget.settings.popupIconFont
            font.pixelSize: updatesWidget.settings.popupIconSize
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
            visible: updatesWidget.settings.icon !== ""
            text: updatesWidget.settings.icon
            color: updatesWidget.settings.textColor
            font.pixelSize: updatesWidget.settings.iconSize
        }

        Label {
            id: barLabel

            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: updatesWidget.text
            textFormat: Text.PlainText
            color: updatesWidget.settings.textColor
            font: updatesWidget.settings.font
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
                updatesWidget.togglePopup()
            else
                available.check("")
        }
    }

    ToolTip {
        objectName: "tooltip"
        popupType: Popup.Window
        visible: updatesWidget.settings.tooltip && area.containsMouse && !popup.visible
        delay: 400
        text: available.count === 0 ? qsTr("Everything is up to date")
            : [qsTr("%n update(s)", "", available.count),
                ...available.sources.filter(source => source.count > 0).map(source => `${source.name}: ${source.count}`)]
                .join("\n")
        // Away from the bar's edge
        y: updatesWidget.edge === "bottom" ? -implicitHeight - 6 : updatesWidget.height + 6
    }

    BackdropPopup {
        id: popup

        property real reveal: 0
        // Whether the popup lists the versions skipped instead of the updates
        property bool showSkipped: false
        // Supporting text, and labels, times and other text to read last
        // The lines between the parts
        // The sources with something to show: updates, an error, or for Windows a restart waiting
        readonly property var shownSources: available.sources.filter(source => source.installed
            && (source.count > 0 || source.error !== "" || source.installing
                || (source.id === "windows" && available.restartRequired)))
        readonly property string subtitle: {
            // Every source still being checked, as "Windows Update, winget and Scoop"
            const checking = available.sources.filter(source => source.checking).map(source => source.name)
            if (checking.length > 0) {
                const names = checking.length === 1 ? checking[0]
                    : qsTr("%1 and %2").arg(checking.slice(0, -1).join(", ")).arg(checking[checking.length - 1])
                return qsTr("Checking %1...").arg(names)
            }
            if (available.count > 0)
                return qsTr("%n available", "", available.count)
            return available.sources.filter(source => source.installed).map(source => source.name).join(", ")
        }

        objectName: "popup"
        title: qsTr("Updates")
        width: updatesWidget.settings.popupWidth
        // Never taller than the screen
        height: Math.min(popupContent.implicitHeight, updatesWidget.Screen.desktopAvailableHeight - 40)
        anchor: updatesWidget
        font: updatesWidget.settings.popupFont
        theme: updatesWidget.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: updatesWidget.settings.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: updatesWidget.settings.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible)
                reveal = 0
        }

        Rectangle {
            id: surface

            anchors.fill: parent
            radius: updatesWidget.settings.popupRadius
            color: updatesWidget.settings.popupColor
            border.width: 1
            border.color: updatesWidget.settings.popupBorderColor
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: updatesWidget.edge === "bottom" ? Item.Bottom : Item.Top
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

                        PopupText {
                            width: parent.width
                            text: popup.showSkipped ? qsTr("Skipped versions") : qsTr("Updates")
                            font: updatesWidget.settings.popupTitleFont
                        }

                        PopupText {
                            objectName: "subtitle"
                            width: parent.width
                            visible: !popup.showSkipped && text !== ""
                            text: popup.subtitle
                            muted: true
                            font: updatesWidget.settings.popupSmallFont
                        }
                    }

                    Item {
                        objectName: "refresh"
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        visible: !popup.showSkipped
                        enabled: !available.checking
                        opacity: enabled ? 1 : 0.4
                        Accessible.role: Accessible.Button
                        Accessible.name: qsTr("Check again")
                        Accessible.onPressAction: available.check("")
                        ToolTip.visible: refreshArea.containsMouse
                        ToolTip.delay: 500
                        ToolTip.text: qsTr("Check again")

                        Rectangle {
                            anchors.fill: parent
                            radius: 4
                            color: refreshArea.containsMouse ? updatesWidget.settings.popupHoverColor : "transparent"
                        }

                        Glyph {
                            anchors.fill: parent
                            text: updatesWidget.settings.popupIcons.refresh
                            color: refreshArea.containsMouse ? updatesWidget.settings.popupTextColor : updatesWidget.settings.popupTertiaryTextColor
                            iconFont: updatesWidget.settings.popupIconFont
                            font.pixelSize: updatesWidget.settings.popupIconSize
                        }

                        MouseArea {
                            id: refreshArea

                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: available.check("")
                        }
                    }
                }

                // The header's bottom line, which the loading bar runs along
                LoadingLine {
                    Layout.fillWidth: true
                    running: available.checking || available.sources.some(source => source.installing)
                    trackColor: updatesWidget.settings.popupDividerColor
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
                        text: updatesWidget.settings.popupIcons.upToDate
                        color: updatesWidget.settings.successColor
                        iconFont: updatesWidget.settings.popupIconFont
                        font.pixelSize: updatesWidget.settings.statusIconSize
                    }

                    PopupText {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 8
                        text: available.checking && updatesWidget.checked === "" ? qsTr("Checking for updates...")
                            : qsTr("Everything is up to date")
                        font: updatesWidget.settings.statusFont
                    }

                    PopupText {
                        Layout.alignment: Qt.AlignHCenter
                        visible: updatesWidget.checked !== ""
                        text: qsTr("Checked %1").arg(updatesWidget.checked)
                        muted: true
                        font: updatesWidget.settings.popupSmallFont
                    }
                }

                // Each source with updates: its name, count and button, then its updates
                Flickable {
                    id: list

                    objectName: "sources"
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(contentHeight, updatesWidget.settings.maxListHeight)
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
                                readonly property var items: available.updates.filter(update => update.source === modelData.id)
                                readonly property bool failed: modelData.error !== ""
                                readonly property bool restart: modelData.id === "windows" && available.restartRequired

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
                                    PopupText {
                                        Layout.fillWidth: true
                                        Layout.maximumWidth: implicitWidth
                                        text: section.modelData.name
                                        font: updatesWidget.settings.sectionFont
                                    }

                                    Rectangle {
                                        visible: section.modelData.count > 0
                                        implicitWidth: Math.max(implicitHeight, countText.implicitWidth + 12)
                                        implicitHeight: 18
                                        radius: 9
                                        color: Qt.alpha(updatesWidget.settings.popupTextColor, 0.08)

                                        Text {
                                            id: countText

                                            anchors.centerIn: parent
                                            text: String(section.modelData.count)
                                            textFormat: Text.PlainText
                                            color: updatesWidget.settings.popupSecondaryTextColor
                                            font: updatesWidget.settings.countFont
                                        }
                                    }

                                    Item { Layout.fillWidth: true }

                                    PopupText {
                                        visible: section.modelData.installing
                                        text: qsTr("Updating...")
                                        muted: true
                                        font: updatesWidget.settings.popupSmallFont
                                    }

                                    SmallButton {
                                        visible: !section.modelData.installing
                                            && (section.modelData.id === "windows" || section.items.length > 0)
                                        text: section.modelData.id === "windows" ? qsTr("Open settings") : qsTr("Update all")
                                        onClicked: available.install(section.modelData.id, section.items.map(update => update.id))
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

                                            PopupText {
                                                Layout.fillWidth: true
                                                text: section.modelData.error
                                                wrapMode: Text.WordWrap
                                                color: updatesWidget.settings.criticalColor
                                                font: updatesWidget.settings.popupSmallFont
                                            }

                                            Link {
                                                text: qsTr("Try again")
                                                onClicked: available.check(section.modelData.id)
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
                                                    text: updatesWidget.settings.popupIcons.restart
                                                    color: updatesWidget.settings.cautionColor
                                                    iconFont: updatesWidget.settings.popupIconFont
                                                    font.pixelSize: updatesWidget.settings.popupIconSize
                                                }

                                                PopupText {
                                                    Layout.fillWidth: true
                                                    text: qsTr("Restart your PC to finish installing Windows updates")
                                                    wrapMode: Text.WordWrap
                                                    color: updatesWidget.settings.popupSecondaryTextColor
                                                    font: updatesWidget.settings.popupSmallFont
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
                                                    color: rowHover.hovered ? updatesWidget.settings.popupHoverColor : "transparent"
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

                                                        PopupText {
                                                            width: parent.width
                                                            text: updateRow.modelData.name
                                                            font: updatesWidget.settings.updateNameFont
                                                        }

                                                        // The installed version, then the new one in the accent colour
                                                        Row {
                                                            width: parent.width
                                                            visible: updateRow.packaged

                                                            PopupText {
                                                                text: `${updateRow.modelData.installedVersion || qsTr("Unknown")} · `
                                                                muted: true
                                                                font: updatesWidget.settings.popupSmallFont
                                                            }

                                                            PopupText {
                                                                text: updateRow.modelData.availableVersion
                                                                muted: true
                                                                font: updatesWidget.settings.popupSmallFont
                                                            }
                                                        }

                                                        PopupText {
                                                            width: parent.width
                                                            visible: !updateRow.packaged && text !== ""
                                                            text: updateRow.details
                                                            muted: true
                                                            font: updatesWidget.settings.popupSmallFont
                                                        }
                                                    }

                                                    RowAction {
                                                        visible: updateRow.packaged && rowHover.hovered
                                                        glyph: updatesWidget.settings.popupIcons.skip
                                                        tip: qsTr("Skip this version")
                                                        onClicked: available.skip(updateRow.modelData.source, updateRow.modelData.id)
                                                    }

                                                    RowAction {
                                                        visible: updateRow.packaged && rowHover.hovered && !section.modelData.installing
                                                        glyph: updatesWidget.settings.popupIcons.update
                                                        tip: qsTr("Update")
                                                        tint: updatesWidget.settings.accentColor
                                                        onClicked: available.install(updateRow.modelData.source, [updateRow.modelData.id])
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
                    Layout.preferredHeight: Math.min(contentHeight, updatesWidget.settings.maxListHeight)
                    visible: popup.showSkipped
                    clip: true
                    contentHeight: skippedColumn.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}

                    ColumnLayout {
                        id: skippedColumn

                        width: skippedList.width
                        spacing: 0

                        PopupText {
                            Layout.fillWidth: true
                            Layout.margins: 16
                            visible: available.skipped.length === 0
                            text: qsTr("No versions are skipped.")
                            horizontalAlignment: Text.AlignHCenter
                            muted: true
                        }

                        Card {
                            Layout.topMargin: 12
                            Layout.bottomMargin: 12
                            visible: available.skipped.length > 0
                            implicitHeight: skippedRows.implicitHeight

                            ColumnLayout {
                                id: skippedRows

                                width: parent.width
                                spacing: 0

                                Repeater {
                                    model: available.skipped

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

                                                PopupText {
                                                    width: parent.width
                                                    text: skippedRow.modelData.name
                                                    font: updatesWidget.settings.skippedNameFont
                                                }

                                                PopupText {
                                                    width: parent.width
                                                    text: [skippedRow.modelData.version, skippedRow.modelData.source].filter(part => part).join(" · ")
                                                    muted: true
                                                    font: updatesWidget.settings.popupSmallFont
                                                }
                                            }

                                            Link {
                                                text: qsTr("Show again")
                                                onClicked: available.restore(skippedRow.modelData.source, skippedRow.modelData.id)
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
                    bottomLeftRadius: updatesWidget.settings.popupRadius - 1
                    bottomRightRadius: updatesWidget.settings.popupRadius - 1
                    color: updatesWidget.settings.popupSecondaryBackgroundColor

                    Divider { width: parent.width }

                    Link {
                        objectName: "skippedLink"
                        x: 16
                        anchors.verticalCenter: parent.verticalCenter
                        visible: popup.showSkipped || available.skipped.length > 0
                        text: popup.showSkipped ? qsTr("Back") : qsTr("Skipped (%1)").arg(available.skipped.length)
                        onClicked: popup.showSkipped = !popup.showSkipped
                    }

                    PopupText {
                        objectName: "checked"
                        anchors.right: parent.right
                        anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !popup.showSkipped && updatesWidget.checked !== "" && popup.shownSources.length > 0
                        text: qsTr("Checked %1").arg(updatesWidget.checked)
                        muted: true
                        font: updatesWidget.settings.popupSmallFont
                    }
                }
            }
        }
    }
}
