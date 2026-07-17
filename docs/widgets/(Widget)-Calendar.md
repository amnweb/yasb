# Calendar Widget Options

Shows the next upcoming Google Calendar event in the bar. Left-click opens a popup menu listing the next several events with one-click join buttons; middle-click joins the very next meeting (Google Meet, Zoom, Teams) directly.

| Option                  | Type    | Default                                                              | Description |
|-------------------------|---------|----------------------------------------------------------------------|-------------|
| `label`                 | string  | `'{icon} {title} {countdown}'`                                       | Format string for the bar label. Tokens: `{icon}`, `{title}`, `{start_time}`, `{countdown}`, `{status}`, `{meeting_kind}`. |
| `label_alt`             | string  | `'{icon} {title} at {start_time}'`                                   | Alternative label, swapped via `toggle_label`. |
| `class_name`            | string  | `''`                                                                 | Extra CSS class appended to the widget frame. |
| `update_interval`       | integer | `60`                                                                 | Seconds between Google Calendar API polls. Range 15–3600. |
| `tick_interval`         | integer | `1000`                                                               | Milliseconds between countdown re-renders (no API call). Range 250–60000. |
| `calendar_ids`          | list    | `['primary']`                                                        | Calendar IDs to read. Events from all listed calendars are merged and sorted by start time. Use `primary`, another email, or any calendar ID from your Google Calendar settings. |
| `look_ahead_minutes`    | integer | `0`                                                                  | If > 0, only show events starting within this many minutes. `0` = always show the next event regardless of how far away. |
| `grace_period_minutes`  | integer | `5`                                                                  | Keep showing an in-progress event until this many minutes after its start. Range 0–120. |
| `skip_all_day`          | boolean | `true`                                                               | Skip all-day events when picking the "next" event. |
| `max_title_length`      | integer | `30`                                                                 | Truncate event titles longer than this. |
| `hide_when_empty`       | boolean | `true`                                                               | Hide the widget when there are no upcoming events; otherwise show `empty_label`. |
| `empty_label`           | string  | `'No upcoming events'`                                               | Shown when there is no upcoming event (only if `hide_when_empty` is false). |
| `auth_label`            | string  | `'Calendar: sign in'`                                                | Bar text shown when sign-in is needed. Click the widget to open the auth dialog. |
| `tooltip`               | boolean | `true`                                                               | Show a tooltip on hover with full title, time range, and location. |
| `tooltip_event_count`   | integer | `1`                                                                  | Number of upcoming events to list in the tooltip (1–20). |
| `icons`                 | dict    | `{'meet': '', 'zoom': '', 'teams': '', 'other': '', 'none': '', 'calendar': ''}` | Per-platform icon glyphs. Set to whichever Nerd Font codepoints you prefer. |
| `menu`                  | dict    | See [Menu options](#menu-options)                                    | Popup configuration. |
| `notification_dot`      | dict    | See [Notification dot](#notification-dot)                            | Coloured dot painted on the icon when an event is live or imminent. |
| `callbacks`             | dict    | `{'on_left': 'toggle_menu', 'on_middle': 'join_meeting', 'on_right': 'toggle_label'}` | Mouse callbacks. See [Callbacks](#callbacks). |

## Menu options

The popup that opens on left-click. Mirrors the GitHub widget's menu config.

| Option              | Type    | Default     | Description |
|---------------------|---------|-------------|-------------|
| `blur`              | boolean | `true`      | Apply Mica/acrylic blur behind the popup. |
| `round_corners`     | boolean | `true`      | Round the popup's corners. |
| `round_corners_type`| string  | `'normal'`  | `normal` or `small`. |
| `border_color`      | string  | `'System'`  | Border colour. `System` follows the OS accent. |
| `alignment`         | string  | `'right'`   | `left`, `center`, or `right` relative to the bar widget. |
| `direction`         | string  | `'down'`    | `down` or `up`. |
| `offset_top`        | integer | `6`         | Pixel offset from the bar edge. |
| `offset_left`       | integer | `0`         | Horizontal offset. |
| `event_count`       | integer | `5`         | Number of upcoming events to show. Range 1–20. |

## Notification dot

A coloured dot painted on the icon to flag a live or imminent meeting.

| Option                | Type    | Default        | Description |
|-----------------------|---------|----------------|-------------|
| `enabled`             | boolean | `true`         | Master switch. |
| `corner`              | string  | `'bottom_left'`| `top_left`, `top_right`, `bottom_left`, `bottom_right`. |
| `color`               | string  | `'red'`        | Any CSS colour. |
| `margin`              | list    | `[1, 1]`       | `[x, y]` margin in pixels. |
| `threshold_minutes`   | integer | `10`           | Show the dot when the next event starts within this many minutes (or is live). Range 0–240. |

## Example configuration

```yaml
calendar:
  type: "yasb.calendar.CalendarWidget"
  options:
    label: "<span class=\"icon\">{icon}</span> {title} {countdown}"
    label_alt: "<span class=\"icon\">{icon}</span> {title} at {start_time}"
    update_interval: 60
    tick_interval: 1000
    calendar_ids:
      - "primary"
      - "you@example.com"
    look_ahead_minutes: 120
    grace_period_minutes: 5
    skip_all_day: true
    max_title_length: 30
    hide_when_empty: true
    icons:
      meet: "󰼺"
      zoom: "󰹅"
      teams: "󰁳"
      other: ""
      none: ""
      calendar: ""
    menu:
      alignment: "right"
      direction: "down"
      offset_top: 6
      event_count: 5
    notification_dot:
      enabled: true
      corner: "bottom_left"
      color: "#f5a"
      threshold_minutes: 5
    callbacks:
      on_left: "toggle_menu"
      on_middle: "join_meeting"
      on_right: "toggle_label"
```

## One-time Google Calendar setup

The widget reads your calendar via the Google Calendar API. You only have to do this once.

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create (or pick) a project.
2. Enable the **Google Calendar API** for that project (APIs & Services → Library).
3. Configure the OAuth consent screen as **External**, add your own Google account as a test user, and request scope `https://www.googleapis.com/auth/calendar.readonly`.
4. Create credentials → **OAuth client ID** → application type **Desktop app**. Download the JSON file.
5. Save it as `%LOCALAPPDATA%\YASB\google_calendar_credentials.json`.
6. Start YASB. The bar widget shows `Calendar: sign in`. Click it — an auth dialog opens, then your browser. After you authorise, the dialog closes and your events appear.

The auth dialog has an **Open Folder** button that takes you straight to `%LOCALAPPDATA%\YASB\` so you can drop the credentials file in.

The token only grants read access. To revoke it, delete `%LOCALAPPDATA%\YASB\google_calendar_token.json` and remove the app from <https://myaccount.google.com/permissions>.

## Tokens

Tokens you can use in `label` / `label_alt`:

- `{icon}` — picked from `icons` based on the meeting platform (`meet`/`zoom`/`teams`/`other`/`none`).
- `{title}` — event title, truncated to `max_title_length`.
- `{start_time}` — local time of the event start in `HH:MM`.
- `{countdown}` — `in 12m`, `in 1h 20m`, `now`, `started 3m ago`.
- `{status}` — `upcoming`, `live`, `ended` (also applied as a CSS class).
- `{meeting_kind}` — `meet`, `zoom`, `teams`, `other`, or `none`.

## Callbacks

| Name           | Behaviour |
|----------------|-----------|
| `toggle_menu`  | Open or close the popup of upcoming events. If sign-in is needed, opens the auth dialog instead. |
| `join_meeting` | Open the meeting join URL of the very next event. Falls back to the calendar event page if no URL is found. If sign-in is needed, opens the auth dialog. |
| `open_event`   | Open the next event's `htmlLink` (Google Calendar web view). |
| `toggle_label` | Swap between `label` and `label_alt`. |
| `refresh`      | Force a re-poll of the API (skipped if a poll is already in flight). |

## How the meeting URL is detected

In priority order:

1. `event.hangoutLink` — Google Meet links auto-attached to the event.
2. `event.conferenceData.entryPoints[]` — first entry with `entryPointType: video`. Classified by host (`zoom.us`, `teams.microsoft.com`, etc.).
3. Regex over the event's `location` and `description` for `https://*.zoom.us/...`, `https://teams.microsoft.com/l/meetup-join/...`, or `https://meet.google.com/xxx-xxxx-xxx`.

If nothing matches, `join_meeting` falls back to opening the event in Google Calendar.

## Style example

The widget frame gets state classes you can target from `styles.css`:

```css
.calendar-widget {
  padding: 0 8px;
}
.calendar-widget.live {
  color: #f5a;
  font-weight: 600;
}
.calendar-widget.upcoming.meet { color: #00897b; }
.calendar-widget.zoom          { color: #2d8cff; }
.calendar-widget.teams         { color: #6264a7; }
.calendar-widget.setup,
.calendar-widget.error         { color: #ff8a65; }

.calendar-menu {
  background: rgba(20, 20, 20, 0.85);
  color: #fff;
  min-width: 320px;
  padding: 8px;
}
.calendar-menu .header { font-size: 14px; padding: 6px 8px; }
.calendar-menu .item { padding: 6px 8px; border-radius: 4px; }
.calendar-menu .item.live { color: #f5a; font-weight: 600; }
.calendar-menu .item .title { font-weight: 600; }
.calendar-menu .item .description { color: rgba(255,255,255,0.6); font-size: 11px; }
.calendar-menu .item .join,
.calendar-menu .item .open { padding: 2px 8px; border-radius: 3px; background: #2d8cff; color: #fff; }
```

State classes added to the frame: one of `loading`, `ok`, `empty`, `setup`, `error`, plus when state is `ok`: the meeting kind (`meet`/`zoom`/`teams`/`other`/`none`) and the status (`upcoming`/`live`/`ended`).
