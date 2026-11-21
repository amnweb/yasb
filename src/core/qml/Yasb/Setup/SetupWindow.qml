pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb
import Yasb.Cloud

// Shown when config.yaml is missing or from YASB 2
Window {
    id: window

    required property Setup setup

    // Set when Windows draws Mica behind the window
    property bool mica: false
    property string error: ""

    readonly property Choices choices: Choices {
        backdropSupported: window.setup.backdropSupported
        manifests: window.setup.widgets
        autostart: window.setup.canAutostart
    }
    readonly property bool lastPage: pages.currentIndex === pages.count - 1

    // A link with the open in new window icon
    component ExternalLink: LinkButton {
        id: link

        contentItem: RowLayout {
            spacing: 6

            Label {
                text: link.text
                font: link.font
                color: link.palette.buttonText
            }

            Label {
                text: "\uE8A7"
                font.family: "Segoe Fluent Icons"
                font.pixelSize: 13
                color: link.palette.buttonText
            }
        }
    }

    function finish(): void {
        error = setup.finish(choices.toSetup())
        if (error === "")
            close()
        else
            pages.currentIndex = pages.count - 1
    }

    title: qsTr("Welcome to YASB")
    flags: Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint
        | Qt.MSWindowsFixedSizeDialogHint
 
    color: mica ? "transparent" : palette.window
    width: 1000
    height: 620

    Component.onCompleted: {
        x = screen.virtualX + (screen.width - width) / 2
        y = screen.virtualY + (screen.height - height) / 2
    }

    SwipeView {
        id: pages

        anchors.fill: parent
        interactive: false
        clip: true

        WelcomePage {
            setup: window.setup
            onSetUp: pages.currentIndex = 1
        }

        BarPage {
            setup: window.setup
            choices: window.choices
        }

        BehaviorPage {
            choices: window.choices
        }

        WidgetsPage {
            choices: window.choices
        }

        DonePage {
            setup: window.setup
            choices: window.choices
            error: window.error
        }
    }

    // The last page's links
    RowLayout {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        // The page's margin minus the links' padding
        anchors.leftMargin: 16
        anchors.bottomMargin: 24
        spacing: 4
        enabled: window.lastPage
        opacity: enabled ? 1 : 0

        Behavior on opacity {
            NumberAnimation {
                duration: 250
            }
        }

        ExternalLink {
            text: qsTr("Documentation")
            onClicked: window.setup.open(window.setup.docsUrl)
        }

        ExternalLink {
            text: qsTr("YASB Cloud")
            onClicked: window.setup.open(window.setup.cloudUrl)
        }
    }

    // Back and Next, from the second page on
    RowLayout {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 24
        spacing: 8
        enabled: pages.currentIndex > 0
        opacity: enabled ? 1 : 0

        // Not an OpacityAnimator, which halves the slide's frame rate
        Behavior on opacity {
            NumberAnimation {
                duration: 250
            }
        }

        Button {
            Layout.preferredWidth: 120
            text: qsTr("Back")
            onClicked: {
                window.error = ""
                pages.currentIndex--
            }
        }

        Button {
            Layout.preferredWidth: 120
            text: window.lastPage ? qsTr("Finish") : qsTr("Next")
            highlighted: true
            onClicked: {
                if (window.lastPage)
                    window.finish()
                else
                    pages.currentIndex++
            }
        }
    }
}
