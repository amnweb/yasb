# Prayer Times Widget

Displays Islamic prayer times fetched from the [Aladhan API](https://aladhan.com/prayer-times-api). Shows the next upcoming prayer by default, with an alt label that lists all daily prayer times.

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
| `prayers_to_show`   | list    | `["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]`                          | Ordered list of prayers used to determine the "next prayer" and tooltip. Must match Aladhan names.     |
| `update_interval`   | integer | `3600`                                                                  | How often (in seconds) to re-fetch from the API. Min `60`, max `86400`.                                |
| `tooltip`           | boolean | `true`                                                                  | Show a tooltip listing all prayer times in `prayers_to_show` on hover.                                 |
| `icons`             | dict    | *(see below)*                                                           | Nerd-Font icon per prayer name.                                                                        |
| `callbacks`         | dict    | `{on_left: "toggle_label", on_middle: "do_nothing", on_right: "do_nothing"}` | Mouse-click actions.                                                                              |
| `animation`         | dict    | `{enabled: true, type: "fadeInOut", duration: 200}`                     | Animation settings.                                                                                    |
| `label_shadow`      | dict    | `{enabled: false, ...}`                                                 | Label shadow options.                                                                                  |
| `container_shadow`  | dict    | `{enabled: false, ...}`                                                 | Container shadow options.                                                                              |
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
  fajr: "\uf185"
  sunrise: "\uf185"
  dhuhr: "\uf185"
  asr: "\uf185"
  maghrib: "\uf186"
  isha: "\uf186"
  imsak: "\uf185"
  midnight: "\uf186"
  default: "\uf017"
```

## Minimal Configuration

```yaml
prayer_times:
  type: "yasb.prayer_times.PrayerTimesWidget"
  options:
    label: "{icon} {next_prayer} {next_prayer_time}"
    latitude: -6.1783
    longitude: 106.6319
    method: 20         # Kementerian Agama Republik Indonesia
    timezone: "Asia/Jakarta"
```

## Advanced Configuration

```yaml
prayer_times:
  type: "yasb.prayer_times.PrayerTimesWidget"
  options:
    label: "{icon} {next_prayer} {next_prayer_time}"
    label_alt: "Fajr {fajr} · Dhuhr {dhuhr} · Asr {asr} · Maghrib {maghrib} · Isha {isha}"
    latitude: -6.1783
    longitude: 106.6319
    method: 20                        # Kementerian Agama RI
    school: 0                         # Shafi'i
    midnight_mode: 0
    tune: "5,3,5,7,9,-1,0,8,-6"      # Tune offsets in minutes
    timezone: "Asia/Jakarta"
    prayers_to_show:
      - "Fajr"
      - "Dhuhr"
      - "Asr"
      - "Maghrib"
      - "Isha"
    update_interval: 3600             # Re-fetch every hour
    tooltip: true
    icons:
      fajr: "\uf185"
      sunrise: "\uf185"
      dhuhr: "\uf185"
      asr: "\uf185"
      maghrib: "\uf186"
      isha: "\uf186"
      imsak: "\uf185"
      midnight: "\uf186"
      default: "\uf017"
    callbacks:
      on_left: "toggle_label"
      on_middle: "do_nothing"
      on_right: "do_nothing"
    animation:
      enabled: true
      type: "fadeInOut"
      duration: 200
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

## Styling

```css
.prayer-times-widget {}
.prayer-times-widget .widget-container {}
.prayer-times-widget .label {}
.prayer-times-widget .label.fajr {}
.prayer-times-widget .label.dhuhr {}
.prayer-times-widget .label.asr {}
.prayer-times-widget .label.maghrib {}
.prayer-times-widget .label.isha {}
.prayer-times-widget .label.alt {}
.prayer-times-widget .icon {}
```

> **Note:** The active prayer name is added as a CSS class on the label (e.g. `.fajr`, `.maghrib`), allowing you to colour each prayer differently.
