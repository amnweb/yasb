pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl
import QtQuick.Layouts
import QtQuick.Shapes
import Yasb
import Yasb.Common

Item {
    id: weather

    property Item bar: null
    // Widgets with the same id show the same saved place; give a widget its own id for another place
    property string locationId: "weather"
    // metric or imperial
    property string units: "metric"
    // Days in the popup, 1 to 14
    property int forecastDays: 7
    // How often the forecast is fetched, in milliseconds, from 60000 to 86400000
    property int updateInterval: 3600000
    // Whether temperatures are rounded to whole degrees
    property bool hideDecimal: false
    // 24h or 12h
    property string timeFormat: "24h"
    // Label placeholders: {temp}, {feelslike}, {min_temp}, {max_temp}, {humidity}, {pressure}, {precipitation},
    // {precipitation_probability}, {rain_chance}, {snow_chance}, {wind}, {wind_dir}, {cloud}, {uv}, {location},
    // {condition_text}, {is_day}, {sunrise} and {sunset}; empty shows only the picture
    property string label: "{temp}"
    property string alternateLabel: "{location}: Min {min_temp}, Max {max_temp}"
    property string noLocationLabel: qsTr("Set location")
    // The place, the sky and today's temperatures when the pointer rests on the widget
    property bool tooltip: true
    // The picture, or glyph, in front of the label
    property bool showIcon: true
    property int iconSize: 18
    // The picture for each condition; a widget file can point any of them at its own SVG or PNG
    property var pictures: ({
        sunnyDay: Qt.resolvedUrl("icons/sunny-day.svg"),
        clearNight: Qt.resolvedUrl("icons/clear-night.svg"),
        cloudyDay: Qt.resolvedUrl("icons/cloudy-day.svg"),
        cloudyNight: Qt.resolvedUrl("icons/cloudy-night.svg"),
        foggyDay: Qt.resolvedUrl("icons/foggy.svg"),
        foggyNight: Qt.resolvedUrl("icons/foggy.svg"),
        drizzleDay: Qt.resolvedUrl("icons/drizzle.svg"),
        drizzleNight: Qt.resolvedUrl("icons/drizzle.svg"),
        rainyDay: Qt.resolvedUrl("icons/rainy-day.svg"),
        rainyNight: Qt.resolvedUrl("icons/rainy-night.svg"),
        snowyDay: Qt.resolvedUrl("icons/snowy.svg"),
        snowyNight: Qt.resolvedUrl("icons/snowy.svg"),
        thunderstormDay: Qt.resolvedUrl("icons/thunderstorm.svg"),
        thunderstormNight: Qt.resolvedUrl("icons/thunderstorm.svg"),
        default: Qt.resolvedUrl("icons/sunny-day.svg")
    })
    // Glyphs drawn in iconFont on the bar instead of the pictures, by the same conditions,
    // such as ({ sunnyDay: "\ue30d", clearNight: "\ue32b", rainyDay: "\ue308", default: "\ue30d" })
    property var glyphs: ({})
    // Hotkey that opens the popup, such as "alt+shift+w"
    property string keys: ""
    property int popupWidth: 440
    // Popup alignment relative to the widget on a horizontal bar: left, right or center
    property string popupAlignment: "center"
    property bool showHourly: true
    // The narrowest an hour gets; the hours share out the rest of the width
    property int hourWidth: 54
    // Scroll the days when they exceed this height
    property int maxListHeight: 320
    // The days' temperature bars run from cold to warm across the week's coldest and warmest; the hourly graph is cold
    property color coldColor: dark ? "#2F7CF6" : "#0B3F9E"
    property color warmColor: dark ? "#8BE0FF" : "#3AA0F0"
    // Chances of rain and snow
    property color rainColor: Qt.alpha(dark ? "#ffffff" : "#000000", 0.544)
    property color errorColor: dark ? "#ff99a4" : "#c42b1c"

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

    readonly property var values: forecast.values
    readonly property string glyph: glyphs[forecast.condition] ?? glyphs["default"] ?? ""
    readonly property string text: forecast.hasLocation ? format(showAlternate ? alternateLabel : label) : noLocationLabel
    // When the forecast was fetched: the time today, the day and time before
    readonly property string updated: {
        const at = forecast.updated
        if (!(at instanceof Date) || isNaN(at))
            return ""
        const time = Qt.formatTime(at, timeFormat === "12h" ? "h:mm AP" : "HH:mm")
        return at.toDateString() === new Date().toDateString() ? time
            : `${Qt.locale().dayName(at.getDay(), Locale.ShortFormat)} ${time}`
    }

    function format(template: string): string {
        return template.replace(/\{(\w+)\}/g, (match, key) => weather.values[key] ?? match)
    }

    // A chance of rain or snow, empty when Open-Meteo has none
    function chance(value: var): string {
        return Number.isFinite(value) ? `${Math.round(value)}%` : ""
    }

    // A temperature as the popup shows it, without its unit: 12° or 12.4°
    function degrees(value: var): string {
        return Number.isFinite(value) ? `${hideDecimal ? Math.round(value) : value}°` : "--"
    }

    // A temperature in whole degrees, for the hours and days: 12°
    function whole(value: var): string {
        return Number.isFinite(value) ? `${Math.round(value)}°` : "--"
    }

    function picture(condition: string): url {
        return pictures[condition] ?? pictures["default"] ?? ""
    }

    function dayName(index: int, weekday: int, format: int): string {
        return index === 0 ? qsTr("Today") : Qt.locale().dayName(weekday, format)
    }

    // An SVG path through the points, curving without overshooting them
    function spline(points: var): string {
        if (points.length < 2)
            return ""
        let path = `M ${points[0].x} ${points[0].y}`
        const last = points.length - 1
        for (let index = 0; index < last; ++index) {
            const p0 = points[Math.max(0, index - 1)]
            const p1 = points[index]
            const p2 = points[index + 1]
            const p3 = points[Math.min(last, index + 2)]
            const low = Math.min(p1.y, p2.y)
            const high = Math.max(p1.y, p2.y)
            const y1 = Math.max(low, Math.min(p1.y + (p2.y - p0.y) * 0.2, high))
            const y2 = Math.max(low, Math.min(p2.y - (p3.y - p1.y) * 0.2, high))
            path += ` C ${p1.x + (p2.x - p0.x) * 0.2} ${y1} ${p2.x - (p3.x - p1.x) * 0.2} ${y2} ${p2.x} ${p2.y}`
        }
        return path
    }

    // A colour from coldColor at 0 to warmColor at 1, through the hues between them
    function warmth(position: real): color {
        const mix = (from, to) => from + (to - from) * position
        return Qt.hsla(mix(coldColor.hslHue, warmColor.hslHue), mix(coldColor.hslSaturation, warmColor.hslSaturation),
            mix(coldColor.hslLightness, warmColor.hslLightness), 1)
    }

    function placePopup() {
        const start = mapToGlobal(0, 0)
        const gap = 6
        const margin = 8
        const screen = weather.Screen
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
        popup.day = 0
        popup.choosing = false
        hourlyFlick.contentX = 0
        dayList.contentY = 0
        placePopup()
        popup.open()
        if (popup.picking)
            chooseLocation()
    }

    function chooseLocation() {
        popup.choosing = true
        field.text = ""
        Qt.callLater(() => field.forceActiveFocus())
    }

    function pick(place: var) {
        forecast.setLocation(place)
        popup.choosing = false
        popup.day = 0
    }

    implicitWidth: row.implicitWidth
    implicitHeight: row.implicitHeight
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: !forecast.hasLocation ? qsTr("Weather, no location set")
        : forecast.ready ? qsTr("Weather in %1, %2, %3").arg(values.location).arg(values.temp).arg(values.condition_text)
        : qsTr("Weather in %1").arg(values.location)
    Accessible.onPressAction: togglePopup()
    Keys.onReturnPressed: togglePopup()
    Keys.onSpacePressed: togglePopup()

    Component.onDestruction: popup.hide()

    WeatherForecast {
        id: forecast

        locationId: weather.locationId
        units: weather.units
        forecastDays: weather.forecastDays
        updateInterval: weather.updateInterval
        hideDecimal: weather.hideDecimal
        timeFormat: weather.timeFormat
    }

    Hotkey {
        keys: weather.keys
        onActivated: weather.togglePopup()
    }

    Connections {
        target: weather.Window.window

        function onVisibleChanged() {
            if (!weather.Window.window?.visible)
                popup.hide()
        }

        function onXChanged() {
            if (popup.visible)
                weather.placePopup()
        }

        function onYChanged() {
            if (popup.visible)
                weather.placePopup()
        }
    }

    // Keep the popup anchored when its height changes
    Connections {
        target: popup

        function onHeightChanged() {
            if (popup.visible)
                weather.placePopup()
        }
    }

    component Glyph: Text {
        textFormat: Text.PlainText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.family: weather.iconFont.family
        font.weight: weather.iconFont.weight
    }

    component Picture: Image {
        property string condition

        source: weather.picture(condition)
        sourceSize: Qt.size(width, height)
        fillMode: Image.PreserveAspectFit
    }

    // A chance of rain or snow behind a drop
    component Chance: Row {
        id: chanceRow

        property var value

        spacing: 2
        visible: Number.isFinite(value)

        IconImage {
            anchors.verticalCenter: parent.verticalCenter
            width: 9
            height: 9
            sourceSize: Qt.size(width, height)
            source: Qt.resolvedUrl("icons/drop.svg")
            color: weather.rainColor
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: weather.chance(chanceRow.value)
            color: weather.rainColor
            font.pixelSize: 12
        }
    }

    // Text in the popup: plain, in its ink or muted colour, cut short with an ellipsis
    component Label: Text {
        property bool muted: false

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

    // A card in WinUI's card colours, on the popup's 16px edge
    component Card: Rectangle {
        Layout.fillWidth: true
        Layout.leftMargin: 16
        Layout.rightMargin: 16
        radius: 8
        color: weather.dark ? Qt.alpha("#ffffff", 0.0512) : Qt.alpha("#ffffff", 0.7)
        border.width: 1
        border.color: Qt.alpha("#000000", weather.dark ? 0.1 : 0.0578)
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
        spacing: 6

        Picture {
            objectName: "picture"
            y: Math.round((parent.height - height) / 2)
            width: weather.iconSize
            height: weather.iconSize
            visible: weather.showIcon && weather.glyph === ""
            condition: forecast.condition
            opacity: forecast.ready ? 1 : 0.55
        }

        Glyph {
            objectName: "glyph"
            y: Math.round((parent.height - height) / 2)
            width: weather.iconSize
            height: weather.iconSize
            visible: weather.showIcon && weather.glyph !== ""
            text: weather.glyph
            color: weather.textColor
            opacity: forecast.ready ? 1 : 0.55
            font.pixelSize: weather.iconSize
        }

        Text {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: weather.text
            textFormat: Text.PlainText
            color: weather.textColor
            font: weather.font
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
                weather.togglePopup()
            else
                weather.showAlternate = !weather.showAlternate
        }
    }

    ToolTip {
        objectName: "tooltip"
        popupType: Popup.Window
        visible: weather.tooltip && area.containsMouse && !popup.visible
        delay: 400
        text: !forecast.hasLocation ? qsTr("Choose a location for the forecast")
            : forecast.ready ? [weather.values.location, weather.values.condition_text,
                qsTr("Min %1 / Max %2").arg(weather.values.min_temp).arg(weather.values.max_temp)].join("\n")
            : forecast.error || qsTr("Fetching the forecast...")
        // Away from the bar's edge
        y: weather.edge === "bottom" ? -implicitHeight - 6 : weather.height + 6
    }

    BackdropPopup {
        id: popup

        property real reveal: 0
        // The day whose hours the graph shows
        property int day: 0
        // While a new place is being searched for
        property bool choosing: false
        readonly property bool picking: choosing || !forecast.hasLocation
        readonly property color ink: weather.dark ? "#ffffff" : "#000000"
        // Supporting text, and labels, times and other text to read last
        readonly property color secondary: Qt.alpha(ink, 0.786)
        readonly property color muted: Qt.alpha(ink, 0.544)
        // The lines between the parts
        readonly property color line: Qt.alpha(ink, 0.08)
        readonly property string error: picking ? forecast.searchError : forecast.error
        readonly property var today: forecast.days[0] ?? ({})
        // Name and value of each reading
        readonly property var readings: [
            [qsTr("Humidity"), weather.values.humidity],
            [qsTr("Wind"), weather.values.wind],
            [qsTr("Rain"), weather.values.precipitation_probability],
            [qsTr("Sunrise"), today.sunriseText ?? "--"],
            [qsTr("Sunset"), today.sunsetText ?? "--"]
        ]

        objectName: "popup"
        title: qsTr("Weather")
        width: weather.popupWidth
        // Never taller than the screen; the days scroll instead
        height: Math.min(popupContent.implicitHeight + 16, weather.Screen.desktopAvailableHeight - 24)
        anchor: weather
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: 140; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible)
                reveal = 0
        }
        onDayChanged: hourlyFlick.contentX = 0

        Rectangle {
            id: surface

            anchors.fill: parent
            anchors.margins: 8
            radius: 8
            color: weather.dark ? Qt.alpha("#202020", 0.85) : Qt.alpha("#F3F3F3", 0.85)
            border.width: 1
            border.color: weather.dark ? "#3A3A3A" : "#D9D9D9"
            opacity: popup.reveal
            scale: 0.85 + popup.reveal * 0.15
            transformOrigin: weather.edge === "bottom" ? Item.Bottom : Item.Top

            ColumnLayout {
                id: popupContent

                anchors.fill: parent
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

                        Label {
                            width: parent.width
                            text: popup.picking ? qsTr("Choose a location") : forecast.location.name ?? ""
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }

                        Label {
                            width: parent.width
                            visible: !popup.picking && text !== ""
                            text: forecast.location.region ?? ""
                            muted: true
                            font.pixelSize: 12
                        }
                    }

                    Item {
                        objectName: "refresh"
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        visible: !popup.picking
                        enabled: !forecast.loading
                        opacity: enabled ? 1 : 0.4
                        Accessible.role: Accessible.Button
                        Accessible.name: qsTr("Refresh")
                        Accessible.onPressAction: forecast.refresh()
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
                            onClicked: forecast.refresh()
                        }
                    }
                }

                // The header's bottom line, which the loading bar runs along
                LoadingLine {
                    Layout.fillWidth: true
                    running: popup.picking ? forecast.searching : forecast.loading
                    trackColor: popup.line
                }

                Label {
                    objectName: "error"
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    Layout.topMargin: 6
                    visible: popup.error !== ""
                    text: popup.error
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    color: weather.errorColor
                    font.pixelSize: 12
                }

                Label {
                    objectName: "placeholder"
                    Layout.fillWidth: true
                    Layout.topMargin: 24
                    Layout.bottomMargin: 24
                    visible: !popup.picking && !forecast.ready
                    text: forecast.loading ? qsTr("Fetching the forecast...") : qsTr("The forecast is not available")
                    horizontalAlignment: Text.AlignHCenter
                    muted: true
                }

                ColumnLayout {
                    objectName: "forecast"
                    Layout.fillWidth: true
                    // Gives way on a short screen, through the day list
                    Layout.fillHeight: true
                    visible: !popup.picking && forecast.ready
                    spacing: 0

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: 16
                        Layout.rightMargin: 16
                        Layout.topMargin: 12
                        Layout.bottomMargin: 14
                        spacing: 14

                        Picture {
                            Layout.preferredWidth: 52
                            Layout.preferredHeight: 52
                            condition: forecast.condition
                        }

                        Label {
                            objectName: "temperature"
                            text: weather.degrees(forecast.current.temperature)
                            font.pixelSize: 48
                            font.weight: Font.Light
                        }

                        Column {
                            Layout.fillWidth: true
                            spacing: 2

                            Label {
                                width: parent.width
                                text: weather.values.condition_text
                                font.pixelSize: 14
                            }

                            Label {
                                width: parent.width
                                text: qsTr("High %1 · Low %2 · Feels %3").arg(weather.whole(popup.today.high))
                                    .arg(weather.whole(popup.today.low)).arg(weather.whole(forecast.current.feelsLike))
                                color: popup.secondary
                                font.pixelSize: 12
                            }
                        }
                    }

                    // The readings, each value above its name
                    Card {
                        implicitHeight: readingRow.implicitHeight + 20

                        RowLayout {
                            id: readingRow

                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 4
                            uniformCellSizes: true

                            Repeater {
                                model: popup.readings

                                delegate: Column {
                                    id: reading

                                    required property var modelData

                                    Layout.fillWidth: true
                                    spacing: 2
                                    Accessible.role: Accessible.StaticText
                                    Accessible.name: `${modelData[0]}: ${modelData[1]}`

                                    Label {
                                        width: parent.width
                                        horizontalAlignment: Text.AlignHCenter
                                        text: reading.modelData[1]
                                        font.pixelSize: 14
                                        font.weight: Font.DemiBold
                                    }

                                    Label {
                                        width: parent.width
                                        horizontalAlignment: Text.AlignHCenter
                                        text: reading.modelData[0]
                                        muted: true
                                        font.pixelSize: 12
                                    }
                                }
                            }
                        }
                    }

                    Flickable {
                        id: dayList

                        // The coldest and warmest of the days, which every bar is measured against
                        readonly property real low: Math.min(...forecast.days.map(day => day.low).filter(Number.isFinite))
                        readonly property real high: Math.max(...forecast.days.map(day => day.high).filter(Number.isFinite))

                        function position(value: real): real {
                            return high > low ? Math.max(0, Math.min((value - low) / (high - low), 1)) : 0.5
                        }

                        Layout.fillWidth: true
                        // The one part that shrinks, down to two days, when the screen is short
                        Layout.fillHeight: true
                        Layout.preferredHeight: Math.min(contentHeight, weather.maxListHeight)
                        Layout.minimumHeight: Math.min(contentHeight, 64)
                        // On the cards' edges, with each day's text inside like a card's
                        Layout.leftMargin: 16
                        Layout.rightMargin: 16
                        Layout.topMargin: 8
                        Layout.bottomMargin: 8
                        clip: true
                        contentHeight: dayColumn.implicitHeight
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar {}

                        Column {
                            id: dayColumn

                            width: dayList.width

                            Repeater {
                                objectName: "days"
                                model: forecast.days

                                delegate: Item {
                                    id: dayRow

                                    required property var modelData
                                    required property int index
                                    // A later day whose hours show; today's show without it being picked
                                    readonly property bool selected: weather.showHourly && index > 0 && popup.day === index

                                    width: dayColumn.width
                                    height: 32
                                    Accessible.role: Accessible.Button
                                    Accessible.name: `${weather.dayName(index, modelData.weekday, Locale.LongFormat)}, ${modelData.text}, `
                                        + qsTr("high %1, low %2").arg(modelData.highText).arg(modelData.lowText)
                                    Accessible.onPressAction: popup.day = index
                                    ToolTip.visible: dayArea.containsMouse
                                    ToolTip.delay: 500
                                    ToolTip.text: modelData.text

                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 4
                                        color: Qt.alpha(popup.ink, dayRow.selected ? 0.06
                                            : dayArea.containsMouse && weather.showHourly ? 0.04 : 0)
                                    }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 12
                                        anchors.rightMargin: 12
                                        spacing: 10

                                        Label {
                                            Layout.preferredWidth: 52
                                            text: weather.dayName(dayRow.index, dayRow.modelData.weekday, Locale.ShortFormat)
                                            font.pixelSize: 14
                                        }

                                        Picture {
                                            Layout.preferredWidth: 20
                                            Layout.preferredHeight: 20
                                            condition: dayRow.modelData.condition
                                        }

                                        Item {
                                            Layout.preferredWidth: 44
                                            Layout.fillHeight: true

                                            Chance {
                                                anchors.verticalCenter: parent.verticalCenter
                                                value: dayRow.modelData.precipitationChance
                                            }
                                        }

                                        Label {
                                            Layout.preferredWidth: 34
                                            horizontalAlignment: Text.AlignRight
                                            text: weather.whole(dayRow.modelData.low)
                                            color: popup.secondary
                                            font.pixelSize: 14
                                        }

                                        Item {
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 4

                                            Rectangle {
                                                anchors.fill: parent
                                                radius: 2
                                                color: Qt.alpha(popup.ink, 0.1)
                                            }

                                            Rectangle {
                                                id: span

                                                readonly property real from: dayList.position(dayRow.modelData.low)
                                                readonly property real to: dayList.position(dayRow.modelData.high)

                                                x: from * parent.width
                                                width: Math.max(height, (to - from) * parent.width)
                                                height: parent.height
                                                radius: 2
                                                visible: Number.isFinite(dayRow.modelData.low) && Number.isFinite(dayRow.modelData.high)
                                                // The day's stretch of the week's cold to warm
                                                gradient: Gradient {
                                                    orientation: Gradient.Horizontal

                                                    GradientStop { position: 0; color: weather.warmth(span.from) }
                                                    GradientStop { position: 1; color: weather.warmth(span.to) }
                                                }
                                            }

                                            // The temperature now, on today's bar
                                            Rectangle {
                                                x: dayList.position(forecast.current.temperature) * parent.width - width / 2
                                                y: (parent.height - height) / 2
                                                width: 8
                                                height: 8
                                                radius: 4
                                                visible: dayRow.index === 0 && Number.isFinite(forecast.current.temperature)
                                                color: weather.dark ? "#202020" : "#F3F3F3"
                                                border.width: 2
                                                border.color: popup.ink
                                            }
                                        }

                                        Label {
                                            Layout.preferredWidth: 34
                                            horizontalAlignment: Text.AlignRight
                                            text: weather.whole(dayRow.modelData.high)
                                            font.pixelSize: 14
                                        }
                                    }

                                    MouseArea {
                                        id: dayArea

                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: weather.showHourly ? Qt.PointingHandCursor : Qt.ArrowCursor
                                        onClicked: {
                                            if (weather.showHourly)
                                                popup.day = dayRow.index
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Sets the hours of the picked day apart from the days above
                    Divider {
                        Layout.leftMargin: 16
                        Layout.rightMargin: 16
                        visible: hourly.visible
                    }

                    // The hours over a graph of the temperature, or of the chance of rain or snow: each value just above
                    // its point on the line, and under the graph each hour's picture, other value and time in rows
                    Item {
                        id: hourly

                        // What the graph shows: temperature, rain or snow
                        property string metric: "temperature"
                        readonly property bool chances: metric !== "temperature"
                        // From the hour under way today, all of another day
                        readonly property var hours: (popup.day === 0 ? forecast.upcoming : forecast.hours[popup.day] ?? [])
                            .filter(hour => Number.isFinite(hour.temperature))
                        // As many whole hours as fit, sharing the width
                        readonly property real hourWidth: {
                            const width = hourlyFlick.width
                            return width / Math.max(1, Math.floor(width / weather.hourWidth))
                        }
                        readonly property real contentWidth: hours.length * hourWidth
                        readonly property var temperatures: hours.map(hour => hour.temperature)
                        readonly property var values: metric === "rain" ? hours.map(hour => hour.rainChance ?? 0)
                            : metric === "snow" ? hours.map(hour => hour.snowChance ?? 0) : temperatures
                        // Temperatures fill the graph's height; chances keep to 0 to 100%
                        readonly property real low: chances ? 0 : Math.min(...values)
                        readonly property real high: chances ? 100 : Math.max(...values)
                        // The line runs between these heights, the highest value highest, and its fill fades out
                        // above the pictures
                        readonly property real graphTop: 20
                        readonly property real graphBottom: 36
                        readonly property real fillBottom: 56
                        readonly property var points: values.map((value, index) => Qt.point(
                            (index + 0.5) * hourWidth,
                            graphBottom - (high > low ? (value - low) / (high - low) : 0.5) * (graphBottom - graphTop)))
                        // Carried on level past the first and last hour, so it always meets both edges
                        readonly property string line: points.length < 2 ? ""
                            : `M 0 ${points[0].y} L ${weather.spline(points).slice(2)} L ${contentWidth} ${points[points.length - 1].y}`
                        readonly property string area: line === "" ? ""
                            : `${line} L ${contentWidth} ${fillBottom} L 0 ${fillBottom} Z`
                        // Wheel turns not yet worth a whole hour
                        property real wheelRest: 0

                        // Scrolls whole hours, so the first and last in view are never cut
                        function scrollTo(index: real) {
                            const end = Math.max(0, hourlyFlick.contentWidth - hourlyFlick.width)
                            hourlyFlick.contentX = Math.max(0, Math.min(Math.round(index) * hourWidth, end))
                        }

                        objectName: "hourly"
                        Layout.fillWidth: true
                        Layout.leftMargin: 16
                        Layout.rightMargin: 16
                        Layout.topMargin: 10
                        Layout.bottomMargin: 10
                        implicitHeight: metrics.height + 2 + 116
                        visible: weather.showHourly && hours.length > 0

                        Row {
                            id: metrics

                            anchors.right: parent.right
                            spacing: 4

                            Repeater {
                                model: [["temperature", qsTr("Temperature")], ["rain", qsTr("Rain")], ["snow", qsTr("Snow")]]

                                delegate: Rectangle {
                                    id: metricButton

                                    required property var modelData
                                    readonly property bool chosen: hourly.metric === modelData[0]

                                    width: metricText.implicitWidth + 20
                                    height: 26
                                    radius: 13
                                    color: Qt.alpha(popup.ink, chosen ? 0.08 : metricArea.containsMouse ? 0.04 : 0)
                                    Accessible.role: Accessible.RadioButton
                                    Accessible.name: modelData[1]
                                    Accessible.checked: chosen
                                    Accessible.onPressAction: hourly.metric = modelData[0]

                                    Label {
                                        id: metricText

                                        anchors.centerIn: parent
                                        text: metricButton.modelData[1]
                                        color: metricButton.chosen ? popup.ink : popup.secondary
                                        font.pixelSize: 12
                                    }

                                    MouseArea {
                                        id: metricArea

                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: hourly.metric = metricButton.modelData[0]
                                    }
                                }
                            }
                        }

                        Flickable {
                            id: hourlyFlick

                            anchors.top: metrics.bottom
                            anchors.topMargin: 2
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            contentWidth: hourly.contentWidth
                            contentHeight: height
                            flickableDirection: Flickable.HorizontalFlick
                            boundsBehavior: Flickable.StopAtBounds
                            clip: true
                            onMovementEnded: hourly.scrollTo(contentX / hourly.hourWidth)

                            Shape {
                                width: hourly.contentWidth
                                height: hourlyFlick.height
                                preferredRendererType: Shape.CurveRenderer

                                // In the cold blue of the days' bars: the fill fading out, the line a little brighter
                                ShapePath {
                                    strokeColor: "transparent"
                                    fillGradient: LinearGradient {
                                        y1: hourly.graphTop
                                        y2: hourly.fillBottom

                                        GradientStop { position: 0; color: Qt.alpha(weather.coldColor, 0.45) }
                                        GradientStop { position: 1; color: Qt.alpha(weather.coldColor, 0) }
                                    }

                                    PathSvg { path: hourly.area }
                                }

                                ShapePath {
                                    fillColor: "transparent"
                                    strokeColor: Qt.alpha(weather.coldColor, 0.75)
                                    strokeWidth: 1.5

                                    PathSvg { path: hourly.line }
                                }
                            }

                            Repeater {
                                model: hourly.hours

                                delegate: Item {
                                    id: hour

                                    required property var modelData
                                    required property int index
                                    readonly property real lineY: hourly.points[index]?.y ?? hourly.graphBottom

                                    x: index * hourly.hourWidth
                                    width: hourly.hourWidth
                                    height: hourlyFlick.height
                                    Accessible.role: Accessible.StaticText
                                    Accessible.name: [modelData.now ? qsTr("Now") : modelData.timeText, modelData.text,
                                        modelData.temperatureText, weather.chance(modelData.precipitationChance)]
                                        .filter(part => part).join(", ")

                                    Label {
                                        width: parent.width
                                        y: hour.lineY - height - 3
                                        horizontalAlignment: Text.AlignHCenter
                                        text: hourly.chances ? weather.chance(hourly.values[hour.index]) : weather.whole(hour.modelData.temperature)
                                        font.pixelSize: 14
                                    }

                                    Picture {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        y: 58
                                        width: 24
                                        height: 24
                                        condition: hour.modelData.condition
                                    }

                                    // The chance of rain or snow under the temperatures, the temperature under the chances
                                    Item {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        y: 84
                                        width: hourly.chances ? hourTemperature.implicitWidth : hourChance.width
                                        height: 14

                                        Chance {
                                            id: hourChance

                                            anchors.centerIn: parent
                                            visible: !hourly.chances && Number.isFinite(value)
                                            value: hour.modelData.precipitationChance
                                        }

                                        Label {
                                            id: hourTemperature

                                            anchors.centerIn: parent
                                            visible: hourly.chances
                                            text: weather.whole(hour.modelData.temperature)
                                            muted: true
                                            font.pixelSize: 12
                                        }
                                    }

                                    Label {
                                        width: parent.width
                                        y: 100
                                        horizontalAlignment: Text.AlignHCenter
                                        text: hour.modelData.now ? qsTr("Now") : hour.modelData.timeText
                                        muted: !hour.modelData.now
                                        font.pixelSize: 12
                                        font.weight: hour.modelData.now ? Font.DemiBold : Font.Normal
                                    }
                                }
                            }
                        }

                        // The wheel scrolls the hours sideways, an hour a notch
                        MouseArea {
                            anchors.fill: hourlyFlick
                            acceptedButtons: Qt.NoButton
                            onWheel: wheel => {
                                if (wheel.angleDelta.y === 0) {
                                    wheel.accepted = false
                                    return
                                }
                                hourly.wheelRest += wheel.angleDelta.y
                                const notches = Math.trunc(hourly.wheelRest / 120)
                                if (notches === 0)
                                    return
                                hourly.wheelRest -= notches * 120
                                hourly.scrollTo(Math.round(hourlyFlick.contentX / hourly.hourWidth) - notches)
                            }
                        }
                    }
                }

                ColumnLayout {
                    objectName: "search"
                    Layout.fillWidth: true
                    visible: popup.picking
                    spacing: 0

                    TextField {
                        id: field

                        objectName: "field"
                        Layout.fillWidth: true
                        Layout.leftMargin: 16
                        Layout.rightMargin: 16
                        Layout.topMargin: 12
                        placeholderText: qsTr("Search for a city")
                        // The popup follows the bar's theme, which can differ from the system's
                        color: popup.ink
                        placeholderTextColor: popup.muted
                        font.pixelSize: 13
                        Accessible.name: qsTr("Search for a city")
                        onTextChanged: forecast.search(text)
                        Keys.onReturnPressed: {
                            if (forecast.searchResults.length > 0)
                                weather.pick(forecast.searchResults[0])
                        }
                    }

                    Label {
                        objectName: "hint"
                        Layout.fillWidth: true
                        Layout.margins: 16
                        visible: places.count === 0 && text !== ""
                        text: field.text.split(",")[0].trim().length < 2
                            ? qsTr("Type the name of a city. A region after a comma narrows it down, as in Paris, Texas.")
                            : forecast.searching ? qsTr("Searching...") : forecast.searchError !== "" ? "" : qsTr("No places found")
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                        muted: true
                        font.pixelSize: 12
                    }

                    Flickable {
                        id: results

                        objectName: "results"
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.min(contentHeight, 280)
                        Layout.leftMargin: 16
                        Layout.rightMargin: 16
                        Layout.topMargin: 6
                        Layout.bottomMargin: 6
                        visible: places.count > 0
                        clip: true
                        contentHeight: resultColumn.implicitHeight
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar {}

                        Column {
                            id: resultColumn

                            width: results.width
                            spacing: 2

                            Repeater {
                                id: places

                                model: forecast.searchResults

                                delegate: Item {
                                    id: place

                                    required property var modelData

                                    width: resultColumn.width
                                    height: 44
                                    Accessible.role: Accessible.Button
                                    Accessible.name: [modelData.name, modelData.region].filter(part => part).join(", ")
                                    Accessible.onPressAction: weather.pick(modelData)

                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 6
                                        color: Qt.alpha(popup.ink, placeArea.containsMouse ? 0.06 : 0)
                                    }

                                    Column {
                                        x: 12
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width - 24

                                        Label {
                                            width: parent.width
                                            text: place.modelData.name
                                        }

                                        Label {
                                            width: parent.width
                                            visible: text !== ""
                                            text: place.modelData.region
                                            muted: true
                                            font.pixelSize: 12
                                        }
                                    }

                                    MouseArea {
                                        id: placeArea

                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: weather.pick(place.modelData)
                                    }
                                }
                            }
                        }
                    }
                }

                // A darker strip, as in the GitHub popup
                Rectangle {
                    Layout.fillWidth: true
                    Layout.topMargin: popup.picking ? 6 : 0
                    Layout.leftMargin: 1
                    Layout.rightMargin: 1
                    Layout.bottomMargin: 1
                    implicitHeight: 40
                    bottomLeftRadius: 7
                    bottomRightRadius: 7
                    color: Qt.alpha("#000000", weather.dark ? 0.15 : 0.03)

                    Divider { width: parent.width }

                    Link {
                        objectName: "changeLocation"
                        x: 16
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !popup.picking || forecast.hasLocation
                        text: popup.picking ? qsTr("Cancel") : qsTr("Change location")
                        onClicked: {
                            if (popup.picking)
                                popup.choosing = false
                            else
                                weather.chooseLocation()
                        }
                    }

                    Label {
                        objectName: "updated"
                        anchors.right: parent.right
                        anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !popup.picking && weather.updated !== ""
                        text: qsTr("Updated %1").arg(weather.updated)
                        muted: true
                        font.pixelSize: 12
                    }
                }
            }
        }
    }
}
