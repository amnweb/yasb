pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Label {
    id: clock

    component Settings: QtObject {
        required property Theme theme

        property string format: "HH:mm"
        property string alternateFormat: "ddd d MMM yyyy  HH:mm"
        property string locale: ""
        property var timeZones: []
        property bool showWeekNumbers: false
        // The clock's text takes the bar's font, each part unless set here
        property font font
        property color accentColor: theme.colors.accent
        // Today's number in the calendar, on the accent colour
        property color todayTextColor: theme.colors.textOnAccent
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
        property font popupTitleFont
        popupTitleFont.family: theme.popup.font.family
        popupTitleFont.pixelSize: 16
        popupTitleFont.weight: 600
        // The arrows that change the month, the weekday names and the week numbers
        property font arrowFont
        arrowFont.family: theme.popup.font.family
        arrowFont.pixelSize: 18
        property font weekdayFont
        weekdayFont.family: theme.popup.font.family
        weekdayFont.pixelSize: 11
        property font weekNumberFont
        weekNumberFont.family: theme.popup.font.family
        weekNumberFont.pixelSize: 11
        property color popupDividerColor: theme.colors.divider
    }

    required property BarBase bar
    readonly property Theme theme: bar.theme
    readonly property Settings settings: Settings {
        theme: clock.theme
        onLocaleChanged: clock.refresh()
    }

    property bool showAlternate: false
    property int timeZoneIndex: 0

    readonly property string activeFormat: showAlternate ? settings.alternateFormat : settings.format
    readonly property string timeZone: settings.timeZones.length > 0
        ? settings.timeZones[timeZoneIndex % settings.timeZones.length] : ""
    readonly property bool dark: theme.dark
    readonly property string edge: bar.edge

    function nextTick(): int {
        const time = new Date()
        if (activeFormat.includes("s"))
            return 1000 - time.getMilliseconds()
        return 60000 - time.getSeconds() * 1000 - time.getMilliseconds()
    }

    function refresh() {
        text = zones.format(timeZone, activeFormat, settings.locale)
        tick.interval = nextTick()
        tick.restart()
    }

    function toggleFormat() {
        showAlternate = !showAlternate
    }

    function nextTimeZone() {
        if (settings.timeZones.length > 1)
            timeZoneIndex = (timeZoneIndex + 1) % settings.timeZones.length
    }

    function toggleCalendar() {
        if (calendar.visible) {
            calendar.close()
            return
        }
        const [year, month, day] = zones.format(timeZone, "yyyy-M-d", "C").split("-").map(Number)
        calendar.today = new Date(year, month - 1, day)
        calendar.month = calendar.today.getMonth()
        calendar.year = calendar.today.getFullYear()
        placePopup()
        calendar.open()
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + settings.popupGap
            : edge === "right" ? start.x - calendar.width - settings.popupGap : start.x + (width - calendar.width) / 2
        let py = edge === "top" ? start.y + height + settings.popupGap
            : edge === "bottom" ? start.y - calendar.height - settings.popupGap : start.y + (height - calendar.height) / 2
        const screen = clock.Screen
        px = Math.max(screen.virtualX + 8, Math.min(px, screen.virtualX + screen.width - calendar.width - 8))
        py = Math.max(screen.virtualY + 8, Math.min(py, screen.virtualY + screen.desktopAvailableHeight - calendar.height - 8))
        calendar.x = Math.round(px)
        calendar.y = Math.round(py)
    }

    // The theme's text colour, and the bar's font with the parts settings.font sets
    color: clock.settings.popupTextColor
    font: clock.settings.font
    verticalAlignment: Text.AlignVCenter

    Component.onCompleted: refresh()
    onActiveFormatChanged: refresh()
    onTimeZoneChanged: refresh()
    Component.onDestruction: calendar.hide()

    TimeZones {
        id: zones
    }

    Timer {
        id: tick

        onTriggered: clock.refresh()
    }

    Connections {
        target: clock.Window.window
        function onVisibleChanged() {
            if (!clock.Window.window?.visible)
                calendar.hide()
        }
        function onXChanged() { if (calendar.visible) clock.placePopup() }
        function onYChanged() { if (calendar.visible) clock.placePopup() }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton)
                clock.toggleCalendar()
            else if (mouse.button === Qt.MiddleButton)
                clock.nextTimeZone()
            else
                clock.toggleFormat()
        }
    }

    BackdropPopup {
        id: calendar
        property real reveal: 0
        property date today: new Date()
        property int month: today.getMonth()
        property int year: today.getFullYear()

        readonly property var locale: clock.settings.locale ? Qt.locale(clock.settings.locale) : Qt.locale()

        function showMonth(offset: int) {
            const shown = new Date(year, month + offset, 1)
            month = shown.getMonth()
            year = shown.getFullYear()
        }

        function isToday(date: date): bool {
            return date.getFullYear() === today.getFullYear()
                && date.getMonth() === today.getMonth()
                && date.getDate() === today.getDate()
        }

        objectName: "calendar"
        title: "Calendar"
        width: popupContent.implicitWidth + 32
        height: popupContent.implicitHeight + 24
        anchor: clock
        font: clock.settings.popupFont
        theme: clock.theme
        backdropItem: surface
        enter: NumberAnimation { target: calendar; property: "reveal"; to: 1; duration: clock.settings.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: calendar; property: "reveal"; to: 0; duration: clock.settings.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            radius: clock.settings.popupRadius
            color: clock.settings.popupColor
            border.width: 1
            border.color: clock.settings.popupBorderColor
            opacity: calendar.reveal
            scale: 0.85 + calendar.reveal * 0.15
            transformOrigin: clock.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: popupContent
                x: 16
                y: 12
                spacing: 8

                RowLayout {
                    Text {
                        objectName: "title"
                        Layout.fillWidth: true
                        text: `${calendar.locale.standaloneMonthName(calendar.month)} ${calendar.year}`
                        font: clock.settings.popupTitleFont
                        color: clock.settings.popupTextColor
                    }

                    Repeater {
                        model: [{ label: "<", offset: -1 }, { label: ">", offset: 1 }]

                        delegate: Text {
                            required property var modelData

                            text: modelData.label
                            color: clock.settings.popupTextColor
                            font: clock.settings.arrowFont
                            leftPadding: 8
                            rightPadding: 8

                            MouseArea {
                                anchors.fill: parent
                                onClicked: calendar.showMonth(parent.modelData.offset)
                            }
                        }
                    }
                }

                // The header's bottom line, across the whole calendar
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: -16
                    Layout.rightMargin: -16
                    Layout.topMargin: 2
                    implicitHeight: 1
                    color: clock.settings.popupDividerColor
                }

                GridLayout {
                    columns: clock.settings.showWeekNumbers ? 2 : 1
                    columnSpacing: 4
                    rowSpacing: 4

                    Item {
                        visible: clock.settings.showWeekNumbers
                    }

                    DayOfWeekRow {
                        Layout.fillWidth: true
                        locale: calendar.locale

                        delegate: Text {
                            required property string shortName

                            text: shortName
                            color: clock.settings.popupTextColor
                            opacity: 0.6
                            font: clock.settings.weekdayFont
                            horizontalAlignment: Text.AlignHCenter
                        }
                    }

                    WeekNumberColumn {
                        visible: clock.settings.showWeekNumbers
                        Layout.fillHeight: true
                        month: calendar.month
                        year: calendar.year
                        locale: calendar.locale

                        delegate: Text {
                            required property int weekNumber

                            text: weekNumber
                            color: clock.settings.popupTextColor
                            opacity: 0.5
                            font: clock.settings.weekNumberFont
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    MonthGrid {
                        id: grid

                        Layout.preferredWidth: 7 * 34
                        Layout.preferredHeight: 6 * 30
                        month: calendar.month
                        year: calendar.year
                        locale: calendar.locale

                        delegate: Text {
                            id: day

                            required property var model
                            readonly property bool today: calendar.isToday(model.date)

                            text: model.day
                            color: today ? clock.settings.todayTextColor : clock.settings.popupTextColor
                            opacity: model.month === grid.month ? 1 : 0.35
                            font: clock.settings.popupSmallFont
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter

                            Rectangle {
                                anchors.centerIn: parent
                                width: 26
                                height: 26
                                radius: 13
                                color: clock.settings.accentColor
                                visible: day.today
                                z: -1
                            }
                        }
                    }
                }
            }
        }
    }
}
