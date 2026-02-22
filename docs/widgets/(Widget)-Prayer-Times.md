# Prayer Times Widget

Displays Islamic prayer times fetched from the [Aladhan API](https://aladhan.com/prayer-times-api). Shows the next upcoming prayer by default, with an alt label that lists all daily prayer times. Left-clicking opens a popup card listing all prayers with their times and remaining countdowns.

## Options

| Option              | Type    | Default                                                                 | Description                                                                                            |
|---------------------|---------|-------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| `label`             | string  | `"{icon} {next_prayer} {next_prayer_time}"`                             | Format string for the primary label. Supports all placeholders listed below.                           |
| `label_alt`         | string  | `"Fajr {fajr} · Dhuhr {dhuhr} · Asr {asr} · Maghrib {maghrib} · Isha {isha}"` | Format string for the alternate label.                                              |
| `class_name`        | string  | `""`                                                                    | Additional CSS class name for the widget.                                                              |
| `latitude`          | float   | `51.5074`                                                               | Latitude of your location (−90 to 90).                                                                 |
| `longitude`         | float   | `-0.1278`                                                               | Longitude of your location (−180 to 180).                                                              |
| `method`            | integer | `2`                                                                     | Aladhan calculation method ID. See [method list](https://aladhan.com/prayer-times-api#GetTimings).     |
| `school`            | integer | `0`                                                                     | Juristic school for Asr: `0` = Shafi'i / Standard, `1` = Hanafi.                                      |
| `midnight_mode`     | integer | `0`                                                                     | Midnight mode: `0` = Standard (mid sunset-to-sunrise), `1` = Jafari (mid sunset-to-Fajr).             |
| `tune`              | string  | `""`                                                                    | Comma-separated minute offsets for each prayer (Imsak,Fajr,Sunrise,Dhuhr,Asr,Maghrib,Sunset,Isha,Midnight). |
| `timezone`          | string  | `""`                                                                    | IANA timezone string (e.g. `"Asia/Jakarta"`). Defaults to the server's local timezone.                 |
| `shafaq`            | string  | `""`                                                                    | Shafaq type used for Isha calculation in some methods (`general`, `ahmer`, `abyad`).                   |
| `prayers_to_show`   | list    | `["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]`                          | Ordered list of prayers used to determine the "next prayer", popup rows, and tooltip. Must match Aladhan names. |
| `update_interval`   | integer | `3600`                                                                  | How often (in seconds) to re-fetch from the API. Min `60`, max `86400`.                                |
| `tooltip`           | boolean | `true`                                                                  | Show a tooltip listing all prayer times in `prayers_to_show` on hover.                                 |
| `icons`             | dict    | *(see below)*                                                           | Nerd-Font icon per prayer name. Also includes `mosque` shown in the popup header.                      |
| `menu`              | dict    | *(see below)*                                                           | Appearance and position settings for the popup card.                                                   |
| `callbacks`         | dict    | `{on_left: "toggle_card", on_middle: "do_nothing", on_right: "toggle_label"}` | Mouse-click actions.                                                                         |
| `animation`         | dict    | `{enabled: true, type: "fadeInOut", duration: 200}`                     | Animation settings.                                                                                    |
| `label_shadow`      | dict    | `{enabled: false, color: "black", radius: 3, offset: [1, 1]}`           | Label shadow options.                                                                                  |
| `container_shadow`  | dict    | `{enabled: false, color: "black", radius: 3, offset: [1, 1]}`           | Container shadow options.                                                                              |
| `keybindings`       | list    | `[]`                                                                    | Hotkey bindings.                                                                                       |

### Label Placeholders

| Placeholder          | Description                                              |
|----------------------|----------------------------------------------------------|
| `{icon}`             | Icon for the next upcoming prayer                        |
| `{next_prayer}`      | Name of the next upcoming prayer (e.g. `Fajr`)          |
| `{next_prayer_time}` | Time of the next upcoming prayer (e.g. `04:43`)         |
| `{fajr}`             | Fajr time                                                |
| `{sunrise}`          | Sunrise time                                             |
| `{dhuhr}`            | Dhuhr time                                               |
| `{asr}`              | Asr time                                                 |
| `{sunset}`           | Sunset time                                              |
| `{maghrib}`          | Maghrib time                                             |
| `{isha}`             | Isha time                                                |
| `{imsak}`            | Imsak time                                               |
| `{midnight}`         | Midnight time                                            |
| `{hijri_date}`       | Full Hijri date (e.g. `23 Sha'bān 1446`)               |
| `{hijri_day}`        | Hijri day number                                         |
| `{hijri_month}`      | Hijri month name (English)                               |
| `{hijri_year}`       | Hijri year                                               |

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
  default: "\uf017"
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
      - "Fajr"
      - "Dhuhr"
      - "Asr"
      - "Maghrib"
      - "Isha"
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
      blur: false
      round_corners: false
      alignment: "right"
      direction: "down"
      offset_top: 6
      offset_left: 0
    callbacks:
      on_left: "toggle_card"
      on_middle: "do_nothing"
      on_right: "toggle_label"
    label_shadow:
      enabled: true
      color: "#000000"
      radius: 2
      offset: [ 1, 1 ]
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

> **Note:** The active prayer name is added as a CSS class on the label (e.g. `.label.fajr`, `.label.maghrib`), allowing you to colour each prayer differently.

```css
/* Bar widget */
.prayer-times-widget {}
.prayer-times-widget.your_class {}         /* If class_name is set */
.prayer-times-widget .widget-container {}
.prayer-times-widget .label {}
.prayer-times-widget .label.alt {}         /* Alt label (toggle_label) */
.prayer-times-widget .label.loading {}     /* While API is fetching */
.prayer-times-widget .label.fajr {}        /* Active when Fajr is next */
.prayer-times-widget .label.sunrise {}
.prayer-times-widget .label.dhuhr {}
.prayer-times-widget .label.asr {}
.prayer-times-widget .label.sunset {}
.prayer-times-widget .label.maghrib {}
.prayer-times-widget .label.isha {}
.prayer-times-widget .label.imsak {}
.prayer-times-widget .label.midnight {}
.prayer-times-widget .icon {}

/* Popup card */
.prayer-times-menu {}
.prayer-times-menu .header {}
.prayer-times-menu .header .mosque-icon {}
.prayer-times-menu .header .title {}
.prayer-times-menu .header .hijri-date {}
.prayer-times-menu .rows-container {}
.prayer-times-menu .prayer-row {}
.prayer-times-menu .prayer-row.active {}   /* Next upcoming prayer */
.prayer-times-menu .prayer-row.passed {}   /* Already passed prayers */
.prayer-times-menu .prayer-icon {}
.prayer-times-menu .prayer-name {}
.prayer-times-menu .prayer-time {}
.prayer-times-menu .prayer-remaining {}    /* e.g. "in 2h 15m" / "passed" */
.prayer-times-menu .footer {}
.prayer-times-menu .method-name {}         /* Calculation method shown in footer */
.prayer-times-menu .loading-placeholder {} /* Shown before first API response */
```

## Example Style

```css
.prayer-times-widget {
    padding: 0 6px;
}
.prayer-times-widget .icon {
    font-size: 16px;
    margin: 0 2px 1px 0;
    color: #ffd16d;
}
/* Night prayer icon tint */
.prayer-times-widget .icon.maghrib,
.prayer-times-widget .icon.isha {
    color: #b4befe;
}
/* Per-prayer label accent colours */
.prayer-times-widget .label.fajr,
.prayer-times-widget .label.sunrise,
.prayer-times-widget .label.dhuhr,
.prayer-times-widget .label.asr {
    color: #ffd16d;
}
.prayer-times-widget .label.maghrib,
.prayer-times-widget .label.isha {
    color: #b4befe;
}

/* Popup card */
.prayer-times-menu {
    background-color: #191919;
    border-radius: 8px;
    border: 1px solid #333333;
    min-width: 280px;
}
.prayer-times-menu .header {
    background-color: transparent;
    border-bottom: 1px solid #333333;
}
.prayer-times-menu .header .mosque-icon {
    font-size: 16px;
    color: #ffd16d;
}
.prayer-times-menu .header .title {
    font-size: 13px;
    font-weight: 700;
    font-family: 'Segoe UI';
    color: #d4d9eb;
}
.prayer-times-menu .header .hijri-date {
    font-size: 11px;
    font-family: 'Segoe UI';
    color: #8f929e;
}
.prayer-times-menu .prayer-row {
    background-color: transparent;
}
.prayer-times-menu .prayer-row.active {
    background-color: rgba(68, 143, 255, 0.12);
    border-left: 2px solid #448fff;
}
.prayer-times-menu .prayer-row.passed {
    opacity: 0.4;
}
.prayer-times-menu .prayer-icon {
    font-size: 15px;
    color: #ffd16d;
}
.prayer-times-menu .prayer-row.active .prayer-icon {
    color: #448fff;
}
.prayer-times-menu .prayer-name {
    font-size: 12px;
    font-weight: 600;
    font-family: 'Segoe UI';
    color: #d4d9eb;
}
.prayer-times-menu .prayer-time {
    font-size: 12px;
    font-family: 'Segoe UI';
    color: #8f929e;
}
.prayer-times-menu .prayer-row.active .prayer-time {
    color: #d4d9eb;
}
.prayer-times-menu .prayer-remaining {
    font-size: 11px;
    font-family: 'Segoe UI';
    color: #7f849c;
}
.prayer-times-menu .prayer-row.active .prayer-remaining {
    color: #448fff;
    font-weight: 700;
}
.prayer-times-menu .footer {
    border-top: 1px solid #333333;
}
.prayer-times-menu .method-name {
    font-size: 10px;
    font-family: 'Segoe UI';
    color: #7f849c;
}
```
