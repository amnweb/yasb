pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Common

Item {
    id: claude

    property Item bar: null
    // How often the usage is fetched, in milliseconds, from 30000 to 3600000; Anthropic limits how often it answers
    property int updateInterval: 120000
    // Whether Claude Code's session logs are scanned for the tokens it used, shown in the popup; the scan runs in the
    // background, and the section shows once it ends
    property bool tokenHistory: true
    // How often the logs are scanned, in milliseconds, from 30000 to 3600000
    property int scanInterval: 120000
    // Whether tokens read back from the prompt cache count in the totals; they are most of a long session's tokens
    property bool countCacheRead: true
    // monday or sunday
    property string weekStartsOn: "monday"
    // Whether Claude's status is checked and shown in the popup
    property bool checkStatus: true
    // How often the status is checked, in milliseconds, from 60000 to 3600000
    property int statusInterval: 300000
    // 24h or 12h
    property string timeFormat: "24h"
    // Label placeholders: {five_hour}, {seven_day}, {five_hour_reset}, {seven_day_reset}, {session_tokens},
    // {today_tokens}, {week_tokens}, {month_tokens}, {year_tokens} and {status_text}
    property string label: "Claude {five_hour}%"
    property string alternateLabel: "Claude {seven_day}%"
    // The label while Claude Code is not signed in, so there are no limits but there is the token history
    property string signedOutLabel: "Claude {today_tokens}"
    // The period the token history opens on: session, today, week, month or year
    property string defaultPeriod: "today"
    // The warning glyph after the label while Claude Code's sign-in has run out
    property bool showExpired: true
    property bool tooltip: true
    // Hotkey that opens the popup, such as "alt+shift+c"
    property string keys: ""
    property int popupWidth: 360
    // Popup alignment relative to the widget on a horizontal bar: left, right or center
    property string popupAlignment: "center"
    property color accentColor: dark ? "#60CDFF" : "#005FB8"
    property color cautionColor: dark ? "#FCE100" : "#9D5D00"
    property color criticalColor: dark ? "#FF99A4" : "#C42B1C"
    property color successColor: dark ? "#6CCB5F" : "#0F7B0F"

    property bool showAlternate: false

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

    readonly property string text: format(!usage.signedIn ? signedOutLabel : showAlternate ? alternateLabel : label)
    // When the usage was fetched: the time today, the day and time before
    readonly property string updated: {
        const at = usage.updated
        if (!(at instanceof Date) || isNaN(at))
            return ""
        const time = Qt.formatTime(at, timeFormat === "12h" ? "h:mm AP" : "HH:mm")
        return at.toDateString() === new Date().toDateString() ? time
            : `${Qt.locale().dayName(at.getDay(), Locale.ShortFormat)} ${time}`
    }

    function format(template: string): string {
        return template.replace(/\{(\w+)\}/g, (match, key) => usage.values[key] ?? match)
    }

    function levelColor(level: string): color {
        return level === "high" ? criticalColor : level === "medium" ? cautionColor : accentColor
    }

    // A token count in a few characters: 950, 12.3K, 4.5M, 1.2B
    function compact(tokens: var): string {
        const value = Number(tokens ?? 0)
        for (const [size, suffix] of [[1e9, "B"], [1e6, "M"], [1e3, "K"]]) {
            if (value >= size)
                return `${(value / size).toFixed(1).replace(/\.0$/, "")}${suffix}`
        }
        return String(value)
    }

    function statusColor(indicator: string): color {
        return indicator === "none" ? successColor : indicator === "minor" ? cautionColor
            : indicator === "major" || indicator === "critical" ? criticalColor : Qt.alpha(popup.ink, 0.4)
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        const gap = 6
        const margin = 8
        const screen = claude.Screen
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
        popup.period = defaultPeriod
        placePopup()
        popup.open()
    }

    implicitWidth: row.implicitWidth
    implicitHeight: row.implicitHeight
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: usage.ready ? qsTr("Claude usage, 5-hour %1%, 7-day %2%").arg(usage.values.five_hour).arg(usage.values.seven_day)
        : qsTr("Claude usage")
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    Component.onDestruction: popup.hide()

    ClaudeUsageMonitor {
        id: usage

        updateInterval: claude.updateInterval
        tokenHistory: claude.tokenHistory
        scanInterval: claude.scanInterval
        countCacheRead: claude.countCacheRead
        weekStartsOn: claude.weekStartsOn
        checkStatus: claude.checkStatus
        statusInterval: claude.statusInterval
        timeFormat: claude.timeFormat
    }

    Hotkey {
        keys: claude.keys
        onActivated: claude.togglePopup()
    }

    Connections {
        target: claude.Window.window

        function onVisibleChanged() {
            if (!claude.Window.window?.visible)
                popup.hide()
        }

        function onXChanged() {
            if (popup.visible)
                claude.placePopup()
        }

        function onYChanged() {
            if (popup.visible)
                claude.placePopup()
        }
    }

    // Keep the popup anchored when its height changes
    Connections {
        target: popup

        function onHeightChanged() {
            if (popup.visible)
                claude.placePopup()
        }
    }

    component Glyph: Text {
        textFormat: Text.PlainText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.family: claude.iconFont.family
        font.weight: claude.iconFont.weight
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

    // A bar filled to a part of its width, from 0 to 1
    component Meter: Rectangle {
        property real part: 0
        property color fill: claude.accentColor

        implicitHeight: 4
        radius: height / 2
        color: Qt.alpha(popup.ink, 0.1)

        Rectangle {
            width: parent.width * Math.max(0, Math.min(parent.part, 1))
            height: parent.height
            radius: parent.radius
            visible: parent.part > 0
            color: parent.fill
        }
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

    Row {
        id: row

        height: parent.height
        spacing: 4

        Text {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: claude.text
            textFormat: Text.PlainText
            color: claude.textColor
            font: claude.font
        }

        Glyph {
            objectName: "expired"
            anchors.verticalCenter: parent.verticalCenter
            visible: claude.showExpired && usage.tokenExpired
            text: "\ue7ba"
            color: claude.cautionColor
            font.pixelSize: claude.font.pixelSize
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
                claude.togglePopup()
            else
                claude.showAlternate = !claude.showAlternate
        }
    }

    ToolTip {
        objectName: "tooltip"
        popupType: Popup.Window
        visible: claude.tooltip && area.containsMouse && !popup.visible
        delay: 400
        text: !usage.signedIn ? qsTr("%1 tokens today
%2").arg(usage.values.today_tokens).arg(usage.error)
            : !usage.ready ? usage.error || qsTr("Fetching the Claude usage...")
            : usage.limits.length === 0 ? qsTr("Anthropic reports no usage limits for this account right now.")
            : usage.limits.map(limit => qsTr("%1: %2% used, resets in %3").arg(limit.name).arg(limit.value).arg(limit.resetIn))
                .join("\n")
        // Away from the bar's edge
        y: claude.edge === "bottom" ? -implicitHeight - 6 : claude.height + 6
    }

    BackdropPopup {
        id: popup

        property real reveal: 0
        // The token history's period: session, today, week, month or year
        property string period: "today"
        readonly property color ink: claude.dark ? "#ffffff" : "#000000"
        // Supporting text, and labels, times and other text to read last
        readonly property color secondary: Qt.alpha(ink, 0.786)
        readonly property color muted: Qt.alpha(ink, 0.544)
        // The lines between the parts
        readonly property color line: Qt.alpha(ink, 0.08)
        readonly property var tokens: usage.history.periods?.[period] ?? null
        // A warning above the usage: Claude Code signed out or its sign-in run out, or a fetch that failed
        readonly property string notice: !usage.signedIn ? usage.error
            : usage.tokenExpired ? qsTr("Claude Code's sign-in has expired. Run any Claude Code command to renew it.")
            : usage.error

        objectName: "popup"
        title: qsTr("Claude usage")
        width: claude.popupWidth
        // Never taller than the screen
        height: Math.min(popupContent.implicitHeight + 16, claude.Screen.desktopAvailableHeight - 24)
        anchor: claude
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
            color: claude.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: claude.dark ? "#3A3A3A" : "#D9D9D9"
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: claude.edge === "bottom" ? Item.Bottom : Item.Top
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
                            text: qsTr("Claude usage")
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }

                        // Claude's status, with a dot in its colour
                        Row {
                            objectName: "status"
                            width: parent.width
                            visible: claude.checkStatus && usage.status.description !== ""
                            spacing: 6

                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 7
                                height: 7
                                radius: 3.5
                                color: claude.statusColor(usage.status.indicator)
                            }

                            Label {
                                width: parent.width - 13
                                text: usage.status.description
                                muted: true
                                font.pixelSize: 12
                            }
                        }
                    }

                    Item {
                        objectName: "refresh"
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        enabled: !usage.loading
                        opacity: enabled ? 1 : 0.4
                        Accessible.role: Accessible.Button
                        Accessible.name: qsTr("Refresh")
                        Accessible.onPressAction: usage.refresh()
                        ToolTip.visible: refreshArea.containsMouse
                        ToolTip.delay: 500
                        ToolTip.text: qsTr("Refresh")

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
                            onClicked: usage.refresh()
                        }
                    }
                }

                // The header's bottom line, which the loading bar runs along
                LoadingLine {
                    Layout.fillWidth: true
                    running: usage.loading || usage.scanning
                    trackColor: popup.line
                }

                Label {
                    objectName: "notice"
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 12
                    Layout.bottomMargin: usage.ready ? 0 : 14
                    visible: popup.notice !== ""
                    text: popup.notice
                    wrapMode: Text.WordWrap
                    // Signing in is a step to take, not a failure
                    color: !usage.signedIn ? popup.secondary : usage.ready ? claude.cautionColor : claude.criticalColor
                    font.pixelSize: 12
                }

                Label {
                    objectName: "placeholder"
                    Layout.fillWidth: true
                    Layout.topMargin: 24
                    Layout.bottomMargin: 24
                    visible: !usage.ready && popup.notice === ""
                    text: qsTr("Fetching the Claude usage...")
                    horizontalAlignment: Text.AlignHCenter
                    muted: true
                }

                // Anthropic answered, but left out every window and cap
                Label {
                    objectName: "noLimits"
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 24
                    Layout.bottomMargin: 24
                    visible: usage.ready && usage.limits.length === 0
                    text: qsTr("Anthropic reports no usage limits for this account right now.")
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    muted: true
                }

                // Each limit: its name and how much of it is used, a bar, and when it resets
                ColumnLayout {
                    objectName: "limits"
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 14
                    Layout.bottomMargin: 16
                    visible: usage.limits.length > 0
                    spacing: 16

                    Repeater {
                        model: usage.limits

                        delegate: ColumnLayout {
                            id: limit

                            required property var modelData

                            Layout.fillWidth: true
                            spacing: 6
                            Accessible.role: Accessible.StaticText
                            Accessible.name: qsTr("%1: %2% used, resets in %3").arg(modelData.name).arg(modelData.value)
                                .arg(modelData.resetIn)

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Label {
                                    Layout.fillWidth: true
                                    text: limit.modelData.name
                                    font.pixelSize: 14
                                }

                                Label {
                                    text: qsTr("%1%").arg(limit.modelData.value)
                                    color: limit.modelData.level === "low" ? popup.ink : claude.levelColor(limit.modelData.level)
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                }
                            }

                            Meter {
                                Layout.fillWidth: true
                                part: limit.modelData.percent / 100
                                fill: claude.levelColor(limit.modelData.level)
                            }

                            Label {
                                Layout.fillWidth: true
                                visible: limit.modelData.resetIn !== ""
                                text: qsTr("Resets in %1 · %2").arg(limit.modelData.resetIn).arg(limit.modelData.resetOn)
                                muted: true
                                font.pixelSize: 12
                            }
                        }
                    }
                }

                Divider { visible: tokensPart.visible }

                // The tokens Claude Code used here in a period: the total, how it splits, a graph and the models
                ColumnLayout {
                    id: tokensPart

                    objectName: "tokens"
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 10
                    Layout.bottomMargin: 16
                    visible: claude.tokenHistory && popup.tokens !== null
                    spacing: 10

                    // Which period, marked as Windows marks the chosen view: bold, with a short accent bar under it
                    // In a box of its own, so a long translation is cut off at the edge instead of widening the popup
                    Item {
                        Layout.fillWidth: true
                        implicitHeight: 24
                        clip: true

                        Row {
                            spacing: 16

                            Repeater {
                                model: [["session", qsTr("Session")], ["today", qsTr("Today")], ["week", qsTr("Week")],
                                    ["month", qsTr("Month")], ["year", qsTr("Year")]]

                                delegate: Item {
                                    id: periodItem

                                    required property var modelData
                                    readonly property bool chosen: popup.period === modelData[0]

                                    width: periodText.implicitWidth
                                    height: 24
                                    Accessible.role: Accessible.RadioButton
                                    Accessible.name: modelData[1]
                                    Accessible.checked: chosen
                                    Accessible.onPressAction: popup.period = modelData[0]

                                    Label {
                                        id: periodText

                                        text: periodItem.modelData[1]
                                        color: periodItem.chosen || periodArea.containsMouse ? popup.ink : popup.secondary
                                        font.weight: periodItem.chosen ? Font.DemiBold : Font.Normal
                                    }

                                    Rectangle {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        anchors.bottom: parent.bottom
                                        width: 16
                                        height: 3
                                        radius: 1.5
                                        visible: periodItem.chosen
                                        color: claude.accentColor
                                    }

                                    MouseArea {
                                        id: periodArea

                                        anchors.fill: parent
                                        anchors.margins: -4
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: popup.period = periodItem.modelData[0]
                                    }
                                }
                            }
                        }
                    }

                    Row {
                        spacing: 6

                        Label {
                            objectName: "tokenTotal"
                            anchors.baseline: tokensWord.baseline
                            text: Number(popup.tokens?.total ?? 0).toLocaleString(Qt.locale(), "f", 0)
                            font.pixelSize: 20
                            font.weight: Font.DemiBold
                        }

                        Label {
                            id: tokensWord

                            y: 7
                            text: qsTr("tokens")
                            muted: true
                        }
                    }

                    // The tokens split by kind, as Anthropic counts them
                    Label {
                        readonly property var kinds: popup.tokens?.kinds ?? ({})

                        Layout.fillWidth: true
                        text: qsTr("Input %1 · Output %2 · Cache write %3 · Cache read %4")
                            .arg(claude.compact(kinds.input)).arg(claude.compact(kinds.output))
                            .arg(claude.compact(kinds.cacheCreation)).arg(claude.compact(kinds.cacheRead))
                        muted: true
                        font.pixelSize: 12
                    }

                    // The tokens per hour, day or month across the period
                    Item {
                        id: graph

                        readonly property var series: popup.tokens?.series ?? []
                        readonly property real most: Math.max(1, ...series)

                        objectName: "graph"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 48
                        visible: series.length > 0

                        Rectangle {
                            anchors.bottom: parent.bottom
                            width: parent.width
                            height: 1
                            color: popup.line
                        }

                        Row {
                            id: bars

                            anchors.fill: parent
                            spacing: graph.series.length > 40 ? 1 : 2

                            Repeater {
                                model: graph.series

                                // A bar as tall as its tokens against the period's most, and never too short to see
                                delegate: Rectangle {
                                    required property var modelData

                                    anchors.bottom: parent?.bottom
                                    width: (bars.width - bars.spacing * (graph.series.length - 1)) / graph.series.length
                                    height: modelData > 0 ? Math.max(2, bars.height * modelData / graph.most) : 0
                                    radius: Math.min(2, width / 2)
                                    color: Qt.alpha(claude.accentColor, 0.75)
                                }
                            }
                        }
                    }

                    // The models that used the most tokens in the period
                    ColumnLayout {
                        objectName: "models"
                        Layout.fillWidth: true
                        visible: (popup.tokens?.models ?? []).length > 0
                        spacing: 8

                        Repeater {
                            model: (popup.tokens?.models ?? []).slice(0, 5)

                            delegate: ColumnLayout {
                                id: modelRow

                                required property var modelData

                                Layout.fillWidth: true
                                spacing: 4

                                RowLayout {
                                    Layout.fillWidth: true

                                    Label {
                                        Layout.fillWidth: true
                                        text: modelRow.modelData.name
                                    }

                                    Label {
                                        text: Number(modelRow.modelData.tokens).toLocaleString(Qt.locale(), "f", 0)
                                        muted: true
                                        font.pixelSize: 12
                                    }
                                }

                                Meter {
                                    Layout.fillWidth: true
                                    implicitHeight: 3
                                    part: modelRow.modelData.tokens / Math.max(1, popup.tokens?.total ?? 1)
                                    fill: Qt.alpha(claude.accentColor, 0.75)
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
                    color: Qt.alpha("#000000", claude.dark ? 0.15 : 0.03)

                    Divider { width: parent.width }

                    Link {
                        objectName: "usagePage"
                        x: 16
                        anchors.verticalCenter: parent.verticalCenter
                        // Cut short before it reaches the time
                        width: Math.min(implicitWidth, parent.width - 48 - (updatedLabel.visible ? updatedLabel.implicitWidth : 0))
                        elide: Text.ElideRight
                        text: qsTr("Usage on claude.ai")
                        onClicked: {
                            Qt.openUrlExternally("https://claude.ai/settings/usage")
                            popup.close()
                        }
                    }

                    Label {
                        id: updatedLabel

                        objectName: "updated"
                        anchors.right: parent.right
                        anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        visible: claude.updated !== ""
                        text: qsTr("Updated %1").arg(claude.updated)
                        muted: true
                        font.pixelSize: 12
                    }
                }
            }
        }
    }
}
