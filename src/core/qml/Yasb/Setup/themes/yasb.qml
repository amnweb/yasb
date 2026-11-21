import QtQuick
import Yasb.Themes

// Your theme: every color, font and shape of the bar, its widgets, popups and menus, set to YASB's defaults.
// Change what you like; the bar updates when you save. A value written as "dark ? A : B" is A in dark mode
// and B in light mode. Fonts are Qt fonts, so any part of one can be set, such as weight or letterSpacing.
Theme {
    colors {
        // Text, from the strongest to the weakest
        text: dark ? "#FFFFFF" : Qt.alpha("#000000", 0.894)
        textSecondary: dark ? Qt.alpha("#FFFFFF", 0.773) : Qt.alpha("#000000", 0.62)
        textTertiary: dark ? Qt.alpha("#FFFFFF", 0.53) : Qt.alpha("#000000", 0.447)
        textDisabled: dark ? Qt.alpha("#FFFFFF", 0.365) : Qt.alpha("#000000", 0.36)
        // Text and icons on an accent fill
        textOnAccent: dark ? "#000000" : "#FFFFFF"
        // The base the bar and popups start from, and an area a step darker laid over it
        background: dark ? "#202020" : "#F3F3F3"
        backgroundSecondary: dark ? Qt.alpha("#000000", 0.1) : Qt.alpha("#000000", 0.024)
        // Boxes that hold a group of things, and their outline
        card: dark ? Qt.alpha("#FFFFFF", 0.05) : Qt.alpha("#FFFFFF", 0.7)
        cardBorder: dark ? Qt.alpha("#000000", 0.1) : Qt.alpha("#000000", 0.06)
        // Outer edges of the bar, popups and menus, and lines between the parts of a popup
        border: dark ? "#3A3A3A" : "#D9D9D9"
        divider: dark ? Qt.alpha("#FFFFFF", 0.08) : Qt.alpha("#000000", 0.06)
        // Fills laid over any background: under the pointer, while pressed, and behind the selected item
        hover: dark ? Qt.alpha("#FFFFFF", 0.06) : Qt.alpha("#000000", 0.035)
        pressed: dark ? Qt.alpha("#FFFFFF", 0.04) : Qt.alpha("#000000", 0.024)
        selected: dark ? Qt.alpha("#FFFFFF", 0.06) : Qt.alpha("#000000", 0.035)
        // Buttons: their fill at rest, under the pointer and while pressed, and their outline
        control: dark ? Qt.alpha("#FFFFFF", 0.06) : Qt.alpha("#FFFFFF", 0.7)
        controlHover: dark ? Qt.alpha("#FFFFFF", 0.08) : Qt.alpha("#F9F9F9", 0.5)
        controlPressed: dark ? Qt.alpha("#FFFFFF", 0.03) : Qt.alpha("#F9F9F9", 0.3)
        controlBorder: dark ? Qt.alpha("#FFFFFF", 0.07) : Qt.alpha("#000000", 0.06)
        smoke: Qt.alpha("#000000", 0.3)
        // The accent color set in Windows; a color such as "#4CC2FF" replaces it
        accent: system.accent
        success: dark ? "#6CCB5F" : "#0F7B0F"
        warning: dark ? "#FCE100" : "#9D5D00"
        critical: dark ? "#FF99A4" : "#C42B1C"
    }

    bar {
        background: Qt.alpha(colors.background, 0.85)
        border: colors.border
        // Widget labels on the bar
        font.family: "Segoe UI"
        font.pixelSize: 13
        // Widget icons on the bar
        iconFont.family: "Segoe Fluent Icons"
        iconFont.pixelSize: 16
    }

    popup {
        background: Qt.alpha(colors.background, 0.85)
        border: colors.border
        radius: 8
        // Between the bar and the popup
        gap: 8
        // Milliseconds
        openDuration: 180
        closeDuration: 140
        font.family: "Segoe UI"
        // Icons in popups
        iconFont.family: "Segoe Fluent Icons"
    }

    // Right-click menus
    menu {
        background: dark ? "#2C2C2C" : "#F9F9F9"
        border: colors.border
        radius: 8
        font.family: "Segoe UI"
        font.pixelSize: 13
        // Milliseconds the menu takes to fade in
        openDuration: 150
    }
}
