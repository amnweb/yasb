# Claude Usage Widget Options

Shows your Claude (Claude Code) subscription usage on the bar — the 5-hour and 7-day
rolling limit utilization — with a popup menu that displays both windows as progress bars
together with their reset times (a countdown plus the exact reset timestamp).

The data is read from the same OAuth credentials the Claude Code CLI uses
(`~/.claude/.credentials.json`) and fetched from Anthropic's usage endpoint. No API key or
extra configuration is required as long as you are signed in to Claude Code.

| Option            | Type    | Default | Description |
|-------------------|---------|---------|-------------|
| `label`           | string  | `'Claude {five_hour}%'` | The format string for the label. Supports the placeholders below. |
| `label_alt`       | string  | `'Claude {seven_day}%'` | The alternative format string, toggled by the `toggle_label` callback. |
| `update_interval` | integer | `60` | How often the label and reset countdown are refreshed, in seconds. Must be between 30 and 3600. |
| `cache_ttl`       | integer | `120` | How long (seconds) a fetched result is cached on disk before the endpoint is queried again. The endpoint is rate-limited, so keep this at a sane value. |
| `tooltip`         | boolean | `true` | Whether to show a summary tooltip on hover. |
| `callbacks`       | dict    | `{'on_left': 'toggle_menu', 'on_middle': 'do_nothing', 'on_right': 'toggle_label'}` | Mouse-click callbacks. |
| `menu`            | dict    | `{'blur': true, 'round_corners': true, 'round_corners_type': 'normal', 'border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0}` | Popup menu settings. |

## Placeholders

The label is plain text by default. You can prepend a Nerd Font glyph in a `<span>` if you
want an icon (e.g. `<span>\U000f06a9</span> {five_hour}%`), or embed your own image with an
`<img>` tag (e.g. `<img src='C:/path/to/claude.svg' width='14' height='14'> {five_hour}%`). The
following placeholders can be used in `label` / `label_alt`:

- `{five_hour}` — 5-hour window utilization (percent, `--` when unavailable).
- `{seven_day}` — 7-day window utilization (percent, `--` when unavailable).
- `{five_hour_reset}` — time until the 5-hour window resets. Shown as a countdown when under a
  day away (e.g. `4h 27m`), otherwise as a local weekday + time (e.g. `Sat 6:00 AM`).
- `{seven_day_reset}` — time until the 7-day window resets (e.g. `Sat 6:00 AM`).

```yaml
claude_usage:
  type: "yasb.claude_usage.ClaudeUsageWidget"
  options:
    label: "Claude {five_hour}% · {five_hour_reset}"
    label_alt: "Claude 7d {seven_day}% · {seven_day_reset}"
    update_interval: 60
    cache_ttl: 120
    callbacks:
      on_left: "toggle_menu"    # open the usage menu
      on_middle: "do_nothing"
      on_right: "toggle_label"  # switch the bar text between 5h and 7d
    menu:
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "System"
      alignment: "right"
      direction: "down"
      offset_top: 6
      offset_left: 0
```

## Description of Options

- **label:** The format string for the label. Supports the placeholders listed above.
- **label_alt:** The alternative format string, toggled with the `toggle_label` callback.
- **update_interval:** How often the bar label and reset countdown are refreshed, in seconds (30–3600).
- **cache_ttl:** How long a fetched result is cached on disk before the usage endpoint is queried again. Because the endpoint is rate-limited (HTTP 429), the widget serves the last cached value on any error instead of going blank.
- **tooltip:** Whether to show a summary tooltip on hover.
- **callbacks:** Mouse-click callbacks. Built-in actions: `toggle_menu` (open/close the popup menu), `toggle_label` (swap between `label` and `label_alt`), `do_nothing`, and `exec`.
- **menu:** A dictionary specifying the popup menu settings:
  - **blur:** Enable blur effect for the menu.
  - **round_corners:** Enable round corners (not supported on Windows 10).
  - **round_corners_type:** Type of round corners (`normal`, `small`).
  - **border_color:** Border color of the menu.
  - **alignment:** Horizontal alignment of the menu (`left`, `right`, `center`).
  - **direction:** Whether the menu opens `down` or `up`.
  - **offset_top / offset_left:** Pixel offsets for fine positioning.

## Authentication

The widget reuses Claude Code's existing OAuth session. It reads the access token from
`%USERPROFILE%\.claude\.credentials.json` (or `$CLAUDE_CONFIG_DIR\.credentials.json` when
that environment variable is set) and never logs or stores it elsewhere. If you are not
signed in to Claude Code, the widget shows `--` until you sign in.

## Widget Style
```css
.claude-usage {}
.claude-usage .widget-container {}
.claude-usage .icon {}
.claude-usage .label {}
/* Popup menu */
.claude-usage-menu {}
.claude-usage-menu .header {}        /* "Claude Usage" title */
.claude-usage-menu .section {}
.claude-usage-menu .section .title {}
.claude-usage-menu .section .progress {}               /* progress-bar track */
.claude-usage-menu .section .progress .fill {}         /* filled portion */
.claude-usage-menu .section .progress.low .fill {}     /* < 50%  */
.claude-usage-menu .section .progress.medium .fill {}  /* 50-79% */
.claude-usage-menu .section .progress.high .fill {}    /* >= 80% */
.claude-usage-menu .section .footer .reset {}
.claude-usage-menu .section .footer .percent {}
.claude-usage-menu .section .footer .percent.low {}
.claude-usage-menu .section .footer .percent.medium {}
.claude-usage-menu .section .footer .percent.high {}
.claude-usage-menu .section .date {}     /* absolute reset timestamp */
```

## Example Style
```css
.claude-usage .icon {
    color: #fab387;
    font-size: 16px;
    margin: 1px 4px 0 0;
}
.claude-usage .label {
    color: #cdd6f4;
    padding: 0 2px;
}
.claude-usage-menu {
    background-color: #1e1e2e;
    min-width: 260px;
}
.claude-usage-menu .header {
    color: #cdd6f4;
    font-size: 15px;
    font-weight: bold;
    padding: 14px 16px 10px 16px;
}
.claude-usage-menu .section {
    padding: 4px 16px 12px 16px;
}
.claude-usage-menu .section .title {
    color: #cdd6f4;
    font-size: 13px;
    font-weight: 600;
    padding-bottom: 6px;
}
.claude-usage-menu .progress {
    background-color: #313244;
    border-radius: 5px;
    min-height: 10px;
    max-height: 10px;
}
.claude-usage-menu .progress .fill {
    background-color: #a6e3a1;
    border-radius: 5px;
}
.claude-usage-menu .progress.medium .fill { background-color: #f9e2af; }
.claude-usage-menu .progress.high .fill { background-color: #f38ba8; }
.claude-usage-menu .reset {
    color: #a6adc8;
    font-size: 12px;
    padding-top: 6px;
}
.claude-usage-menu .percent {
    color: #a6e3a1;
    font-size: 13px;
    font-weight: bold;
    padding-top: 6px;
}
.claude-usage-menu .percent.medium { color: #f9e2af; }
.claude-usage-menu .percent.high { color: #f38ba8; }
.claude-usage-menu .date {
    color: #6c7086;
    font-size: 11px;
    padding-top: 2px;
}
```
