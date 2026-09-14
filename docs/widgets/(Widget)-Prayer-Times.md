# Prayer Times Widget

Displays Islamic prayer times fetched from the [Aladhan API](https://aladhan.com/prayer-times-api). Shows the next upcoming (or currently active) prayer by default, with an alt label that lists all daily prayer times. Left-clicking opens a popup card with the Hijri and Gregorian date, a day ribbon showing that date's own light with each prayer notched onto it, a countdown to the next prayer with a progress bar running from the previous one, and every prayer's time.

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
| `tune`              | string  | `""`                                                                                  | Exactly nine comma-separated minute offsets (Imsak,Fajr,Sunrise,Dhuhr,Asr,Maghrib,Sunset,Isha,Midnight). Rejected at startup if malformed. |
| `timezone`          | string  | `""`                                                                                  | IANA timezone string (e.g. `"Asia/Jakarta"`) the API should calculate for. Defaults to the timezone of your coordinates. See [Timezones](#timezones). |
| `shafaq`            | string  | `""`                                                                                  | Shafaq type used for Isha calculation in some methods. One of `""`, `general`, `ahmer`, `abyad`.                                         |
| `prayers_to_show`   | list    | `["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]`                                        | Which prayers drive the active/next prayer, popup rows, and tooltip. See [Prayer names](#prayer-names). Order does not matter — entries are always sorted chronologically. |
| `grace_period`      | integer | `15`                                                                                  | Minutes to stay on the current prayer after its time before advancing to the next. Min `0`, max `120`.                                   |
| `update_interval`   | integer | `3600`                                                                                | How often (in seconds) to re-fetch prayer times from the API. Min `60`, max `86400`.                                                     |
| `tooltip`           | boolean | `true`                                                                                | Show a hover tooltip summarising prayer times. Displays a **"Today's Prayers"** (or **"Tomorrow's Prayers"**) header, each prayer in `prayers_to_show` with its time, and a `◀` marker on the next upcoming prayer. |
| `icons`             | dict    | *(see below)*                                                                         | Nerd Font icon per prayer name. Includes `mosque` shown in the popup header.                                                             |
| `menu`              | dict    | *(see below)*                                                                         | Appearance and position settings for the popup card.                                                                                     |
| `flash`             | dict    | *(see below)*                                                                         | Smooth animated glow effect triggered when a prayer time arrives.                                                                        |
| `callbacks`         | dict    | `{on_left: "toggle_card", on_middle: "do_nothing", on_right: "toggle_label"}`        | Mouse-click actions.                                                                                                                     |
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
| `{midnight}`         | Midnight time (belongs to the *following* calendar day)                              |
| `{firstthird}`       | End of the first third of the night                                                   |
| `{lastthird}`        | Start of the last third of the night (following calendar day)                         |
| `{hijri_date}`       | Full Hijri date (e.g. `23 Sha'bān 1446`)                                             |
| `{hijri_day}`        | Hijri day number                                                                      |
| `{hijri_month}`      | Hijri month name (English)                                                            |
| `{hijri_year}`       | Hijri year                                                                            |

> **Note on `{next_prayer}` / `{icon}`:** During the `grace_period` window after a prayer's time, these values stay on the current prayer rather than jumping to the next one.

### Prayer Names

`prayers_to_show` accepts only these values, spelled exactly as the Aladhan API returns them. Anything else is rejected at startup rather than silently rendering `--:--`:

`Imsak`, `Fajr`, `Sunrise`, `Dhuhr`, `Asr`, `Sunset`, `Maghrib`, `Isha`, `Firstthird`, `Midnight`, `Lastthird`

`Midnight` and `Lastthird` fall *after* midnight and are automatically resolved onto the following calendar day, so they count down correctly instead of always reading `passed`.

### Timezones

The API returns times for the timezone of your coordinates, which is not necessarily the timezone your PC is set to. The widget reads the timezone from the API response and converts every prayer to your local clock before working out what is next, so countdowns stay correct when the two differ (travelling, a VM on UTC, or deliberately tracking another city). You only need to set `timezone` if you want the API to calculate for a zone other than the one implied by your coordinates.

### Default Icons

Every prayer default comes from the Nerd Fonts v3 Weather Icons set (`U+E300` to `U+E3E3`), so the glyphs share one drawing style and follow the sun through the day. The mosque and the fallback clock are Font Awesome. Avoid the old Material Design range (`U+F500` to `U+FD46`): Nerd Fonts v3 removed those glyphs and they render as an empty box.

```yaml
icons:
  mosque: "\ueed3"      # Popup header (fa-mosque)
  imsak: "\ue3c2"       # weather-moonset
  fajr: "\ue342"        # weather-horizon_alt
  sunrise: "\ue34c"     # weather-sunrise
  dhuhr: "\ue30d"       # weather-day_sunny
  asr: "\ue30d"         # weather-day_sunny
  sunset: "\ue34d"      # weather-sunset
  maghrib: "\ue343"     # weather-horizon
  isha: "\ue390"        # weather-moon_waxing_crescent_3
  firstthird: "\ue32b"  # weather-night_clear
  midnight: "\ue32b"    # weather-night_clear
  lastthird: "\ue32b"   # weather-night_clear
  done: "\uf444"        # oct-dot_fill, marks a prayer the day has gone past
  default: "\uf017"     # Fallback when no matching icon is found
```

### Day Ribbon

Between the dates and the countdown the popup paints a band of that date's own light: night until Fajr, warming through dawn to full daylight at sunrise, holding through the day, warming again at sunset and dark by Isha. Every boundary is a moment the API returned, so the band's proportions belong to your coordinates and that date — a narrow dawn wash near the equator, a wide one in a northern summer. Each prayer in `prayers_to_show` is notched underneath it, dimmed once the day has gone past it, and the current moment is pinned through the band.

The band needs sunrise and sunset to mean anything, so a response carrying neither drops the section rather than painting a flat bar. Missing moments otherwise cost only their own transition: without `Sunrise` there is no dawn wash.

Because a Qt stylesheet cannot express a gradient with data-driven stops, the band is painted rather than composed of widgets, and its colours and dimensions arrive as `-qproperty-` values — the same mechanism the adaptive bar uses (see [Styling](Styling)):

| Property | Type | Default | Description |
|---|---|---|---|
| `-qproperty-nightcolor` | color | `#181825` | The band before Fajr and after Isha. |
| `-qproperty-dawncolor` | color | `#74c7ec` | Peak of the wash between Fajr and sunrise. |
| `-qproperty-daycolor` | color | `#f9e2af` | Full daylight, sunrise through sunset. |
| `-qproperty-duskcolor` | color | `#fab387` | Peak of the wash between sunset and Isha. |
| `-qproperty-tickcolor` | color | `rgba(255,255,255,110)` | Notch for a prayer still ahead. |
| `-qproperty-passedtickcolor` | color | `rgba(0,0,0,70)` | Notch for a prayer the day has gone past. |
| `-qproperty-nowcolor` | color | `#cdd6f4` | The stem and cap marking the current moment. |
| `-qproperty-bandheight` | int | `10` | Height of the light band in pixels. |
| `-qproperty-tickwidth` | int | `2` | Width of each notch and of the now stem. |
| `-qproperty-tickheight` | int | `4` | Height of the notch lane below the band. |
| `-qproperty-nowradius` | int | `3` | Radius of the cap on the now stem. |

Give `.day-ribbon` a `min-height` and `max-height` of the same value, as with any YASB container; `nowradius + bandheight + 3 + tickheight` is the height the ribbon asks for by default.

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
| `debug`    | boolean | `false`     | Trigger the flash animation immediately on widget startup (useful for testing colors and timing).          |
| `duration` | integer | `30`        | How long (in seconds) to run the flash after the prayer time arrives. Min `1`, max `3600`.                |
| `interval` | integer | `500`       | Duration in milliseconds of one half-cycle (fade to `color_a`, then back). Min `100`, max `5000`.         |
| `color_a`  | string  | `"#ff8c00"` | The bright peak color the background pulses to on each cycle.                                             |
| `color_b`  | string  | `"#1e1e2e"` | The dim base color the background fades from. Should match your container background.                     |

The animation uses `QVariantAnimation` with an `InOutSine` easing curve, producing a smooth pulse rather than an abrupt flash. Colors ping-pong (`color_b` → `color_a` → `color_b` → …) for the full `duration`. The background is applied directly to the entire widget container so the glow covers the whole pill. Every label and icon span also carries a `flash` CSS class for the whole `duration`, on top of its own class and the current prayer class (e.g. `label dhuhr flash`), so you can change the text or icon color independently via CSS. The class stays through the per-minute refresh and follows the label when you `toggle_label` mid-flash.

### Grace Period

The `grace_period` option (default `15` minutes) controls how long the widget stays on the current prayer after its time has passed, before moving to the next.

**Example:** Asr at 15:14 with `grace_period: 15` → label shows `Asr 15:14` until 15:29, then switches to Maghrib.

This affects:
- **Bar label** — `{next_prayer}` and `{icon}` stay on the current prayer during the grace window.
- **Popup card**: the hero stays on the current prayer and reads `started 5m ago`, with its progress bar full, until the grace window ends.
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
      mosque: "\ueed3"
      imsak: "\ue3c2"
      fajr: "\ue342"
      sunrise: "\ue34c"
      dhuhr: "\ue30d"
      asr: "\ue30d"
      sunset: "\ue34d"
      maghrib: "\ue343"
      isha: "\ue390"
      firstthird: "\ue32b"
      midnight: "\ue32b"
      lastthird: "\ue32b"
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
      debug: false
      duration: 60                    # Flash for 60 seconds
      interval: 800                   # 800ms per half-cycle
      color_a: "#ff8c00"              # Bright glow color
      color_b: "#1e1e2e"              # Dim base color (match your container background)
    callbacks:
      on_left: "toggle_card"
      on_middle: "do_nothing"
      on_right: "toggle_label"
```

> **Note:** `animation`, `label_shadow` and `container_shadow` are deprecated project-wide and are not accepted by this widget. Use CSS animations, `text-shadow` and `box-shadow` instead.

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

> **Note:** The active prayer name is added as a CSS class on the bar label *and* its icon (e.g. `.label.maghrib`, `.icon.maghrib`), on the popup hero (e.g. `.hero.maghrib`) and on every popup row (e.g. `.prayer-row.fajr`). That lets you tint each prayer independently; the example style uses it to run a dawn-to-night colour ramp through the card.

> **Note:** The widget sets no padding, margins or fixed widths in code; every popup dimension comes from CSS. The header, hero, rows container and footer are frames, so `padding`, `border` and `background-color` all apply to them. Column alignment in the prayer rows comes from `min-width` on `.prayer-icon`, `.prayer-name` and `.prayer-time`.

> **Upgrading:** The popup gained a [day ribbon](#day-ribbon) above the hero, a `now` state on the hero and the active row for the minutes a prayer is actually being called, and a `.prayer-remaining.done` mark in place of the word "passed" on every prayer the day has gone by. Style `.day-ribbon` with `-qproperty-` values, or leave it unstyled and it falls back to its own defaults.
>
> **Earlier:** The popup gained a hero block, a second header line and a timezone in the footer. Copy the popup rules from the [example style](#example-style) to pick up the new layout. Rules you already had for `.header`, `.rows-container` and `.footer` now take effect as well (they were silently ignored before), which can change their spacing.

```css
/* ── Bar widget ──────────────────────────────────────────────────── */
.prayer-times-widget {}
.prayer-times-widget.your_class {}          /* If class_name is set */
.prayer-times-widget .widget-container {}
.prayer-times-widget .label {}
.prayer-times-widget .label.alt {}          /* Alt label (toggle_label) */
.prayer-times-widget .label.loading {}      /* While API is fetching */
.prayer-times-widget .icon {}               /* Span elements without an explicit class (e.g. <span>\uf19c</span>) */

/* Per-prayer classes, on every label and icon span while that prayer is active/current */
.prayer-times-widget .label.fajr {}
.prayer-times-widget .label.sunrise {}
.prayer-times-widget .label.dhuhr {}
.prayer-times-widget .label.asr {}
.prayer-times-widget .label.sunset {}
.prayer-times-widget .label.maghrib {}
.prayer-times-widget .label.isha {}
.prayer-times-widget .label.imsak {}
.prayer-times-widget .label.midnight {}
.prayer-times-widget .label.firstthird {}
.prayer-times-widget .label.lastthird {}
.prayer-times-widget .icon.fajr {}          /* Icon spans carry the same names, e.g. .icon.maghrib */

/* Flash: layered on every label and icon span for the whole flash duration, next to the prayer class */
.prayer-times-widget .label.flash {}        /* Background color is animated in Python via QVariantAnimation */
.prayer-times-widget .label.alt.flash {}    /* Same, when the alt label is currently shown */
.prayer-times-widget .icon.flash {}         /* Icon spans during the flash */
.prayer-times-widget .icon.maghrib.flash {} /* The prayer class stays, so per-prayer flash rules work */

/* ── Popup card ──────────────────────────────────────────────────── */
.prayer-times-menu {}
.prayer-times-menu .header {}
.prayer-times-menu .header .mosque-icon {}
.prayer-times-menu .header .title {}
.prayer-times-menu .header .hijri-date {}
.prayer-times-menu .header .gregorian-date {}   /* "Today, Sunday 13 September" */
.prayer-times-menu .day {}                      /* Day ribbon section */
.prayer-times-menu .day-ribbon {}               /* The painted band itself, see [Day Ribbon](#day-ribbon) */
.prayer-times-menu .day-icon.sunrise {}         /* Sunrise glyph under the band's left end */
.prayer-times-menu .day-icon.sunset {}          /* Sunset glyph under the band's right end */
.prayer-times-menu .day-sunrise {}              /* Sunrise time, e.g. "06:06" */
.prayer-times-menu .day-sunset {}               /* Sunset time, e.g. "17:54" */
.prayer-times-menu .day-length {}               /* "11h 48m of daylight" */
.prayer-times-menu .hero {}
.prayer-times-menu .hero.dhuhr {}               /* The hero also carries its prayer name */
.prayer-times-menu .hero.now {}                 /* This prayer has been called and is still in grace */
.prayer-times-menu .hero-icon {}
.prayer-times-menu .hero-name {}
.prayer-times-menu .hero-countdown {}           /* "in 1h 43m" / "started 5m ago" / "now" */
.prayer-times-menu .hero-progress {}            /* Runs from the previous prayer to this one */
.prayer-times-menu .hero-progress::chunk {}
.prayer-times-menu .hero-from {}                /* Previous prayer, e.g. "Fajr 04:31" */
.prayer-times-menu .hero-to {}                  /* This prayer's time */
.prayer-times-menu .rows-container {}
.prayer-times-menu .prayer-row {}
.prayer-times-menu .prayer-row.fajr {}          /* Row also carries its prayer name */
.prayer-times-menu .prayer-row.active {}        /* Currently active prayer (within grace period) */
.prayer-times-menu .prayer-row.active.now {}    /* Same, but only while it is actually being called */
.prayer-times-menu .prayer-row.passed {}        /* Prayers whose grace period has fully expired */
.prayer-times-menu .prayer-icon {}
.prayer-times-menu .prayer-name {}
.prayer-times-menu .prayer-time {}
.prayer-times-menu .prayer-remaining {}         /* "in 2h 15m" / "5m ago" (grace window) */
.prayer-times-menu .prayer-remaining.done {}    /* The `icons.done` mark, once the prayer has gone by */
.prayer-times-menu .footer {}
.prayer-times-menu .method-name {}              /* Calculation method name */
.prayer-times-menu .timezone {}                 /* Timezone the times were calculated for */
.prayer-times-menu .loading-placeholder {}      /* Shown before the first API response arrives */
```

## Example Style

```css
/* "Day arc": each prayer owns a hue on a dawn-to-night ramp (dawn blue, noon gold,
   afternoon amber, dusk ember, night lavender). The hue only appears on icons, the
   progress fill and the rail of the prayer happening now, so the countdown in the hero
   stays the one loud element on the card. Qt ignores `opacity` on widgets, so every
   dimmed state is an explicit colour. */

/* ---- Bar pill ---- */
.prayer-times-widget {
  padding: 0 6px;
}
.prayer-times-widget .widget-container {
  margin: 4px 0;
  border-radius: 8px;
  border: 1px solid rgba(128, 130, 158, 0.3);
  background-color: rgba(255, 255, 255, 0.04);
  padding: 0 10px;
}
.prayer-times-widget .widget-container:hover {
  background-color: rgba(255, 255, 255, 0.08);
}
.prayer-times-widget .icon {
  font-size: 15px;
  margin: 0 6px 0 0;
  color: rgba(255, 255, 255, 0.75);
}
.prayer-times-widget .label {
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.92);
}
.prayer-times-widget .label.loading {
  color: rgba(255, 255, 255, 0.35);
}

/* The pill icon carries the current time of day */
.prayer-times-widget .icon.imsak,
.prayer-times-widget .icon.fajr,
.prayer-times-widget .icon.sunrise {
  color: #8ecae6;
}
.prayer-times-widget .icon.dhuhr {
  color: #f9c74f;
}
.prayer-times-widget .icon.asr {
  color: #f4a261;
}
.prayer-times-widget .icon.sunset,
.prayer-times-widget .icon.maghrib {
  color: #e29578;
}
.prayer-times-widget .icon.isha {
  color: #b39ddb;
}
.prayer-times-widget .icon.midnight,
.prayer-times-widget .icon.firstthird,
.prayer-times-widget .icon.lastthird {
  color: #9b8ec4;
}

/* ---- Popup card ---- */
.prayer-times-menu {
  min-width: 300px;
  background-color: rgba(18, 20, 28, 0.94);
  border-radius: 8px;
}

/* Header: where and when. The Hijri date leads, the civil date sits under it. */
.prayer-times-menu .header {
  padding: 14px 18px 4px 18px;
}
.prayer-times-menu .header .mosque-icon {
  font-family: 'JetBrainsMono NFP';
  font-size: 15px;
  color: rgba(249, 199, 79, 0.9);
  padding-right: 8px;
}
.prayer-times-menu .header .title {
  font-family: 'Segoe UI';
  font-size: 13px;
  font-weight: 600;
  color: rgba(235, 238, 245, 0.6);
}
.prayer-times-menu .header .hijri-date {
  font-family: 'Segoe UI';
  font-size: 13px;
  font-weight: 600;
  color: rgba(244, 245, 248, 0.95);
}
.prayer-times-menu .header .gregorian-date {
  font-family: 'Segoe UI';
  font-size: 11px;
  color: rgba(235, 238, 245, 0.45);
}

/* Day ribbon: the band reuses the same hues as the rows below, so it doubles as
   their legend. The light runs unbroken and the prayers are notched underneath. */
.prayer-times-menu .day {
  padding: 14px 18px 11px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}
.prayer-times-menu .day-ribbon {
  min-height: 22px;
  max-height: 22px;
  -qproperty-nightcolor: #262b3a;
  -qproperty-dawncolor: #7aa2f7;
  -qproperty-daycolor: #f2d57e;
  -qproperty-duskcolor: #e8935f;
  -qproperty-tickcolor: rgba(235, 238, 245, 0.55);
  -qproperty-passedtickcolor: rgba(235, 238, 245, 0.18);
  -qproperty-nowcolor: #ffffff;
  -qproperty-bandheight: 12;
  -qproperty-tickwidth: 2;
  -qproperty-tickheight: 4;
  -qproperty-nowradius: 3;
}
.prayer-times-menu .day-icon {
  font-family: 'JetBrainsMono NFP';
  font-size: 12px;
  padding-top: 6px;
}
.prayer-times-menu .day-icon.sunrise {
  color: #f2d57e;
  padding-right: 6px;
}
.prayer-times-menu .day-icon.sunset {
  color: #e8935f;
  padding-left: 6px;
}
.prayer-times-menu .day-sunrise,
.prayer-times-menu .day-sunset {
  font-family: 'Segoe UI';
  font-size: 11px;
  color: rgba(235, 238, 245, 0.55);
  padding-top: 6px;
}
.prayer-times-menu .day-length {
  font-family: 'Segoe UI';
  font-size: 11px;
  color: rgba(235, 238, 245, 0.35);
  padding-top: 6px;
}

/* Hero: the one loud thing on the card is how long until the next prayer. */
.prayer-times-menu .hero {
  padding: 12px 18px 16px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}
.prayer-times-menu .hero-icon {
  font-family: 'JetBrainsMono NFP';
  font-size: 17px;
  padding-right: 8px;
}
.prayer-times-menu .hero-name {
  font-family: 'Segoe UI';
  font-size: 14px;
  font-weight: 600;
  color: rgba(244, 245, 248, 0.9);
}
.prayer-times-menu .hero-countdown {
  font-family: 'Segoe UI';
  font-size: 28px;
  font-weight: 600;
  color: #ffffff;
  padding: 0 0 10px 0;
}
.prayer-times-menu .hero-progress {
  min-height: 4px;
  max-height: 4px;
  border: none;
  border-radius: 2px;
  background-color: rgba(255, 255, 255, 0.09);
}
.prayer-times-menu .hero-progress::chunk {
  border-radius: 2px;
}
.prayer-times-menu .hero-from,
.prayer-times-menu .hero-to {
  font-family: 'Segoe UI';
  font-size: 11px;
  color: rgba(235, 238, 245, 0.45);
  padding-top: 6px;
}

/* ---- Rows ---- */
.prayer-times-menu .rows-container {
  padding: 6px 0;
}
.prayer-times-menu .prayer-row {
  padding: 7px 18px 7px 15px;
  border-left: 3px solid transparent;
}
.prayer-times-menu .prayer-icon {
  font-family: 'JetBrainsMono NFP';
  min-width: 26px;
  font-size: 15px;
}
.prayer-times-menu .prayer-name {
  min-width: 84px;
  font-family: 'Segoe UI';
  font-size: 13px;
  color: rgba(244, 245, 248, 0.82);
}
/* Segoe UI's regular weight has tabular figures, so the column lines up without a monospace face. */
.prayer-times-menu .prayer-time {
  min-width: 44px;
  font-family: 'Segoe UI';
  font-size: 13px;
  color: rgba(235, 238, 245, 0.62);
}
.prayer-times-menu .prayer-remaining {
  font-family: 'Segoe UI';
  font-size: 11px;
  color: rgba(235, 238, 245, 0.42);
}

/* ---- The day arc: one hue per time of day ---- */
.prayer-times-menu .prayer-row.imsak .prayer-icon,
.prayer-times-menu .prayer-row.fajr .prayer-icon,
.prayer-times-menu .prayer-row.sunrise .prayer-icon,
.prayer-times-menu .hero.imsak .hero-icon,
.prayer-times-menu .hero.fajr .hero-icon,
.prayer-times-menu .hero.sunrise .hero-icon {
  color: #8ecae6;
}
.prayer-times-menu .prayer-row.dhuhr .prayer-icon,
.prayer-times-menu .hero.dhuhr .hero-icon {
  color: #f9c74f;
}
.prayer-times-menu .prayer-row.asr .prayer-icon,
.prayer-times-menu .hero.asr .hero-icon {
  color: #f4a261;
}
.prayer-times-menu .prayer-row.sunset .prayer-icon,
.prayer-times-menu .prayer-row.maghrib .prayer-icon,
.prayer-times-menu .hero.sunset .hero-icon,
.prayer-times-menu .hero.maghrib .hero-icon {
  color: #e29578;
}
.prayer-times-menu .prayer-row.isha .prayer-icon,
.prayer-times-menu .hero.isha .hero-icon {
  color: #b39ddb;
}
.prayer-times-menu .prayer-row.firstthird .prayer-icon,
.prayer-times-menu .prayer-row.midnight .prayer-icon,
.prayer-times-menu .prayer-row.lastthird .prayer-icon,
.prayer-times-menu .hero.firstthird .hero-icon,
.prayer-times-menu .hero.midnight .hero-icon,
.prayer-times-menu .hero.lastthird .hero-icon {
  color: #9b8ec4;
}

.prayer-times-menu .hero.imsak .hero-progress::chunk,
.prayer-times-menu .hero.fajr .hero-progress::chunk,
.prayer-times-menu .hero.sunrise .hero-progress::chunk {
  background-color: #8ecae6;
}
.prayer-times-menu .hero.dhuhr .hero-progress::chunk {
  background-color: #f9c74f;
}
.prayer-times-menu .hero.asr .hero-progress::chunk {
  background-color: #f4a261;
}
.prayer-times-menu .hero.sunset .hero-progress::chunk,
.prayer-times-menu .hero.maghrib .hero-progress::chunk {
  background-color: #e29578;
}
.prayer-times-menu .hero.isha .hero-progress::chunk {
  background-color: #b39ddb;
}
.prayer-times-menu .hero.firstthird .hero-progress::chunk,
.prayer-times-menu .hero.midnight .hero-progress::chunk,
.prayer-times-menu .hero.lastthird .hero-progress::chunk {
  background-color: #9b8ec4;
}

/* The prayer happening now: a rail in its hue. Its countdown already leads the hero. */
.prayer-times-menu .prayer-row.active .prayer-name {
  color: #ffffff;
  font-weight: 600;
}
.prayer-times-menu .prayer-row.active .prayer-time {
  color: rgba(244, 245, 248, 0.95);
}
.prayer-times-menu .prayer-row.active .prayer-remaining {
  color: transparent;
}
.prayer-times-menu .prayer-row.active.imsak,
.prayer-times-menu .prayer-row.active.fajr,
.prayer-times-menu .prayer-row.active.sunrise {
  border-left-color: #8ecae6;
  background-color: rgba(142, 202, 230, 0.08);
}
.prayer-times-menu .prayer-row.active.dhuhr {
  border-left-color: #f9c74f;
  background-color: rgba(249, 199, 79, 0.08);
}
.prayer-times-menu .prayer-row.active.asr {
  border-left-color: #f4a261;
  background-color: rgba(244, 162, 97, 0.08);
}
.prayer-times-menu .prayer-row.active.sunset,
.prayer-times-menu .prayer-row.active.maghrib {
  border-left-color: #e29578;
  background-color: rgba(226, 149, 120, 0.08);
}
.prayer-times-menu .prayer-row.active.isha {
  border-left-color: #b39ddb;
  background-color: rgba(179, 157, 219, 0.08);
}
.prayer-times-menu .prayer-row.active.firstthird,
.prayer-times-menu .prayer-row.active.midnight,
.prayer-times-menu .prayer-row.active.lastthird {
  border-left-color: #9b8ec4;
  background-color: rgba(155, 142, 196, 0.08);
}

/* Spent prayers recede. Kept after the hues so it wins. */
.prayer-times-menu .prayer-row.passed .prayer-icon {
  color: rgba(235, 238, 245, 0.28);
}
.prayer-times-menu .prayer-row.passed .prayer-name,
.prayer-times-menu .prayer-row.passed .prayer-time {
  color: rgba(235, 238, 245, 0.36);
}
.prayer-times-menu .prayer-row.passed .prayer-remaining {
  color: transparent;
}

/* Called, and still inside the grace period: the one state the whole widget is for.
   Matches what the bar pill is doing at the same moment. */
.prayer-times-menu .hero.now .hero-countdown,
.prayer-times-menu .hero.now .hero-name {
  color: #e8935f;
}
.prayer-times-menu .prayer-row.active.now {
  background-color: rgba(232, 147, 95, 0.14);
  border-left-color: #e8935f;
}
.prayer-times-menu .prayer-row.active.now .prayer-icon,
.prayer-times-menu .prayer-row.active.now .prayer-name,
.prayer-times-menu .prayer-row.active.now .prayer-time,
.prayer-times-menu .prayer-row.active.now .prayer-remaining {
  color: #e8935f;
}

/* The done mark needs a min-width of its own: Qt sizes a glyph-only label against the
   family the stylesheet named, which on a machine without it is not the one that paints. */
.prayer-times-menu .prayer-remaining.done {
  font-family: 'JetBrainsMono NFP';
  font-size: 11px;
  min-width: 14px;
  color: rgba(235, 238, 245, 0.3);
}

/* ---- Footer ---- */
.prayer-times-menu .footer {
  padding: 10px 18px 12px 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.07);
}
.prayer-times-menu .method-name,
.prayer-times-menu .timezone {
  font-family: 'Segoe UI';
  font-size: 11px;
  color: rgba(235, 238, 245, 0.4);
}
.prayer-times-menu .timezone {
  padding-left: 12px;
}
.prayer-times-menu .loading-placeholder {
  padding: 28px 18px;
  font-family: 'Segoe UI';
  font-size: 13px;
  color: rgba(235, 238, 245, 0.45);
}
```
