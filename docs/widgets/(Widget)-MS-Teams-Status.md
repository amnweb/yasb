# Microsoft Teams Status Widget Options

Displays your Microsoft Teams presence in the status bar as a coloured status dot, with optional status text and unread notification count. Clicking the widget can open a status card where you can change your presence (Available, Away, Be Right Back, Busy, Do Not Disturb, Offline) or reset it so Teams manages it automatically.

> **Note:** This widget works with the new Microsoft Teams (the Microsoft Store / MSIX app). Classic Teams is not supported. No sign-in or API token is required, the widget reads the status from the Teams log files and changes it through the Teams command line.

| Option | Type | Default                                                                                                                                                                                                                                                                                                                   | Description |
|--------|------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|
| `label`           | string  | `'{dot}'`                                                                                                                                                                                                                                                                                                                 | The format string for the label. See [Label Placeholders](#label-placeholders). |
| `label_alt`       | string  | `"{dot} {status_text} <span class='bell'>\uf0f3</span> {unread_notifs}"`                                                                                                                                                                                                                                                                                  | The alternative format string for the label, shown after calling the `toggle_label` callback. |
| `class_name`      | string  | `'ms_teams_status'`                                                                                                                                                                                                                                                                                                       | Additional CSS class added to the widget. |
| `update_interval` | integer | `10000`                                                                                                                                                                                                                                                                                                                   | How often, in milliseconds, the Teams logs are read for a new status. Must be between 1000 and 60000. |
| `tooltip`         | boolean | `true`                                                                                                                                                                                                                                                                                                                    | Whether to show the current status in a tooltip on hover. |
| `status_colours`  | dict    | See [Statuses](#statuses)                                                                                                                                                                                                                                                                                                 | Colour of the status dot for each status. |
| `status_icons`    | dict    | See [Statuses](#statuses)                                                                                                                                                                                                                                                                                                 | Icon used as the status dot for each status. |
| `status_card`     | dict    | `{'blur': true, 'round_corners': true, 'round_corners_type': 'normal', 'border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0, 'columns': 1, 'pinnable': false, 'display_current_info': true, 'show_icons': true, 'icons_before_status': true, 'section_dividers': true}` | Settings for the status card popup. |
| `callbacks`       | dict    | `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'toggle_label'}`                                                                                                                                                                                                                                      | Callbacks for mouse events on the widget. |

```yaml
ms_teams_status:
  type: "yasb.ms_teams_status.MSTeamsStatusWidget"
  options:
    label: "{dot}"
    label_alt: "{dot} {status_text} {unread_notifs}"
    update_interval: 10000 # How often to read the Teams logs, in milliseconds (1000 - 60000)
    tooltip: true
    status_colours: # Only the statuses you want to change need to be listed
      available: "#92C353"
      busy: "#C4314B"
    status_icons:
      offline: "\u25cf"
    status_card:
      blur: true # Enable blur effect for the card
      round_corners: true # Enable round corners for the card (this option is not supported on Windows 10)
      round_corners_type: "normal" # Set the type of round corners for the card (normal, small) (this option is not supported on Windows 10)
      border_color: "System" # Set the border color for the card (this option is not supported on Windows 10)
      alignment: "right"
      direction: "down"
      offset_top: 6
      offset_left: 0
      columns: 1 # Number of columns in the status grid
      pinnable: false # Open the card pinned, so it stays open until you pick a status or click the widget again
      display_current_info: true # Show the current status and unread count at the top of the card
      show_icons: true # Show a status dot next to each option
      icons_before_status: true # Place the dot before the status text instead of after it
      section_dividers: true # Draw a line between the card sections
    callbacks:
      on_left: "toggle_card"
      on_middle: "do_nothing"
      on_right: "toggle_label"
```

## Label Placeholders

The `label` and `label_alt` options support the following placeholders:

| Placeholder | Output Example | Description |
|-------------|----------------|-------------|
| `{dot}` | `●` | The status icon, coloured using `status_colours`. |
| `{status_text}` | `Available`, `In A Meeting` | The current status as text. |
| `{unread_notifs}` | `3` | The unread notification count reported by Teams. |

The colour of `{dot}` is set inline from the `status_colours` option, so it can't be changed with CSS. On its own, `{dot}` is part of the surrounding label text and follows the `.label` font size. To style it separately, wrap it in a `<span>` as shown below.

### Icons in the label

Any `<span>` you add to `label` or `label_alt` becomes its own element with the span's `class`, or `icon` if it has no class. Only the class is kept. Inline `style` attributes are dropped, so style the span with CSS instead. Span elements don't get the `status-*` classes, so the same style applies to every status.

```yaml
label_alt: "<span class='status-dot'>{dot}</span> {status_text} <span class='bell'>\uf0f3</span> {unread_notifs}"
```

```css
.ms-teams-status-widget .widget-container .status-dot {
    font-size: 12px;
    padding-right: 2px;
}
.ms-teams-status-widget .widget-container .bell {
    font-size: 10px;
}
```

A `{dot}` inside a span keeps its colour from `status_colours`.

## Description of Options

- **label:** The format string for the label. You can use the `{dot}`, `{status_text}` and `{unread_notifs}` placeholders.
- **label_alt:** The alternative format string for the label, shown after calling the `toggle_label` callback.
- **class_name:** Additional CSS class name for the widget. This allows for custom styling.
- **update_interval:** How often, in milliseconds, the widget reads the Teams log files for a new status. Must be between 1000 and 60000.
- **tooltip:** Whether to show the current status in a tooltip on hover.
- **status_colours:** A dictionary mapping each status to the colour of its dot. Colours can be hex or named colours. Any status you leave out keeps its default. See [Statuses](#statuses) for the available keys and defaults. The `reset` key sets the colour of the icon on the card's Reset option.
- **status_icons:** A dictionary mapping each status to the icon used as its dot. Any status you leave out keeps its default. See [Statuses](#statuses) for the available keys and defaults. Two extra keys are available:
  - **reset:** The icon on the card's Reset option.
  - **notification_bell:** The icon shown before the unread count at the top of the card.
- **status_card:** A dictionary specifying the settings for the status card. It contains the following keys:
  - **blur:** Enable blur effect for the card.
  - **round_corners:** Enable round corners for the card (this option is not supported on Windows 10).
  - **round_corners_type:** Set the type of round corners for the card (normal, small) (this option is not supported on Windows 10).
  - **border_color:** Set the border color for the card (this option is not supported on Windows 10).
  - **alignment:** Set the alignment of the card (left, right, center).
  - **direction:** Set the direction of the card (up, down).
  - **offset_top:** Set the vertical offset of the card from the bar.
  - **offset_left:** Set the horizontal offset of the card.
  - **columns:** The number of columns in the grid of status options. Must be at least 1. There are 6 settable statuses, so `1` gives a single list, `2` gives three rows and `3` gives two rows. The Reset option is always shown on its own row below the grid.
  - **pinnable:** When `true`, the card opens pinned: it stays open when you click outside it and can be dragged. It closes when you pick a status or click the widget again. When `false`, the card also closes when you click outside it or switch to another window.
  - **display_current_info:** Show the current status and the unread notification count at the top of the card. This section is left out until the widget has read a status from the Teams logs.
  - **show_icons:** Show the status dot next to each option in the card.
  - **icons_before_status:** Place the status dot before the status text instead of after it.
  - **section_dividers:** Draw a divider between the current info, the status grid and the Reset option.
- **callbacks:** A dictionary specifying the callbacks for mouse events. It contains the following keys:
  - **on_left:** The name of the callback function for left mouse button click.
  - **on_middle:** The name of the callback function for middle mouse button click.
  - **on_right:** The name of the callback function for right mouse button click.

## Callbacks

| Callback | Description |
|----------|-------------|
| `toggle_card` | Opens or closes the status card. |
| `toggle_label` | Toggles between `label` and `label_alt`. |
| `update_label` | Reads the Teams logs and refreshes the label straight away, without waiting for the next update. |
| `do_nothing` | Does nothing. |

## Statuses

Each status has a key used in `status_colours` and `status_icons`, and a CSS class added to the widget label. Only the statuses marked as settable appear in the status card. The others are set by Teams itself, for example when you join a meeting or call, and are only displayed.

| Key | Status text | CSS class | Settable | Default colour | Default icon |
|-----|-------------|-----------|----------|----------------|--------------|
| `available`      | Available      | `status-available`      | Yes | `#92C353` | `●` ● |
| `available_idle` | Available Idle | `status-available-idle` | No  | `#92C353` | `●` ● |
| `away`           | Away           | `status-away`           | Yes | `#F8D22A` | `●` ● |
| `be_right_back`  | Be Right Back  | `status-be-right-back`  | Yes | `#F8D22A` | `●` ● |
| `busy`           | Busy           | `status-busy`           | Yes | `#C4314B` | `●` ● |
| `in_a_meeting`   | In A Meeting   | `status-in-a-meeting`   | No  | `#C4314B` | `●` ● |
| `in_a_call`      | In A Call      | `status-in-a-call`      | No  | `#C4314B` | `●` ● |
| `presenting`     | Presenting     | `status-presenting`     | No  | `#C4314B` | `●` ● |
| `on_the_phone`   | On The Phone   | `status-on-the-phone`   | No  | `#C4314B` | `●` ● |
| `do_not_disturb` | Do Not Disturb | `status-do-not-disturb` | Yes | `#C4314B` | `⊖` ⊖ |
| `focusing`       | Focusing       | `status-focusing`       | No  | `#C4314B` | `⊖` ⊖ |
| `offline`        | Offline        | `status-offline`        | Yes | `#8A8886` | `○` ○ |

## How It Works

**Reading the status.** Teams writes your availability and unread notification count to its log files at `%LOCALAPPDATA%\Packages\MSTeams_*\LocalCache\Microsoft\MSTeams\Logs\`. On every update the widget reads the end of the three newest `MSTeams_*.log` files and uses the most recent entries it finds. Teams logs a new entry whenever your presence changes and also on a regular heartbeat, so the widget can still find your status after Teams starts a new log file. If no status is found, the widget keeps showing the last one it knew.

**Changing the status.** When you pick an option in the status card, the widget runs the Teams command line (`ms-teams.exe --set-presence-to-<status>`, or `--reset-presence` for Reset). This needs the `ms-teams` app execution alias, which the new Teams registers when it is installed. The widget shows the status you picked straight away, then skips the next 5 updates (50 seconds with the default `update_interval`) so that an older log entry can't switch it back before Teams logs the change.

**Reset.** Reset clears any status you set manually and lets Teams choose your presence from your activity and calendar. The widget does not guess the new status. It is shown once Teams writes it to the log.

## Troubleshooting

- **The widget shows the raw label text, such as `{dot}`:** No status has been found in the Teams logs yet. Check that the new Teams is installed, running and signed in. The status appears after Teams next writes it to the log.
- **Picking a status in the card does nothing:** Check that the new Teams is installed for your user and that `ms-teams` runs from a terminal. If it doesn't, enable the Microsoft Teams alias under *Settings > Apps > Advanced app settings > App execution aliases*.
- **The status is slow to update:** Lower `update_interval`, or bind the `update_label` callback to a mouse button to refresh on demand.

## Widget Style

```css
.ms-teams-status-widget {}
.ms-teams-status-widget .widget-container {}
.ms-teams-status-widget .widget-container .label {}
.ms-teams-status-widget .widget-container .label.alt {}
.ms-teams-status-widget .widget-container .icon {} /* Parts of the label wrapped in <span> tags without a class. A <span class="..."> uses its own class instead */
/* Status classes, added to the label */
.ms-teams-status-widget .widget-container .label.status-available {}
.ms-teams-status-widget .widget-container .label.status-available-idle {}
.ms-teams-status-widget .widget-container .label.status-away {}
.ms-teams-status-widget .widget-container .label.status-be-right-back {}
.ms-teams-status-widget .widget-container .label.status-busy {}
.ms-teams-status-widget .widget-container .label.status-in-a-meeting {}
.ms-teams-status-widget .widget-container .label.status-in-a-call {}
.ms-teams-status-widget .widget-container .label.status-presenting {}
.ms-teams-status-widget .widget-container .label.status-on-the-phone {}
.ms-teams-status-widget .widget-container .label.status-do-not-disturb {}
.ms-teams-status-widget .widget-container .label.status-focusing {}
.ms-teams-status-widget .widget-container .label.status-offline {}
/* Status card */
.ms-teams-status-card {}
.ms-teams-status-card .current-info {} /* Row at the top of the card, when display_current_info is enabled */
.ms-teams-status-card .current-info .current-status {} /* Current status icon and text */
.ms-teams-status-card .current-info .current-status-icon {} /* Current status icon */
.ms-teams-status-card .current-info .current-status-text-label {} /* "Current status" caption */
.ms-teams-status-card .current-info .current-status-label {} /* Current status text */
.ms-teams-status-card .current-info .current-notification {} /* Unread count */
.ms-teams-status-card .current-info .notification-label {} /* Bell icon and unread count */
.ms-teams-status-card .card-divider {} /* Divider line, when section_dividers is enabled */
.ms-teams-status-card .availability-option {} /* Each status option in the grid, and the Reset option */
.ms-teams-status-card .availability-option:hover {}
.ms-teams-status-card .availability-option.reset {} /* Reset option */
.ms-teams-status-card .availability-option .label-text {} /* Status text of an option */
.ms-teams-status-card .availability-option .label-text.available {}
.ms-teams-status-card .availability-option .label-text.away {}
.ms-teams-status-card .availability-option .label-text.be-right-back {}
.ms-teams-status-card .availability-option .label-text.busy {}
.ms-teams-status-card .availability-option .label-text.do-not-disturb {}
.ms-teams-status-card .availability-option .label-text.offline {}
.ms-teams-status-card .availability-option .label-text.reset {}
.ms-teams-status-card .availability-option .icon-label {} /* Status dot of an option */
```

`.current-info`, `.current-status` and `.current-notification` are containers. They take background, border, padding and margin, but font and colour set on them don't carry through to the labels inside, so set those on the labels directly.

## Example Style

```css
.ms-teams-status-card {
    background-color: var(--yasb-popup-bg);
    padding: 0px;
    font-family: var(--system-font);
    color: var(--yasb-fg);
}

.ms-teams-status-card .availability-option {
    background: var(--yasb-white-alpha-03);
    border-radius: 4px;
    padding-left: 6px;
    padding-right: 6px;
    padding-top: 1.5px;
    padding-bottom: 1.5px;
    min-width: 100px;
}

.ms-teams-status-card .availability-option:hover {
    background: var(--yasb-white-alpha-05);
}

.ms-teams-status-card .availability-option .label-text {
    color: var(--yasb-fg);
}

.ms-teams-status-card .icon-label {
    font-size: 16px;
    margin-right: 5px;
}

.ms-teams-status-card .current-status-icon {
    font-size: 16px;
}


.ms-teams-status-card .current-status-text-label {
    color: rgba(255, 255, 255, 0.5);
    font-size: 10px;
}

.ms-teams-status-card .current-status-label {
    color: var(--yasb-fg);
    font-size: 12px;
    font-weight: 500;
}

.ms-teams-status-card .notification-label {
    padding: 0 6 0 6;
    background-color: var(--yasb-white-alpha-03);
    border-radius: 20px;
}

.ms-teams-status-card .current-info {
    font-size: 16px;
}

.ms-teams-status-card .card-divider {
    background-color: var(--yasb-white-alpha-05);
    min-height: 1px;
    max-height: 1px;      /* min+max pins it to a hairline */
    margin-top: 6px;
    margin-bottom: 6px;
}

.ms-teams-status-card .availability-option.reset {
    margin-top: 0px;
}

.ms-teams-status-widget .bell {
    padding-left: 5px;
    padding-right: 5px;
    font-size: 10px;
}
```

## Preview of the Widget
![Microsoft Teams Status YASB Widget](assets/8af88592-613f-471a-91a8-7812c5a3614d.png)