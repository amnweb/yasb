pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Yasb

Window {
    id: window

    required property Addons addons

    // Set when Windows draws Mica behind the window
    property bool mica: false

    title: qsTr("YASB Addons")
    color: mica ? "transparent" : palette.window
    minimumWidth: 860
    minimumHeight: 540

    Component.onCompleted: {
        width = Math.min(1260, screen.desktopAvailableWidth)
        height = Math.min(740, screen.desktopAvailableHeight)
        x = screen.virtualX + (screen.width - width) / 2
        y = screen.virtualY + (screen.height - height) / 2
    }

    // An item of the rail: an icon, a label and a badge
    component RailItem: AbstractButton {
        id: item

        required property string name
        required property string glyph
        property int badge

        readonly property bool chosen: browsing.section === name && !browsing.searching

        Layout.fillWidth: true
        implicitHeight: 56
        hoverEnabled: true
        onClicked: {
            search.text = ""
            browsing.showSection(name)
        }

        background: Rectangle {
            radius: 6
            color: item.pressed ? browsing.subtlePressed : item.chosen || item.hovered ? browsing.subtleFill
                : Qt.alpha(browsing.subtleFill, 0)

            Behavior on color {
                ColorAnimation {
                    duration: 83
                }
            }

            // Grows from the side the selection comes from, and shrinks toward the side it goes to
            Rectangle {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                width: 3
                height: 16
                radius: 1.5
                color: system.accent
                transform: Scale {
                    origin.y: item.chosen === window.selectionDown ? 0 : 16
                    yScale: item.chosen ? 1 : 0

                    Behavior on yScale {
                        SequentialAnimation {
                            PauseAnimation {
                                duration: item.chosen ? 100 : 0
                            }

                            NumberAnimation {
                                duration: 167
                                easing.type: Easing.BezierSpline
                                easing.bezierCurve: browsing.decelerate
                            }
                        }
                    }
                }
            }
        }

        contentItem: Item {
            Column {
                anchors.centerIn: parent
                spacing: 4

                Glyph {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: item.glyph
                    font.pixelSize: 20
                    color: item.chosen ? system.accent : palette.windowText
                    scale: item.pressed ? 0.86 : 1

                    Behavior on color {
                        ColorAnimation {
                            duration: 83
                        }
                    }

                    Behavior on scale {
                        NumberAnimation {
                            duration: 120
                            easing.type: Easing.BezierSpline
                            easing.bezierCurve: browsing.decelerate
                        }
                    }
                }

                Label {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: item.text
                    font.pixelSize: 10
                    color: item.pressed ? browsing.tertiaryText : item.chosen ? palette.windowText : browsing.secondaryText

                    Behavior on color {
                        ColorAnimation {
                            duration: 83
                        }
                    }
                }
            }

            Label {
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.top: parent.top
                anchors.topMargin: 6
                height: 16
                width: Math.max(16, implicitWidth)
                visible: item.badge > 0
                leftPadding: 4
                rightPadding: 4
                text: item.badge
                font.pixelSize: 11
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                color: browsing.onAccent
                background: Rectangle {
                    radius: 8
                    color: system.accent
                }
            }
        }
    }

    SystemPalette {
        id: system
    }

    // The rail's sections in order, and whether the selection last moved down it
    readonly property list<string> railOrder: ["all", "widget", "theme", "layout", "config", "installed"]
    property bool selectionDown: true
    property string lastSection: "all"

    Connections {
        target: browsing

        function onSectionChanged() {
            window.selectionDown = window.railOrder.indexOf(browsing.section) > window.railOrder.indexOf(window.lastSection)
            window.lastSection = browsing.section
        }
    }

    AddonsState {
        id: browsing

        addons: window.addons
        query: search.text
        onLinkRequested: linkDialog.start()
        onActRequested: (addon, version) => {
            const run = () => browsing.action(addon) === "update" && version === 0 ? window.addons.update(addon.id)
                : window.addons.install(addon.id, version)
            if (addon.type === "config")
                configDialog.ask(addon.title, run)
            else
                run()
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        ColumnLayout {
            Layout.fillWidth: false
            Layout.preferredWidth: 68
            Layout.fillHeight: true
            Layout.margins: 4
            spacing: 4

            RailItem {
                name: "all"
                glyph: "\uE80F"
                text: qsTr("Browse")
            }

            RailItem {
                name: "widget"
                glyph: "\uECA5"
                text: qsTr("Widgets")
            }

            RailItem {
                name: "theme"
                glyph: "\uE790"
                text: qsTr("Themes")
            }

            RailItem {
                name: "layout"
                glyph: "\uE75A"
                text: qsTr("Layouts")
            }

            RailItem {
                name: "config"
                glyph: "\uE713"
                text: qsTr("Configs")
            }

            Item {
                Layout.fillHeight: true
            }

            RailItem {
                name: "installed"
                glyph: "\uE896"
                text: qsTr("Installed")
                badge: window.addons.installed.filter(row => row.update > 0).length
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            topLeftRadius: 8
            color: browsing.dark ? Qt.alpha("#3a3a3a", 0.3) : Qt.alpha("#ffffff", 0.5)
            border.color: browsing.cardStroke

            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: 16
                spacing: 4

                Field {
                    id: search

                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: Math.min(440, parent.width - 48)
                    rightPadding: 36
                    placeholderText: qsTr("Search addons")
                    maximumLength: 24
                    onTextChanged: browsing.shown = null

                    Glyph {
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: "\uE721"
                        font.pixelSize: 12
                        color: browsing.secondaryText
                    }
                }

                StackLayout {
                    id: pages

                    // Each change slides the page in, or zooms it in when an addon opens
                    readonly property string view: [browsing.addons.state,
                        browsing.shown ? "addon" : browsing.searching ? "search" : browsing.section].join()
                    // The view is set once while the window is built, which must not slide in
                    property bool built: false

                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: browsing.shown ? 2 : browsing.section === "installed" && !browsing.searching ? 1 : 0
                    transform: [
                        Translate {
                            id: shift
                        },
                        Scale {
                            id: zoom

                            origin.x: pages.width / 2
                            origin.y: pages.height / 2
                        }
                    ]
                    Component.onCompleted: built = true
                    onViewChanged: {
                        if (!built)
                            return
                        entrance.complete()
                        drillIn.complete()
                        if (browsing.shown)
                            drillIn.restart()
                        else
                            entrance.restart()
                    }

                    // Not an OpacityAnimator, which halves the frame rate
                    ParallelAnimation {
                        id: entrance

                        NumberAnimation {
                            target: pages
                            property: "opacity"
                            from: 0
                            to: 1
                            duration: 250
                        }

                        NumberAnimation {
                            target: shift
                            property: "y"
                            from: 24
                            to: 0
                            duration: 250
                            easing.type: Easing.BezierSpline
                            easing.bezierCurve: browsing.decelerate
                        }
                    }

                    ParallelAnimation {
                        id: drillIn

                        NumberAnimation {
                            target: pages
                            property: "opacity"
                            from: 0
                            to: 1
                            duration: 250
                        }

                        NumberAnimation {
                            target: zoom
                            properties: "xScale,yScale"
                            from: 0.94
                            to: 1
                            duration: 250
                            easing.type: Easing.BezierSpline
                            easing.bezierCurve: browsing.decelerate
                        }
                    }

                    BrowsePage {
                        host: browsing
                        arriving: entrance.running
                    }

                    InstalledPage {
                        host: browsing
                    }

                    DetailPage {
                        host: browsing
                        addon: browsing.shown
                    }
                }
            }
        }
    }

    Dialog {
        id: configDialog

        property string addonTitle
        property var accepted: null

        function ask(title: string, run: var) {
            addonTitle = title
            accepted = run
            open()
        }

        anchors.centerIn: Overlay.overlay
        width: Math.min(460, window.width - 48)
        modal: true
        title: qsTr("Install %1?").arg(addonTitle)
        onAccepted: accepted()

        footer: DialogButtonBox {
            Button {
                text: qsTr("Replace my config")
                highlighted: true
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
            }

            Button {
                text: qsTr("Cancel")
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
            }
        }

        Label {
            width: configDialog.availableWidth
            text: qsTr("%1 replaces your whole config. Yours is saved first as a ZIP file in yasb-backups. YASB stops "
                + "while the folder is swapped and starts again afterwards.").arg(configDialog.addonTitle)
            wrapMode: Text.Wrap
        }
    }

    // In two steps: the link, then the addon it holds
    Dialog {
        id: linkDialog

        property var manifest: ({})
        property bool checking: false
        property string error
        readonly property bool found: manifest.id !== undefined
        readonly property int installedVersion: found ? browsing.installedRow(manifest.id)?.version ?? 0 : 0

        function start() {
            manifest = {}
            checking = false
            error = ""
            link.text = ""
            open()
            link.forceActiveFocus()
        }

        function check() {
            if (checking || link.text.trim() === "")
                return
            error = ""
            checking = true
            window.addons.checkLink(link.text)
        }

        function install() {
            const checked = manifest
            close()
            if (checked.type === "config")
                configDialog.ask(checked.title, () => window.addons.installLink(checked))
            else
                window.addons.installLink(checked)
        }

        function back() {
            manifest = {}
            link.forceActiveFocus()
        }

        anchors.centerIn: Overlay.overlay
        width: Math.min(480, window.width - 48)
        modal: true
        title: found ? qsTr("Install %1?").arg(manifest.title) : qsTr("Install from a GitHub link")

        // Without roles the buttons keep this order and close nothing themselves
        footer: DialogButtonBox {
            defaultButton: primary

            Button {
                id: primary

                text: linkDialog.found ? qsTr("Install") : qsTr("Check")
                enabled: linkDialog.found ? browsing.canStart(linkDialog.manifest.type)
                    : !linkDialog.checking && link.text.trim() !== ""
                onClicked: linkDialog.found ? linkDialog.install() : linkDialog.check()

                // Beside the label, which stays
                BusyIndicator {
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    width: 16
                    height: 16
                    visible: running
                    running: linkDialog.checking
                }
            }

            Button {
                text: linkDialog.found ? qsTr("Back") : qsTr("Cancel")
                onClicked: linkDialog.found ? linkDialog.back() : linkDialog.close()
            }
        }

        ColumnLayout {
            width: linkDialog.availableWidth
            spacing: 0

            ColumnLayout {
                visible: !linkDialog.found
                spacing: 0

                Label {
                    Layout.fillWidth: true
                    text: qsTr("Paste the link of a GitHub repository that holds an addon with a manifest.json.")
                    wrapMode: Text.Wrap
                }

                Label {
                    Layout.topMargin: 12
                    text: qsTr("Repository link")
                }

                Field {
                    id: link

                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    onTextChanged: linkDialog.error = ""
                    onAccepted: linkDialog.check()
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    visible: linkDialog.error !== ""
                    spacing: 6

                    Glyph {
                        Layout.alignment: Qt.AlignTop
                        Layout.topMargin: 2
                        text: "\uE783"
                        font.pixelSize: 12
                        color: browsing.criticalText
                    }

                    Label {
                        Layout.fillWidth: true
                        text: linkDialog.error
                        font.pixelSize: 12
                        color: browsing.criticalText
                        wrapMode: Text.Wrap
                    }
                }
            }

            ColumnLayout {
                visible: linkDialog.found
                spacing: 12

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: addonInfo.implicitHeight + 24
                    radius: 8
                    color: browsing.cardFill
                    border.color: browsing.cardStroke

                    RowLayout {
                        id: addonInfo

                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 12

                        Rectangle {
                            Layout.alignment: Qt.AlignTop
                            Layout.preferredWidth: 32
                            Layout.preferredHeight: 32
                            radius: 4
                            color: browsing.subtleFill

                            Glyph {
                                anchors.centerIn: parent
                                text: linkDialog.manifest.type === "theme" ? "\uE790"
                                    : linkDialog.manifest.type === "layout" ? "\uE75A"
                                    : linkDialog.manifest.type === "config" ? "\uE713" : "\uECA5"
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Label {
                                Layout.fillWidth: true
                                text: linkDialog.manifest.title ?? ""
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }

                            Label {
                                Layout.fillWidth: true
                                text: linkDialog.found ? [browsing.typeName(linkDialog.manifest.type),
                                    qsTr("Version %1").arg(linkDialog.manifest.version), linkDialog.manifest.id]
                                    .join("  ·  ") : ""
                                font.pixelSize: 12
                                color: browsing.secondaryText
                                elide: Text.ElideRight
                            }

                            Label {
                                Layout.fillWidth: true
                                Layout.topMargin: 4
                                text: linkDialog.manifest.description ?? ""
                                wrapMode: Text.Wrap
                            }

                            RowLayout {
                                Layout.topMargin: 4
                                spacing: 4

                                Label {
                                    Layout.alignment: Qt.AlignVCenter
                                    text: (linkDialog.manifest.link ?? "").replace("https://", "")
                                    font.pixelSize: 12
                                    font.underline: repositoryHover.hovered
                                    color: system.accent
                                }

                                Glyph {
                                    Layout.alignment: Qt.AlignVCenter
                                    text: "\uE8A7"
                                    font.pixelSize: 12
                                    color: system.accent
                                }

                                HoverHandler {
                                    id: repositoryHover

                                    cursorShape: Qt.PointingHandCursor
                                }

                                TapHandler {
                                    onTapped: window.addons.open(linkDialog.manifest.link)
                                }
                            }
                        }
                    }
                }

                Label {
                    Layout.fillWidth: true
                    visible: linkDialog.manifest.exists === true
                    text: linkDialog.installedVersion > 0
                        ? qsTr("You have version %1. This replaces it.").arg(linkDialog.installedVersion)
                        : qsTr("This replaces the copy you have.")
                    wrapMode: Text.Wrap
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: warningText.implicitHeight + 24
                    radius: 4
                    color: browsing.cautionBackground
                    border.color: browsing.cardStroke

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 10

                        Glyph {
                            Layout.alignment: Qt.AlignTop
                            Layout.topMargin: 2
                            text: "\uE7BA"
                            color: browsing.cautionText
                        }

                        Label {
                            id: warningText

                            Layout.fillWidth: true
                            text: qsTr("<b>Not reviewed by YASB.</b> It runs with your user rights and can change your "
                                + "files. Install it only if you trust the author.")
                            textFormat: Text.StyledText
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: messageDialog

        property string message
        // The messages that came while one was open, each [title, message]
        property var waiting: []

        function tell(heading: string, text: string) {
            if (visible) {
                waiting = [...waiting, [heading, text]]
                return
            }
            title = heading
            message = text
            open()
        }

        anchors.centerIn: Overlay.overlay
        width: Math.min(460, window.width - 48)
        modal: true
        standardButtons: Dialog.Ok
        onClosed: {
            if (waiting.length > 0) {
                const [heading, text] = waiting[0]
                waiting = waiting.slice(1)
                tell(heading, text)
            }
        }

        Label {
            width: messageDialog.availableWidth
            text: messageDialog.message
            wrapMode: Text.Wrap
        }
    }

    Connections {
        target: window.addons

        function onMessageRequested(title: string, message: string) {
            messageDialog.tell(title, message)
        }

        function onLinkChecked(manifest: var) {
            // The dialog was closed or opened again since
            if (!linkDialog.checking)
                return
            linkDialog.checking = false
            linkDialog.error = manifest.error ?? ""
            linkDialog.manifest = manifest.error === undefined ? manifest : {}
        }
    }
}
