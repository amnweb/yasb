import QtQuick

// What the user picks in the setup, starting from these defaults
QtObject {
    id: choices

    property bool backdropSupported: false

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

    // name, title, description, icon, position, on the bar by default
    readonly property var offered: [
        ["KomorebiWorkspaces", qsTr("Komorebi workspaces"), qsTr("Workspaces of the Komorebi tiling window manager"), "\uECA5", "left", false],
        ["GlazewmWorkspaces", qsTr("GlazeWM workspaces"), qsTr("Workspaces of the GlazeWM tiling window manager"), "\uECA5", "left", false],
        ["WindowsDesktops", qsTr("Virtual desktops"), qsTr("Your Windows virtual desktops"), "\uE7C4", "left", false],
        ["Taskbar", qsTr("Taskbar"), qsTr("Your pinned and open apps, like the Windows taskbar"), "\uE90E", "left", false],
        ["ActiveWindow", qsTr("Active window"), qsTr("The window you're working in"), "\uECAA", "left", true],
        ["Clock", qsTr("Clock"), qsTr("The time and date"), "\uEC92", "center", true],
        ["Weather", qsTr("Weather"), qsTr("The weather for your location"), "\uE753", "center", false],
        ["Media", qsTr("Media"), qsTr("What's playing on your PC"), "\uE8D6", "right", true],
        ["AudioVisualizer", qsTr("Audio visualizer"), qsTr("An animation that moves with the sound playing"), "\uE9E9", "right", false],
        ["Cpu", qsTr("CPU"), qsTr("Your processor usage"), "\uEEA1", "right", false],
        ["Memory", qsTr("Memory"), qsTr("Your memory usage"), "\uEEA0", "right", false],
        ["Gpu", qsTr("GPU"), qsTr("Your graphics card usage"), "\uF211", "right", false],
        ["NetworkTraffic", qsTr("Network traffic"), qsTr("Your download and upload speed"), "\uEDA3", "right", false],
        ["Systray", qsTr("System tray"), qsTr("The tray icons of apps running in the background"), "\uE70E", "right", true],
        ["Language", qsTr("Keyboard language"), qsTr("Your keyboard layout"), "\uE765", "right", false],
        ["Bluetooth", qsTr("Bluetooth"), qsTr("Bluetooth and your paired devices"), "\uE702", "right", false],
        ["Network", qsTr("Network"), qsTr("Your network connection"), "\uE701", "right", true],
        ["Volume", qsTr("Volume"), qsTr("Your sound volume"), "\uE767", "right", true],
        ["Microphone", qsTr("Microphone"), qsTr("Your microphone"), "\uE720", "right", false],
        ["Brightness", qsTr("Brightness"), qsTr("Your screen brightness"), "\uE706", "right", false],
        ["Battery", qsTr("Battery"), qsTr("Your battery level"), "\ueba6", "right", false],
        ["PowerPlan", qsTr("Power plan"), qsTr("The Windows power plan"), "\uE945", "right", false],
        ["Updates", qsTr("Updates"), qsTr("Available updates for Windows and your apps"), "\uE896", "right", false],
        ["Github", qsTr("GitHub"), qsTr("Your GitHub notifications"), "\uE943", "right", false],
        ["ServerMonitor", qsTr("Server monitor"), qsTr("Whether your servers and websites are online"), "\uf760", "right", false],
        ["Obs", qsTr("OBS"), qsTr("Recording and streaming in OBS Studio"), "\uE7C8", "right", false],
        ["Wallpapers", qsTr("Wallpapers"), qsTr("A gallery of your wallpapers"), "\uE91B", "right", false],
        ["QuickLaunch", qsTr("Quick Launch"), qsTr("A search launcher for your apps, files and more"), "\uE721", "right", false],
        ["Dnd", qsTr("Do not disturb"), qsTr("Windows' do not disturb, off, priority only or alarms only"), "\uE708", "right", false],
        ["Notifications", qsTr("Notifications"), qsTr("Your Windows notifications menu"), "\uE7E7", "right", true],
        ["PowerMenu", qsTr("Power menu"), qsTr("A power menu to lock, sign out, sleep, restart or shut down"), "\uE7E8", "right", true]
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
        return offered.filter(widget => !shown.has(widget[0]))
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
        return { header: false, name: widget[0], title: widget[1], description: widget[2], icon: widget[3] }
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
                if (widget[4] === position && widget[5])
                    widgets.append(widgetRow(widget))
            }
        }
    }
}
