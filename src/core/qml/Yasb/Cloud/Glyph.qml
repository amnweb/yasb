import QtQuick
import QtQuick.Controls

// An icon from the Windows icon font, which is Segoe MDL2 Assets before Windows 11
Label {
    font.family: Qt.fontFamilies().includes("Segoe Fluent Icons") ? "Segoe Fluent Icons" : "Segoe MDL2 Assets"
    font.pixelSize: 16
}
