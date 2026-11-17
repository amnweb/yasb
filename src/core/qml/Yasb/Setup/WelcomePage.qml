pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import QtQuick.Layouts
import Yasb
import Yasb.Cloud

// The first page, or what to fix before the setup: a YASB 2 config or a missing icon font
Item {
    id: page

    required property Setup setup
    // One at a time: the font only once the YASB 2 config is gone
    readonly property bool fontMissing: setup.iconFontMissing && !setup.upgrade
    readonly property bool blocked: setup.iconFontMissing || setup.upgrade

    signal setUp()

    // Blurred at reveal 0, sharp at 1
    component Unblur: MultiEffect {
        required property real reveal

        blurEnabled: true
        blurMax: 64
        blurMultiplier: 1
        blur: 1 - reveal
    }

    Item {
        anchors.centerIn: parent
        width: 640
        height: hero.implicitHeight + actions.anchors.topMargin + actions.implicitHeight

        ColumnLayout {
            id: hero

            width: parent.width
            spacing: 0

            Image {
                id: logo

                property real reveal: 0

                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 128
                Layout.preferredHeight: 128
                source: page.setup.iconUrl
                sourceSize: Qt.size(128, 128)
                opacity: reveal
                scale: 0.72 + 0.28 * reveal
                layer.enabled: reveal < 1
                layer.effect: Unblur {
                    reveal: logo.reveal
                }
            }

            Label {
                id: heading

                property real reveal: 0

                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: 24
                text: qsTr("Welcome to YASB")
                font.pixelSize: 42
                font.weight: Font.DemiBold
                opacity: reveal
                transform: Translate {
                    y: 8 * (1 - heading.reveal)
                }
                layer.enabled: reveal < 1
                layer.effect: Unblur {
                    reveal: heading.reveal
                }
            }

            Label {
                id: subtitle

                property real reveal: 0

                Layout.fillWidth: true
                Layout.topMargin: 10
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                color: Qt.alpha(palette.windowText, 0.7)
                font.pixelSize: 14
                text: page.setup.upgrade
                    ? qsTr("Before the setup, your YASB 2 config has to go.")
                    : page.fontMissing
                    ? qsTr("Before the setup, Windows needs one font.")
                    : qsTr("Set up your bar in a few steps. You can change everything later in config.yaml.")
                opacity: reveal
                transform: Translate {
                    y: 8 * (1 - subtitle.reveal)
                }
                layer.enabled: reveal < 1
                layer.effect: Unblur {
                    reveal: subtitle.reveal
                }
            }
        }

        ColumnLayout {
            id: actions

            anchors.top: hero.bottom
            anchors.topMargin: 32
            width: parent.width
            spacing: 16
            opacity: 0

            InfoBar {
                Layout.fillWidth: true
                visible: page.setup.upgrade
                severity: "warning"
                title: qsTr("Your config.yaml is from YASB 2")
                message: qsTr("YASB 3.0 uses a new config format and can't read it. Close YASB, move config.yaml out of %1 or back it up and delete it, then start YASB again.").arg(page.setup.configFolder)
            }

            InfoBar {
                Layout.fillWidth: true
                visible: page.fontMissing
                severity: "warning"
                title: qsTr("Segoe Fluent Icons is missing")
                message: qsTr("YASB draws its icons with this font from Microsoft, which Windows 10 doesn't include. Download it, open the font file and click Install, then restart YASB.")
            }

            Button {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 200
                visible: !page.blocked
                text: qsTr("Get started")
                highlighted: true
                onClicked: page.setUp()
            }

            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                visible: page.blocked
                spacing: 8

                Button {
                    Layout.preferredWidth: 140
                    visible: page.setup.upgrade
                    text: qsTr("Open folder")
                    onClicked: page.setup.open(page.setup.configFolder)
                }

                Button {
                    Layout.preferredWidth: 140
                    visible: page.fontMissing
                    text: qsTr("Download")
                    onClicked: page.setup.open(page.setup.iconFontUrl)
                }

                Button {
                    Layout.preferredWidth: 140
                    visible: page.fontMissing
                    text: qsTr("Restart")
                    highlighted: true
                    onClicked: page.setup.restart()
                }

                Button {
                    Layout.preferredWidth: 140
                    text: qsTr("Close")
                    highlighted: page.setup.upgrade
                    onClicked: page.setup.quit()
                }
            }
        }
    }

    // NumberAnimations, not Animators: on the render thread they halve the blur's frame rate
    ParallelAnimation {
        running: true

        NumberAnimation {
            target: logo
            property: "reveal"
            to: 1
            duration: 1250
            easing.type: Easing.OutCubic
        }

        SequentialAnimation {
            PauseAnimation {
                duration: 500
            }

            NumberAnimation {
                target: heading
                property: "reveal"
                to: 1
                duration: 1000
                easing.type: Easing.OutCubic
            }
        }

        SequentialAnimation {
            PauseAnimation {
                duration: 800
            }

            NumberAnimation {
                target: subtitle
                property: "reveal"
                to: 1
                duration: 1000
                easing.type: Easing.OutCubic
            }
        }

        SequentialAnimation {
            PauseAnimation {
                duration: 1800
            }

            NumberAnimation {
                target: actions
                property: "opacity"
                to: 1
                duration: 400
            }
        }
    }
}
