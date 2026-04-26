# Calendar Widget Options

Shows the next upcoming Google Calendar event in the bar. Left-click joins the meeting (Google Meet, Zoom, or Microsoft Teams) by opening the join URL in the default browser.

| Option                  | Type    | Default                                                              | Description |
|-------------------------|---------|----------------------------------------------------------------------|-------------|
| `label`                 | string  | `'{icon} {title} {countdown}'`                                       | Format string for the bar label. Tokens: `{icon}`, `{title}`, `{start_time}`, `{countdown}`, `{status}`, `{meeting_kind}`. |
| `label_alt`             | string  | `'{icon} {title} at {start_time}'`                                   | Alternative label, swapped via `toggle_label`. |
| `class_name`            | string  | `''`                                                                 | Extra CSS class appended to the widget frame. |
| `update_interval`       | integer | `60`                                                                 | Seconds between Google Calendar API polls. Range 15–3600. |
| `tick_interval`         | integer | `1000`                                                               | Milliseconds between countdown re-renders (no API call). Range 250–60000. |
| `calendar_ids`          | list of strings | `['primary']`                                                | Calendar IDs to read. Events from all listed calendars are merged and sorted by start time. Use `primary`, another email, or any calendar ID from your Google Calendar settings. |
| `credentials_path`      | string  | `'~/.config/yasb/calendar/credentials.json'`                         | Path to the OAuth client JSON downloaded from Google Cloud Console. |
| `token_path`            | string  | `'~/.config/yasb/calendar/token.json'`                               | Where the refresh token is cached after first authorisation. |
| `look_ahead_minutes`    | integer | `0`                                                                  | If > 0, only show events starting within this many minutes. `0` = always show the next event regardless of how far away. |
| `grace_period_minutes`  | integer | `5`                                                                  | Keep showing an in-progress event until this many minutes after its start. Range 0–120. |
| `skip_all_day`          | boolean | `true`                                                               | Skip all-day events when picking the "next" event. |
| `max_title_length`      | integer | `30`                                                                 | Truncate event titles longer than this. |
| `tooltip_event_count`   | integer | `3`                                                                  | Number of upcoming events to show in the hover tooltip. The bar label always shows just the next one. Range 1–10. |
| `hide_when_empty`       | boolean | `true`                                                               | Hide the widget when there are no upcoming events; otherwise show `empty_label`. |
| `empty_label`           | string  | `'No upcoming events'`                                               | Shown when there is no upcoming event (only if `hide_when_empty` is false). |
| `auth_label`            | string  | `'Calendar: setup needed'`                                           | Shown when `credentials.json` is missing. Click to open the setup docs. |
| `setup_url`             | string  | `'https://github.com/amnweb/yasb/blob/main/docs/widgets/calendar.md'` | URL opened by `open_setup`. |
| `tooltip`               | boolean | `true`                                                               | Show a tooltip on hover with full title, time range, and location. |
| `icons`                 | dict    | `{'meet': '', 'zoom': '', 'teams': '', 'other': '', 'none': '', 'calendar': ''}` | Per-platform icon glyphs. Set to whichever Nerd Font codepoints you prefer. |
| `callbacks`             | dict    | `{'on_left': 'join_meeting', 'on_middle': 'open_event', 'on_right': 'toggle_label'}` | Mouse callbacks. See *Callbacks* below. |

## Example Configuration

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
    tooltip_event_count: 3
    hide_when_empty: true
    icons:
      meet: "󰼺"
      zoom: "󰹅"
      teams: "󰁳"
      other: ""
      none: ""
      calendar: ""
    callbacks:
      on_left: "join_meeting"
      on_middle: "open_event"
      on_right: "toggle_label"
```

## One-time Google Calendar Setup

The widget reads your calendar via the Google Calendar API. You only have to do this once.

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create (or pick) a project.
2. Enable the **Google Calendar API** for that project (APIs & Services → Library).
3. Configure the OAuth consent screen as **External**, add your own Google account as a test user, and set scope `https://www.googleapis.com/auth/calendar.readonly`.
4. Create credentials → **OAuth client ID** → application type **Desktop app**. Download the JSON file.
5. Save it as `%USERPROFILE%\.config\yasb\calendar\credentials.json` (or set `credentials_path` to wherever you put it).
6. Start YASB. The first time the widget runs it opens a browser tab asking you to authorise read-only access to your calendar. After you accept, a refresh token is cached at `token_path` and no further prompts are needed.

The token only grants read access. To revoke it, delete `token.json` and remove the app from <https://myaccount.google.com/permissions>.

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
| `join_meeting` | Open the meeting join URL in the default browser. Falls back to the calendar event page if no URL is found. If credentials are missing, opens `setup_url` instead. |
| `open_event`   | Open the event's `htmlLink` (Google Calendar web view). |
| `toggle_label` | Swap between `label` and `label_alt`. |
| `refresh`      | Force a re-poll of the API (skipped if a poll is already in flight). |
| `open_setup`   | Open `setup_url`. |

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
.calendar-widget.upcoming.meet {
  color: #00897b;
}
.calendar-widget.zoom { color: #2d8cff; }
.calendar-widget.teams { color: #6264a7; }
.calendar-widget.setup,
.calendar-widget.error {
  color: #ff8a65;
}
```

State classes added to the frame: one of `loading`, `ok`, `empty`, `setup`, `error`, plus when state is `ok`: the meeting kind (`meet`/`zoom`/`teams`/`other`/`none`) and the status (`upcoming`/`live`/`ended`).
