# DeepSeek Usage Widget Options

Shows your DeepSeek platform balance on the bar, with a popup that breaks the balance into
its topped-up and granted parts, charts how much you have spent over Today / Week / Month /
Year, and optionally measures that spend against a budget you set.

The data comes from DeepSeek's `GET /user/balance` endpoint using your platform API key.

> **What this widget can and cannot measure.** DeepSeek's platform API exposes a balance but
> **no usage or token-history endpoint** - token counts are only returned inside each
> chat-completion response, to whichever process made the call, and YASB is not in that path.
> So this widget reports **money, not tokens**. It does so exactly rather than by estimation:
> polling the balance and differencing consecutive readings yields real spend with no pricing
> table involved. If you want token counts for a subscription tool instead, see the
> [Claude Usage](./(Widget)-Claude-Usage) and [Codex Usage](./(Widget)-Codex-Usage) widgets.

## Requirements

- A DeepSeek platform API key from [platform.deepseek.com](https://platform.deepseek.com).
- Pay-as-you-go (prepaid balance) access. The endpoint reports a balance, not a subscription quota.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `label` | string | `'DeepSeek {balance}'` | The format string for the label. Supports the placeholders below. |
| `label_alt` | string | `'DeepSeek {today_spend} today'` | The alternative format string, toggled by the `toggle_label` callback. |
| `api_key` | string | `'env'` | `env` reads `YASB_DEEPSEEK_API_KEY`, then `DEEPSEEK_API_KEY`. A literal key also works. See [Authentication](#authentication). |
| `currency` | string | `'auto'` | Which balance entry to show: `auto`, `CNY` or `USD`. `auto` prefers the entry holding actual money. |
| `currency_symbol` | string | `''` | Override the symbol. Blank derives one from the currency (`CNY` → `¥`, `USD` → `$`). |
| `decimal_places` | integer | `2` | Decimal places for every amount (0-6). Raise it if a day's spend rounds to zero. |
| `update_interval` | integer | `60` | How often the label is refreshed, in seconds (30-3600). |
| `cache_ttl` | integer | `120` | How long a fetched result is cached on disk before the endpoint is queried again. |
| `low_balance_threshold` | float | `0.0` | Show the `{low}` glyph when the balance falls below this. `0` disables the threshold (the glyph still appears if DeepSeek reports the account cannot make calls). |
| `show_account` | boolean | `true` | Show the account line under the popup title and in the bar tooltip. |
| `account_label` | string | `""` | What to call this account. Blank falls back to a masked fingerprint of the key in use, e.g. `sk-…1e06`. |
| `spend_history` | dict | `{'enabled': true, ...}` | Spend tracking and the popup's Spend section. See [Spend history](#spend-history). |
| `budget` | dict | `{'enabled': false, ...}` | An optional budget to measure spend against. See [Budget](#budget). |
| `low_icon` | string | `''` | Glyph used by `{low}`. |
| `stale_icon` | string | `''` | Glyph used by `{stale}`. |
| `tooltip` | boolean | `true` | Whether to show a summary tooltip on hover. |
| `callbacks` | dict | `{'on_left': 'toggle_menu', 'on_middle': 'refresh', 'on_right': 'toggle_label'}` | Mouse-click callbacks. |
| `menu` | dict | `{'blur': true, 'round_corners': true, ...}` | Popup menu settings. |

## Placeholders

The label is plain text by default. You can prepend a Nerd Font glyph in a `<span>` (e.g.
`<span>\U000f1a10</span> {balance}`), or embed your own image with an `<img>` tag - useful
here, since no Nerd Font ships a DeepSeek mark:

```yaml
    label: "<span><img src='C:/Users/you/.config/yasb/assets/deepseek.png' width='14' height='14'></span> {balance}"
```

> An `<img>` is a bitmap, so unlike a glyph it does **not** follow the `color` set in CSS.
> Tint the image itself, and keep a second copy if you want a different colour per theme.
> Use forward slashes in the path. Note the 8-digit `\U` form for glyph escapes rather than a
> `\udbXX\udcXX` surrogate pair: YAML leaves lone surrogates as two unrenderable characters.

The following placeholders can be used in `label` / `label_alt`:

- `{balance}` / `{total}` - total available balance, formatted with the currency symbol (`--` when unknown).
- `{granted}` - the not-yet-expired granted (free) balance.
- `{topped_up}` - the balance you have paid for.
- `{currency}` - the currency code reported by the API (e.g. `CNY`).
- `{today_spend}` `{week_spend}` `{month_spend}` `{year_spend}` - spend for each period. Require `spend_history.enabled`; `--` otherwise.
- `{budget_used}` - spend as a percentage of the budget, without the `%` sign (e.g. `34`). Requires `budget.enabled`; `--` otherwise. Colour it via the `.low`/`.medium`/`.high`/`.critical` classes.
- `{budget_amount}` - the configured budget.
- `{budget_remaining}` - budget minus spend for the budget period. Goes negative when you overspend.
- `{low}` - a warning glyph shown only when the balance is low, empty otherwise. Place it in its own `<span>`.
- `{stale}` - a warning glyph shown only while the balance could not be fetched, empty otherwise. Place it in its own `<span>`.

```yaml
deepseek_usage:
  type: "yasb.deepseek_usage.DeepSeekUsageWidget"
  options:
    label: "DeepSeek {balance} <span class='low'>{low}</span>"
    label_alt: "DeepSeek {budget_used}% · {today_spend} today"
    api_key: "env"
    currency: "auto"
    decimal_places: 2
    update_interval: 60
    cache_ttl: 120
    low_balance_threshold: 5.0
    account_label: "you@example.com"
    spend_history:
      enabled: true
      default_period: "today"
      show_graph: true
    budget:
      enabled: true
      amount: 100.0
      period: "month"
    callbacks:
      on_left: "toggle_menu"    # open the usage menu
      on_middle: "refresh"      # force an immediate re-fetch, bypassing cache_ttl
      on_right: "toggle_label"  # switch the bar text
    menu:
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "System"
      alignment: "right"
      direction: "down"
      offset_top: 6
      offset_left: 0
      icon: "C:/Users/you/.config/yasb/assets/deepseek.png"
```

## Description of Options

- **label:** The format string for the label. Supports the placeholders listed above.
- **label_alt:** The alternative format string, toggled with the `toggle_label` callback.
- **api_key:** How the widget authenticates. See [Authentication](#authentication).
- **currency:** An account can report both a CNY and a USD entry. `auto` picks the first one holding actual money, so a zeroed-out secondary currency never hides the real balance. An explicit `CNY`/`USD` wins when present and falls back to `auto` when absent.
- **currency_symbol:** Override the derived symbol, e.g. to use `CN¥` or `RMB`.
- **decimal_places:** DeepSeek calls are cheap, so a quiet day can round to `0.00` at the default of 2. Raise this to 3-4 if you want to see small amounts move.
- **update_interval:** How often the label is refreshed. This also sets the resolution of the spend history: spend is attributed to the moment it is *observed*, so a longer interval means coarser buckets.
- **cache_ttl:** How long a fetched result is cached on disk before the endpoint is queried again. On any error the widget serves the last cached balance instead of going blank.
- **low_balance_threshold:** The balance below which `{low}` appears. The glyph also appears whenever DeepSeek's `is_available` flag says the account can no longer make calls, regardless of this setting.
- **show_account:** Whether the popup header and bar tooltip name the account.
- **account_label:** What to call the account. DeepSeek's API carries no identity of its
  own - `/user/balance` returns money and nothing else - so unlike the Claude and Codex
  widgets there is no e-mail to read. Set this to whatever names the account to you. Left
  blank, the header shows a masked fingerprint of the key in use (`sk-…1e06`), which is
  enough to tell two accounts apart on one machine and far too little to reconstruct a key.
- **tooltip:** Whether to show a summary tooltip on hover.
- **callbacks:** Mouse-click callbacks. Built-in actions: `toggle_menu`, `toggle_label`, `refresh` (force an immediate re-fetch, bypassing `cache_ttl`), `do_nothing`, and `exec`.
- **menu:** A dictionary specifying the popup menu settings:
  - **blur:** Enable blur effect for the menu.
  - **round_corners:** Enable round corners (not supported on Windows 10).
  - **round_corners_type:** Type of round corners (`normal`, `small`).
  - **border_color:** Border color of the menu.
  - **alignment:** Horizontal alignment of the menu (`left`, `right`, `center`).
  - **direction:** Whether the menu opens `down` or `up`.
  - **offset_top / offset_left:** Pixel offsets for fine positioning.
  - **icon:** Path to an image drawn at 22x22 at the left of the popup header, beside the title. Any
    format Qt can read works (PNG, SVG, JPEG). Leave it empty for a header with no mark.
  - **show_breakdown:** Show the Topped-up / Granted rows under the balance.
  - **pin_icon / unpin_icon:** Nerd Font glyphs for the pin button in the popup header.

## Authentication

The widget needs a DeepSeek platform API key. `api_key: "env"` (the default) reads
`YASB_DEEPSEEK_API_KEY` first, then `DEEPSEEK_API_KEY`, so a key you already export for the
DeepSeek SDK works with no extra setup:

```powershell
[Environment]::SetEnvironmentVariable("YASB_DEEPSEEK_API_KEY", "sk-...", "User")
```

A literal key in `api_key` also works, but a YASB config is often kept in a dotfiles repo, and
a key pasted there is a key you have published. Prefer the environment variable.

The key is read at fetch time and used only for the `Authorization` header. It is never logged
and never written to the cache: the cache file holds normalized balance figures only. When no
key is found the widget shows `--` and the popup explains why.

## Spend history

DeepSeek reports a balance, not usage - so spend is derived by snapshotting the balance on
every poll and differencing consecutive readings. Only downward movement counts, so topping up
never registers as negative spend. The result is exact, because it reads the money that
actually left the account rather than estimating from token counts and a price list.

Totals are calendar-anchored: Today starts at local midnight, Week at the configured weekday,
Month on the 1st and Year on Jan 1. The ledger lives in
`%LOCALAPPDATA%\YASB\deepseek_spend_history.json` and is trimmed on every write (15 days of
hourly buckets, 400 days of daily ones), so it stays small indefinitely.

```yaml
    spend_history:
      enabled: true
      default_period: "today"     # today | week | month | year
      show_graph: true
      show_graph_grid: false
      week_starts_on: "monday"    # monday | sunday
      count_granted_as_spend: true
```

- **enabled:** Turn the Spend section and the `{*_spend}` placeholders on.
- **default_period:** Which period is selected when the menu first opens.
- **show_graph / show_graph_grid:** Show a spend graph for the selected period, with an optional grid.
- **week_starts_on:** First day of the week for the Week total.
- **count_granted_as_spend:** Whether drawdown of granted (free) credit counts as spend. See below.

### Two limits worth knowing

Both follow from having a balance instead of a usage endpoint, and neither is worked around
by guessing:

- **A top-up between two polls masks the spend before it.** If you spend 2 and then top up 100,
  the next reading is 98 higher than the last one, and that interval records no spend. There is
  no way to recover it without a usage API. Top up when you are not mid-session and the loss is
  negligible.
- **Granted credit is spent before topped-up credit**, so a granted balance *falling* looks
  identical to a granted balance *expiring* - both are a drop with nothing else to distinguish
  them. Rather than guess, `count_granted_as_spend` decides. The default (`true`) counts every
  drop, which tracks true usage but will record an expiring grant as a one-off spike. Setting it
  to `false` counts only topped-up money, which makes "spend" mean "money you actually paid" and
  is immune to grant expiry by construction. If you are past your free credits, the two settings
  behave identically.

> Changing `count_granted_as_spend` only affects readings taken from then on; it does not
> rewrite history already recorded.

## Budget

A prepaid account has no quota, so to get a percentage bar like the Claude and Codex widgets,
give the widget a budget to measure spend against:

```yaml
    budget:
      enabled: true
      amount: 100.0     # in the account's currency
      period: "month"   # today | week | month | year
```

- **enabled:** Turn the popup's Budget bar and the `{budget_*}` placeholders on. Requires `spend_history.enabled`.
- **amount:** The budget for one period, in the account's currency.
- **period:** Which period's spend is measured. Calendar-anchored, so `month` resets on the 1st rather than on your top-up date.

The percentage is deliberately uncapped: overspending reads as `120%`, not a silent `100%`.
Only the bar's fill clamps. The bar and `{budget_used}` take `.low` (<50%), `.medium` (50-74%),
`.high` (75-89%) and `.critical` (>=90%) classes for colouring.

## Refresh

The popup header has a refresh button that forces an immediate re-fetch, bypassing `cache_ttl`.
The same action is available as the `refresh` callback for any mouse button. While the menu is
open, its sections redraw in place when fresh data arrives. A refresh is ignored while a fetch
is already in flight. Only live readings are recorded in the ledger - replaying a cached or
failed result would difference a balance against itself.

## Widget Style
```css
.deepseek-usage {}
.deepseek-usage .widget-container {}
.deepseek-usage .icon {}
.deepseek-usage .label {}
.deepseek-usage .low {}                  /* {low} glyph while the balance is low */
.deepseek-usage .stale {}                /* {stale} glyph while the balance could not be fetched */
.deepseek-usage .budget.low {}           /* {budget_used} colouring: < 50%  */
.deepseek-usage .budget.medium {}        /* 50-74% */
.deepseek-usage .budget.high {}          /* 75-89% */
.deepseek-usage .budget.critical {}      /* >= 90% */
/* Popup menu */
.deepseek-usage-menu {}
.deepseek-usage-menu .header {}                 /* header row (title + refresh + pin) */
.deepseek-usage-menu .header .text {}           /* "DeepSeek Usage" title */
.deepseek-usage-menu .header .refresh {}
.deepseek-usage-menu .header .refresh:hover {}
.deepseek-usage-menu .header .pin-btn {}
.deepseek-usage-menu .header .pin-btn.pinned {}
.deepseek-usage-menu .section {}                /* every popup section */
.deepseek-usage-menu .section .title {}
/* Balance */
.deepseek-usage-menu .header .app-icon {}        /* product mark, when menu.icon is set */
.deepseek-usage-menu .header .title-stack {}     /* title and account, stacked */
.deepseek-usage-menu .header .account {}         /* account_label, or the key fingerprint */
.deepseek-usage-menu .section.balance.hero {}
.deepseek-usage-menu .section.hero .hero-value {}      /* the large balance figure */
.deepseek-usage-menu .section.hero .hero-value.low {}  /* below low_balance_threshold */
.deepseek-usage-menu .section.hero .hero-caption {}    /* "available to spend" */
.deepseek-usage-menu .section.hero .ledger {}          /* Topped-up / Granted rows */
.deepseek-usage-menu .section.hero .ledger .row {}
.deepseek-usage-menu .section.hero .ledger .row .name {}
.deepseek-usage-menu .section.hero .ledger .row .value {}
/* Budget */
.deepseek-usage-menu .section.budget {}
.deepseek-usage-menu .section.budget .progress {}                /* progress-bar track */
.deepseek-usage-menu .section.budget .progress .fill {}          /* filled portion */
.deepseek-usage-menu .section.budget .progress.low .fill {}      /* < 50%  */
.deepseek-usage-menu .section.budget .progress.medium .fill {}   /* 50-74% */
.deepseek-usage-menu .section.budget .progress.high .fill {}     /* 75-89% */
.deepseek-usage-menu .section.budget .progress.critical .fill {} /* >= 90% */
.deepseek-usage-menu .section.budget .footer .detail {}          /* "¥34.10 of ¥100.00" */
.deepseek-usage-menu .section.budget .footer .percent {}
/* Spend */
.deepseek-usage-menu .section.spend {}
.deepseek-usage-menu .section.spend .period-toggle {}
.deepseek-usage-menu .section.spend .period-btn {}
.deepseek-usage-menu .section.spend .period-btn.active {}
.deepseek-usage-menu .section.spend .spend-total {}
.deepseek-usage-menu .section.spend .graph-container {}
.deepseek-usage-menu .section.spend .spend-graph {}
.deepseek-usage-menu .section.spend .spend-graph-grid {}   /* its CSS color drives the grid lines */
/* Footer */
.deepseek-usage-menu .section.status .updated {}
.deepseek-usage-menu .section.status .updated.error {}     /* shown instead when a fetch failed */
```

## Example Style

A full style covering every element. Matches the look the other usage widgets use: a dark
panel (pair with `menu.blur: true`), section titles as small pills, a slim progress track, and
thin 1px separators between sections rather than boxed cards. Copy/paste and adjust colours
to taste.

> **Size the progress track with `min-height` and `max-height`, never `height`.** The widget
> draws the filled portion as a child frame sized to the track, and only the min/max pair
> constrains it - a bare `height` paints a short background inside a frame the layout has
> already stretched, leaving the fill standing proud of the bar.

```css
/* Bar */
.deepseek-usage {
    padding: 0 2px;
}
.deepseek-usage .widget-container {
    background-color: #24273a;
    margin: 2px 0;
    padding: 2px 8px;
    border-radius: 8px;
    min-height: 16px;
    height: 16px;
}
.deepseek-usage .icon {
    color: #74c7ec;
    padding-right: 5px;
}
.deepseek-usage .label {
    color: #74c7ec;
    padding: 2px 0;
}
.deepseek-usage .low,
.deepseek-usage .stale {
    color: #f9e2af;
    padding-left: 4px;
}
.deepseek-usage .budget.low      { color: #a6e3a1; }
.deepseek-usage .budget.medium   { color: #f9e2af; }
.deepseek-usage .budget.high     { color: #fab387; }
.deepseek-usage .budget.critical { color: #f38ba8; }

/* Popup */
.deepseek-usage-menu {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 14px;
    min-width: 320px;
}
.deepseek-usage-menu .header {
    background-color: rgba(17, 17, 27, 0.4);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 14px 18px 12px 18px;
}
.deepseek-usage-menu .header .text {
    font-family: 'Segoe UI';
    font-size: 14px;
    font-weight: 700;
    color: #cdd6f4;
}
.deepseek-usage-menu .header .refresh {
    font-size: 13px;
    color: #7f849c;
    background-color: transparent;
    border: none;
    padding: 0 6px;
}
.deepseek-usage-menu .header .refresh:hover {
    color: #89b4fa;
}
.deepseek-usage-menu .header .pin-btn {
    font-family: 'Segoe Fluent Icons';
    font-size: 12px;
    color: #7f849c;
    background-color: transparent;
    border: none;
    padding: 0 4px;
}
.deepseek-usage-menu .header .pin-btn.pinned {
    color: #cba6f7;
}
.deepseek-usage-menu .section {
    padding: 18px 18px 16px 18px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
/* Section titles read as small pills. */
.deepseek-usage-menu .section .title {
    font-family: 'Segoe UI';
    font-size: 10px;
    font-weight: 700;
    color: #bac2de;
    background-color: #313244;
    border-radius: 7px;
    padding: 3px 9px;
}
.deepseek-usage-menu .section .progress {
    background-color: #313244;
    border-radius: 3px;
    min-height: 6px;
    max-height: 6px;
    margin: 16px 0 13px 0;
}
/* The bar rests in the product's own colour, so the popup and the bar button that opened
   it read as one thing, then escalates away from it - identity never looks like a warning. */
.deepseek-usage-menu .section .progress .fill {
    background-color: #74c7ec;
    border-radius: 3px;
}
.deepseek-usage-menu .section .progress.medium .fill   { background-color: #f9e2af; }
.deepseek-usage-menu .section .progress.high .fill     { background-color: #fab387; }
.deepseek-usage-menu .section .progress.critical .fill { background-color: #f38ba8; }

/* Header mark */
.deepseek-usage-menu .header .app-icon {
    padding-right: 10px;
}
.deepseek-usage-menu .header .account {
    font-size: 10px;
    color: rgba(255, 255, 255, 0.55);
    padding-top: 2px;
}

/* Balance, as the hero of the popup */
.deepseek-usage-menu .section.balance.hero {
    padding: 20px 18px 16px 18px;
}
.deepseek-usage-menu .section.hero .hero-value {
    font-family: 'Segoe UI';
    font-size: 34px;
    font-weight: 700;
    color: #cdd6f4;
}
.deepseek-usage-menu .section.hero .hero-value.low {
    color: #f9e2af;
}
.deepseek-usage-menu .section.hero .hero-caption {
    font-family: 'Segoe UI';
    font-size: 11px;
    font-weight: 600;
    color: #a6adc8;
    padding-top: 2px;
}
.deepseek-usage-menu .section.hero .ledger {
    padding-top: 14px;
}
.deepseek-usage-menu .section.hero .ledger .row {
    padding: 4px 0;
}
.deepseek-usage-menu .section.hero .ledger .row .name {
    font-family: 'Segoe UI';
    font-size: 11px;
    color: #a6adc8;
}
.deepseek-usage-menu .section.hero .ledger .row .value {
    font-family: 'Segoe UI';
    font-size: 11px;
    font-weight: 600;
    color: #cdd6f4;
}

/* Budget */
.deepseek-usage-menu .section.budget .footer .detail {
    font-family: 'Segoe UI';
    font-size: 11px;
    color: #a6adc8;
}
.deepseek-usage-menu .section.budget .footer .percent {
    font-family: 'Segoe UI';
    font-size: 13px;
    font-weight: 700;
    color: #cdd6f4;
}
.deepseek-usage-menu .section.budget .footer .percent.medium   { color: #f9e2af; }
.deepseek-usage-menu .section.budget .footer .percent.high     { color: #fab387; }
.deepseek-usage-menu .section.budget .footer .percent.critical { color: #f38ba8; }

/* Spend */
.deepseek-usage-menu .section.spend .period-toggle {
    padding: 11px 0 8px 0;
}
.deepseek-usage-menu .section.spend .period-btn {
    font-family: 'Segoe UI';
    font-size: 11px;
    font-weight: 600;
    color: #7f849c;
    background-color: transparent;
    border: none;
    padding: 4px 10px;
    border-radius: 7px;
}
.deepseek-usage-menu .section.spend .period-btn:hover {
    color: #cdd6f4;
    background-color: #313244;
}
.deepseek-usage-menu .section.spend .period-btn.active {
    color: #1e1e2e;
    background-color: #74c7ec;
}
.deepseek-usage-menu .section.spend .spend-total {
    font-family: 'Segoe UI';
    font-size: 20px;
    font-weight: 700;
    color: #cdd6f4;
    padding: 5px 0 7px 0;
}
.deepseek-usage-menu .section.spend .graph-container {
    padding-top: 6px;
    padding-bottom: 8px;
}
.deepseek-usage-menu .section.spend .spend-graph {
    min-height: 46px;
    height: 46px;
    color: #74c7ec;
}
.deepseek-usage-menu .section.spend .spend-graph-grid {
    color: #313244;
}

/* Footer */
.deepseek-usage-menu .section.status .updated {
    font-family: 'Segoe UI';
    font-size: 10px;
    color: #6c7086;
}
.deepseek-usage-menu .section.status .updated.error {
    color: #f9e2af;
}
```

## Troubleshooting

**The bar shows `--` and the popup says "No API key".**
The widget found no key. With the default `api_key: "env"` it reads `YASB_DEEPSEEK_API_KEY`
and then `DEEPSEEK_API_KEY`. Setting a user environment variable does not affect processes
that are already running, so restart YASB after setting it:

```powershell
[Environment]::SetEnvironmentVariable("YASB_DEEPSEEK_API_KEY", "sk-...", "User")
```

**The popup says "API key rejected".**
The endpoint returned 401/403. The key is wrong, revoked, or belongs to a different account.
Check it on [platform.deepseek.com](https://platform.deepseek.com).

**Spend stays at 0 and the graph is flat.**
Expected until the balance actually moves. Spend is derived by differencing consecutive
balance readings, so the first reading establishes a baseline and nothing is recorded until a
later reading comes back lower. A brand-new ledger shows nothing on day one.

**Spend jumped by the size of my free credits.**
A granted-credit balance expiring looks exactly like spending it, because both are a drop with
no other signal. Set `spend_history.count_granted_as_spend: false` to count only topped-up
money, which cannot be affected by expiry.

**The balance is right but spend looks low.**
A top-up between two polls hides the spend that came before it - the net movement is upward,
so that interval records nothing. There is no usage endpoint to recover it from. Topping up
while idle avoids it.
