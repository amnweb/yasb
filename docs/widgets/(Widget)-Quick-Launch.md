# Quick Launch Widget

The Quick Launch widget provides a Spotlight style search launcher accessible from the bar. It displays a centered popup where you can search for applications, perform calculations, convert currencies, search browser bookmarks, search the web, run system commands, open Windows Settings pages, kill processes, find files and more, all from a single unified search interface.

## Widget Options

| Option               | Type   | Default                    | Description                                               |
|----------------------|--------|----------------------------|-----------------------------------------------------------|
| `label`              | string | `"\uf002"`                 | The label/icon for the widget on the bar.                 |
| `search_placeholder` | string | `"Search applications..."` | Placeholder text for the search field.                    |
| `max_results`        | int    | `50`                       | Maximum number of results displayed.                      |
| `show_icons`         | bool   | `true`                     | Show icons next to search results.                        |
| `icon_size`          | int    | `32`                       | Size of result icons in pixels.                           |
| `providers`          | dict   | See below                  | Configuration for each search provider.                   |
| `popup`              | dict   | See below                  | Popup window appearance settings.                         |
| `animation`          | dict   | `{enabled: true, type: "fadeInOut", duration: 200}` | Widget animation settings.       |
| `label_shadow`       | dict   | `None`                     | Label shadow options.                                     |
| `container_shadow`   | dict   | `None`                     | Container shadow options.                                 |
| `keybindings`        | list   | `[]`                       | Global keybindings for toggling the popup.                |
| `callbacks`          | dict   | `{on_left: "toggle_quick_launch", on_right: "do_nothing", on_middle: "do_nothing"}` | Mouse event callbacks. |

## Popup Options

| Option               | Type   | Default    | Description                                                     |
|----------------------|--------|------------|-----------------------------------------------------------------|
| `width`              | int    | `560`      | Width of the popup window in pixels.                            |
| `height`             | int    | `480`      | Height of the popup window in pixels.                           |
| `blur`               | bool   | `true`     | Enable background blur effect (Windows 11).                     |
| `round_corners`      | bool   | `true`     | Enable rounded corners on the popup window.                     |
| `round_corners_type` | string | `"normal"` | Corner rounding type (`"normal"` or `"small"`).                 |
| `border_color`       | string | `"System"` | Border color of the popup (`"System"`, HEX value, or `"None"`). |
| `dark_mode`          | bool   | `false`    | Force dark mode colors for the popup (Windows 11).              |

## Providers

Quick Launch uses a plugin-based provider system. Each provider handles a specific type of search and can be enabled/disabled independently. Providers are activated either automatically or via a prefix character typed into the search field.

**Provider Index**

- [Apps](#apps-provider)
- [Calculator](#calculator-provider)
- [Currency](#currency-provider)
- [Web Search](#web-search-provider)
- [Bookmarks](#bookmarks-provider)
- [System Commands](#system-commands-provider)
- [Settings](#settings-provider)
- [Kill Process](#kill-process-provider)
- [Port Viewer](#port-viewer-provider)
- [File Search](#file-search-provider)
- [Unit Converter](#unit-converter-provider)
- [Emoji](#emoji-provider)
- [Color Converter](#color-converter-provider)

### Apps Provider

Searches installed applications (Start Menu shortcuts). This is the default provider when no prefix is used.

| Option        | Type   | Default | Description                                     |
|---------------|--------|---------|-------------------------------------------------|
| `enabled`     | bool   | `true`  | Enable/disable the apps provider.               |
| `prefix`      | string | `"*"`  | Trigger prefix. `"*"` means included in default results. |
| `priority`    | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |
| `show_recent` | bool   | `true`  | Show recently launched apps at the top.          |
| `max_recent`  | int    | `10`    | Maximum number of recent apps to display.        |
| `show_path`   | bool   | `false` | Show the full path of the application shortcut.  |

### Calculator Provider

Inline math evaluation. Type `=` followed by a math expression (e.g., `=2+2`, `=sqrt(144)`).

| Option    | Type   | Default | Description                            |
|-----------|--------|---------|----------------------------------------|
| `enabled`  | bool   | `true`  | Enable/disable the calculator provider. |
| `prefix`   | string | `"="`  | Trigger prefix. Use `"*"` to include in default results. |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

### Currency Provider

Convert between currencies using ECB (European Central Bank) daily rates. Type `$` followed by an amount and currency codes (e.g., `$100 usd eur`, `$50 gbp jpy`). Rates are cached locally for 12 hours. Works offline using cached data.

| Option    | Type | Default | Description                            |
|-----------|------|---------|----------------------------------------|
| `enabled`  | bool   | `true`  | Enable/disable the currency provider.   |
| `prefix`   | string | `"$"`  | Trigger prefix. Use `"*"` to include in default results. |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

Input formats:
- `$100 usd eur` - Convert 100 USD to EUR
- `$50 gbp to jpy` - Convert 50 GBP to JPY (optional "to")
- `$usd eur` - Show rate for 1 USD to EUR
- `$usd` - Show 1 USD converted to common currencies
- `$eur` - Show EUR rates overview

Click a result to copy the converted value to the clipboard.

> [!NOTE]
> Currency rates are fetched from the ECB and cached for 12 hours. If there is no internet connection and no cached data, a "rates unavailable" message is shown. Stale cached rates are used as fallback when the network is unreachable.

### Web Search Provider

Opens a web search in the default browser. Type `?` followed by a search query (e.g., `?python docs`). The configured engine appears **first** in the results, followed by all other available engines so you can pick any of them with a single click.

| Option    | Type   | Default    | Description                                                   |
|-----------|--------|------------|---------------------------------------------------------------|
| `enabled`  | bool   | `true`     | Enable/disable the web search provider.                       |
| `prefix`   | string | `"?"`     | Trigger prefix. Use `"*"` to include in default results.     |
| `priority` | int    | `0`        | Sort order when multiple providers share the same prefix. Lower values appear first. |
| `engine`   | string | `"google"` | Preferred (first) search engine. All other engines are shown below it. |

Available engines:

| Engine          | Description                          |
|-----------------|--------------------------------------|
| `"google"`      | Google web search (default)          |
| `"bing"`        | Bing web search                      |
| `"duckduckgo"`  | DuckDuckGo private search            |
| `"wikipedia"`   | Wikipedia article search             |
| `"github"`      | GitHub repositories and code search  |
| `"youtube"`     | YouTube video search                 |
| `"reddit"`      | Reddit posts and communities search  |
| `"stackoverflow"`| Stack Overflow programming Q&A      |

### Bookmarks Provider

Search and open browser bookmarks. Type `*` followed by a search term (e.g., `*github`, `*recipes`). Supports Chrome, Edge, Brave, Vivaldi, Chromium, and Firefox.

| Option     | Type   | Default     | Description                                                                     |
|------------|--------|-------------|---------------------------------------------------------------------------------|
| `enabled`  | bool   | `true`      | Enable/disable the bookmarks provider.                                          |
| `prefix`   | string | `"*"`      | Trigger prefix. `"*"` means included in default results.                       |
| `priority` | int    | `0`         | Sort order when multiple providers share the same prefix. Lower values appear first. |
| `browser`  | string | `"all"`     | Browser to read bookmarks from (`"all"`, `"chrome"`, `"edge"`, `"brave"`, `"firefox"`, `"vivaldi"`, `"chromium"`). |
| `profile`  | string | `"Default"` | Chromium browser profile name (e.g., `"Default"`, `"Profile 1"`).               |

Bookmarks are cached in memory and automatically reloaded when the bookmark file changes. Search matches against bookmark title, URL, and folder name.

> [!NOTE]
> When `browser` is set to `"all"` (default), bookmarks are loaded from every supported browser found on the system (Chrome, Edge, Brave, Vivaldi, Chromium, Firefox). Duplicates across browsers are kept. Firefox bookmarks are read from a copy of the `places.sqlite` database to avoid locking issues.

### System Commands Provider

Exposes common system actions. Type `>` followed by a command name (e.g., `>shutdown`, `>lock`).

| Option    | Type | Default | Description                                  |
|-----------|------|---------|----------------------------------------------|
| `enabled`  | bool   | `true`  | Enable/disable the system commands provider.  |
| `prefix`   | string | `">"`  | Trigger prefix. Use `"*"` to include in default results. |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

Available commands: `shutdown`, `restart`, `sleep`, `hibernate`, `lock`, `sign out`, `force shutdown`, `force restart`.

### Settings Provider

Quick access to Windows Settings pages. Type `@` followed by a setting name (e.g., `@wifi`, `@bluetooth`, `@display`).

| Option    | Type | Default | Description                             |
|-----------|------|---------|-----------------------------------------|
| `enabled`  | bool   | `true`  | Enable/disable the settings provider.    |
| `prefix`   | string | `"@"`  | Trigger prefix. Use `"*"` to include in default results. |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

### Kill Process Provider

Search and terminate running processes. Type `!` followed by a process name (e.g., `!notepad`).

| Option    | Type | Default | Description                                |
|-----------|------|---------|--------------------------------------------|
| `enabled`  | bool   | `true`  | Enable/disable the kill process provider.   |
| `prefix`   | string | `"!"`  | Trigger prefix. Use `"*"` to include in default results. |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

### Port Viewer Provider

View TCP/UDP ports (via `netstat`) and the owning PID/process name.

Type `pv` followed by optional filters (e.g. `pv 80`, `pv tcp 443`, `pv kill 80`):
- `pv 80` - show entries for local port 80
- `pv tcp 443` - show TCP entries for local port 443
- `pv udp 53` - show UDP entries for local port 53
- `pv process chrome.exe` - show ports for a process (includes connected TCP entries)
- `pv proccess chrome.exe` - alias for `process`
- `pv kill 80` - kill the owning process for port 80 (if resolvable)
- `pv kill 12345` - kill PID 12345 (heuristic: numbers > 65535 are treated as PID)

Port numbers are matched by digits (substring match). For example, `pv udp 5` can match ports like `500`, `5353`, `5985`, etc.

Selecting a normal (non-`kill`) result copies a short summary string to the clipboard.

| Option                | Type   | Default | Description |
|-----------------------|--------|---------|-------------|
| `enabled`             | bool   | `true`  | Enable/disable the port viewer provider. |
| `prefix`              | string | `"pv"` | Trigger prefix. |
| `priority`            | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |
| `tcp_listening_only`  | bool   | `true`  | Only show `LISTENING` TCP entries by default. |
| `include_established` | bool   | `false` | Include non-`LISTENING` TCP entries (e.g. `ESTABLISHED`). |

### File Search Provider

Search files and folders on the system. Type `/` followed by a filename (e.g., `/readme.txt`). Uses the bundled [Everything](https://www.voidtools.com/) SDK for instant results or falls back to Windows Search.

| Option            | Type   | Default | Description                                                                     |
|-------------------|--------|---------|---------------------------------------------------------------------------------|
| `enabled`         | bool   | `true`  | Enable/disable the file search provider.                                        |
| `prefix`          | string | `"/"`  | Trigger prefix. Use `"*"` to include in default results.                       |
| `priority`        | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |
| `backend`         | string | `"auto"`| Search backend: `"auto"`, `"everything"`, or `"windows_search"`.                |

> [!NOTE]
> The Everything SDK DLL is bundled with the widget - no manual SDK setup is required. When `backend` is set to `"auto"`, the provider will try Everything SDK first and fall back to Windows Search if Everything is not running. For best performance, install [Everything](https://www.voidtools.com/) by voidtools.

### Unit Converter Provider

Convert between units of measurement. Type `~` followed by a value and unit (e.g., `~10 kg to lb`, `~100 f to c`). Supports length, weight, volume, speed, data sizes, time, and temperature.

| Option     | Type   | Default | Description                                |
|------------|--------|---------|--------------------------------------------|
| `enabled`  | bool   | `true`  | Enable/disable the unit converter provider. |
| `prefix`   | string | `"~"`  | Trigger prefix. Use `"*"` to include in default results. |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

Supported categories:
- **Length:** mm, cm, m, km, in, ft, yd, mi, nmi
- **Weight:** mg, g, kg, t, oz, lb, st
- **Volume:** ml, l, gal, qt, pt, cup, floz, tbsp, tsp
- **Speed:** m/s, km/h, mph, knots, ft/s
- **Data:** b, kb, mb, gb, tb, pb
- **Time:** ms, s, min, h, d, wk, yr
- **Temperature:** c, f, k

If no target unit is specified, common conversions within the same category are shown. Click a result to copy the value.

### Emoji Provider

Search and copy emojis to the clipboard. Type `:` followed by a name (e.g., `:smile`, `:fire`, `:heart`).

| Option     | Type   | Default | Description                           |
|------------|--------|---------|---------------------------------------|
| `enabled`  | bool   | `true`  | Enable/disable the emoji provider.    |
| `prefix`   | string | `":"`  | Trigger prefix. Use `"*"` to include in default results. |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

Searches emoji names, aliases, and tags. Click a result to copy the emoji character to the clipboard.

### Color Converter Provider

Convert colors between HEX, RGB, HSL, HSV, HWB, LAB, LCH, OKLAB, and OKLCH formats. Type `c:` followed by a color value (e.g., `c:#FF5500`, `c:rgb(255,85,0)`, `c:coral`).

| Option     | Type   | Default | Description                                  |
|------------|--------|---------|----------------------------------------------|
| `enabled`  | bool   | `true`  | Enable/disable the color converter provider.  |
| `prefix`   | string | `"c:"` | Trigger prefix. Use `"*"` to include in default results. |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

Accepted input formats:
- HEX: `#FF5500`, `#F50`, `FF5500`
- RGB: `rgb(255, 85, 0)` or `255, 85, 0`
- HSL: `hsl(20, 100%, 50%)`
- HWB: `hwb(20, 0%, 0%)`
- LAB: `lab(62.83, 51.28, 64.35)`
- LCH: `lch(62.83, 82.34, 51.42)`
- OKLAB: `oklab(0.6726, 0.0834, 0.1221)`
- OKLCH: `oklch(0.6726, 0.148, 55.65)`
- Named colors: `coral`, `steelblue`, `crimson`, etc.

Shows all nine representations (HEX, RGB, HSL, HSV, HWB, LAB, LCH, OKLAB, OKLCH). Press Enter on a result to copy the value.

## Provider Prefixes Reference

Prefixes are configurable per provider. Set `prefix` to `"*"` to include a provider in the default (unprefixed) results. These are the defaults:

| Prefix   | Provider         | Example               |
|----------|------------------|-----------------------|
| `*`      | Apps             | `notepad`             |
| `=`      | Calculator       | `=2*pi`               |
| `$`      | Currency         | `$100 usd eur`        |
| `*`      | Bookmarks        | `*github`             |
| `?`      | Web Search       | `?python tutorial`    |
| `>`      | System Commands  | `>lock`               |
| `@`      | Settings         | `@wifi`               |
| `!`      | Kill Process     | `!chrome`             |
| `/`      | File Search      | `/report.docx`        |
| `~`      | Unit Converter   | `~10 kg to lb`        |
| `:`      | Emoji            | `:fire`               |
| `c:`     | Color Converter  | `c:#FF5500`           |


## Example Minimal Configuration

```yaml
quick_launch:
  type: "yasb.quick_launch.QuickLaunchWidget"
  options:
    label: "<span>\uf002</span>"
    search_placeholder: "Search applications..."
    max_results: 50
    show_icons: true
    icon_size: 24
    popup:
      width: 640
      height: 480
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "System"
      dark_mode: true
    callbacks:
      on_left: "toggle_quick_launch"
    keybindings:
      - keys: "alt+space"
        action: "toggle_quick_launch"
```
## Example Configuration

```yaml
quick_launch:
  type: "yasb.quick_launch.QuickLaunchWidget"
  options:
    label: "<span>\uf002</span>"
    search_placeholder: "Search applications..."
    max_results: 50
    show_icons: true
    icon_size: 32
    providers:
      apps:
        enabled: true
        prefix: "*"
        priority: 0
        show_recent: true
        max_recent: 10
        show_path: false
      calculator:
        enabled: true
        prefix: "="
        priority: 0
      currency:
        enabled: true
        prefix: "$"
        priority: 0
      bookmarks:
        enabled: true
        prefix: "*"
        priority: 0
        browser: "all"
        profile: "Default"
      web_search:
        enabled: true
        prefix: "?"
        priority: 0
        engine: "google"
      system_commands:
        enabled: true
        prefix: ">"
        priority: 0
      settings:
        enabled: true
        prefix: "@"
        priority: 0
      kill_process:
        enabled: true
        prefix: "!"
        priority: 0
      file_search:
        enabled: true
        prefix: "/"
        priority: 0
        backend: "auto"
      unit_converter:
        enabled: true
        prefix: "~"
        priority: 0
      emoji:
        enabled: true
        prefix: ":"
        priority: 0
      color_converter:
        enabled: true
        prefix: "c:"
        priority: 0
    popup:
      width: 640
      height: 480
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "System"
      dark_mode: true
    callbacks:
      on_left: "toggle_quick_launch"
    keybindings:
      - keys: "alt+space"
        action: "toggle_quick_launch"
```

## Description of Options

- **label:** The label/icon displayed on the bar. Can contain HTML with icon fonts.
- **search_placeholder:** Placeholder text shown in the search input when empty.
- **max_results:** Maximum number of results displayed across all providers.
- **show_icons:** Whether to show icons next to each result.
- **icon_size:** The size of application icons (in pixels). Only applies to image-based icons.
- **providers:** Configuration for each search provider. Each provider can be individually enabled/disabled and configured.
  - ***apps:*** Application search with frecency-ranked results. See Apps Provider table above.
  - ***calculator:*** Inline math evaluation with prefix `=`.
  - ***currency:*** Currency conversion using ECB daily rates with prefix `$`. Rates cached for 12 hours.
  - ***web_search:*** Browser-based web search with prefix `?`. Shows all engines (Google, Bing, DuckDuckGo, Wikipedia, GitHub, YouTube, Reddit, Stack Overflow) with the preferred engine listed first.
  - ***system_commands:*** System actions (shutdown, restart, lock, etc.) with prefix `>`.
  - ***settings:*** Quick access to Windows Settings pages with prefix `@`.
  - ***kill_process:*** Process search and termination with prefix `!`.
  - ***file_search:*** File and folder search with prefix `/`. Uses Everything SDK or Windows Search.
  - ***unit_converter:*** Convert between units (length, weight, volume, speed, data, time, temperature) with prefix `~`.
  - ***emoji:*** Search and copy emojis to clipboard with prefix `:`.
  - ***color_converter:*** Convert colors between HEX, RGB, HSL, HSV with prefix `c:`.
- **popup:** Popup window appearance settings.
  - ***width:*** Width of the popup window in pixels.
  - ***height:*** Height of the popup window in pixels.
  - ***blur:*** Enable background blur effect (requires Windows 11).
  - ***round_corners:*** Enable rounded corners on the popup.
  - ***round_corners_type:*** Type of corner rounding (`"normal"` or `"small"`).
  - ***border_color:*** Border color of the popup window (`"System"` for system accent color, HEX value, or `"None"`).
- **animation:** Widget animation settings.
  - ***enabled:*** Whether animations are enabled.
  - ***type:*** Type of animation (`"fadeInOut"`).
  - ***duration:*** Duration of the animation in milliseconds.
- **keybindings:** A list of global keybindings. Each entry must specify `keys` (a list of key combinations) and `action` (the callback to invoke, e.g., `"toggle_quick_launch"`).
- **callbacks:** Mouse event callbacks (`on_left`, `on_middle`, `on_right`). Valid actions: `"toggle_quick_launch"`, `"do_nothing"`.
- **label_shadow:** Shadow options for the bar label.
- **container_shadow:** Shadow options for the widget container.

## Example Style

```css
/* Bar widget */
.quick-launch-widget .icon {
    font-size: 14px;
    padding: 0 4px;
}
.quick-launch-widget .icon:hover {
    color: #fff;
}
.quick-launch-popup .container {
    background-color:rgba(30, 30, 30, 0.9)
}
.quick-launch-popup .search {
    padding: 12px 16px;
    background-color: transparent;
    border-bottom: 1px solid rgba(255, 255, 255, 0.15);
}
.quick-launch-popup .search-icon {
    font-family: "Segoe Fluent Icons";
    font-size: 18px;
    color: rgba(255, 255, 255, 0.6);
    padding-right: 8px;
    min-width: 18px;
}
.quick-launch-popup .search-submit-icon {
    font-family: "Segoe Fluent Icons";
    font-size: 18px;
    color: rgba(255, 255, 255, 0.6);
    min-width: 18px;
}
.quick-launch-popup .search-input {
    background: transparent;
    border: none;
    color: #ffffff;
    font-size: 16px;
    font-family: 'Segoe UI';
    font-weight: 400;
    padding: 4px 0;
} 
.quick-launch-popup .results {
    background: transparent;
    padding: 8px;
}
.quick-launch-popup .results .item {
    padding: 16px;
    border-radius: 8px;
}
.quick-launch-popup .results .item:hover,
.quick-launch-popup .results .item.selected {
    background-color: rgba(128, 130, 158, 0.15);
} 
.quick-launch-popup .results .item-title {
    font-size: 15px;
    font-family: 'Segoe UI';
    font-weight: 600;
    color: #ffffff;
}
.quick-launch-popup .results .item-description {
    font-size: 11px;
    font-weight: 600;
    font-family: 'Segoe UI';
    color: rgba(255, 255, 255, 0.6);     
}
.quick-launch-popup .results .item-icon-char {
    font-family: "Segoe Fluent Icons";
    font-size: 18px;
    color: #c6cad8;
    margin: 0;
    padding: 0;
}
.quick-launch-popup .results-empty {
    font-size: 24px;
    font-family: 'Segoe UI';
    color: rgba(255, 255, 255, 0.6);
    padding-top: 32px;
}
```

> [!NOTE]
> All provider icons use **Segoe Fluent Icons** (built into Windows 11). The `font-family: "Segoe Fluent Icons"` must be set on `.search-icon`, `.search-enter-icon`, and `.result-icon-char` for icons to render correctly.

## Preview 
![QL Widget Preview](assets/3c5a8b2f-e7d1f4a9-6c8b-4d2e-9f1a3e5c7b2d.png)

