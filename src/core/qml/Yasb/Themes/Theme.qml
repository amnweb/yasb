import QtQuick

// The colours, fonts and shapes the bar and its widgets share. A theme file starts from Theme and sets only what it
// changes, for example colors.accent, menu.radius or popup.font.family. Fonts are Qt fonts, so any part of one can be
// set, variableAxes included.
QtObject {
    id: theme

    readonly property bool dark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    // Windows' own colours, such as its accent colour
    readonly property SystemPalette system: SystemPalette {}

    component Colors: QtObject {
        // Text, from the strongest to the weakest
        property color text
        property color textSecondary
        property color textTertiary
        property color textDisabled
        // Text and icons on an accent fill
        property color textOnAccent
        // The base the bar and popups start from
        property color background
        // An area a step darker, laid over the background
        property color backgroundSecondary
        // Boxes that hold a group of things, and their outline
        property color card
        property color cardBorder
        // Outer edges of the bar, popups and menus
        property color border
        // Lines between the parts of a popup, such as under its header
        property color divider
        // Fills laid over any background: under the pointer, while pressed, and behind the selected or current item
        property color hover
        property color pressed
        property color selected
        // Buttons: their fill at rest, under the pointer and while pressed, and their outline
        property color control
        property color controlHover
        property color controlPressed
        property color controlBorder
        // Laid over a popup's content to set it back behind something opened on top, such as a group
        property color smoke
        property color accent
        property color success
        property color warning
        property color critical
    }

    component Bar: QtObject {
        property color background
        property color border
        // Widget labels on the bar
        property font font
        // Widget icons, on the bar and in popups; a widget's iconSize sets the size on the bar
        property font iconFont
    }

    component Popup: QtObject {
        property color background
        property color border
        property real radius
        // Between the bar and the popup
        property real gap
        // Milliseconds
        property int openDuration
        property int closeDuration
        // Only its family is used: each widget sets the sizes and weights of its own popup text
        property font font
        // Icons in popups; each widget sets their sizes
        property font iconFont
    }

    // Right-click menus
    component Menu: QtObject {
        property color background
        property color border
        property real radius
        property font font
        // Milliseconds the menu takes to fade in
        property int openDuration
    }

    readonly property Colors colors: Colors {
        text: theme.dark ? "#FFFFFF" : Qt.alpha("#000000", 0.894)
        textSecondary: theme.dark ? Qt.alpha("#FFFFFF", 0.773) : Qt.alpha("#000000", 0.62)
        textTertiary: theme.dark ? Qt.alpha("#FFFFFF", 0.53) : Qt.alpha("#000000", 0.447)
        textDisabled: theme.dark ? Qt.alpha("#FFFFFF", 0.365) : Qt.alpha("#000000", 0.36)
        textOnAccent: theme.dark ? "#000000" : "#FFFFFF"
        background: theme.dark ? "#202020" : "#F3F3F3"
        backgroundSecondary: theme.dark ? Qt.alpha("#000000", 0.1) : Qt.alpha("#000000", 0.024)
        card: theme.dark ? Qt.alpha("#FFFFFF", 0.05) : Qt.alpha("#FFFFFF", 0.7)
        cardBorder: theme.dark ? Qt.alpha("#000000", 0.1) : Qt.alpha("#000000", 0.06)
        border: theme.dark ? "#3A3A3A" : "#D9D9D9"
        divider: theme.dark ? Qt.alpha("#FFFFFF", 0.08) : Qt.alpha("#000000", 0.06)
        hover: theme.dark ? Qt.alpha("#FFFFFF", 0.06) : Qt.alpha("#000000", 0.035)
        pressed: theme.dark ? Qt.alpha("#FFFFFF", 0.04) : Qt.alpha("#000000", 0.024)
        selected: theme.dark ? Qt.alpha("#FFFFFF", 0.06) : Qt.alpha("#000000", 0.035)
        control: theme.dark ? Qt.alpha("#FFFFFF", 0.06) : Qt.alpha("#FFFFFF", 0.7)
        controlHover: theme.dark ? Qt.alpha("#FFFFFF", 0.08) : Qt.alpha("#F9F9F9", 0.5)
        controlPressed: theme.dark ? Qt.alpha("#FFFFFF", 0.03) : Qt.alpha("#F9F9F9", 0.3)
        controlBorder: theme.dark ? Qt.alpha("#FFFFFF", 0.07) : Qt.alpha("#000000", 0.06)
        smoke: Qt.alpha("#000000", 0.3)
        // The accent colour set in Windows
        accent: theme.system.accent
        success: theme.dark ? "#6CCB5F" : "#0F7B0F"
        warning: theme.dark ? "#FCE100" : "#9D5D00"
        critical: theme.dark ? "#FF99A4" : "#C42B1C"
    }

    // Fonts are given part by part: a theme file that sets one part keeps the others
    readonly property Bar bar: Bar {
        background: Qt.alpha(theme.colors.background, 0.85)
        border: theme.colors.border
        font.family: "Segoe UI"
        font.pixelSize: 13
        iconFont.family: "Segoe Fluent Icons"
        iconFont.pixelSize: 16
    }

    readonly property Popup popup: Popup {
        background: Qt.alpha(theme.colors.background, 0.85)
        border: theme.colors.border
        radius: 8
        gap: 8
        openDuration: 180
        closeDuration: 140
        font.family: "Segoe UI"
        iconFont.family: "Segoe Fluent Icons"
    }

    readonly property Menu menu: Menu {
        background: theme.dark ? "#2C2C2C" : "#F9F9F9"
        border: theme.colors.border
        radius: 8
        font.family: "Segoe UI"
        font.pixelSize: 13
        openDuration: 150
    }
}
