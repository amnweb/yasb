pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// An addon in the grid
ItemDelegate {
    id: card

    required property AddonsState host
    required property var addon
    // install, update or installed
    required property string offer
    required property bool busy

    topPadding: 0
    bottomPadding: 0
    leftPadding: 0
    rightPadding: 0
    topInset: 0
    bottomInset: 0
    leftInset: 0
    rightInset: 0
    hoverEnabled: true

    background: Rectangle {
        radius: 8
        color: card.hovered ? card.host.cardHover : card.host.cardFill
        border.color: card.host.cardStroke

        Behavior on color {
            ColorAnimation {
                duration: 83
            }
        }
    }

    contentItem: ColumnLayout {
        spacing: 0

        RoundedImage {
            Layout.fillWidth: true
            Layout.preferredHeight: width
            Layout.margins: 1
            radius: 7
            roundBottom: false
            source: card.addon.images.length > 0 ? card.addon.images[0] : ""
            fill: card.host.subtleFill
            glyph: card.addon.type === "theme" ? "\uE790" : card.addon.type === "layout" ? "\uE75A"
                : card.addon.type === "config" ? "\uE713" : "\uECA5"
            glyphSize: 40
            glyphColor: card.host.secondaryText
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 12
            Layout.rightMargin: 12
            Layout.topMargin: 10
            Layout.bottomMargin: 12
            spacing: 2

            Label {
                Layout.fillWidth: true
                text: card.addon.title
                font.pixelSize: 14
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: false
                spacing: 8

                Label {
                    Layout.alignment: Qt.AlignVCenter
                    Layout.fillWidth: true
                    text: card.addon.author
                    font.pixelSize: 12
                    color: card.host.secondaryText
                    elide: Text.ElideRight
                }

                // Only once installed
                Label {
                    Layout.alignment: Qt.AlignVCenter
                    visible: card.busy || card.offer !== "install"
                    leftPadding: 8
                    rightPadding: 8
                    topPadding: 1
                    bottomPadding: 1
                    text: card.busy ? qsTr("Working...") : card.offer === "update" ? qsTr("Update") : qsTr("Installed")
                    font.pixelSize: 12
                    color: card.offer === "update" && !card.busy ? card.host.onAccent : palette.windowText
                    background: Rectangle {
                        radius: 4
                        color: card.offer === "update" && !card.busy ? system.accent : card.host.subtleFill
                    }
                }
            }
        }
    }

    SystemPalette {
        id: system
    }
}
