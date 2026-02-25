# Quick Launch Widget

The Quick Launch widget provides a Spotlight style search launcher accessible from the bar. It displays a centered popup where you can search for applications, perform calculations, convert currencies, search browser bookmarks, search the web, run system commands, open Windows Settings pages, kill processes, find files and more, all from a single unified search interface.

## Widget Options

| Option               | Type   | Default                                                                             | Description                                                                                                             |
| -------------------- | ------ | ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `label`              | string | `"\uf002"`                                                                          | The label/icon for the widget on the bar.                                                                               |
| `search_placeholder` | string | `"Search applications..."`                                                          | Placeholder text for the search field.                                                                                  |
| `max_results`        | int    | `50`                                                                                | Maximum number of results displayed (1–500).                                                                            |
| `show_icons`         | bool   | `true`                                                                              | Show icons next to search results.                                                                                      |
| `icon_size`          | int    | `32`                                                                                | Size of result icons in pixels.                                                                                         |
| `home_page`          | bool   | `true`                                                                              | Show provider shortcut tiles when search is empty.                                                                      |
| `compact_mode`       | bool   | `false`                                                                             | When enabled, the popup starts collapsed to just the search bar and only expands to show results when you start typing. |
| `compact_text`       | bool   | `false`                                                                             | When enabled, each result row is single-line: the description is shown inline on the right side instead of on a second line below the title. |
| `providers`          | dict   | See below                                                                           | Configuration for each search provider.                                                                                 |
| `popup`              | dict   | See below                                                                           | Popup window appearance settings.                                                                                       |
| `animation`          | dict   | `{enabled: true, type: "fadeInOut", duration: 200}`                                 | Widget animation settings.                                                                                              |
| `label_shadow`       | dict   | `None`                                                                              | Label shadow options.                                                                                                   |
| `container_shadow`   | dict   | `None`                                                                              | Container shadow options.                                                                                               |
| `keybindings`        | list   | `[]`                                                                                | Global keybindings for toggling the popup.                                                                              |
| `callbacks`          | dict   | `{on_left: "toggle_quick_launch", on_right: "do_nothing", on_middle: "do_nothing"}` | Mouse event callbacks.                                                                                                  |

## Popup Options

| Option               | Type   | Default    | Description                                                               |
| -------------------- | ------ | ---------- | ------------------------------------------------------------------------- |
| `width`              | int    | `720`      | Width of the popup window in pixels.                                      |
| `height`             | int    | `480`      | Height of the popup window in pixels.                                     |
| `blur`               | bool   | `true`     | Enable background blur effect (Windows 11).                               |
| `round_corners`      | bool   | `true`     | Enable rounded corners on the popup window.                               |
| `round_corners_type` | string | `"normal"` | Corner rounding type (`"normal"` or `"small"`).                           |
| `border_color`       | string | `"System"` | Border color of the popup (`"System"`, HEX value, or `"None"`).           |
| `dark_mode`          | bool   | `true`     | Force dark mode colors for the popup (Windows 11).                        |
| `screen`             | string | `"focus"`  | Which screen to show the popup on: `"focus"`, `"cursor"`, or `"primary"`. |

#### Screen Modes

| Mode        | Description                                                     |
| ----------- | --------------------------------------------------------------- |
| `"focus"`   | Show popup on the screen where the currently focused window is. |
| `"cursor"`  | Show popup on the screen where the mouse cursor is.             |
| `"primary"` | Always show popup on the primary monitor.                       |

> [!NOTE]
> When using multiple monitors with bars on each screen, only one popup is shown at a time regardless of which screen triggers it.

## Providers

Quick Launch uses a plugin-based provider system. Each provider handles a specific type of search and can be enabled/disabled independently. Providers are activated either automatically or via a prefix character typed into the search field.

**Provider Index**

- [Apps](#apps-provider)
- [Bookmarks](#bookmarks-provider)
- [Calculator](#calculator-provider)
- [Clipboard History](#clipboard-history-provider)
- [Color](#color-provider)
- [Currency](#currency-provider)
- [Developer Tools](#developer-tools-provider)
- [Emoji](#emoji-provider)
- [File Search](#file-search-provider)
- [GitHub Notifications](#github-notifications-provider)
- [Hacker News](#hacker-news-provider)
- [IP / Network Info](#ip--network-info-provider)
- [Kill Process](#kill-process-provider)
- [Port Viewer](#port-viewer-provider)
- [Settings](#settings-provider)
- [Snippets](#snippets-provider)
- [System Commands](#system-commands-provider)
- [Unit Converter](#unit-converter-provider)
- [VSCode](#vscode-provider)
- [Web Search](#web-search-provider)
- [Window Switcher](#window-switcher-provider)
- [Windows Terminal](#windows-terminal-provider)
- [World Clock](#world-clock-provider)
- [WSL](#wsl-provider)

### Apps Provider

Searches installed applications (Start Menu shortcuts). This is the default provider when no prefix is used.

| Option             | Type   | Default | Description                                                                          |
| ------------------ | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`          | bool   | `true`  | Enable/disable the apps provider.                                                    |
| `prefix`           | string | `"*"`   | Trigger prefix. `"*"` means included in default results.                             |
| `priority`         | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |
| `show_recent`      | bool   | `true`  | Show recently launched apps at the top.                                              |
| `max_recent`       | int    | `10`    | Maximum number of recent apps to display.                                            |
| `show_description` | bool   | `false` | Show a short description of the application.                                         |

### Bookmarks Provider

Search and open browser bookmarks. Type `*` followed by a search term (e.g., `*github`, `*recipes`). Supports Chrome, Edge, Brave, Vivaldi, Chromium, and Firefox.

| Option     | Type   | Default     | Description                                                                                                        |
| ---------- | ------ | ----------- | ------------------------------------------------------------------------------------------------------------------ |
| `enabled`  | bool   | `false`     | Enable/disable the bookmarks provider.                                                                             |
| `prefix`   | string | `"*"`       | Trigger prefix. `"*"` means included in default results.                                                           |
| `priority` | int    | `0`         | Sort order when multiple providers share the same prefix. Lower values appear first.                               |
| `browser`  | string | `"all"`     | Browser to read bookmarks from (`"all"`, `"chrome"`, `"edge"`, `"brave"`, `"firefox"`, `"vivaldi"`, `"zen"`). |
| `profile`  | string | `"Default"` | Chromium browser profile name (e.g., `"Default"`, `"Profile 1"`).                                                  |

Bookmarks are cached in memory and automatically reloaded when the bookmark file changes. Search matches against bookmark title, URL, and folder name.

> [!NOTE]
> When `browser` is set to `"all"` (default), bookmarks are loaded from every supported browser found on the system (Chrome, Edge, Brave, Vivaldi, Chromium, Firefox, Zen). Duplicates across browsers are kept. To limit to a specific browser, set the `browser` option to one of the supported browser names.

### Calculator Provider

Inline math evaluation. Type `=` followed by a math expression (e.g., `=2+2`, `=sqrt(144)`).

| Option     | Type   | Default | Description                                                                          |
| ---------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`  | bool   | `false` | Enable/disable the calculator provider.                                              |
| `prefix`   | string | `"="`   | Trigger prefix. Use `"*"` to include in default results.                             |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

### Clipboard History Provider

Browse and restore Windows Clipboard History entries. Type `cb` to list recent items, `cb <term>` to filter, or `cb clear` to reveal the "Clear clipboard history" action. Supports plain text, rich text (HTML), and images with previews, press Enter to restore an item to the clipboard.

| Option      | Type   | Default | Description                                                                          |
| ----------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`   | bool   | `false` | Enable/disable the clipboard history provider.                                       |
| `prefix`    | string | `"cb"`  | Trigger prefix. Use `"*"` to include in default results.                             |
| `priority`  | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |
| `max_items` | int    | `30`    | Maximum number of clipboard history items to show.                                   |

Usage:

- Press Enter on a result to restore it to the clipboard.
- Right-click a result for `Copy to clipboard` or `Delete from history` actions.

> [!NOTE]
> Clipboard History requires Windows' Clipboard History feature. If the feature is disabled or access is denied, Quick Launch will show an explanatory message and can open the Windows Clipboard settings.

### Color Provider

Pick colors from the screen and convert between HEX, RGB, HSL, HSV, HWB, LAB, LCH, OKLAB, and OKLCH formats. Type `c:` followed by a color value (e.g., `c:#FF5500`, `c:rgb(255,85,0)`, `c:coral`).

| Option     | Type   | Default | Description                                                                          |
| ---------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`  | bool   | `false` | Enable/disable the color provider.                                                   |
| `prefix`   | string | `"c:"`  | Trigger prefix. Use `"*"` to include in default results.                             |
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

### Currency Provider

Convert between currencies using ECB (European Central Bank) daily rates. Type `$` followed by an amount and currency codes (e.g., `$100 usd eur`, `$50 gbp jpy`). Rates are cached locally for 12 hours. Works offline using cached data.

| Option     | Type   | Default | Description                                                                          |
| ---------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`  | bool   | `false` | Enable/disable the currency provider.                                                |
| `prefix`   | string | `"$"`   | Trigger prefix. Use `"*"` to include in default results.                             |
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

### Developer Tools Provider

A collection of common developer utilities accessible from Quick Launch. All operations are local — no network requests, no API keys, instant results.

| Option     | Type   | Default | Description                                  |
| ---------- | ------ | ------- | -------------------------------------------- |
| `enabled`  | bool   | `false` | Enable/disable the Developer Tools provider. |
| `prefix`   | string | `"dev"` | Prefix to activate the provider.             |
| `priority` | int    | `0`     | Display priority (higher = shown first).     |

**Available tools:**

| Command  | Description                                        | Example                     |
| -------- | -------------------------------------------------- | --------------------------- |
| `uuid`   | Generate UUID v4 values (optional count)           | `dev uuid` or `dev uuid 10` |
| `hash`   | MD5, SHA1, SHA256, SHA512 hashes                   | `dev hash hello world`      |
| `base64` | Base64 encode (and auto-decode if valid)           | `dev base64 hello`          |
| `url`    | URL percent-encode/decode                          | `dev url hello world`       |
| `jwt`    | Decode JWT token payload                           | `dev jwt eyJhbG...`         |
| `lorem`  | Generate lorem ipsum paragraphs/words              | `dev lorem`                 |
| `ts`     | Convert between unix timestamps and dates          | `dev ts 1700000000`         |
| `pw`     | Generate secure random passwords (optional length) | `dev pw` or `dev pw 32`     |

**Usage examples:**

- Type `dev` to see all available tools as tiles
- Type `dev uuid` to generate 5 random UUIDs (click to copy)
- Type `dev hash mypassword` to see MD5/SHA1/SHA256/SHA512 hashes
- Type `dev base64 hello` to encode; paste Base64 text to auto-decode
- Type `dev jwt <token>` to decode JWT payload with timestamp formatting
- Type `dev ts` to see current unix timestamp; type `dev ts 1700000000` to convert
- Type `dev pw 24` to generate 24-character passwords

> [!NOTE]
> All Developer Tools operations run entirely offline using Python's standard library. Click any result to copy it to the clipboard.

### Emoji Provider

Search and copy emojis to the clipboard. Type `:` followed by a name (e.g., `:smile`, `:fire`, `:heart`).

| Option     | Type   | Default | Description                                                                          |
| ---------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`  | bool   | `false` | Enable/disable the emoji provider.                                                   |
| `prefix`   | string | `":"`   | Trigger prefix. Use `"*"` to include in default results.                             |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

Searches emoji names, aliases, and tags. Click a result to copy the emoji character to the clipboard.

### File Search Provider

Search files and folders on the system. Type `/` followed by a filename (e.g., `/readme.txt`). Supports glob patterns like `/*.mp3` or `/config*.json`.

| Option      | Type   | Default  | Description                                                                          |
| ----------- | ------ | -------- | ------------------------------------------------------------------------------------ |
| `enabled`   | bool   | `false`  | Enable/disable the file search provider.                                             |
| `prefix`    | string | `"/"`    | Trigger prefix. Use `"*"` to include in default results.                             |
| `priority`  | int    | `0`      | Sort order when multiple providers share the same prefix. Lower values appear first. |
| `backend`   | string | `"auto"` | Search backend: `"auto"`, `"everything"`, `"index"`, or `"disk"`.                    |
| `show_path` | bool   | `true`   | Show the parent folder path and file size in the result description.                 |

#### Backends

| Backend        | Description                                                                                                                                                                                                             |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `"auto"`       | Tries Everything first, then Index, then Disk as a final fallback.                                                                                                                                                      |
| `"everything"` | Uses the bundled [Everything](https://www.voidtools.com/) SDK for instant indexed search. Requires the Everything process to be running. Supports installations via installer, portable, or [Scoop](https://scoop.sh/). |
| `"index"`      | Uses the Windows Search indexer via ADODB/SystemIndex. Only searches indexed locations.                                                                                                                                 |
| `"disk"`       | Full disk scan using Win32 `FindFirstFileExW`. No index required. Works on any system but slower than Everything.                                                                                                       |

> [!NOTE]
> The Everything SDK DLL is bundled with the widget - no manual SDK setup is required. For best performance, install [Everything](https://www.voidtools.com/) by voidtools. The widget automatically detects Everything installed via the official installer, Scoop package manager, or in the standard Program Files directory. If Everything is not running, the widget shows a prompt to launch it.

> [!NOTE]
> The `"disk"` backend only scans fixed local drives. Removable drives (USB), network drives, and CD/DVD drives are automatically skipped. System directories like `Windows`, `$Recycle.Bin`, `node_modules`, `.git`, and other common cache/build folders are also excluded for performance.

### GitHub Notifications Provider

Browse GitHub notifications directly from Quick Launch. Type `gh` to see your notifications grouped by unread/read status, sorted by most recent. Clicking a notification opens it in the browser and marks it as read. Uses the same GitHub API layer as the bar widget.

| Option     | Type   | Default | Description                                                                          |
| ---------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`  | bool   | `false` | Enable/disable the GitHub Notifications provider.                                    |
| `prefix`   | string | `"gh"`  | Trigger prefix. Use `"*"` to include in default results.                             |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |
| `token`    | string | `"env"` | GitHub personal access token. Use `"env"` to read from the `YASB_GITHUB_TOKEN` environment variable, or paste the token directly. |

**Usage examples:**

- Type `gh` to fetch and list all notifications (fetches fresh data each time the popup opens).
- Type `gh review` to filter notifications by title, repo, type, or reason.
- Click a notification to open it in the browser and mark as read.
- Right-click a notification for:
  - **Copy URL** — copy the notification URL to clipboard.
  - **Mark as read** — mark a single notification as read.
  - **Mark all as read** — mark every notification as read.

> [!NOTE]
> The provider fetches fresh notifications every time the popup opens (no stale cache). If the same GitHub token is used for both the bar widget and this provider, the bar widget automatically refreshes when the provider fetches new data or marks notifications as read.

> [!NOTE]
> You need a GitHub Personal Access Token (classic) with the `notifications` scope. Generate one at https://github.com/settings/tokens. You can set the token via the `YASB_GITHUB_TOKEN` environment variable (recommended) or directly in the config.

### Hacker News Provider

Browse and search Hacker News stories directly from Quick Launch. Type `hn` to see available topics (Front Page, Newest, Best, Ask HN, Show HN, Jobs, Best Comments, Active), then click a topic to load stories. You can also type a keyword after a topic to filter (e.g., `hn newest rust`), or type any keyword directly to search all of HN (e.g., `hn python`).

Clicking a story opens it in your default browser. Right-click a story to open the HN comments page or copy the URL.

| Option      | Type   | Default | Description                                                                          |
| ----------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`   | bool   | `false` | Enable/disable the Hacker News provider.                                             |
| `prefix`    | string | `"hn"`  | Trigger prefix to activate the provider.                                             |
| `priority`  | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |
| `cache_ttl` | int    | `300`   | How long (in seconds) to cache feed results before fetching again.                   |
| `max_items` | int    | `30`    | Maximum number of stories to fetch per topic (hnrss.org limit is 100).               |

**Available topics:**

| Topic          | Description                                    |
| -------------- | ---------------------------------------------- |
| `frontpage`    | Top stories on the HN front page               |
| `newest`       | Most recently submitted stories                |
| `best`         | Highest-voted stories overall                  |
| `ask`          | Ask HN posts and discussions                   |
| `show`         | Show HN community projects and launches        |
| `jobs`         | Job postings from YC companies                 |
| `bestcomments` | Highly voted comments from across Hacker News  |
| `active`       | Posts with the most active ongoing discussions |

**Usage examples:**

- `hn` — Show all topic tiles
- `hn frontpage` — Load front page stories
- `hn newest rust` — Search newest stories for "rust"
- `hn python` — Search all of HN for "python"
- `hn ask` — Browse Ask HN posts

Each story result displays:

- **Title:** The story title
- **Description:** Points, comment count, author, and relative time (e.g., `42 points │ 15 comments │ by username │ 3h ago`)

**Context menu actions:**

- **Open HN comments** — Opens the Hacker News discussion page
- **Copy URL** — Copies the story URL to clipboard

> [!NOTE]
> Hacker News provider uses [hnrss.org](https://hnrss.org) RSS feeds. Results are cached in memory and on disk to minimize network requests. No API key is required.

### IP / Network Info Provider

Provides local network interface details, public IP lookup, subnet calculator, IP analysis, DNS lookup, and MAC address listing. All operations except public IP are fully offline.

| Option     | Type   | Default | Description                                    |
| ---------- | ------ | ------- | ---------------------------------------------- |
| `enabled`  | bool   | `false` | Enable/disable the IP / Network Info provider. |
| `prefix`   | string | `"ip"`  | Prefix to activate the provider.               |
| `priority` | int    | `0`     | Display priority (higher = shown first).       |

**Available tools:**

| Command  | Description                                        | Example                  |
| -------- | -------------------------------------------------- | ------------------------ |
| `info`   | Show local interfaces (IP, MAC, subnet mask)       | `ip info`                |
| `public` | Fetch your external IP, ISP, location (online)     | `ip public`              |
| `calc`   | Subnet calculator from CIDR notation               | `ip calc 192.168.1.0/24` |
| `check`  | Analyze IP (type, class, binary, hex, reverse DNS) | `ip check 10.0.0.1`      |
| `dns`    | Resolve hostname to IP addresses                   | `ip dns google.com`      |
| `mac`    | List all adapter MAC addresses                     | `ip mac`                 |

**Usage examples:**

- Type `ip` to see all available tools as tiles
- Type `ip info` to list all local network interfaces with IPv4, IPv6, MAC, and subnet mask
- Type `ip public` to fetch your public IP with ISP, location, and timezone
- Type `ip calc 10.0.0.0/16` to see network, broadcast, host range, total hosts
- Type `ip check 172.16.5.1` to see type (Private), class (B), binary, hex representation
- Type `ip dns github.com` to resolve IPv4 and IPv6 addresses
- Type `ip mac` to list all adapter MAC addresses

> [!NOTE]
> Public IP uses [ip-api.com](http://ip-api.com)

### Kill Process Provider

Search and terminate running processes. Type `!` followed by a process name (e.g., `!notepad`).

| Option     | Type   | Default | Description                                                                          |
| ---------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`  | bool   | `false` | Enable/disable the kill process provider.                                            |
| `prefix`   | string | `"!"`   | Trigger prefix. Use `"*"` to include in default results.                             |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

### Port Viewer Provider

View TCP/UDP ports (via `netstat`) and the owning PID/process name.

Type `pv` followed by optional filters (e.g. `pv 80`, `pv tcp 443`, `pv kill 80`):

- `pv 80` - show entries for local port 80
- `pv tcp 443` - show TCP entries for local port 443
- `pv udp 53` - show UDP entries for local port 53
- `pv chrome` - show ports for processes matching "chrome" (includes all TCP states)
- `pv kill 80` - kill the owning process for port 80 (if resolvable)
- `pv kill 12345` - kill PID 12345 (heuristic: numbers > 65535 are treated as PID)
- `pv kill chrome` - kill processes matching "chrome"

Port numbers are matched by digits (substring match). For example, `pv udp 5` can match ports like `500`, `5353`, `5985`, etc. Text filters search across process names, addresses, protocols and states.

Selecting a normal (non-`kill`) result copies a short summary string to the clipboard.

| Option                | Type   | Default | Description                                                                          |
| --------------------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`             | bool   | `false` | Enable/disable the port viewer provider.                                             |
| `prefix`              | string | `"pv"`  | Trigger prefix.                                                                      |
| `priority`            | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |
| `tcp_listening_only`  | bool   | `true`  | Only show `LISTENING` TCP entries by default.                                        |
| `include_established` | bool   | `false` | Include non-`LISTENING` TCP entries (e.g. `ESTABLISHED`).                            |

### Settings Provider

Quick access to Windows Settings pages. Type `@` followed by a setting name (e.g., `@wifi`, `@bluetooth`, `@display`).

| Option     | Type   | Default | Description                                                                          |
| ---------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`  | bool   | `false` | Enable/disable the settings provider.                                                |
| `prefix`   | string | `"@"`   | Trigger prefix. Use `"*"` to include in default results.                             |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

### Snippets Provider

Save and type text snippets into the previously focused window. Type `;` to see all your snippets sorted by recent use, or `;meeting` to filter by name or content. Selecting a snippet closes the popup and types the text into whatever window was focused before, using SendInput. You can also create and edit snippets inline using the preview panel.

Snippets support template variables that get resolved at the moment you use them:

| Variable            | Description                                |
| ------------------- | ------------------------------------------ |
| `{{date}}`          | Current date (default format: YYYY-MM-DD). |
| `{{date:%d/%m/%Y}}` | Current date with a custom format.         |
| `{{time}}`          | Current time (default format: HH:MM:SS).   |
| `{{time:%I:%M %p}}` | Current time with a custom format.         |
| `{{datetime}}`      | Current date and time.                     |
| `{{clipboard}}`     | Current clipboard text.                    |
| `{{username}}`      | Windows username.                          |

Right-click a snippet for options like Copy to clipboard, Edit, or Delete.

| Option       | Type   | Default | Description                                                                                                                       |
| ------------ | ------ | ------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `enabled`    | bool   | `false` | Enable/disable the snippets provider.                                                                                             |
| `prefix`     | string | `";"`   | Trigger prefix. Use `"*"` to include in default results.                                                                          |
| `priority`   | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first.                                              |
| `type_delay` | int    | `200`   | Delay in milliseconds before typing starts after the popup closes. Increase if the target window needs more time to regain focus. |

### System Commands Provider

Exposes common system actions. Type `>` followed by a command name (e.g., `>shutdown`, `>lock`).

| Option     | Type   | Default | Description                                                                          |
| ---------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`  | bool   | `false` | Enable/disable the system commands provider.                                         |
| `prefix`   | string | `">"`   | Trigger prefix. Use `"*"` to include in default results.                             |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

Available commands: `shutdown`, `restart`, `sleep`, `hibernate`, `lock`, `sign out`, `force shutdown`, `force restart`.

### Unit Converter Provider

Convert between units of measurement. Type `~` followed by a value and unit (e.g., `~10 kg to lb`, `~100 f to c`). Supports length, weight, volume, speed, data sizes, time, and temperature.

| Option     | Type   | Default | Description                                                                          |
| ---------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`  | bool   | `false` | Enable/disable the unit converter provider.                                          |
| `prefix`   | string | `"~"`   | Trigger prefix. Use `"*"` to include in default results.                             |
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

### VSCode Provider

Search and open recently used projects, folders, and files directly in Visual Studio Code. Type `vsc` (or your configured prefix) to see your recent VSCode history, or `vsc <query>` to fuzzy search through them. Results are intelligently scored based on the search query.

| Option     | Type   | Default | Description                              |
| ---------- | ------ | ------- | ---------------------------------------- |
| `enabled`  | bool   | `false` | Enable/disable the VSCode provider.      |
| `prefix`   | string | `"vsc"` | Prefix to activate the provider.         |
| `priority` | int    | `0`     | Display priority (higher = shown first). |

**Usage examples:**

- Type `vsc` to see your most recent VSCode projects chronologically.
- Type `vsc yasb` to fuzzy search for any recent folders or files matching "yasb".
- Selecting any project opens it instantly via the `code` CLI.

> [!NOTE]
> The VSCode provider reads directly from VSCode's internal SQLite state database (`state.vscdb`) in read-only mode to prevent lock issues and does not require VSCode to be running.

### Web Search Provider

Opens a web search in the default browser. Type `?` followed by a search query (e.g., `?python docs`). The configured engine appears **first** in the results, followed by all other available engines so you can pick any of them with a single click.

| Option     | Type   | Default    | Description                                                                          |
| ---------- | ------ | ---------- | ------------------------------------------------------------------------------------ |
| `enabled`  | bool   | `false`    | Enable/disable the web search provider.                                              |
| `prefix`   | string | `"?"`      | Trigger prefix. Use `"*"` to include in default results.                             |
| `priority` | int    | `0`        | Sort order when multiple providers share the same prefix. Lower values appear first. |
| `engine`   | string | `"google"` | Preferred (first) search engine. All other engines are shown below it.               |

Available engines:

| Engine            | Description                         |
| ----------------- | ----------------------------------- |
| `"google"`        | Google web search (default)         |
| `"bing"`          | Bing web search                     |
| `"duckduckgo"`    | DuckDuckGo private search           |
| `"wikipedia"`     | Wikipedia article search            |
| `"github"`        | GitHub repositories and code search |
| `"youtube"`       | YouTube video search                |
| `"reddit"`        | Reddit posts and communities search |
| `"stackoverflow"` | Stack Overflow programming Q&A      |

### Window Switcher Provider

Quickly search and switch to currently open application windows. Type `win` followed by the window title or application name to filter the list. When no query is provided, windows are listed in Z-order.

| Option     | Type   | Default | Description                                                                          |
| ---------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`  | bool   | `false`  | Enable/disable the window switcher provider.                                         |
| `prefix`   | string | `"win"` | Trigger prefix. Use `"*"` to include in default results.                             |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

### Windows Terminal Provider

Browse and launch Windows Terminal profiles. Type `wt` to list all available profiles from installed terminal variants (Stable, Preview, Canary). Profiles are grouped by terminal installation. Supports launching profiles normally or as administrator via the context menu.

| Option     | Type   | Default | Description                                                                          |
| ---------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`  | bool   | `false` | Enable/disable the Windows Terminal provider.                                        |
| `prefix`   | string | `"wt"`  | Trigger prefix. Use `"*"` to include in default results.                             |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

**Usage examples:**

- Type `wt` to see all profiles from every installed terminal variant.
- Type `wt powershell` to filter profiles by name.
- Click a profile to launch it.
- Right-click a profile for **Open** or **Open as Administrator**.

**Supported terminal variants:**

| Variant                    | Package Family                                      |
| -------------------------- | --------------------------------------------------- |
| Windows Terminal (Stable)  | `Microsoft.WindowsTerminal_8wekyb3d8bbwe`           |
| Windows Terminal Preview   | `Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe`    |
| Windows Terminal Canary    | `Microsoft.WindowsTerminalCanary_8wekyb3d8bbwe`     |

> [!NOTE]
> The provider re-discovers installed terminals each time the popup is opened, so newly installed variants or profiles are picked up automatically.

### WSL Provider

Browse and manage Windows Subsystem for Linux (WSL) distributions. Type `wsl` to list all installed distributions with their running state. Supports starting and stopping distros, opening a shell, setting the default, and unregistering. Optionally shows distributions available to install from the online catalog.

| Option        | Type   | Default  | Description                                                                          |
| ------------- | ------ | -------- | ------------------------------------------------------------------------------------ |
| `enabled`     | bool   | `false`  | Enable/disable the WSL provider.                                                     |
| `prefix`      | string | `"wsl"`  | Trigger prefix. Use `"*"` to include in default results.                             |
| `priority`    | int    | `0`      | Sort order when multiple providers share the same prefix. Lower values appear first. |
| `show_online` | bool   | `true`   | Show distributions available to install from the online catalog below installed ones. |

**Usage examples:**

- Type `wsl` to list all installed distributions.
- Type `wsl ubuntu` to filter by name.
- Press **Enter** on a running distro to **stop** it.
- Press **Enter** on a stopped distro to **start** it.
- Right-click a distro for **Open shell**, **Start/Stop**, **Set as default**, and **Unregister**.
- Type `wsl` and press Enter on an online distro to open a terminal and run `wsl --install -d <name>`.

### World Clock Provider

Show current time in cities around the world. Type `tz` to see your pinned cities (or a default set if nothing is pinned), or `tz tokyo` to filter by city name. Click a result to copy the formatted time to the clipboard. Right-click a city to pin or unpin it. Pinned cities appear first when searching and are shown as the default view.

| Option     | Type   | Default | Description                                                                          |
| ---------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `enabled`  | bool   | `false` | Enable/disable the world clock provider.                                             |
| `prefix`   | string | `"tz"`  | Trigger prefix. Use `"*"` to include in default results.                             |
| `priority` | int    | `0`     | Sort order when multiple providers share the same prefix. Lower values appear first. |

Each result displays:

- **Title:** City name and current time (e.g., `Tokyo  -  2:30 AM`)
- **Description:** Date, UTC offset, and difference from local time (e.g., `Wed, Feb 14 - UTC+9 (14h ahead)`)

> [!NOTE]
> World Clock uses Python's built-in `zoneinfo` module - no API calls or external dependencies required. Times are always live and accurate.

## Provider Prefixes Reference

Prefixes are configurable per provider. Set `prefix` to `"*"` to include a provider in the default (unprefixed) results. These are the defaults:

| Prefix | Provider             | Example            |
| ------ | -------------------- | ------------------ |
| `*`    | Apps                 | `notepad`          |
| `*`    | Bookmarks            | `*github`          |
| `=`    | Calculator           | `=2*pi`            |
| `cb`   | Clipboard History    | `cb notepad`       |
| `c:`   | Color                | `c:#FF5500`        |
| `$`    | Currency             | `$100 usd eur`     |
| `dev`  | Developer Tools      | `dev uuid`         |
| `:`    | Emoji                | `:fire`            |
| `/`    | File Search          | `/report.docx`     |
| `gh`   | GitHub Notifications | `gh review`        |
| `hn`   | Hacker News          | `hn frontpage`     |
| `ip`   | IP / Network Info    | `ip info`          |
| `!`    | Kill Process         | `!chrome`          |
| `pv`   | Port Viewer          | `pv 80`            |
| `@`    | Settings             | `@wifi`            |
| `;`    | Snippets             | `;meeting notes`   |
| `>`    | System Commands      | `>lock`            |
| `~`    | Unit Converter       | `~10 kg to lb`     |
| `vsc`  | VSCode               | `vsc project`      |
| `?`    | Web Search           | `?python tutorial` |
| `win`  | Window Switcher      | `win notepad`      |
| `wt`   | Windows Terminal     | `wt powershell`    |
| `tz`   | World Clock          | `tz tokyo`         |
| `wsl`  | WSL                  | `wsl ubuntu`       |

## Example Minimal Configuration enabling just the apps provider

```yaml
quick_launch:
  type: "yasb.quick_launch.QuickLaunchWidget"
  options:
    label: "<span>\uf002</span>"
    search_placeholder: "Search applications..."
    max_results: 30
    show_icons: true
    icon_size: 32
    popup:
      width: 720
      height: 480
      screen: "focus"
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "system"
      dark_mode: true
    callbacks:
      on_left: "toggle_quick_launch"
    keybindings:
      - keys: "alt+space"
        action: "toggle_quick_launch"
```

## Example Configuration enabling multiple providers

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
        max_recent: 5
        show_description: true
      bookmarks:
        enabled: true
        prefix: "*"
        priority: 1
        browser: "all"
        profile: "Default"
      calculator:
        enabled: true
        prefix: "="
        priority: 2
      clipboard_history:
        enabled: true
        prefix: "cb"
        priority: 3
        max_items: 30
      color:
        enabled: true
        prefix: "c:"
        priority: 4
      currency:
        enabled: true
        prefix: "$"
        priority: 5
      dev_tools:
        enabled: true
        prefix: "dev"
        priority: 6
      emoji:
        enabled: true
        prefix: ":"
        priority: 7
      file_search:
        enabled: true
        prefix: "/"
        priority: 8
        backend: "auto"
        show_path: true
      github_notifications:
        enabled: true
        prefix: "gh"
        priority: 9
        token: "env"
      hacker_news:
        enabled: true
        prefix: "hn"
        priority: 10
        cache_ttl: 300
        max_items: 30
      ip_info:
        enabled: true
        prefix: "ip"
        priority: 11
      kill_process:
        enabled: true
        prefix: "!"
        priority: 12
      port_viewer:
        enabled: true
        prefix: "pv"
        priority: 13
        tcp_listening_only: true
        include_established: false
      settings:
        enabled: true
        prefix: "@"
        priority: 14
      snippets:
        enabled: true
        prefix: ";"
        priority: 15
        type_delay: 200
      system_commands:
        enabled: true
        prefix: ">"
        priority: 16
      unit_converter:
        enabled: true
        prefix: "~"
        priority: 17
      vscode:
        enabled: true
        prefix: "vsc"
        priority: 18
      web_search:
        enabled: true
        prefix: "?"
        priority: 19
        engine: "google"
      window_switcher:
        enabled: true
        prefix: "win"
        priority: 20
      windows_terminal:
        enabled: true
        prefix: "wt"
        priority: 21
      world_clock:
        enabled: true
        prefix: "tz"
        priority: 22
      wsl:
        enabled: true
        prefix: "wsl"
        priority: 23
        show_online: true
    popup:
      width: 720
      height: 480
      screen: "focus"
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "system"
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
- **home_page:** When true, show provider shortcut tiles (home page) when the search input is empty.
- **providers:** Configuration for each search provider. Each provider can be individually enabled/disabled and configured.
    - **_apps:_** Application search with frecency-ranked results. See Apps Provider table above.
    - **_bookmarks:_** Search and open browser bookmarks (Chrome, Edge, Brave, Vivaldi, Chromium, Firefox). Configurable `browser` and `profile` options.
    - **_calculator:_** Inline math evaluation with prefix `=`.
    - **_clipboard_history:_** Browse and restore Windows Clipboard History entries (text, rich text, images). Use `max_items` to limit how many entries are shown.
    - **_color:_** Pick colors from screen and convert between HEX, RGB, HSL, HSV, HWB, LAB, LCH, OKLAB, OKLCH with prefix `c:`.
    - **_currency:_** Currency conversion using ECB daily rates with prefix `$`. Rates cached for 12 hours.
    - **_dev_tools:_** Common developer utilities (UUID, hash, base64, JWT, lorem, timestamps, passwords) with prefix `dev`.
    - **_emoji:_** Search and copy emojis to clipboard with prefix `:`.
    - **_file_search:_** File and folder search with prefix `/`. Uses Everything SDK, Windows Search indexer, or full disk scan.
    - **_github_notifications:_** Browse GitHub notifications with prefix `gh`. Requires a personal access token.
    - **_hacker_news:_** Browse and search Hacker News stories with prefix `hn`. Supports topic browsing and keyword search.
    - **_ip_info:_** Local network info, public IP, subnet calculator, DNS lookup with prefix `ip`.
    - **_kill_process:_** Process search and termination with prefix `!`.
    - **_port_viewer:_** View TCP/UDP ports and the owning PID/process name (via `netstat`). Supports filtering and kill actions.
    - **_settings:_** Quick access to Windows Settings pages with prefix `@`.
    - **_snippets:_** Save and type text snippets with prefix `;`. Supports template variables and inline editing.
    - **_system_commands:_** System actions (shutdown, restart, lock, etc.) with prefix `>`.
    - **_unit_converter:_** Convert between units (length, weight, volume, speed, data, time, temperature) with prefix `~`.
    - **_vscode:_** Launch recent files and folders in Visual Studio Code with prefix `vsc`. Uses fuzzy searching.
    - **_web_search:_** Browser-based web search with prefix `?`. Shows all engines with the preferred engine listed first.
    - **_window_switcher:_** Search and switch to open application windows with prefix `win`.
    - **_windows_terminal:_** Browse and launch Windows Terminal profiles (Stable, Preview, Canary) with prefix `wt`.
    - **_world_clock:_** Show current time in cities worldwide with prefix `tz`. Pin cities via right-click.
    - **_wsl:_** Browse and manage WSL distributions with prefix `wsl`. Start/stop distros, open a shell, set default, and unregister. Optionally shows the online install catalog.
- **compact_text:** When enabled, each result row is rendered as a single line with the description shown inline on the right. Useful when you want a denser list with more results visible at once.
- **popup:** Popup window appearance settings.
    - **_width:_** Width of the popup window in pixels.
    - **_height:_** Height of the popup window in pixels.
    - **_screen:_** Which screen to show the popup on (`"focus"`, `"cursor"`, or `"primary"`).
    - **_blur:_** Enable background blur effect (requires Windows 11).
    - **_round_corners:_** Enable rounded corners on the popup.
    - **_round_corners_type:_** Type of corner rounding (`"normal"` or `"small"`).
    - **_border_color:_** Border color of the popup window (`"System"` for system accent color, HEX value, or `"None"`).
- **animation:** Widget animation settings.
    - **_enabled:_** Whether animations are enabled.
    - **_type:_** Type of animation (`"fadeInOut"`).
    - **_duration:_** Duration of the animation in milliseconds.
- **keybindings:** A list of global keybindings. Each entry must specify `keys` (a list of key combinations) and `action` (the callback to invoke, e.g., `"toggle_quick_launch"`).
- **callbacks:** Mouse event callbacks (`on_left`, `on_middle`, `on_right`). Valid actions: `"toggle_quick_launch"`, `"do_nothing"`.
- **label_shadow:** Shadow options for the bar label.
- **container_shadow:** Shadow options for the widget container.

## Example Style

```css
/* Quick Launch Widget */
.quick-launch-widget .icon {
	font-size: 14px;
	padding: 0 4px;
}
.quick-launch-widget .icon:hover {
	color: #fff;
}

/* Quick Launch Popup - main window */
.quick-launch-popup .container {
	background-color: rgba(29, 29, 29, 0.452);
}
/* Search bar container */
.quick-launch-popup .search {
	padding: 12px 16px;
	background-color: transparent;
	border-bottom: 1px solid rgba(255, 255, 255, 0.15);
}
/* Search loader line color */
.quick-launch-popup .search .loader-line {
	color: #449bff;
}
.quick-launch-popup .search .search-icon {
	font-family: "Segoe Fluent Icons";
	font-size: 18px;
	color: rgba(255, 255, 255, 0.6);
	padding-right: 8px;
	min-width: 18px;
}
.quick-launch-popup .search .search-submit-icon {
	font-family: "Segoe Fluent Icons";
	font-size: 18px;
	color: rgba(255, 255, 255, 0.6);
	min-width: 18px;
}
.quick-launch-popup .search .search-input {
	background: transparent;
	border: none;
	color: #ffffff;
	font-size: 16px;
	font-family: "Segoe UI";
	font-weight: 400;
	padding: 4px 0;
}
/* Search prefix styling (e.g., ">" for commands) */
.quick-launch-popup .search .prefix {
	background: #2167d8;
	border-radius: 6px;
	color: #ffffff;
	padding: -2px 8px 0px 8px;
	margin-top: 2px;
	margin-right: 4px;
	font-size: 13px;
	font-weight: 600;
	font-family: "Segoe UI";
	max-height: 28px;
}

/* Results list */
.quick-launch-popup .results {
	background: transparent;
	padding: 8px;
}
/* Individual result item here you can set font szie for title */
.quick-launch-popup .results-list-view {
	font-size: 16px;
	font-family: "Segoe UI";
	font-weight: 600;
	color: #ffffff;
}
.quick-launch-popup .results-list-view .description {
	color: rgba(255, 255, 255, 0.6);
	font-size: 11px;
	font-family: "Segoe UI";
	font-weight: 600;
}
.quick-launch-popup .results-list-view .separator {
    color: rgba(255, 255, 255, 0.6);
    font-size: 13px;
    font-family: 'Segoe UI';
    font-weight: 600;
    padding: 4px 0 4px 12px;
}
/* Result item hover and selected states */
.quick-launch-popup .results-list-view::item {
	padding: 12px;
	border-radius: 8px;
}
.quick-launch-popup .results-list-view::item:hover,
.quick-launch-popup .results-list-view::item:selected {
	background-color: rgba(128, 130, 158, 0.1);
}
/* Empty state when no results found */
.quick-launch-popup .results-empty-text {
	font-size: 24px;
	font-family: "Segoe UI";
	color: rgb(255, 255, 255);
	padding-top: 8px;
}

/* Preview Pane */
.quick-launch-popup .preview {
	background: rgba(0, 0, 0, 0);
	border-left: 1px solid rgba(255, 255, 255, 0.06);
}
.quick-launch-popup .preview .preview-text {
	font-size: 13px;
	color: rgba(255, 255, 255, 0.85);
	padding: 8px 12px;
	font-family: "Segoe UI";
	background-color: rgba(255, 255, 255, 0.03);
	border: none;
}
.quick-launch-popup .preview .preview-image {
	background-color: rgba(255, 255, 255, 0.03);
	padding: 8px 12px;
}
.quick-launch-popup .preview .preview-meta {
	padding: 6px 12px;
	border-top: 1px solid rgba(255, 255, 255, 0.06);
	font-family: "Segoe UI";
}
.quick-launch-popup .preview .preview-meta .preview-title {
	font-size: 14px;
	font-weight: 600;
	color: rgb(255, 255, 255);
	font-family: "Segoe UI";
	margin-bottom: 10px;
	margin-left: -2px;
}

.quick-launch-popup .preview .preview-meta .preview-subtitle {
	font-size: 12px;
	color: rgba(255, 255, 255, 0.8);
	font-family: "Segoe UI";
	padding-bottom: 1px;
}

/* Preview inline edit form (.preview.edit) */
.quick-launch-popup .preview.edit .preview-title {
	font-size: 13px;
	font-family: "Segoe UI";
	font-weight: 600;
	color: #ffffff;
	padding: 8px 12px 4px 12px;
}
.quick-launch-popup .preview.edit .preview-line-edit {
	background: rgba(255, 255, 255, 0.06);
	border: 1px solid rgba(255, 255, 255, 0.12);
	border-radius: 4px;
	color: #ffffff;
	font-size: 13px;
	font-family: "Segoe UI";
	padding: 6px 8px;
	margin: 0 12px;
}
.quick-launch-popup .preview.edit .preview-line-edit:focus {
	border-color: rgba(255, 255, 255, 0.3);
}
.quick-launch-popup .preview.edit .preview-text-edit {
	background: rgba(255, 255, 255, 0.06);
	border: 1px solid rgba(255, 255, 255, 0.12);
	border-radius: 4px;
	color: #ffffff;
	font-size: 13px;
	font-family: "Segoe UI";
	padding: 6px 8px;
	margin: 0 12px;
}
.quick-launch-popup .preview.edit .preview-text-edit:focus {
	border-color: rgba(255, 255, 255, 0.3);
}
.quick-launch-popup .preview.edit .preview-actions {
	padding: 8px 12px;
}
.quick-launch-popup .preview.edit .preview-btn {
	background: rgb(45, 46, 48);
	border: none;
	border-radius: 4px;
	color: rgba(255, 255, 255, 0.8);
	font-size: 12px;
	font-family: "Segoe UI";
	font-weight: 600;
	padding: 4px 16px;
}
.quick-launch-popup .preview.edit .preview-btn:hover {
	background: rgb(59, 60, 63);
}
.quick-launch-popup .preview.edit .preview-btn.save {
	background: rgb(12, 81, 190);
	color: #ffffff;
}
.quick-launch-popup .preview.edit .preview-btn.save:hover {
	background: rgb(19, 90, 204);
}
```

> [!NOTE]
> This widget uses SVG icons by default, which cannot be styled with CSS. Also, keep in mind that styling may be limited for certain elements.

> [!IMPORTANT]  
> Quick Launch widget uses the `QMenu`, which supports various styles. You can customize the appearance of the menu using CSS styles. For more information on styling, refer to the [Styling](https://github.com/amnweb/yasb/wiki/Styling#context-menu-styling).

## Preview

![QL Widget Preview](assets/3c5a8b2f-e7d1f4a9-6c8b-4d2e-9f1a3e5c7b2d.png)
