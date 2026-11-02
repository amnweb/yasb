import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Common

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
    readonly property string edge: bar?.edge ?? "top"

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
        calendar.month = calendar.today.getMonth()
        calendar.year = calendar.today.getFullYear()
        placePopup()
        calendar.open()
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        let px = edge === "left" ? start.x + width + 6
            : edge === "right" ? start.x - calendar.width - 6 : start.x + (width - calendar.width) / 2
        let py = edge === "top" ? start.y + height + 6
            : edge === "bottom" ? start.y - calendar.height - 6 : start.y + (height - calendar.height) / 2
        const screen = clock.Screen
        px = Math.max(screen.virtualX + 8, Math.min(px, screen.virtualX + screen.width - calendar.width - 8))
        py = Math.max(screen.virtualY + 8, Math.min(py, screen.virtualY + screen.desktopAvailableHeight - calendar.height - 8))
        calendar.x = Math.round(px)
        calendar.y = Math.round(py)
    }

    // The bar's colour and font, each part unless the widget file sets it
    color: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    font.family: bar?.font.family ?? Qt.application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})
    verticalAlignment: Text.AlignVCenter

    Component.onCompleted: refresh()
    onActiveFormatChanged: refresh()
    onTimeZoneChanged: refresh()
    onLocaleChanged: refresh()
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

        readonly property color textColor: clock.dark ? "#ffffff" : "#000000"
        readonly property color accent: "#0a84ff"
        readonly property var locale: clock.locale ? Qt.locale(clock.locale) : Qt.locale()

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
        width: content.implicitWidth + 48
        height: content.implicitHeight + 40
        anchor: clock
        backdropItem: surface
        enter: NumberAnimation { target: calendar; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: calendar; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: { if (!visible) reveal = 0 }

        Rectangle {
            id: surface
            anchors.fill: parent
            anchors.margins: 8
            radius: 8
            color: clock.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: clock.dark ? Qt.alpha("#3A3A3A", 1) : Qt.alpha("#D9D9D9", 1)
            opacity: calendar.reveal
            scale: 0.85 + calendar.reveal * 0.15
            transformOrigin: clock.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: content
                x: 16
                y: 12
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
                            color: today ? "#ffffff" : calendar.textColor
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
}
