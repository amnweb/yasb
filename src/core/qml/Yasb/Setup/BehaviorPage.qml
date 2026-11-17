import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb.Cloud

// How the bar acts around windows
SetupPage {
    id: page

    required property Choices choices

    title: qsTr("How your bar behaves")
    description: qsTr("How the bar acts around your windows.")

    SettingCard {
        Layout.fillWidth: true
        heading: qsTr("Always on top")
        description: qsTr("The bar stays above other windows")

        Switch {
            checked: page.choices.alwaysOnTop
            onToggled: page.choices.alwaysOnTop = checked
        }
    }

    SettingCard {
        Layout.fillWidth: true
        heading: qsTr("Hide in fullscreen")
        description: page.choices.alwaysOnTop
            ? qsTr("Hides while a game or video fills the screen")
            : qsTr("Needs Always on top")

        Switch {
            enabled: page.choices.alwaysOnTop
            checked: page.choices.alwaysOnTop && page.choices.hideOnFullscreen
            onToggled: page.choices.hideOnFullscreen = checked
        }
    }

    SettingCard {
        Layout.fillWidth: true
        heading: qsTr("Auto-hide")
        description: {
            switch (page.choices.autoHide) {
            case "always": return qsTr("The bar slides away until the pointer touches its screen edge")
            case "maximized": return qsTr("The bar slides away while a window is maximized")
            default: return qsTr("The bar stays in view")
            }
        }

        ComboBox {
            Layout.preferredWidth: 240
            textRole: "text"
            valueRole: "value"
            model: [
                { value: "never", text: qsTr("Never") },
                { value: "always", text: qsTr("Always") },
                { value: "maximized", text: qsTr("When a window is maximized") }
            ]
            Component.onCompleted: currentIndex = indexOfValue(page.choices.autoHide)
            onActivated: page.choices.autoHide = currentValue
        }
    }

    SettingCard {
        Layout.fillWidth: true
        heading: qsTr("Keep windows off the bar")
        description: page.choices.autoHide === "never"
            ? qsTr("Maximized windows stop at the bar instead of covering it")
            : qsTr("Off while the bar auto-hides")

        Switch {
            enabled: page.choices.autoHide === "never"
            checked: page.choices.autoHide === "never" && page.choices.reserveSpace
            onToggled: page.choices.reserveSpace = checked
        }
    }
}
