import QtQuick
import Yasb
import Yasb.Bar

Item {
    id: battery

    // Placeholders: {percent} {time_remaining} {is_charging} {power} {voltage} {capacity} {full_capacity}
    // {designed_capacity} {temperature} {cycle_count} {health} {chemistry}; "" shows only the icons
    property string label: "{percent}%"
    property string alternateLabel: "{percent}% | remaining: {time_remaining}"
    property int updateInterval: 5000
    // {time_remaining} in words ("2 hours") instead of H:MM:SS
    property bool timeRemainingNatural: false
    property string timeRemainingUnlimited: "unlimited"
    // Hide the widget on systems without a battery, otherwise it says so
    property bool hideUnsupported: true
    // Highest percentage of each status, above high is full
    property int criticalThreshold: 10
    property int lowThreshold: 25
    property int mediumThreshold: 75
    property int highThreshold: 95
    property string iconFont: Qt.fontFamilies().includes("Segoe Fluent Icons") ? "Segoe Fluent Icons" : "Segoe MDL2 Assets"

    property list<string> batteryIcons: ["", "", "", "", "", "", "", "", "", "", ""]
    property list<string> chargingIcons: ["", "", "", "", "", "", "", "", "", "", ""]
    property int iconSize: 18
    // The charging icon blinks while the battery charges
    property bool blinkCharging: true
    property int blinkInterval: 500
    property color criticalColor: dark ? "#ff99a4" : "#c42b1c"
    property color lowColor: dark ? "#fce100" : "#9d5d00"
    property color mediumColor: textColor
    property color highColor: textColor
    property color fullColor: textColor
    property color chargingColor: textColor
    property color blinkingColor: Qt.alpha("#119909", 0.8)

    property BarBase bar: null

    property bool showAlternate: false

    readonly property bool dark: bar ? bar.dark : Application.styleHints.colorScheme === Qt.ColorScheme.Dark

    property color textColor: bar?.textColor ?? (dark ? "#ffffff" : "#000000")
    property font font
    font.family: bar?.font.family ?? Application.font.family
    font.pixelSize: bar?.font.pixelSize ?? 13
    font.weight: bar?.font.weight ?? Font.Normal
    font.italic: bar?.font.italic ?? false
    font.letterSpacing: bar?.font.letterSpacing ?? 0
    font.capitalization: bar?.font.capitalization ?? Font.MixedCase
    font.variableAxes: bar?.font.variableAxes ?? ({})

    readonly property var info: monitor.data
    readonly property bool shown: monitor.available || !hideUnsupported
    readonly property bool pluggedIn: info.charging || info.pluggedIn
    // critical, low, medium, high or full by percentage
    readonly property string level: {
        const percent = info.percent
        if (percent <= criticalThreshold)
            return "critical"
        if (percent <= lowThreshold)
            return "low"
        if (percent <= mediumThreshold)
            return "medium"
        if (percent <= highThreshold)
            return "high"
        return "full"
    }
    // The level, or charging while the battery charges
    readonly property string status: info.charging ? "charging" : level
    readonly property color statusColor: ({
            critical: criticalColor,
            low: lowColor,
            medium: mediumColor,
            high: highColor,
            full: fullColor,
            charging: chargingColor
        })[status]
    readonly property string text: {
        if (!monitor.available)
            return "Battery info not available"
        return format(showAlternate ? alternateLabel : label)
    }

    function fixed(value: var, digits: int): string {
        return value === null || value === undefined ? "N/A" : Number(value).toFixed(digits)
    }

    function timeRemaining(): string {
        if (info.timeUnlimited)
            return timeRemainingUnlimited
        if (info.timeUnknown)
            return "unknown"
        return timeRemainingNatural ? info.timeNatural : info.timeText
    }

    function format(template: string): string {
        if (template === "")
            return ""
        const values = {
            percent: String(info.percent),
            time_remaining: timeRemaining(),
            is_charging: info.charging ? "yes" : "no",
            power: info.rate === null || info.rate === undefined ? "N/A" : Math.abs(info.rate).toFixed(1),
            voltage: fixed(info.voltage, 2),
            capacity: fixed(info.capacity, 0),
            full_capacity: fixed(info.fullCapacity, 0),
            designed_capacity: fixed(info.designedCapacity, 0),
            temperature: fixed(info.temperature, 1),
            cycle_count: fixed(info.cycleCount, 0),
            health: fixed(info.health, 1),
            chemistry: info.chemistry || "N/A"
        }
        return template.replace(/\{(\w+)\}/g, (match, key) => values[key] ?? match)
    }

    implicitWidth: shown ? row.implicitWidth : 0
    implicitHeight: shown ? row.implicitHeight : 0
    visible: shown
    Accessible.role: Accessible.StaticText
    Accessible.name: monitor.available ? `Battery ${info.percent}%${info.charging ? ", charging" : pluggedIn ? ", plugged in" : ""}`
        : "Battery info not available"

    BatteryMonitor {
        id: monitor

        updateInterval: battery.updateInterval
    }

    Row {
        id: row

        height: parent.height
        spacing: 4

        Text {
            id: icon

            property bool blinkOn: true
            readonly property list<string> icons: battery.pluggedIn ? battery.chargingIcons : battery.batteryIcons

            objectName: "icon"
            y: Math.round((parent.height - height) / 2)
            width: battery.iconSize
            height: battery.iconSize
            visible: monitor.available && text !== ""
            // Spread the percentage over however many glyphs there are
            text: icons.length > 0 ? icons[Math.max(0, Math.min(icons.length - 1,
                Math.round(battery.info.percent / 100 * (icons.length - 1))))] : ""
            textFormat: Text.PlainText
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.family: battery.iconFont
            font.pixelSize: battery.iconSize
            color: blinkOn ? battery.statusColor : battery.blinkingColor

            Behavior on color {
                ColorAnimation { duration: Math.min(150, battery.blinkInterval / 2) }
            }

            // Only while charging, not while plugged in and full
            Timer {
                interval: battery.blinkInterval
                repeat: true
                running: icon.visible && battery.blinkCharging && battery.info.charging
                onRunningChanged: {
                    if (!running)
                        icon.blinkOn = true
                }
                onTriggered: icon.blinkOn = !icon.blinkOn
            }
        }

        Text {
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: battery.text
            textFormat: Text.PlainText
            color: battery.textColor
            font: battery.font
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: battery.showAlternate = !battery.showAlternate
    }
}
