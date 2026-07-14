# Claude Usage Widget Options

Shows your Claude (Claude Code) subscription usage on the bar - the 5-hour and 7-day
rolling limit utilization - with a popup menu that displays both windows as progress bars
together with their reset times (a countdown plus the exact reset timestamp). Any per-model
weekly cap your plan has (e.g. a separate Fable limit) shows up as an extra bar automatically;
see [Per-model weekly caps](#per-model-weekly-caps).

The data is read from the same OAuth credentials the Claude Code CLI uses
(`~/.claude/.credentials.json`) and fetched from Anthropic's usage endpoint. No API key or
extra configuration is required as long as you are signed in to Claude Code.

| Option            | Type    | Default | Description |
|-------------------|---------|---------|-------------|
| `label`           | string  | `'Claude {five_hour}%'` | The format string for the label. Supports the placeholders below. |
| `label_alt`       | string  | `'Claude {seven_day}%'` | The alternative format string, toggled by the `toggle_label` callback. |
| `update_interval` | integer | `60` | How often the label and reset countdown are refreshed, in seconds. Must be between 30 and 3600. |
| `cache_ttl`       | integer | `120` | How long (seconds) a fetched result is cached on disk before the endpoint is queried again. The endpoint is rate-limited, so keep this at a sane value. |
| `five_hour_reset_format` | string | `'relative'` | How the 5-hour window's reset line is phrased in the popup: `relative` (`Resets in 4h 11m`) or `absolute` (`Resets on Sat @ 6:00 AM`). |
| `seven_day_reset_format` | string | `'absolute'` | How the 7-day window's reset line is phrased in the popup: `relative` or `absolute`. |
| `reset_show_date` | boolean | `true` | In `absolute` mode, include the month/day (`Resets on Sat, Jun 13 @ 6:00 AM`) so two windows resetting on the same weekday stay distinguishable. |
| `token_history`   | dict    | `{'enabled': false, ...}` | Optional local token-usage history. See [Token history](#token-history). |
| `status`          | dict    | `{'enabled': false, ...}` | Optional Claude API status indicator. See [API status](#api-status). |
| `tooltip`         | boolean | `true` | Whether to show a summary tooltip on hover. |
| `callbacks`       | dict    | `{'on_left': 'toggle_menu', 'on_middle': 'do_nothing', 'on_right': 'toggle_label'}` | Mouse-click callbacks. |
| `menu`            | dict    | `{'blur': true, 'round_corners': true, 'round_corners_type': 'normal', 'border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0, 'pin_icon': '', 'unpin_icon': ''}` | Popup menu settings. |

## Placeholders

The label is plain text by default. You can prepend a Nerd Font glyph in a `<span>` if you
want an icon (e.g. `<span>\U000f06a9</span> {five_hour}%`), or embed your own image with an
`<img>` tag (e.g. `<img src='C:/path/to/claude.svg' width='14' height='14'> {five_hour}%`). The
following placeholders can be used in `label` / `label_alt`:

- `{five_hour}` - 5-hour window utilization (percent, `--` when unavailable).
- `{seven_day}` - 7-day window utilization (percent, `--` when unavailable).
- `{five_hour_reset}` - time until the 5-hour window resets. Shown as a countdown when under a
  day away (e.g. `4h 27m`), otherwise as a local weekday + time (e.g. `Sat 6:00 AM`).
- `{seven_day_reset}` - time until the 7-day window resets (e.g. `Sat 6:00 AM`).
- `{stale}` - a warning glyph shown only while Claude Code's OAuth token has expired, empty
  otherwise. Place it in its own `<span>` (e.g. `{five_hour}% <span class='stale'>{stale}</span>`).
- `{session_tokens}` `{today_tokens}` `{week_tokens}` `{month_tokens}` `{year_tokens}` - compact
  token totals (e.g. `1.2M`) for each period. Require `token_history.enabled`; `--` otherwise.
- `{status}` - a status dot, coloured by the current Claude API status level via
  `.status.<none|minor|major|critical>` classes. Place it in its own `<span>`. Requires
  `status.enabled`; empty otherwise.
- `{status_text}` - the status description (e.g. `All Systems Operational`).

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
      on_middle: "refresh"      # force an immediate re-fetch, bypassing cache_ttl
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
- **update_interval:** How often the bar label and reset countdown are refreshed, in seconds (30-3600).
- **cache_ttl:** How long a fetched result is cached on disk before the usage endpoint is queried again. Because the endpoint is rate-limited (HTTP 429), the widget serves the last cached value on any error instead of going blank.
- **five_hour_reset_format / seven_day_reset_format:** How each window's reset line is phrased in the popup. `relative` shows a countdown (`Resets in 4h 11m`); `absolute` shows a local weekday and time (`Resets on Sat @ 6:00 AM`). The exact reset timestamp is always shown on the line below.
- **reset_show_date:** In `absolute` mode, include the month/day in the reset line so the 5-hour and 7-day windows can be told apart when they fall on the same weekday. No effect in `relative` mode.
- **tooltip:** Whether to show a summary tooltip on hover.
- **callbacks:** Mouse-click callbacks. Built-in actions: `toggle_menu` (open/close the popup menu), `toggle_label` (swap between `label` and `label_alt`), `refresh` (force an immediate re-fetch, bypassing `cache_ttl`), `do_nothing`, and `exec`.
- **menu:** A dictionary specifying the popup menu settings:
  - **blur:** Enable blur effect for the menu.
  - **round_corners:** Enable round corners (not supported on Windows 10).
  - **round_corners_type:** Type of round corners (`normal`, `small`).
  - **border_color:** Border color of the menu.
  - **alignment:** Horizontal alignment of the menu (`left`, `right`, `center`).
  - **direction:** Whether the menu opens `down` or `up`.
  - **offset_top / offset_left:** Pixel offsets for fine positioning.
  - **pin_icon / unpin_icon:** Nerd Font glyphs for the pin button in the popup header. The button keeps the popup open and lets it be dragged when pinned.

## Authentication

The widget reuses Claude Code's existing OAuth session. It reads the access token from
`%USERPROFILE%\.claude\.credentials.json` (or `$CLAUDE_CONFIG_DIR\.credentials.json` when
that environment variable is set) and never logs or stores it elsewhere. If you are not
signed in to Claude Code, the widget shows `--` until you sign in.

Only Claude Code itself renews the OAuth token. If it has expired (e.g. you have not used
Claude Code in a while), the usage endpoint rejects the request and the widget keeps serving
the last cached values; the `{stale}` placeholder shows a warning glyph until the token is
refreshed by running any Claude Code command. The `refresh` action forces a re-fetch but
cannot renew an expired token.

## Refresh

The popup header has a refresh button that forces an immediate re-fetch, bypassing `cache_ttl`.
The same action is available as the `refresh` callback for any mouse button. While the menu is
open, its sections redraw in place when fresh data arrives. A refresh is ignored while a fetch
is already in flight.

## Per-model weekly caps

Some plans give one or more models their own weekly cap on top of the shared 5-hour/7-day
windows (e.g. a separate Fable limit). When the usage endpoint reports one, the popup gains an
extra bar for it - titled with the model's name (`Fable Weekly`) - right after the 7-Day
section, using the same progress bar, reset line and `low`/`medium`/`high` colouring as the
built-in windows. There is no config option for this: it is read directly from the API response
and appears or disappears with your plan, so a model added later needs no widget update.

## Token history

When `token_history.enabled` is `true`, the popup gains a **Tokens** section with a
Session / Today / Week / Month / Year toggle, the selected period's total, and an optional
usage graph. The same totals are available on the bar via the `{*_tokens}` placeholders.

The data comes from Claude Code's own session transcripts (`~/.claude/projects/**/*.jsonl`):
no API key and no network. Only numeric token counts, timestamps, the model name and the
session id are read; message content is never touched. The scan is incremental (a file is
re-parsed only when its size or mtime changes) and runs off the UI thread.

```yaml
    token_history:
      enabled: true
      default_period: "today"   # session | today | week | month | year
      show_graph: true
      show_graph_grid: false
      week_starts_on: "monday"  # monday | sunday
      count_cache_read: true    # false counts only new input/output/cache-creation
      scan_interval: 120        # seconds between transcript scans (30–3600)
```

- **enabled:** Turn the Tokens section and `{*_tokens}` placeholders on.
- **default_period:** Which period is selected when the menu first opens.
- **show_graph / show_graph_grid:** Show a usage graph for the selected period, with an optional grid.
- **show_models:** Show a per-model token breakdown in the Tokens section, following the selected period. Top 5 models, computed from local transcripts.
- **week_starts_on:** First day of the week for the Week total.
- **count_cache_read:** Whether cache-read tokens count toward the totals. They dominate for heavy users; set `false` for "new work only".
- **scan_interval:** Seconds between transcript scans (30–3600).

> Session is the most recently active session's whole lifetime, so it can span days and may exceed Today.

## API status

When `status.enabled` is `true`, the widget can show a coloured dot reflecting the public
Claude API status (`status.claude.com`, no authentication). Use the `{status}` placeholder on
the bar, and/or an optional status line in the popup header (`show_in_menu`).

```yaml
    status:
      enabled: true
      show_in_menu: true
      icon: "●"           # any glyph; coloured by .status.<level>
      poll_interval: 300  # seconds between status checks (60–3600)
```

- **enabled:** Turn the `{status}`/`{status_text}` placeholders and the menu status line on.
- **show_in_menu:** Show a dot + description line in the popup header.
- **icon:** The glyph used for the dot. Its colour comes from the `.status.<level>` class.
- **poll_interval:** Seconds between status checks (60–3600).

## Widget Style
```css
.claude-usage {}
.claude-usage .widget-container {}
.claude-usage .icon {}
.claude-usage .label {}
.claude-usage .stale {}              /* warning glyph while the OAuth token is expired */
.claude-usage .status {}             /* {status} dot on the bar */
.claude-usage .status.none {}        /* green / minor / major / critical / unknown */
.claude-usage .status.minor {}
.claude-usage .status.major {}
.claude-usage .status.critical {}
/* Popup menu */
.claude-usage-menu {}
.claude-usage-menu .header {}        /* header row (title + refresh button) */
.claude-usage-menu .header .text {}  /* "Claude Usage" title */
.claude-usage-menu .header .refresh {}        /* refresh button */
.claude-usage-menu .header .refresh:hover {}
.claude-usage-menu .status-row {}             /* status line below the header (show_in_menu) */
.claude-usage-menu .status-row .dot {}        /* coloured via .dot.<level> */
.claude-usage-menu .status-row .status-text {}
.claude-usage-menu .section {}                          /* 5-Hour / 7-Day / per-model weekly bars */
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
/* Token history section (token_history.enabled) */
.claude-usage-menu .section.tokens {}
.claude-usage-menu .section .period-toggle {}
.claude-usage-menu .section .period-btn {}
.claude-usage-menu .section .period-btn.active {}
.claude-usage-menu .section .token-total {}
.claude-usage-menu .section.tokens .model-usage {}      /* per-model breakdown container */
.claude-usage-menu .section.tokens .model-usage .title {} /* "Models" header */
.claude-usage-menu .section.tokens .model-rows {}       /* the per-model bar rows */
.claude-usage-menu .section.tokens .model-name {}
.claude-usage-menu .section.tokens .model-total {}
.claude-usage-menu .section.tokens .model-rows .progress.model-0 .fill {}  /* bar accent 0..4 */
.claude-usage-menu .section.tokens .model-rows .progress.model-1 .fill {}
.claude-usage-menu .section.tokens .model-rows .progress.model-2 .fill {}
.claude-usage-menu .section.tokens .model-rows .progress.model-3 .fill {}
.claude-usage-menu .section.tokens .model-rows .progress.model-4 .fill {}
.claude-usage-menu .header .pin-btn {}        /* pin button (use font-family "Segoe Fluent Icons" for the glyphs) */
.claude-usage-menu .header .pin-btn.pinned {} /* while pinned */
.claude-usage-menu .section .graph-container {}
```

## Example Style

A full style covering every element, including the optional status, token-history and
per-model rows. Copy/paste and adjust colours to taste.

```css
/* Bar */
.claude-usage .icon {
    color: #fab387;
    font-size: 16px;
    margin: 1px 4px 0 0;
}
.claude-usage .label {
    color: #cdd6f4;
    padding: 0 2px;
}
.claude-usage .stale {
    color: #f38ba8;
    margin-left: 4px;
}
.claude-usage .status { margin-right: 4px; }
.claude-usage .status.none { color: #a6e3a1; }
.claude-usage .status.minor { color: #f9e2af; }
.claude-usage .status.major { color: #fab387; }
.claude-usage .status.critical { color: #f38ba8; }
.claude-usage .status.unknown { color: #6c7086; }

/* Popup menu */
.claude-usage-menu {
    background-color: #1e1e2e;
    min-width: 280px;
}
.claude-usage-menu .header {
    padding: 14px 16px 10px 16px;
}
.claude-usage-menu .header .text {
    color: #cdd6f4;
    font-size: 15px;
    font-weight: bold;
}
.claude-usage-menu .header .refresh,
.claude-usage-menu .header .pin-btn {
    color: #6c7086;
    font-size: 15px;
    padding: 0 2px;
    margin-left: 6px;
}
.claude-usage-menu .header .pin-btn {
    font-family: "Segoe Fluent Icons";
}
.claude-usage-menu .header .refresh:hover,
.claude-usage-menu .header .pin-btn:hover { color: #fab387; }
.claude-usage-menu .header .pin-btn.pinned { color: #fab387; }

/* Optional status line (status.show_in_menu) */
.claude-usage-menu .status-row { padding: 0 16px 8px 16px; }
.claude-usage-menu .status-row .dot { font-size: 12px; margin-right: 6px; }
.claude-usage-menu .status-row .dot.none { color: #a6e3a1; }
.claude-usage-menu .status-row .dot.minor { color: #f9e2af; }
.claude-usage-menu .status-row .dot.major { color: #fab387; }
.claude-usage-menu .status-row .dot.critical { color: #f38ba8; }
.claude-usage-menu .status-row .dot.unknown { color: #6c7086; }
.claude-usage-menu .status-row .status-text { color: #a6adc8; font-size: 12px; }

/* 5-hour / 7-day sections, and any per-model weekly cap bar (e.g. Fable) - all share these rules */
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

/* Token history (token_history.enabled) */
.claude-usage-menu .section .period-toggle { padding-bottom: 8px; }
.claude-usage-menu .section .period-btn {
    color: #a6adc8;
    background-color: #313244;
    border: none;
    /* No left padding so the first button lines up with the 16px edge; spacing is on the right. */
    padding: 4px 12px 4px 0;
    font-size: 12px;
}
.claude-usage-menu .section .period-btn.active {
    color: #1e1e2e;
    background-color: #89b4fa;
    font-weight: 600;
}
.claude-usage-menu .section .token-total {
    color: #cdd6f4;
    font-size: 18px;
    font-weight: bold;
    padding: 2px 0 6px 0;
}
.claude-usage-menu .section .graph-container { min-height: 60px; }

/* Per-model breakdown (token_history.show_models). The name and total columns are
   given a min-width so the bar column stretches to fill the remaining space. */
.claude-usage-menu .section.tokens .model-usage { padding-bottom: 10px; }
.claude-usage-menu .section.tokens .model-name {
    color: #cdd6f4;
    font-size: 12px;
    min-width: 90px;
}
.claude-usage-menu .section.tokens .model-total {
    color: #a6adc8;
    font-size: 12px;
    min-width: 48px;
}
.claude-usage-menu .section.tokens .model-rows .progress {
    min-height: 8px;
    max-height: 8px;
}
.claude-usage-menu .section.tokens .model-rows .progress.model-0 .fill { background-color: #89b4fa; }
.claude-usage-menu .section.tokens .model-rows .progress.model-1 .fill { background-color: #cba6f7; }
.claude-usage-menu .section.tokens .model-rows .progress.model-2 .fill { background-color: #94e2d5; }
.claude-usage-menu .section.tokens .model-rows .progress.model-3 .fill { background-color: #f9e2af; }
.claude-usage-menu .section.tokens .model-rows .progress.model-4 .fill { background-color: #fab387; }
```

## Example Widget
<img width="286" height="698" alt="image" src="https://github.com/user-attachments/assets/90166652-9dfa-4959-a185-bf28f18d20ba" />

