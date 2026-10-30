import QtQuick
import QtQuick.Controls

Button {
    implicitWidth: implicitContentWidth + leftPadding + rightPadding
    flat: true
    leftPadding: 8
    rightPadding: 8
    palette.buttonText: system.accent

    SystemPalette {
        id: system
    }
}
