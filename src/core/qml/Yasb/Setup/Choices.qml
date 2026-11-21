import QtQuick

// What the user picks in the setup, starting from these defaults
QtObject {
    id: choices

    property bool backdropSupported: false
    // YASB's widgets by name, each with its title and description
    property var manifests: ({})

    // top or bottom: widgets aren't made for a vertical bar yet
    property string edge: "top"
    // bar, floating or islands
    property string barStyle: "bar"
    property int thickness: 40
    // * or primary
    property string screens: "*"
    property bool backdrop: backdropSupported
    property bool alwaysOnTop: true
    // Only with alwaysOnTop
    property bool hideOnFullscreen: false
    // never, always or maximized
    property string autoHide: "never"
    // Only when the bar never auto-hides
    property bool reserveSpace: true
    property bool updateCheck: true
    property bool autostart: false

    // name, icon, position, on the bar by default
    readonly property var offered: [
        ["KomorebiWorkspaces", "\uECA5", "left", false],
        ["GlazewmWorkspaces", "\uECA5", "left", false],
        ["WindowsDesktops", "\uE7C4", "left", false],
        ["Taskbar", "\uE90E", "left", false],
        ["ActiveWindow", "\uECAA", "left", true],
        ["Clock", "\uEC92", "center", true],
        ["Weather", "\uE753", "center", false],
        ["Media", "\uE8D6", "right", true],
        ["AudioVisualizer", "\uE9E9", "right", false],
        ["Cpu", "\uEEA1", "right", false],
        ["Memory", "\uEEA0", "right", false],
        ["Gpu", "\uF211", "right", false],
        ["NetworkTraffic", "\uEDA3", "right", false],
        ["Systray", "\uE70E", "right", true],
        ["Language", "\uE765", "right", false],
        ["Bluetooth", "\uE702", "right", false],
        ["Network", "\uE701", "right", true],
        ["Volume", "\uE767", "right", true],
        ["Microphone", "\uE720", "right", false],
        ["Brightness", "\uE706", "right", false],
        ["Battery", "\ueba6", "right", false],
        ["PowerPlan", "\uE945", "right", false],
        ["Updates", "\uE896", "right", false],
        ["Github", "\uE943", "right", false],
        ["ServerMonitor", "\uf760", "right", false],
        ["Obs", "\uE7C8", "right", false],
        ["Wallpapers", "\uE91B", "right", false],
        ["WindowSwitcher", "\uf156", "right", false],
        ["Launchpad", "\ue8a9", "right", false],
        ["QuickLaunch", "\uE721", "right", false],
        ["Dnd", "\uE708", "right", false],
        ["Notifications", "\uE7E7", "right", true],
        ["PowerMenu", "\uE7E8", "right", true]
    ]

    // A header row for each position, followed by its widgets
    readonly property ListModel widgets: ListModel {}

    function chosenWidgets(): var {
        const chosen = { left: [], center: [], right: [] }
        let position = "left"
        for (let index = 0; index < widgets.count; index++) {
            const row = widgets.get(index)
            if (row.header)
                position = row.name
            else
                chosen[position].push(row.name)
        }
        return chosen
    }

    // The offered widgets that aren't on the bar
    function available(): var {
        const shown = new Set()
        for (let index = 0; index < widgets.count; index++)
            shown.add(widgets.get(index).name)
        return offered.filter(widget => !shown.has(widget[0])).map(widget => widgetRow(widget))
    }

    function addWidget(position: string, name: string): void {
        let index = 0
        while (!(widgets.get(index).header && widgets.get(index).name === position))
            index++
        index++
        while (index < widgets.count && !widgets.get(index).header)
            index++
        widgets.insert(index, widgetRow(offered.find(widget => widget[0] === name)))
    }

    // Never above the first header
    function moveWidget(from: int, to: int): void {
        if (to >= 1 && to < widgets.count && to !== from)
            widgets.move(from, to, 1)
    }

    function widgetRow(widget: var): var {
        const manifest = manifests[widget[0]]
        return { header: false, name: widget[0], title: manifest.title, description: manifest.description, icon: widget[1] }
    }

    function toSetup(): var {
        return {
            edge: edge,
            style: barStyle,
            thickness: thickness,
            screens: screens,
            backdrop: backdrop,
            alwaysOnTop: alwaysOnTop,
            hideOnFullscreen: alwaysOnTop && hideOnFullscreen,
            autoHide: autoHide,
            reserveSpace: autoHide === "never" && reserveSpace,
            widgets: chosenWidgets(),
            updateCheck: updateCheck,
            autostart: autostart
        }
    }

    Component.onCompleted: {
        const positions = [["left", qsTr("Left")], ["center", qsTr("Center")], ["right", qsTr("Right")]]
        for (const [position, heading] of positions) {
            widgets.append({ header: true, name: position, title: heading, description: "", icon: "" })
            for (const widget of offered) {
                if (widget[2] === position && widget[3])
                    widgets.append(widgetRow(widget))
            }
        }
    }
}
