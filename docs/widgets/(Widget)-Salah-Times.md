# Salah Times Widget

Displays Islamic salah times in the bar. The compact label shows the next
salah and a live countdown; the alternate label (and the tooltip) show the
full day's schedule. Clicking the widget opens an interactive popup that is
both a **location chooser** and a **location editor** — add a location by
searching for a city, edit its calculation method / Asr school / per-salah
offsets, delete it, and switch the time format, all without touching a config
file.

Salah times are computed with the [adhanpy](https://pypi.org/project/adhanpy/) library and the Hijri date with [hijridate](https://pypi.org/project/hijridate/) (Umm al-Qura). There is no bundled executable and no external
calculation service; the only network call is the free Open-Meteo geocoding API
(city search, no key required).

## Example Configuration

```yaml
salah_times:
  type: "yasb.salah_times.SalahTimesWidget"
  options:
    label: "<span></span> {compact}"
    label_alt: "{list_inline}"
    label_placeholder: "Loading salah times..."
    class_name: "salah-times-widget"
    update_interval: 10
    time_format: "12h"
    location_mode: "manual"
    show_sunnah_times: true
    tooltip: true
    menu:
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "System"
      alignment: "right"
      direction: "down"
      offset_top: 6
      offset_left: 0
    callbacks:
      on_left: "toggle_menu"
      on_middle: "do_nothing"
      on_right: "toggle_label"
```

## Description of Options

| Option              | Type    | Default                        | Description |
| ------------------- | ------- | ------------------------------ | ----------- |
| `label`             | string  | `<span></span> {compact}` | Compact label. Supports the placeholders below. |
| `label_alt`         | string  | `{list_inline}`                | Alternate label toggled by `toggle_label`. |
| `label_placeholder` | string  | `Loading salah times...`      | Text shown until the first computation completes. |
| `class_name`        | string  | `salah-times-widget`          | CSS class of the bar item. |
| `update_interval`   | integer | `10`                           | Seconds between label refreshes (recomputes the countdown). 1–3600. |
| `time_format`       | string  | `12h`                          | Initial time format, `12h` or `24h`. Changeable in the popup. |
| `show_sunnah_times` | boolean | `true`                         | Include midnight and last-third-of-the-night in the list. |
| `tooltip`           | boolean | `true`                         | Show the full schedule, Hijri date, location and method in a tooltip. |
| `data_file`         | string  | `""`                           | Optional path override for the persisted data. Default: `%LOCALAPPDATA%/YASB/salah_times.json`. |
| `menu`              | dict    | see below                      | Popup appearance. |
| `callbacks`         | dict    | `on_left: toggle_menu`, `on_right: toggle_label` | Mouse callbacks. |
| `keybindings`       | list    | `[]`                           | Optional hotkeys (standard YASB keybinding format). |

### `menu` options

| Option              | Type    | Default   | Description |
| ------------------- | ------- | --------- | ----------- |
| `blur`              | boolean | `true`    | Acrylic blur behind the popup. |
| `round_corners`     | boolean | `true`    | Rounded corners (Windows 11). |
| `round_corners_type`| string  | `normal`  | `normal` or `small`. |
| `border_color`      | string  | `System`  | Border colour, or `System`/`None`. |
| `alignment`         | string  | `right`   | `left`, `right`, or `center`. |
| `direction`         | string  | `down`    | `down` or `up`. |
| `offset_top`        | integer | `6`       | Vertical offset in pixels. |
| `offset_left`       | integer | `0`       | Horizontal offset in pixels. |

### Callbacks

| Callback        | Description |
| --------------- | ----------- |
| `toggle_menu`   | Open the location chooser / editor popup. |
| `toggle_label`  | Switch between the compact label and the full-day list. |
| `update_label`  | Force a recomputation and label refresh. |

## Label Placeholders

| Placeholder         | Example |
| ------------------- | ------- |
| `{compact}`         | `Maghrib \| 8:24 PM  (2h 10m)` |
| `{next_salah}`     | `Maghrib` |
| `{next_time}`       | `8:24 PM` |
| `{time_left}`       | `2h 10m` |
| `{list_inline}`     | `Fajr: 5:17 AM \| Sunrise: 6:33 AM \| ...` |
| `{list_multiline}`  | one salah per line |
| `{hijri_date}`      | `30 Muharram 1448 AH` |
| `{location}`        | `London, GB` |
| `{location_source}` | `manual:London` |
| `{method}`          | `ISNA` |
| `{asr}`             | `Standard` or `Hanafi` |

## Calculation methods

`auto`, `MuslimWorldLeague`, `Egyptian`, `Karachi`, `UmmAlQura`, `Dubai`,
`MoonsightingCommittee`, `NorthAmerica` (ISNA), `Kuwait`, `Qatar`, `Singapore`,
`Tehran`, `Turkey`, `Other`.

`auto` picks a sensible method from the location's ISO country code (e.g. Umm
al-Qura in Saudi Arabia, ISNA in the US/Canada, Moonsighting Committee in the
UK). Asr can be calculated with the `standard` (Shafi/Maliki/Hanbali) or
`hanafi` shadow rule.

## Persisted data

Saved locations, the selected location, the time format and the location mode
are stored as JSON in `%LOCALAPPDATA%/YASB/salah_times.json` (or `data_file`).
On first run it is seeded with a few example cities.

## Available Styles

| Selector | Applies to |
| --- | --- |
| `.salah-times-widget` | The bar item container |
| `.salah-times-widget .icon` / `.label` / `.label.alt` | Bar icon and (primary / alternate) label text |
| `.salah-times-menu` | The click popup |
| `.salah-times-menu .header` / `.title` | Popup header bar and title |
| `.salah-times-menu .toggle-button` / `.toggle-button.active` | 12h/24h time-format toggle |
| `.salah-times-menu .summary` / `.summary-location` / `.summary-next` / `.summary-meta` | Next-salah summary block |
| `.salah-times-menu .times` / `.time-row` / `.time-row.next` / `.time-name` / `.time-value` | Today's times list (next salah highlighted) |
| `.salah-times-menu .section-label` | The "LOCATIONS" section label |
| `.salah-times-menu .location-item` / `.location-item.active` / `.name` / `.detail` | A saved-location row (active = selected) |
| `.salah-times-menu .icon-button` / `.edit-button` / `.delete-button` | Per-row edit / delete buttons |
| `.salah-times-menu .add-location` | "Add location" button |
| `.salah-times-menu .empty-state` / `.empty-icon` / `.empty-text` | Shown when no location is configured |
| `.salah-times-dialog` | The add / edit modal dialog |
| `.salah-times-dialog .field-label` / `.search-input` / `.search-results` / `.offset-name` | Dialog fields, city search, offset labels |
| `.salah-times-dialog .button.save` / `.button.cancel` | Dialog action buttons |

## Example Styles

```css
/* ===========================================================================
   Salah Times widget styles
   Append to your styles.css. Colours use the Catppuccin variables already
   defined at the top of your stylesheet (--text, --mauve, --surface1, ...).
   =========================================================================== */

/* --- Bar item ------------------------------------------------------------ */
.salah-times-widget .label {
    color: var(--text);
    font-size: 14px;
}

.salah-times-widget .icon {
    color: var(--mauve);
    padding-right: 8px;
    font-size: 18px;
}

.salah-times-widget .label.alt {
    font-size: 13px;
}

/* --- Popup shell --------------------------------------------------------- */
.salah-times-menu {
    background-color: rgba(24, 24, 37, 0.98);
    min-width: 340px;
    max-width: 380px;
}

.salah-times-menu .menu-body {
    background-color: transparent;
}

/* Header: title + time-format toggle */
.salah-times-menu .header {
    padding: 12px 14px;
    background-color: rgba(203, 166, 247, 0.06);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.salah-times-menu .header .title {
    font-family: 'Segoe UI';
    font-size: 14px;
    font-weight: 700;
    color: #fff;
}

.salah-times-menu .toggle-button {
    font-family: 'Segoe UI';
    font-size: 11px;
    font-weight: 600;
    color: var(--overlay1);
    background-color: rgba(255, 255, 255, 0.04);
    border: none;
    padding: 4px 10px;
    margin-left: 4px;
    border-radius: 4px;
}

.salah-times-menu .toggle-button:hover {
    background-color: rgba(255, 255, 255, 0.1);
    color: var(--text);
}

.salah-times-menu .toggle-button.active {
    background-color: var(--mauve);
    color: #1e1e2e;
}

/* Summary: selected location + next salah + meta */
.salah-times-menu .summary {
    padding: 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.salah-times-menu .summary-location {
    font-family: 'Segoe UI';
    font-size: 20px;
    font-weight: 700;
    color: #fff;
}

.salah-times-menu .summary-next {
    font-family: 'Segoe UI';
    font-size: 14px;
    font-weight: 600;
    color: var(--mauve);
    margin-top: 2px;
}

.salah-times-menu .summary-meta {
    font-family: 'Segoe UI';
    font-size: 11px;
    color: var(--subtext0);
    margin-top: 4px;
}

/* Today's salah times */
.salah-times-menu .times {
    padding: 6px 10px;
}

.salah-times-menu .time-row {
    padding: 6px 8px;
    border-radius: 6px;
}

.salah-times-menu .time-row.next {
    background-color: rgba(203, 166, 247, 0.16);
}

.salah-times-menu .time-row .time-name {
    font-family: 'Segoe UI';
    font-size: 13px;
    color: var(--subtext1);
}

.salah-times-menu .time-row.next .time-name,
.salah-times-menu .time-row.next .time-value {
    color: #fff;
    font-weight: 700;
}

.salah-times-menu .time-row .time-value {
    font-family: 'Segoe UI';
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
}

/* Locations section */
.salah-times-menu .section-label {
    font-family: 'Segoe UI';
    font-size: 10px;
    font-weight: 700;
    color: var(--overlay0);
    padding: 10px 16px 4px 16px;
}

.salah-times-menu .locations-container {
    background-color: transparent;
}

.salah-times-menu .location-item {
    padding: 8px 10px 8px 14px;
    margin: 2px 8px;
    border-radius: 6px;
    border: 1px solid transparent;
}

.salah-times-menu .location-item:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

.salah-times-menu .location-item.active {
    background-color: rgba(203, 166, 247, 0.12);
    border: 1px solid rgba(203, 166, 247, 0.35);
}

.salah-times-menu .location-item .name {
    font-family: 'Segoe UI';
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
}

.salah-times-menu .location-item .detail {
    font-family: 'Segoe UI';
    font-size: 11px;
    color: var(--overlay1);
}

.salah-times-menu .icon-button {
    font-family: 'JetBrainsMono NFP';
    background-color: transparent;
    border: none;
    color: var(--overlay1);
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    border-radius: 4px;
    font-size: 14px;
}

.salah-times-menu .edit-button:hover {
    background-color: rgba(255, 255, 255, 0.12);
    color: #fff;
}

.salah-times-menu .delete-button:hover {
    background-color: rgba(243, 139, 168, 0.22);
    color: var(--red);
}

/* Add-location button */
.salah-times-menu .add-location {
    font-family: 'JetBrainsMono NFP';
    font-size: 12px;
    font-weight: 600;
    color: var(--text);
    background-color: rgba(255, 255, 255, 0.05);
    border: none;
    padding: 10px;
    margin: 8px;
    border-radius: 6px;
}

.salah-times-menu .add-location:hover {
    background-color: rgba(203, 166, 247, 0.18);
    color: #fff;
}

/* Empty state */
.salah-times-menu .empty-state {
    padding: 26px 16px;
}

.salah-times-menu .empty-icon {
    font-family: 'JetBrainsMono NFP';
    font-size: 44px;
    color: var(--overlay0);
}

.salah-times-menu .empty-text {
    font-family: 'Segoe UI';
    font-size: 13px;
    color: var(--subtext0);
    margin-top: 8px;
}

/* --- Add / Edit dialog ---------------------------------------------------- */
.salah-times-dialog {
    background-color: #1e1e2e;
}

.salah-times-dialog QLabel {
    color: var(--text);
    font-family: 'Segoe UI';
}

.salah-times-dialog .field-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--subtext0);
    margin-top: 8px;
}

.salah-times-dialog QLineEdit,
.salah-times-dialog QComboBox,
.salah-times-dialog QSpinBox,
.salah-times-dialog QDoubleSpinBox {
    font-family: 'Segoe UI';
    font-size: 13px;
    color: var(--text);
    background-color: rgba(17, 17, 27, 0.6);
    border: 1px solid var(--surface1);
    border-radius: 6px;
    padding: 6px 8px;
}

.salah-times-dialog QLineEdit:focus,
.salah-times-dialog QComboBox:focus,
.salah-times-dialog QSpinBox:focus,
.salah-times-dialog QDoubleSpinBox:focus {
    border: 1px solid var(--blue);
}

.salah-times-dialog .search-input {
    font-size: 14px;
    padding: 8px 10px;
}

.salah-times-dialog .search-description {
    font-size: 12px;
    color: var(--subtext0);
}

.salah-times-dialog .search-status {
    font-size: 11px;
    color: var(--overlay1);
}

.salah-times-dialog .search-results {
    font-family: 'Segoe UI';
    font-size: 13px;
    background-color: rgba(17, 17, 27, 0.4);
    border: 1px solid var(--surface1);
    border-radius: 6px;
}

.salah-times-dialog .search-results::item {
    padding: 8px;
}

.salah-times-dialog .search-results::item:hover {
    background-color: rgba(255, 255, 255, 0.06);
}

.salah-times-dialog .offset-name {
    font-size: 13px;
    color: var(--subtext1);
}

.salah-times-dialog .button {
    font-size: 12px;
    font-weight: 600;
    font-family: 'Segoe UI';
    padding: 7px 20px;
    border-radius: 6px;
    border: none;
}

.salah-times-dialog .button.save {
    background-color: var(--mauve);
    color: #1e1e2e;
}

.salah-times-dialog .button.cancel {
    background-color: rgba(255, 255, 255, 0.06);
    color: var(--text);
}

.salah-times-dialog .link-button {
    font-size: 11px;
    color: var(--blue);
    background-color: transparent;
    border: none;
    padding: 4px;
}
```
