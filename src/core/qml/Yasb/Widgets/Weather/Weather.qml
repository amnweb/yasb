pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl
import QtQuick.Layouts
import QtQuick.Shapes
import Yasb
import Yasb.Bar
import Yasb.Common
import Yasb.Themes

Item {
    id: weather

    required property BarBase bar
    readonly property Theme theme: bar.theme
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
    property string hotkey: ""
    property int popupWidth: 424
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
    property color rainColor: weather.theme.colors.textTertiary
    property color errorColor: weather.theme.colors.critical

    property bool showAlternate: false

    readonly property bool dark: theme.dark
    // Text on the bar takes the theme's colour, and labels the bar's font; parts set in font replace the bar's
    property color textColor: theme.colors.text
    property font font
    // Glyphs take the theme's icon font, each part unless the widget file sets it
    property font iconFont
    iconFont.family: theme.bar.iconFont.family
    iconFont.weight: theme.bar.iconFont.weight
    iconFont.variableAxes: theme.bar.iconFont.variableAxes
    // The mark of the temperature now on today's bar
    property color markerColor: dark ? "#202020" : "#F3F3F3"
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
    // Glyphs in the popup, such as the refresh button
    property int popupIconSize: 14
    property int popupOpenDuration: theme.popup.openDuration
    property int popupCloseDuration: theme.popup.closeDuration
    // The right-click menu of the place search: the theme's, unless set here
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
    property color popupSecondaryBackgroundColor: theme.colors.backgroundSecondary
    property color popupCardColor: theme.colors.card
    property color popupCardBorderColor: theme.colors.cardBorder
    property color popupDividerColor: theme.colors.divider
    property color popupTertiaryTextColor: theme.colors.textTertiary
    property color popupHoverColor: theme.colors.hover
    property color popupSelectedColor: theme.colors.selected
    property font popupTitleFont
    popupTitleFont.family: theme.popup.font.family
    popupTitleFont.pixelSize: 16
    popupTitleFont.weight: Font.DemiBold
    // The temperature now at the top; the sky, each day's name and temperatures and each hour's value; each
    // reading's value; each hour's time, and the hour now
    property font temperatureFont
    temperatureFont.family: theme.popup.font.family
    temperatureFont.pixelSize: 48
    temperatureFont.weight: Font.Light
    property font forecastFont
    forecastFont.family: theme.popup.font.family
    forecastFont.pixelSize: 14
    property font readingFont
    readingFont.family: theme.popup.font.family
    readingFont.pixelSize: 14
    readingFont.weight: Font.DemiBold
    property font hourFont
    hourFont.family: theme.popup.font.family
    hourFont.pixelSize: 12
    property font nowFont
    nowFont.family: theme.popup.font.family
    nowFont.pixelSize: 12
    nowFont.weight: Font.DemiBold
    readonly property string edge: bar.edge

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
        const gap = popupGap
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
        keys: weather.hotkey
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

    // An item of the text fields' right-click menu, its icon in menuIconSize
    component FieldMenuItem: MenuItem {
        icon.width: weather.menuIconSize
        icon.height: weather.menuIconSize
    }

    component Glyph: Text {
        textFormat: Text.PlainText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.family: weather.iconFont.family
        font.weight: weather.iconFont.weight
        font.variableAxes: weather.iconFont.variableAxes
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
            font: weather.popupSmallFont
        }
    }

    // Text in the popup: plain, in its ink or muted colour, cut short with an ellipsis
    component PopupText: Text {
        property bool muted: false

        textFormat: Text.PlainText
        elide: Text.ElideRight
        color: muted ? weather.popupTertiaryTextColor : weather.popupTextColor
        font: weather.popupFont
    }

    // A line between the popup's parts
    component Divider: Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: weather.popupDividerColor
    }

    // A card, on the popup's 16px edge
    component Card: Rectangle {
        Layout.fillWidth: true
        Layout.leftMargin: 16
        Layout.rightMargin: 16
        radius: 8
        color: weather.popupCardColor
        border.width: 1
        border.color: weather.popupCardBorderColor
    }

    component Link: Text {
        id: link

        signal clicked

        color: linkArea.containsMouse ? weather.popupTextColor : weather.popupSecondaryTextColor
        font: weather.popupSmallFont
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

        Label {
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
        // Supporting text, and labels, times and other text to read last
        // The lines between the parts
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
        height: Math.min(popupContent.implicitHeight, weather.Screen.desktopAvailableHeight - 40)
        anchor: weather
        font: weather.popupFont
        theme: weather.theme
        backdropItem: surface
        enter: NumberAnimation { target: popup; property: "reveal"; to: 1; duration: weather.popupOpenDuration; easing.type: Easing.OutCubic }
        exit: NumberAnimation { target: popup; property: "reveal"; to: 0; duration: weather.popupCloseDuration; easing.type: Easing.InCubic }
        onVisibleChanged: {
            if (!visible)
                reveal = 0
        }
        onDayChanged: hourlyFlick.contentX = 0

        Rectangle {
            id: surface

            anchors.fill: parent
            radius: weather.popupRadius
            color: weather.popupColor
            border.width: 1
            border.color: weather.popupBorderColor
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

                        PopupText {
                            width: parent.width
                            text: popup.picking ? qsTr("Choose a location") : forecast.location.name ?? ""
                            font: weather.popupTitleFont
                        }

                        PopupText {
                            width: parent.width
                            visible: !popup.picking && text !== ""
                            text: forecast.location.region ?? ""
                            muted: true
                            font: weather.popupSmallFont
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
                            color: refreshArea.containsMouse ? weather.popupHoverColor : "transparent"
                        }

                        Glyph {
                            anchors.fill: parent
                            text: "\ue72c"
                            color: refreshArea.containsMouse ? weather.popupTextColor : weather.popupTertiaryTextColor
                            font.pixelSize: weather.popupIconSize
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
                    trackColor: weather.popupDividerColor
                }

                PopupText {
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
                    font: weather.popupSmallFont
                }

                PopupText {
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

                        PopupText {
                            objectName: "temperature"
                            text: weather.degrees(forecast.current.temperature)
                            font: weather.temperatureFont
                        }

                        Column {
                            Layout.fillWidth: true
                            spacing: 2

                            PopupText {
                                width: parent.width
                                text: weather.values.condition_text
                                font: weather.forecastFont
                            }

                            PopupText {
                                width: parent.width
                                text: qsTr("High %1 · Low %2 · Feels %3").arg(weather.whole(popup.today.high))
                                    .arg(weather.whole(popup.today.low)).arg(weather.whole(forecast.current.feelsLike))
                                color: weather.popupSecondaryTextColor
                                font: weather.popupSmallFont
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

                                    PopupText {
                                        width: parent.width
                                        horizontalAlignment: Text.AlignHCenter
                                        text: reading.modelData[1]
                                        font: weather.readingFont
                                    }

                                    PopupText {
                                        width: parent.width
                                        horizontalAlignment: Text.AlignHCenter
                                        text: reading.modelData[0]
                                        muted: true
                                        font: weather.popupSmallFont
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
                                        color: dayRow.selected ? weather.popupSelectedColor
                                            : dayArea.containsMouse && weather.showHourly ? weather.popupHoverColor : "transparent"
                                    }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 12
                                        anchors.rightMargin: 12
                                        spacing: 10

                                        PopupText {
                                            Layout.preferredWidth: 52
                                            text: weather.dayName(dayRow.index, dayRow.modelData.weekday, Locale.ShortFormat)
                                            font: weather.forecastFont
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

                                        PopupText {
                                            Layout.preferredWidth: 34
                                            horizontalAlignment: Text.AlignRight
                                            text: weather.whole(dayRow.modelData.low)
                                            color: weather.popupSecondaryTextColor
                                            font: weather.forecastFont
                                        }

                                        Item {
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 4

                                            Rectangle {
                                                anchors.fill: parent
                                                radius: 2
                                                color: Qt.alpha(weather.popupTextColor, 0.1)
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
                                                color: weather.markerColor
                                                border.width: 2
                                                border.color: weather.popupTextColor
                                            }
                                        }

                                        PopupText {
                                            Layout.preferredWidth: 34
                                            horizontalAlignment: Text.AlignRight
                                            text: weather.whole(dayRow.modelData.high)
                                            font: weather.forecastFont
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
                                    color: chosen ? weather.popupSelectedColor : metricArea.containsMouse ? weather.popupHoverColor : "transparent"
                                    Accessible.role: Accessible.RadioButton
                                    Accessible.name: modelData[1]
                                    Accessible.checked: chosen
                                    Accessible.onPressAction: hourly.metric = modelData[0]

                                    PopupText {
                                        id: metricText

                                        anchors.centerIn: parent
                                        text: metricButton.modelData[1]
                                        color: metricButton.chosen ? weather.popupTextColor : weather.popupSecondaryTextColor
                                        font: weather.popupSmallFont
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

                                    PopupText {
                                        width: parent.width
                                        y: hour.lineY - height - 3
                                        horizontalAlignment: Text.AlignHCenter
                                        text: hourly.chances ? weather.chance(hourly.values[hour.index]) : weather.whole(hour.modelData.temperature)
                                        font: weather.forecastFont
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

                                        PopupText {
                                            id: hourTemperature

                                            anchors.centerIn: parent
                                            visible: hourly.chances
                                            text: weather.whole(hour.modelData.temperature)
                                            muted: true
                                            font: weather.popupSmallFont
                                        }
                                    }

                                    PopupText {
                                        width: parent.width
                                        y: 100
                                        horizontalAlignment: Text.AlignHCenter
                                        text: hour.modelData.now ? qsTr("Now") : hour.modelData.timeText
                                        muted: !hour.modelData.now
                                        font: hour.modelData.now ? weather.nowFont : weather.hourFont
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

                    // The text fields' right-click menu: Qt's editing items and icons in the menu's look, acting on the field that
                    // opened it
                    Menu {
                        id: fieldMenu

                        readonly property TextField editor: parent as TextField
                        readonly property bool editable: !(editor?.readOnly ?? true)
                        readonly property bool selected: (editor?.selectedText.length ?? 0) > 0

                        // A window of its own, so it opens where clicked even past the popup's edges
                        popupType: Popup.Window
                        // Its window is made once and reused, and Windows shows it again where it was, under the popup raised
                        // since; raising it before it shows keeps it in front
                        onAboutToShow: contentItem.Window.window?.raise()
                        // Fades in when it opens, in place of the style's growing from a third of its height
                        enter: Transition {
                            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: weather.menuOpenDuration; easing.type: Easing.OutCubic }
                        }
                        topInset: 0
                        leftInset: 0
                        rightInset: 0
                        bottomInset: 0
                        font: weather.menuFont
                        // Active and inactive only, so disabled controls keep the style's dimmed colours
                        palette.active.text: weather.menuTextColor
                        palette.inactive.text: weather.menuTextColor

                        background: Rectangle {
                            implicitWidth: weather.menuWidth
                            radius: weather.menuRadius
                            color: weather.menuColor
                            border.color: weather.menuBorderColor
                        }

                        FieldMenuItem {
                            text: qsTr("Undo")
                            icon.name: "edit-undo"
                            enabled: fieldMenu.editor?.canUndo ?? false
                            onTriggered: fieldMenu.editor.undo()
                        }
                        FieldMenuItem {
                            text: qsTr("Redo")
                            icon.name: "edit-redo"
                            enabled: fieldMenu.editor?.canRedo ?? false
                            onTriggered: fieldMenu.editor.redo()
                        }
                        MenuSeparator {}
                        FieldMenuItem {
                            text: qsTr("Cut")
                            icon.name: "edit-cut"
                            enabled: fieldMenu.editable && fieldMenu.selected
                            onTriggered: fieldMenu.editor.cut()
                        }
                        FieldMenuItem {
                            text: qsTr("Copy")
                            icon.name: "edit-copy"
                            enabled: fieldMenu.selected
                            onTriggered: fieldMenu.editor.copy()
                        }
                        FieldMenuItem {
                            text: qsTr("Paste")
                            icon.name: "edit-paste"
                            enabled: fieldMenu.editable && (fieldMenu.editor?.canPaste ?? false)
                            onTriggered: fieldMenu.editor.paste()
                        }
                        FieldMenuItem {
                            text: qsTr("Delete")
                            icon.name: "edit-delete"
                            enabled: fieldMenu.editable && fieldMenu.selected
                            onTriggered: fieldMenu.editor.remove(fieldMenu.editor.selectionStart, fieldMenu.editor.selectionEnd)
                        }
                        MenuSeparator {}
                        FieldMenuItem {
                            text: qsTr("Select All")
                            icon.name: "edit-select-all"
                            onTriggered: fieldMenu.editor.selectAll()
                        }
                    }

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

                        objectName: "field"
                        Layout.fillWidth: true
                        Layout.leftMargin: 16
                        Layout.rightMargin: 16
                        Layout.topMargin: 12
                        placeholderText: qsTr("Search for a city")
                        // The popup follows the bar's theme, which can differ from the system's
                        color: weather.popupTextColor
                        placeholderTextColor: weather.popupTertiaryTextColor
                        font: weather.popupFont
                        Accessible.name: qsTr("Search for a city")
                        onTextChanged: forecast.search(text)
                        Keys.onReturnPressed: {
                            if (forecast.searchResults.length > 0)
                                weather.pick(forecast.searchResults[0])
                        }
                    }

                    PopupText {
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
                        font: weather.popupSmallFont
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
                                        color: placeArea.containsMouse ? weather.popupHoverColor : "transparent"
                                    }

                                    Column {
                                        x: 12
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width - 24

                                        PopupText {
                                            width: parent.width
                                            text: place.modelData.name
                                        }

                                        PopupText {
                                            width: parent.width
                                            visible: text !== ""
                                            text: place.modelData.region
                                            muted: true
                                            font: weather.popupSmallFont
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
                    bottomLeftRadius: weather.popupRadius - 1
                    bottomRightRadius: weather.popupRadius - 1
                    color: weather.popupSecondaryBackgroundColor

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

                    PopupText {
                        objectName: "updated"
                        anchors.right: parent.right
                        anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !popup.picking && weather.updated !== ""
                        text: qsTr("Updated %1").arg(weather.updated)
                        muted: true
                        font: weather.popupSmallFont
                    }
                }
            }
        }
    }
}
