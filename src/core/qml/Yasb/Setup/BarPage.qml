import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Cloud

// Where the bar sits and how it looks
SetupPage {
    id: page

    required property Setup setup
    required property Choices choices

    title: qsTr("Your bar")
    description: qsTr("Where the bar sits and how it looks.")

    SettingCard {
        Layout.fillWidth: true
        heading: qsTr("Position")
        description: qsTr("The screen edge the bar sits on")

        ComboBox {
            Layout.preferredWidth: 180
            textRole: "text"
            valueRole: "value"
            model: [
                { value: "top", text: qsTr("Top") },
                { value: "bottom", text: qsTr("Bottom") }
            ]
            Component.onCompleted: currentIndex = indexOfValue(page.choices.edge)
            onActivated: page.choices.edge = currentValue
        }
    }

    SettingCard {
        Layout.fillWidth: true
        heading: qsTr("Style")
        description: {
            switch (page.choices.barStyle) {
            case "floating": return qsTr("Rounded corners, with a small gap to the screen edges")
            case "islands": return qsTr("A thin rail along the edge, with each group of widgets on its own island")
            default: return qsTr("Across the whole screen edge")
            }
        }

        ComboBox {
            Layout.preferredWidth: 180
            textRole: "text"
            valueRole: "value"
            model: [
                { value: "bar", text: qsTr("Full bar") },
                { value: "floating", text: qsTr("Floating") },
                { value: "islands", text: qsTr("Islands") }
            ]
            Component.onCompleted: currentIndex = indexOfValue(page.choices.barStyle)
            onActivated: page.choices.barStyle = currentValue
        }
    }

    SettingCard {
        Layout.fillWidth: true
        heading: qsTr("Thickness")
        description: qsTr("How tall the bar is, in pixels")

        SpinBox {
            Layout.preferredWidth: 180
            from: 20
            to: 64
            value: page.choices.thickness
            onValueModified: page.choices.thickness = value
        }
    }

    SettingCard {
        Layout.fillWidth: true
        heading: qsTr("Screens")
        description: qsTr("The screens that get a bar")

        ComboBox {
            Layout.preferredWidth: 180
            textRole: "text"
            valueRole: "value"
            model: [
                { value: "*", text: qsTr("All screens") },
                { value: "primary", text: qsTr("Main screen only") }
            ]
            Component.onCompleted: currentIndex = indexOfValue(page.choices.screens)
            onActivated: page.choices.screens = currentValue
        }
    }

    SettingCard {
        Layout.fillWidth: true
        heading: qsTr("Blur")
        description: page.setup.backdropSupported
            ? qsTr("Blurs what's behind the bar. Needs Windows 11.")
            : qsTr("Needs Windows 11, so it's off on this PC.")

        Switch {
            enabled: page.setup.backdropSupported
            checked: page.choices.backdrop
            onToggled: page.choices.backdrop = checked
        }
    }
}
