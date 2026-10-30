import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb

Text {
    id: clock

    property string format: "HH:mm"
    property string alternateFormat: "ddd d MMM yyyy  HH:mm"
    property string locale: ""
    property var timeZones: []
    property bool showWeekNumbers: false
    property Item bar: null

    property bool showAlternate: false
    property int timeZoneIndex: 0

    readonly property string activeFormat: showAlternate ? alternateFormat : format
    readonly property string timeZone: timeZones.length > 0 ? timeZones[timeZoneIndex % timeZones.length] : ""
    readonly property bool dark: Qt.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property string barEdge: bar?.edge ?? "top"

    // Milliseconds until the shown text changes next, so the clock turns over with the real time
    function nextTick(): int {
        const time = new Date()
        if (activeFormat.includes("s"))
            return 1000 - time.getMilliseconds()
        return 60000 - time.getSeconds() * 1000 - time.getMilliseconds()
    }

    function refresh() {
        text = zones.format(timeZone, activeFormat, locale)
        tick.interval = nextTick()
        tick.restart()
    }

    function toggleFormat() {
        showAlternate = !showAlternate
    }

    function nextTimeZone() {
        if (timeZones.length > 1)
            timeZoneIndex = (timeZoneIndex + 1) % timeZones.length
    }

    function toggleCalendar() {
        if (calendar.visible) {
            calendar.close()
            return
        }
        const [year, month, day] = zones.format(timeZone, "yyyy-M-d", "C").split("-").map(Number)
        calendar.today = new Date(year, month - 1, day)
        calendar.open()
    }

    color: bar ? bar.textColor : dark ? "white" : "black"
    font.family: bar ? bar.font.family : Qt.application.font.family
    font.pixelSize: bar ? bar.font.pixelSize : 13
    font.variableAxes: bar ? bar.font.variableAxes : 400
    verticalAlignment: Text.AlignVCenter

    Component.onCompleted: refresh()
    onActiveFormatChanged: refresh()
    onTimeZoneChanged: refresh()
    onLocaleChanged: refresh()

    TimeZones {
        id: zones
    }

    Timer {
        id: tick

        onTriggered: clock.refresh()
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

    Popup {
        id: calendar

        property date today: new Date()
        property int month: today.getMonth()
        property int year: today.getFullYear()

        readonly property color textColor: clock.dark ? "white" : "black"
        readonly property color accent: "#0a84ff"

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
        popupType: Popup.Window
        padding: 12
        locale: clock.locale ? Qt.locale(clock.locale) : Qt.locale()
        x: clock.barEdge === "left" ? clock.width + 8
            : clock.barEdge === "right" ? -width - 8
            : Math.round((clock.width - width) / 2)
        y: clock.barEdge === "top" ? clock.height + 8
            : clock.barEdge === "bottom" ? -height - 8
            : Math.round((clock.height - height) / 2)

        onAboutToShow: {
            month = today.getMonth()
            year = today.getFullYear()
        }

        background: Rectangle {
            color: clock.dark ? "#f21e1e1e" : "#f2f3f3f3"
            radius: 8
            border.width: 1
            border.color: clock.dark ? "#33ffffff" : "#22000000"
        }

        contentItem: ColumnLayout {
            spacing: 8

            RowLayout {
                Text {
                    objectName: "title"
                    Layout.fillWidth: true
                    text: `${calendar.locale.standaloneMonthName(calendar.month)} ${calendar.year}`
                    color: calendar.textColor
                    font.pixelSize: 14
                    font.bold: true
                }

                Repeater {
                    model: [{ label: "<", offset: -1 }, { label: ">", offset: 1 }]

                    delegate: Text {
                        required property var modelData

                        text: modelData.label
                        color: calendar.textColor
                        font.pixelSize: 18
                        leftPadding: 8
                        rightPadding: 8

                        MouseArea {
                            anchors.fill: parent
                            onClicked: calendar.showMonth(parent.modelData.offset)
                        }
                    }
                }
            }

            GridLayout {
                columns: clock.showWeekNumbers ? 2 : 1
                columnSpacing: 4
                rowSpacing: 4

                Item {
                    visible: clock.showWeekNumbers
                }

                DayOfWeekRow {
                    Layout.fillWidth: true
                    locale: calendar.locale

                    delegate: Text {
                        required property string shortName

                        text: shortName
                        color: calendar.textColor
                        opacity: 0.6
                        font.pixelSize: 11
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                WeekNumberColumn {
                    visible: clock.showWeekNumbers
                    Layout.fillHeight: true
                    month: calendar.month
                    year: calendar.year
                    locale: calendar.locale

                    delegate: Text {
                        required property int weekNumber

                        text: weekNumber
                        color: calendar.textColor
                        opacity: 0.5
                        font.pixelSize: 11
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
                        color: today ? "white" : calendar.textColor
                        opacity: model.month === grid.month ? 1 : 0.35
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter

                        Rectangle {
                            anchors.centerIn: parent
                            width: 26
                            height: 26
                            radius: 13
                            color: calendar.accent
                            visible: day.today
                            z: -1
                        }
                    }
                }
            }
        }
    }
}
