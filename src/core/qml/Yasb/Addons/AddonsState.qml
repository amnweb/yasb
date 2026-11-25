import QtQuick
import Yasb

// What the window shows, and the colours its pages share
QtObject {
    id: state

    required property Addons addons
    // all, widget, theme, layout, config, or installed
    property string section: "all"
    // The addon the detail page shows, or null
    property var shown: null
    property string query
    readonly property bool searching: query.trim() !== ""

    readonly property bool dark: Application.styleHints.colorScheme === Qt.Dark
    readonly property color secondaryText: dark ? Qt.alpha("#ffffff", 0.786) : Qt.alpha("#000000", 0.6063)
    readonly property color tertiaryText: dark ? Qt.alpha("#ffffff", 0.5442) : Qt.alpha("#000000", 0.4458)
    readonly property color cardFill: dark ? Qt.alpha("#ffffff", 0.0512) : Qt.alpha("#ffffff", 0.7)
    readonly property color cardHover: dark ? Qt.alpha("#ffffff", 0.0837) : Qt.alpha("#f9f9f9", 0.5)
    readonly property color cardStroke: dark ? Qt.alpha("#000000", 0.1) : Qt.alpha("#000000", 0.0578)
    readonly property color divider: dark ? Qt.alpha("#ffffff", 0.0837) : Qt.alpha("#000000", 0.0803)
    readonly property color subtleFill: dark ? Qt.alpha("#ffffff", 0.0605) : Qt.alpha("#000000", 0.0373)
    readonly property color subtlePressed: dark ? Qt.alpha("#ffffff", 0.0419) : Qt.alpha("#000000", 0.0241)
    readonly property color cautionText: dark ? "#fce100" : "#9d5d00"
    readonly property color cautionBackground: dark ? "#433519" : "#fff4ce"
    readonly property color criticalText: dark ? "#ff99a4" : "#c42b1c"
    // Text on the accent colour
    readonly property color onAccent: dark ? "#000000" : "#ffffff"
    // Fast at first, then slowing to a stop
    readonly property list<real> decelerate: [0, 0, 0, 1, 1, 1]

    signal actRequested(var addon, int version)
    signal linkRequested

    function installedRow(id: string): var {
        return addons.installed.find(row => row.id === id) ?? null
    }

    // install, update or installed
    function action(addon: var): string {
        const row = installedRow(addon.id)
        return row === null ? "install" : row.update > 0 ? "update" : "installed"
    }

    // Whether an install or update of this type can start now: a config waits for all others, and they for it
    function canStart(type: string): bool {
        return type === "config" ? addons.busy.length === 0 : !addons.configBusy
    }

    function showSection(name: string) {
        section = name
        shown = null
    }

    // 2026-11-22 as 22 Nov 2026
    function date(text: string): string {
        const parsed = new Date(`${text}T00:00:00`)
        return isNaN(parsed) ? text : Qt.formatDate(parsed, "d MMM yyyy")
    }

    function typeName(type: string): string {
        return type.charAt(0).toUpperCase() + type.slice(1)
    }
}
