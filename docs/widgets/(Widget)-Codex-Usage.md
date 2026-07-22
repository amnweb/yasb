# Codex Usage Widget Options

Shows your Codex (Codex CLI) subscription usage on the bar - the 5-hour and weekly
rolling limit utilization - with a popup menu that displays both windows as progress bars
together with their reset times (a countdown plus the exact reset timestamp).

The data is read from the same login credentials the Codex CLI uses
(`~/.codex/auth.json`) and fetched from OpenAI's usage endpoint. No API key or extra
configuration is required as long as you are signed in to Codex CLI.

| Option            | Type    | Default | Description |
|-------------------|---------|---------|-------------|
| `label`           | string  | `'Codex {five_hour}%'` | The format string for the label. Supports the placeholders below. |
| `label_alt`       | string  | `'Codex {weekly}%'` | The alternative format string, toggled by the `toggle_label` callback. |
| `update_interval` | integer | `60` | How often the label and reset countdown are refreshed, in seconds. Must be between 30 and 3600. |
| `cache_ttl`       | integer | `120` | How long (seconds) a fetched result is cached on disk before the endpoint is queried again. The endpoint is rate-limited, so keep this at a sane value. |
| `tooltip`         | boolean | `true` | Whether to show a summary tooltip on hover. |
| `callbacks`       | dict    | `{'on_left': 'toggle_menu', 'on_middle': 'do_nothing', 'on_right': 'toggle_label'}` | Mouse-click callbacks. |
| `menu`            | dict    | `{'blur': true, 'round_corners': true, 'round_corners_type': 'normal', 'border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0}` | Popup menu settings. |

## Placeholders

The label is plain text by default. You can prepend a Nerd Font glyph in a `<span>` if you
want an icon (e.g. `<span>\U000f06a9</span> {five_hour}%`). The following placeholders can be
used in `label` / `label_alt`:

- `{five_hour}` - 5-hour window utilization (percent, `--` when unavailable).
- `{weekly}` - weekly window utilization (percent, `--` when unavailable).
- `{five_hour_reset}` - time until the 5-hour window resets. Shown as a countdown when under a
  day away (e.g. `4h 27m`), otherwise as a local weekday + time (e.g. `Sat 6:00 AM`).
- `{weekly_reset}` - time until the weekly window resets (e.g. `Sat 6:00 AM`).

```yaml
codex_usage:
  type: "yasb.codex_usage.CodexUsageWidget"
  options:
    label: "Codex {five_hour}% · {five_hour_reset}"
    label_alt: "Codex weekly {weekly}% · {weekly_reset}"
    update_interval: 60
    cache_ttl: 120
    callbacks:
      on_left: "toggle_menu"    # open the usage menu
      on_middle: "do_nothing"
      on_right: "toggle_label"  # switch the bar text between 5h and weekly
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
- **update_interval:** How often the bar label and reset countdown are refreshed, in seconds (30-3600).
- **cache_ttl:** How long a fetched result is cached on disk before the usage endpoint is queried again. Because the endpoint is rate-limited, the widget serves the last cached value on any error instead of going blank.
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

The widget reuses Codex CLI's existing login session. It reads the access token and
account id from `%USERPROFILE%\.codex\auth.json` (or `$CODEX_HOME\auth.json` when that
environment variable is set) and never logs or stores them elsewhere. If you are not
signed in to Codex CLI, the widget shows `--` until you sign in.

## Widget Style
```css
.codex-usage {}
.codex-usage .widget-container {}
.codex-usage .icon {}
.codex-usage .label {}
/* Popup menu */
.codex-usage-menu {}
.codex-usage-menu .header {}        /* "Codex Usage" title */
.codex-usage-menu .section {}
.codex-usage-menu .section .title {}
.codex-usage-menu .section .progress {}               /* progress-bar track */
.codex-usage-menu .section .progress .fill {}         /* filled portion */
.codex-usage-menu .section .progress.low .fill {}     /* < 50%  */
.codex-usage-menu .section .progress.medium .fill {}  /* 50-79% */
.codex-usage-menu .section .progress.high .fill {}    /* >= 80% */
.codex-usage-menu .section .footer .reset {}
.codex-usage-menu .section .footer .percent {}
.codex-usage-menu .section .footer .percent.low {}
.codex-usage-menu .section .footer .percent.medium {}
.codex-usage-menu .section .footer .percent.high {}
.codex-usage-menu .section .date {}     /* absolute reset timestamp */
```

## Example Style
```css
.codex-usage .icon {
    color: #91c9ff;
    font-size: 16px;
    margin: 1px 4px 0 0;
}
.codex-usage .label {
    color: #cdd6f4;
    padding: 0 2px;
}
.codex-usage-menu {
    background-color: #1e1e2e;
    min-width: 260px;
}
.codex-usage-menu .header {
    color: #cdd6f4;
    font-size: 15px;
    font-weight: bold;
    padding: 14px 16px 10px 16px;
}
.codex-usage-menu .section {
    padding: 4px 16px 12px 16px;
}
.codex-usage-menu .section .title {
    color: #cdd6f4;
    font-size: 13px;
    font-weight: 600;
    padding-bottom: 6px;
}
.codex-usage-menu .progress {
    background-color: #313244;
    border-radius: 5px;
    min-height: 10px;
    max-height: 10px;
}
.codex-usage-menu .progress .fill {
    background-color: #a6e3a1;
    border-radius: 5px;
}
.codex-usage-menu .progress.medium .fill { background-color: #f9e2af; }
.codex-usage-menu .progress.high .fill { background-color: #f38ba8; }
.codex-usage-menu .reset {
    color: #a6adc8;
    font-size: 12px;
    padding-top: 6px;
}
.codex-usage-menu .percent {
    color: #a6e3a1;
    font-size: 13px;
    font-weight: bold;
    padding-top: 6px;
}
.codex-usage-menu .percent.medium { color: #f9e2af; }
.codex-usage-menu .percent.high { color: #f38ba8; }
.codex-usage-menu .date {
    color: #6c7086;
    font-size: 11px;
    padding-top: 2px;
}
```
