# Prayer Times Widget

Displays Islamic prayer times fetched from the [Aladhan API](https://aladhan.com/prayer-times-api). Shows the next upcoming (or currently active) prayer by default, with an alt label that lists all daily prayer times. Left-clicking opens a popup card listing all prayers with their times and remaining countdowns.

## Options

| Option              | Type    | Default                                                                               | Description                                                                                                                              |
|---------------------|---------|---------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `label`             | string  | `"{icon} {next_prayer} {next_prayer_time}"`                                           | Format string for the primary label. Supports all placeholders listed below.                                                             |
| `label_alt`         | string  | `"Fajr {fajr} · Dhuhr {dhuhr} · Asr {asr} · Maghrib {maghrib} · Isha {isha}"`        | Format string for the alternate label.                                                                                                   |
| `class_name`        | string  | `""`                                                                                  | Additional CSS class name for the widget.                                                                                                |
| `latitude`          | float   | `51.5074`                                                                             | Latitude of your location (−90 to 90).                                                                                                   |
| `longitude`         | float   | `-0.1278`                                                                             | Longitude of your location (−180 to 180).                                                                                                |
| `method`            | integer | `2`                                                                                   | Aladhan calculation method ID. See [method list](#method-ids).                                                                           |
| `school`            | integer | `0`                                                                                   | Juristic school for Asr: `0` = Shafi'i / Standard, `1` = Hanafi.                                                                        |
| `midnight_mode`     | integer | `0`                                                                                   | Midnight mode: `0` = Standard (mid sunset-to-sunrise), `1` = Jafari (mid sunset-to-Fajr).                                               |
| `tune`              | string  | `""`                                                                                  | Comma-separated minute offsets for each prayer (Imsak,Fajr,Sunrise,Dhuhr,Asr,Maghrib,Sunset,Isha,Midnight).                             |
| `timezone`          | string  | `""`                                                                                  | IANA timezone string (e.g. `"Asia/Jakarta"`). Defaults to the server's local timezone.                                                   |
| `shafaq`            | string  | `""`                                                                                  | Shafaq type used for Isha calculation in some methods (`general`, `ahmer`, `abyad`).                                                     |
| `prayers_to_show`   | list    | `["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]`                                        | Ordered list of prayers used to determine the active/next prayer, popup rows, and tooltip. Must match Aladhan names exactly.             |
| `grace_period`      | integer | `15`                                                                                  | Minutes to stay on the current prayer after its time before advancing to the next. Min `0`, max `120`.                                   |
| `update_interval`   | integer | `3600`                                                                                | How often (in seconds) to re-fetch prayer times from the API. Min `60`, max `86400`.                                                     |
| `tooltip`           | boolean | `true`                                                                                | Show a tooltip listing all prayer times in `prayers_to_show` on hover.                                                                   |
| `icons`             | dict    | *(see below)*                                                                         | Nerd Font icon per prayer name. Includes `mosque` shown in the popup header.                                                             |
| `menu`              | dict    | *(see below)*                                                                         | Appearance and position settings for the popup card.                                                                                     |
| `flash`             | dict    | *(see below)*                                                                         | Smooth animated glow effect triggered when a prayer time arrives.                                                                        |
| `callbacks`         | dict    | `{on_left: "toggle_card", on_middle: "do_nothing", on_right: "toggle_label"}`        | Mouse-click actions.                                                                                                                     |
| `animation`         | dict    | `{enabled: true, type: "fadeInOut", duration: 200}`                                   | Animation settings for the toggle_card transition.                                                                                       |
| `label_shadow`      | dict    | `{enabled: false, color: "black", radius: 3, offset: [1, 1]}`                        | Label shadow options.                                                                                                                    |
| `container_shadow`  | dict    | `{enabled: false, color: "black", radius: 3, offset: [1, 1]}`                        | Container shadow options.                                                                                                                |
| `keybindings`       | list    | `[]`                                                                                  | Hotkey bindings.                                                                                                                         |

### Label Placeholders

| Placeholder          | Description                                                                           |
|----------------------|---------------------------------------------------------------------------------------|
| `{icon}`             | Icon for the currently active or next upcoming prayer                                 |
| `{next_prayer}`      | Name of the currently active or next upcoming prayer (e.g. `Asr`)                    |
| `{next_prayer_time}` | Time of the currently active or next upcoming prayer (e.g. `15:14`)                  |
| `{fajr}`             | Fajr time                                                                             |
| `{sunrise}`          | Sunrise time                                                                          |
| `{dhuhr}`            | Dhuhr time                                                                            |
| `{asr}`              | Asr time                                                                              |
| `{sunset}`           | Sunset time                                                                           |
| `{maghrib}`          | Maghrib time                                                                          |
| `{isha}`             | Isha time                                                                             |
| `{imsak}`            | Imsak time                                                                            |
| `{midnight}`         | Midnight time                                                                         |
| `{hijri_date}`       | Full Hijri date (e.g. `23 Sha'bān 1446`)                                             |
| `{hijri_day}`        | Hijri day number                                                                      |
| `{hijri_month}`      | Hijri month name (English)                                                            |
| `{hijri_year}`       | Hijri year                                                                            |

> **Note on `{next_prayer}` / `{icon}`:** During the `grace_period` window after a prayer's time, these values stay on the current prayer rather than jumping to the next one.

### Default Icons

```yaml
icons:
  mosque: "\uf67f"    # Shown in the popup card header
  fajr: "\uf185"
  sunrise: "\uf185"
  dhuhr: "\uf185"
  asr: "\uf185"
  sunset: "\uf185"
  maghrib: "\uf186"
  isha: "\uf186"
  imsak: "\uf185"
  midnight: "\uf186"
  default: "\uf017"   # Fallback when no matching icon is found
```

### Menu Options

Controls the popup card that opens on `toggle_card`.

| Option               | Type    | Default    | Description                                                              |
|----------------------|---------|------------|--------------------------------------------------------------------------|
| `blur`               | boolean | `true`     | Apply blur effect to the popup background.                               |
| `round_corners`      | boolean | `true`     | Round the popup corners (not supported on Windows 10).                   |
| `round_corners_type` | string  | `"normal"` | Corner style: `"normal"` or `"small"` (not supported on Windows 10).    |
| `border_color`       | string  | `"System"` | Border color: `"System"`, `None`, or a hex color e.g. `"#ff0000"`.      |
| `alignment`          | string  | `"right"`  | Popup alignment relative to the widget: `"left"`, `"center"`, `"right"`. |
| `direction`          | string  | `"down"`   | Direction the popup opens: `"up"` or `"down"`.                           |
| `offset_top`         | integer | `6`        | Vertical offset in pixels from the bar edge.                             |
| `offset_left`        | integer | `0`        | Horizontal offset in pixels from the widget edge.                        |

### Flash Options

Controls the smooth animated glow effect that triggers when a prayer time arrives.

| Option     | Type    | Default     | Description                                                                                               |
|------------|---------|-------------|-----------------------------------------------------------------------------------------------------------|
| `enabled`  | boolean | `true`      | Whether to enable the flash effect.                                                                       |
| `duration` | integer | `30`        | How long (in seconds) to run the flash after the prayer time arrives. Min `1`, max `3600`.                |
| `interval` | integer | `500`       | Duration in milliseconds of one half-cycle (fade to `color_a`, then back). Min `100`, max `5000`.         |
| `color_a`  | string  | `"#ff8c00"` | The bright peak color the background pulses to on each cycle.                                             |
| `color_b`  | string  | `"#1e1e2e"` | The dim base color the background fades from. Should match your container background.                     |

The animation uses `QVariantAnimation` with an `InOutSine` easing curve, producing a smooth pulse rather than an abrupt flash. Colors ping-pong (`color_b` → `color_a` → `color_b` → …) for the full `duration`. The background is applied directly to the entire widget container so the glow covers the whole pill. The label also receives a `flash` CSS class so you can change the text color independently via CSS.

### Grace Period

The `grace_period` option (default `15` minutes) controls how long the widget stays on the current prayer after its time has passed, before moving to the next.

**Example:** Asr at 15:14 with `grace_period: 15` → label shows `Asr 15:14` until 15:29, then switches to Maghrib.

This affects:
- **Bar label** — `{next_prayer}` and `{icon}` stay on the current prayer during the grace window.
- **Popup card** — the active row shows an elapsed label (e.g. `5m ago`) instead of `passed` while still within the grace window.
- **Tomorrow's schedule** — fetching tomorrow's times is deferred until the last prayer's grace window has fully expired.

## Callbacks

| Callback       | Description                                 |
|----------------|---------------------------------------------|
| `toggle_card`  | Open/close the popup card.                  |
| `toggle_label` | Toggle between primary and alternate label. |
| `update_label` | Force a label refresh.                      |
| `do_nothing`   | No action.                                  |

## Minimal Configuration

```yaml
prayer_times:
  type: "yasb.prayer_times.PrayerTimesWidget"
  options:
    label: "{icon} {next_prayer} {next_prayer_time}"
    latitude: -6.178306
    longitude: 106.631889
    method: 20         # Kementerian Agama Republik Indonesia
    timezone: "Asia/Jakarta"
```

## Example Configuration

```yaml
prayer_times:
  type: "yasb.prayer_times.PrayerTimesWidget"
  options:
    label: "<span>{icon}</span> {next_prayer} {next_prayer_time}"
    label_alt: "Fajr {fajr} · Dhuhr {dhuhr} · Asr {asr} · Maghrib {maghrib} · Isha {isha}"
    latitude: -6.178306
    longitude: 106.631889
    method: 20                        # Kementerian Agama Republik Indonesia
    school: 0                         # Shafi'i / Standard
    midnight_mode: 0
    shafaq: "general"
    tune: "5,3,5,7,9,-1,0,8,-6"      # Minute offsets: Imsak,Fajr,Sunrise,Dhuhr,Asr,Maghrib,Sunset,Isha,Midnight
    timezone: "Asia/Jakarta"
    prayers_to_show:
      - "Imsak"
      - "Fajr"
      - "Sunrise"
      - "Dhuhr"
      - "Asr"
      - "Sunset"
      - "Maghrib"
      - "Isha"
    grace_period: 15                  # Stay on current prayer for 15 min after its time
    update_interval: 3600
    tooltip: true
    icons:
      mosque: "\uf67f"
      fajr: "\uf185"
      sunrise: "\uf185"
      dhuhr: "\uf185"
      asr: "\uf185"
      sunset: "\uf185"
      maghrib: "\uf186"
      isha: "\uf186"
      imsak: "\uf185"
      midnight: "\uf186"
      default: "\uf017"
    menu:
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "System"
      alignment: "right"
      direction: "down"
      offset_top: 6
      offset_left: 0
    flash:
      enabled: true
      duration: 60                    # Flash for 60 seconds
      interval: 800                   # 800ms per half-cycle
      color_a: "#ff8c00"              # Bright glow color
      color_b: "#1e1e2e"              # Dim base color (match your container background)
    callbacks:
      on_left: "toggle_card"
      on_middle: "do_nothing"
      on_right: "toggle_label"
    animation:
      enabled: true
      type: "fadeInOut"
      duration: 200
    label_shadow:
      enabled: true
      color: "#000000"
      radius: 2
      offset: [1, 1]
    container_shadow:
      enabled: false
      color: "black"
      radius: 3
      offset: [1, 1]
```

## Method IDs

Commonly used Aladhan calculation method IDs:

| ID  | Name                                             |
|-----|--------------------------------------------------|
| 1   | University of Islamic Sciences, Karachi          |
| 2   | Islamic Society of North America (ISNA)          |
| 3   | Muslim World League                              |
| 4   | Umm Al-Qura University, Makkah                  |
| 5   | Egyptian General Authority of Survey             |
| 11  | Majlis Ugama Islam Singapura, Singapore          |
| 12  | Union Organization Islamic de France            |
| 13  | Diyanet İşleri Başkanlığı, Turkey               |
| 14  | Spiritual Administration of Muslims of Russia   |
| 15  | Moonsighting Committee Worldwide (Khalid Shaukat)|
| 16  | Dubai, UAE                                       |
| 17  | Jabatan Kemajuan Islam Malaysia (JAKIM)          |
| 18  | Tunisia                                          |
| 19  | Algeria                                          |
| 20  | Kementerian Agama Republik Indonesia             |
| 21  | Morocco                                          |
| 22  | Comunidade Islâmica de Lisboa, Portugal          |
| 23  | Ministry of Awqaf, Jordan and Palestine         |

For the full list and custom (`method=99`) options, see the [Aladhan API docs](https://aladhan.com/prayer-times-api).

## Available Styles

> **Note:** The active prayer name is added as a CSS class on the bar label (e.g. `.label.fajr`, `.label.maghrib`), allowing you to colour each prayer differently.

```css
/* ── Bar widget ──────────────────────────────────────────────────── */
.prayer-times-widget {}
.prayer-times-widget.your_class {}          /* If class_name is set */
.prayer-times-widget .widget-container {}
.prayer-times-widget .label {}
.prayer-times-widget .label.alt {}          /* Alt label (toggle_label) */
.prayer-times-widget .label.loading {}      /* While API is fetching */

/* Per-prayer label classes (active while that prayer is current) */
.prayer-times-widget .label.fajr {}
.prayer-times-widget .label.sunrise {}
.prayer-times-widget .label.dhuhr {}
.prayer-times-widget .label.asr {}
.prayer-times-widget .label.sunset {}
.prayer-times-widget .label.maghrib {}
.prayer-times-widget .label.isha {}
.prayer-times-widget .label.imsak {}
.prayer-times-widget .label.midnight {}

/* Flash: text color applied to label during the animated background glow */
.prayer-times-widget .label.flash {}        /* Background is interpolated in Python via QVariantAnimation */

.prayer-times-widget .icon {}

/* ── Popup card ──────────────────────────────────────────────────── */
.prayer-times-menu {}
.prayer-times-menu .header {}
.prayer-times-menu .header .mosque-icon {}
.prayer-times-menu .header .title {}
.prayer-times-menu .header .hijri-date {}
.prayer-times-menu .rows-container {}
.prayer-times-menu .prayer-row {}
.prayer-times-menu .prayer-row.active {}    /* Currently active prayer (within grace period) */
.prayer-times-menu .prayer-row.passed {}    /* Prayers whose grace period has fully expired */
.prayer-times-menu .prayer-icon {}
.prayer-times-menu .prayer-name {}
.prayer-times-menu .prayer-time {}
.prayer-times-menu .prayer-remaining {}     /* "in 2h 15m" / "5m ago" (grace window) / "passed" */
.prayer-times-menu .footer {}
.prayer-times-menu .method-name {}          /* Calculation method name shown in footer */
.prayer-times-menu .loading-placeholder {}  /* Shown before the first API response arrives */
```

## Example Style

```css
/* ── Bar widget ─────────────────────────────────────────────────── */
.prayer-times-widget {
    padding: 0 6px;
}
.prayer-times-widget .widget-container {
    background-color: rgba(17, 17, 27, 0.5);
    margin: 4px 0;
    border-radius: 12px;
    border: 1px solid #45475a;
    padding: 0 10px;
}
.prayer-times-widget .widget-container:hover {
    background-color: #282936;
    border-color: #cba6f7;
}
.prayer-times-widget .icon {
    font-size: 16px;
    color: #cba6f7;
    margin: 0 4px 0 0;
}
.prayer-times-widget .label {
    font-size: 13px;
    color: #cdd6f4;
    font-weight: 600;
}
.prayer-times-widget .label.loading {
    color: #6c7086;
}

/* Per-prayer label accent colours */
.prayer-times-widget .label.imsak   { color: #74c7ec; }
.prayer-times-widget .label.fajr    { color: #74c7ec; }
.prayer-times-widget .label.sunrise { color: #f9e2af; }
.prayer-times-widget .label.dhuhr   { color: #f9e2af; }
.prayer-times-widget .label.asr     { color: #fab387; }
.prayer-times-widget .label.sunset  { color: #fab387; }
.prayer-times-widget .label.maghrib { color: #cba6f7; }
.prayer-times-widget .label.isha    { color: #b4befe; }
.prayer-times-widget .label.midnight { color: #b4befe; }

/* Flash: text color during the animated background glow */
.prayer-times-widget .label.flash {
    color: #ff8c00;
}

/* ── Popup card ─────────────────────────────────────────────────── */
.prayer-times-menu {
    background-color: rgba(30, 30, 46, 0.95);
    min-width: 300px;
}
.prayer-times-menu .header {
    background-color: rgba(17, 17, 27, 0.9);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.prayer-times-menu .header .mosque-icon {
    font-size: 18px;
    color: #cba6f7;
}
.prayer-times-menu .header .title {
    font-size: 14px;
    font-weight: 700;
    font-family: 'Segoe UI';
    color: #ffffff;
}
.prayer-times-menu .header .hijri-date {
    font-size: 11px;
    font-weight: 600;
    font-family: 'Segoe UI';
    color: #a6adc8;
}
.prayer-times-menu .rows-container {
    padding: 6px 0;
}
.prayer-times-menu .prayer-row {
    background-color: transparent;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.prayer-times-menu .prayer-row.active {
    background-color: rgba(203, 166, 247, 0.12);
    border-left: 2px solid #cba6f7;
}
.prayer-times-menu .prayer-row.passed {
    opacity: 0.4;
}
.prayer-times-menu .prayer-icon {
    font-size: 15px;
    color: #cba6f7;
}
.prayer-times-menu .prayer-row.active .prayer-icon { color: #cba6f7; }
.prayer-times-menu .prayer-row.passed .prayer-icon { color: #7f849c; }
.prayer-times-menu .prayer-name {
    font-size: 13px;
    font-weight: 600;
    font-family: 'Segoe UI';
    color: #cdd6f4;
}
.prayer-times-menu .prayer-row.active .prayer-name { color: #cba6f7; }
.prayer-times-menu .prayer-row.passed .prayer-name { color: #9399b2; }
.prayer-times-menu .prayer-time {
    font-size: 13px;
    font-weight: 700;
    font-family: 'Segoe UI';
    color: #cdd6f4;
}
.prayer-times-menu .prayer-row.active .prayer-time { color: #cba6f7; }
.prayer-times-menu .prayer-remaining {
    font-size: 11px;
    font-weight: 600;
    font-family: 'Segoe UI';
    color: #a6adc8;
}
.prayer-times-menu .prayer-row.active .prayer-remaining {
    color: #cba6f7;
    font-weight: 700;
}
.prayer-times-menu .footer {
    background-color: rgba(17, 17, 27, 0.6);
    border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.prayer-times-menu .method-name {
    font-size: 11px;
    font-weight: 600;
    font-family: 'Segoe UI';
    color: #7f849c;
}
.prayer-times-menu .loading-placeholder {
    padding: 28px 16px;
    font-size: 12px;
    font-weight: 600;
    font-family: 'Segoe UI';
    color: #6c7086;
}
```
