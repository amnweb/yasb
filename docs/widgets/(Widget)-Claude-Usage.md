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
| `five_hour_reset_format` | string | `'relative'` | How the 5-hour window's reset line is phrased: `'relative'` → `Resets in 4h 11m` (countdown), or `'absolute'` → `Resets on Sat @ 6:00 AM`. |
| `seven_day_reset_format` | string | `'absolute'` | How the 7-day window's reset line is phrased: `'absolute'` → `Resets on Sat @ 6:00 AM` (local weekday + time), or `'relative'` → `Resets in 6d 21h`. |
| `reset_show_date` | boolean | `true` | For windows using `'absolute'`, include the month/day (`Resets on Sat, Jun 13 @ 6:00 AM`) so windows that reset on the same weekday are distinguishable. No effect on `'relative'` windows. |
| `colorize_percent`| boolean | `false` | Colour the `{five_hour}`/`{seven_day}` percentage on the bar by usage level (same green/yellow/orange/red usage bands as the popup bars). See [Color-coded percentage](#color-coded-percentage). |
| `tooltip`         | boolean | `true` | Whether to show a summary tooltip on hover. |
| `token_history`   | dict    | disabled | Optional local token-usage history (Session/Today/Week/Month/Year). See [Token history](#token-history). |
| `callbacks`       | dict    | `{'on_left': 'toggle_menu', 'on_middle': 'do_nothing', 'on_right': 'toggle_label'}` | Mouse-click callbacks. The popup menu also has a refresh button in its header. |
| `menu`            | dict    | `{'blur': true, 'round_corners': true, 'round_corners_type': 'normal', 'border_color': 'System', 'alignment': 'right', 'direction': 'down', 'offset_top': 6, 'offset_left': 0}` | Popup menu settings. |

## Placeholders

The label is plain text by default. You can prepend a Nerd Font glyph in a `<span>` if you
want an icon (e.g. `<span>\U000f06a9</span> {five_hour}%`). The following placeholders can be
used in `label` / `label_alt`:

- `{five_hour}` — 5-hour window utilization (percent, `--` when unavailable).
- `{seven_day}` — 7-day window utilization (percent, `--` when unavailable).
- `{five_hour_reset}` — time until the 5-hour window resets. Shown as a countdown when under a
  day away (e.g. `4h 27m`), otherwise as a local weekday + time (e.g. `Sat 6:00 AM`).
- `{seven_day_reset}` — time until the 7-day window resets (e.g. `Sat 6:00 AM`).
- `{stale}` — an expired-token warning glyph (``), shown only when Claude Code's OAuth token
  has expired and the widget is therefore serving stale cached values; empty otherwise. The
  usage data is read from Claude Code's token, which only Claude Code can refresh, so this is a
  cue to run a `claude` command to renew it. Wrap it in a `<span>` so it renders in your Nerd
  Font and can be styled via `.claude-usage .stale`, e.g.
  `{five_hour}%<span class='stale'>{stale}</span>`.

When `token_history` is enabled, these compact token-count placeholders are also available
(e.g. `15K`, `1.2M`, `218M`, `3.4B`, `1T`; `--` when unavailable):

- `{session_tokens}` — tokens used by the most recent Claude Code session.
- `{today_tokens}` / `{week_tokens}` / `{month_tokens}` / `{year_tokens}` — tokens used in the
  current day / week / month / year (local time).

```yaml
claude_usage:
  type: "yasb.claude_usage.ClaudeUsageWidget"
  options:
    label: "Claude {five_hour}% · {five_hour_reset}<span class='stale'>{stale}</span>"
    label_alt: "Claude 7d {seven_day}% · {seven_day_reset}<span class='stale'>{stale}</span>"
    update_interval: 60
    cache_ttl: 120
    five_hour_reset_format: "relative"  # 5-hour: "Resets in 4h 11m"
    seven_day_reset_format: "absolute"  # 7-day:  "Resets on Sat, Jun 20 @ 2:59 AM"
    reset_show_date: true               # include month/day in absolute reset lines
    callbacks:
      on_left: "toggle_menu"    # open the usage menu
      on_middle: "refresh"      # force an immediate re-fetch, bypassing the cache
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
- **five_hour_reset_format / seven_day_reset_format:** How each window's "Resets …" line is phrased. `relative` shows a countdown (`Resets in 4h 11m`); `absolute` shows a local weekday and time (`Resets on Sat @ 6:00 AM`). The defaults suit each window — the near-term 5-hour window as a countdown, the multi-day 7-day window as a date. The exact reset timestamp is always shown on the line below regardless of this setting.
- **reset_show_date:** For windows using `absolute`, include the month and day in the reset line (`Resets on Sat, Jun 13 @ 6:00 AM`). This disambiguates the two windows when they happen to reset on the same weekday. Ignored for `relative` windows.
- **colorize_percent:** Colour the percentage shown on the bar by usage level. See [Color-coded percentage](#color-coded-percentage).
- **tooltip:** Whether to show a summary tooltip on hover.
- **callbacks:** Mouse-click callbacks. Built-in actions: `toggle_menu` (open/close the popup menu), `toggle_label` (swap between `label` and `label_alt`), `refresh` (force an immediate re-fetch of the usage data, bypassing `cache_ttl`), `do_nothing`, and `exec`. The popup menu header also has a refresh button that triggers the same action.
- **menu:** A dictionary specifying the popup menu settings:
  - **blur:** Enable blur effect for the menu.
  - **round_corners:** Enable round corners (not supported on Windows 10).
  - **round_corners_type:** Type of round corners (`normal`, `small`).
  - **border_color:** Border color of the menu.
  - **alignment:** Horizontal alignment of the menu (`left`, `right`, `center`).
  - **direction:** Whether the menu opens `down` or `up`.
  - **offset_top / offset_left:** Pixel offsets for fine positioning.

## Color-coded percentage

With `colorize_percent: true`, the percentage on the bar is coloured by usage level using the
**same usage bands as the popup progress bars** (`< 50` → low/green, `50–64` → medium/yellow,
`65–79` → high/orange, `≥ 80` → critical/red) for whichever window is shown — `{five_hour}` on the main label or
`{seven_day}` on the alt label.

Because a label segment is coloured as a whole, wrap **only** the percent in its own span so
the surrounding text (icon, reset countdown) keeps its normal colour:

```yaml
    label: "<span>\U000f06a9</span> <span class='percent'>{five_hour}%</span> · {five_hour_reset}"
    label_alt: "<span>\U000f06a9</span> <span class='percent'>{seven_day}%</span> · {seven_day_reset}"
    colorize_percent: true
```

The span gets a `low` / `medium` / `high` / `critical` (or `unknown`) class added automatically;
style them to match the bars:

```css
.claude-usage .percent.low { color: #a6e3a1; }       /* green  */
.claude-usage .percent.medium { color: #f9e2af; }    /* yellow */
.claude-usage .percent.high { color: #fab387; }      /* orange */
.claude-usage .percent.critical { color: #f38ba8; }  /* red    */
```

## Token history

When `token_history.enabled` is `true`, the popup menu gains a **Tokens** section with a
Session / Today / Week / Month / Year toggle, the selected period's total token count, and an
optional usage graph. The data comes from Claude Code's own local session transcripts
(`~/.claude/projects/**/*.jsonl`) — **no API key and no network**. Only numeric token counts,
timestamps, the model name and the session id are read; message content is never touched. The
scan is incremental (each file is re-parsed only when its size/mtime changes) and runs off the
UI thread.

The graph window matches the selected period: **Today** and **Session** are hourly, **Week**
and **Month** are daily, and **Year** is monthly. The graph reuses the shared `GraphWidget`
(the same chart the CPU/Memory/GPU widgets use) and is styled via `.token-graph`.

| Option            | Type    | Default | Description |
|-------------------|---------|---------|-------------|
| `enabled`         | boolean | `false` | Enable the Tokens section and the `{*_tokens}` placeholders. |
| `default_period`  | string  | `'today'` | Which period is selected when the menu opens: `session`, `today`, `week`, `month`, or `year`. |
| `show_graph`      | boolean | `false` | Show the usage graph under the totals. |
| `show_graph_grid` | boolean | `false` | Draw a faint grid behind the graph. |
| `week_starts_on`  | string  | `'monday'` | Week boundary for the Week total: `monday` or `sunday`. |
| `count_cache_read`| boolean | `true` | Whether cache-read tokens count toward totals. Cache reads dominate for heavy users, so totals are far smaller when this is `false` (closer to "new" work done). |
| `scan_interval`   | integer | `120` | How often (seconds) the transcripts are re-scanned (30–3600). |

```yaml
    token_history:
      enabled: true
      default_period: "today"
      show_graph: true
      show_graph_grid: false
      week_starts_on: "monday"
      count_cache_read: true
      scan_interval: 120
```

> [!NOTE]
> **Session** is the most recently active session's *entire lifetime*, which can span several
> days, so it may exceed **Today** (which counts every session but only the current date).

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
.claude-usage .stale {}   /* expired-token warning glyph ({stale} placeholder) */
.claude-usage .percent.low {}       /* colorize_percent: < 50%  (green)  */
.claude-usage .percent.medium {}    /* colorize_percent: 50-64% (yellow) */
.claude-usage .percent.high {}      /* colorize_percent: 65-79% (orange) */
.claude-usage .percent.critical {}  /* colorize_percent: >= 80% (red)    */
/* Popup menu */
.claude-usage-menu {}
.claude-usage-menu .header {}            /* header row (title + refresh button) */
.claude-usage-menu .header .text {}      /* "Claude Usage" title */
.claude-usage-menu .header .refresh {}   /* refresh button */
.claude-usage-menu .header .refresh:hover {}
.claude-usage-menu .section {}
.claude-usage-menu .section .title {}
.claude-usage-menu .section .progress {}               /* progress-bar track */
.claude-usage-menu .section .progress .fill {}         /* filled portion */
.claude-usage-menu .section .progress.low .fill {}       /* < 50%  (green)  */
.claude-usage-menu .section .progress.medium .fill {}    /* 50-64% (yellow) */
.claude-usage-menu .section .progress.high .fill {}      /* 65-79% (orange) */
.claude-usage-menu .section .progress.critical .fill {}  /* >= 80% (red)    */
.claude-usage-menu .section .footer .reset {}
.claude-usage-menu .section .footer .percent {}
.claude-usage-menu .section .footer .percent.low {}
.claude-usage-menu .section .footer .percent.medium {}
.claude-usage-menu .section .footer .percent.high {}
.claude-usage-menu .section .footer .percent.critical {}
.claude-usage-menu .section .date {}     /* absolute reset timestamp */
/* Token history section (token_history.enabled) */
.claude-usage-menu .section.tokens .period-toggle {}        /* Session/Today/Week/... row */
.claude-usage-menu .section.tokens .period-btn {}           /* a period button */
.claude-usage-menu .section.tokens .period-btn:hover {}
.claude-usage-menu .section.tokens .period-btn.active {}    /* the selected period */
.claude-usage-menu .section.tokens .token-total {}          /* the big total count */
.claude-usage-menu .section.tokens .token-graph {}          /* usage graph (its color drives the line) */
.claude-usage-menu .section.tokens .token-graph-grid {}     /* graph grid color (show_graph_grid) */
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
.claude-usage .stale {
    color: #f38ba8;
    font-size: 13px;
    margin-left: 4px;
}
.claude-usage-menu {
    background-color: #1e1e2e;
    min-width: 260px;
}
.claude-usage-menu .header {
    padding: 14px 16px 10px 16px;
}
.claude-usage-menu .header .text {
    color: #cdd6f4;
    font-size: 15px;
    font-weight: bold;
}
.claude-usage-menu .header .refresh {
    background: transparent;
    border: none;
    color: #6c7086;
    font-size: 15px;
    padding: 0 2px;
}
.claude-usage-menu .header .refresh:hover {
    color: #fab387;
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
.claude-usage-menu .progress.high .fill { background-color: #fab387; }
.claude-usage-menu .progress.critical .fill { background-color: #f38ba8; }
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
.claude-usage-menu .percent.high { color: #fab387; }
.claude-usage-menu .percent.critical { color: #f38ba8; }
.claude-usage-menu .date {
    color: #6c7086;
    font-size: 11px;
    padding-top: 2px;
}
```
