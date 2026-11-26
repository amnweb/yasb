# Clock

`import Yasb`

Current time and date in any time zone, formatted your way, in any language.

TimeZones has no properties or signals. Each `format()` call returns the time at that moment, to show a running
clock, call it from a `Timer`, for example once a second.

## TimeZones

### Functions

#### format(zone: string, pattern: string, locale: string) : string

Current time in `zone`, formatted with `pattern`, in the language of `locale`.

- `zone`: IANA time zone name, such as `"Europe/Paris"`, `"America/New_York"` or `"Asia/Tokyo"`. `""` or
  `"local"` is your own time zone. Unknown names fall back to your own time zone, and `yasb.log` notes it once.
- `pattern`: Qt date and time format, described in
  [QDateTime::toString()](https://doc.qt.io/qt-6/qdatetime.html#toString). `"HH:mm"` gives `14:05`, `"h:mm AP"`
  gives `2:05 PM`, `"dddd d MMMM yyyy"` gives `Wednesday 26 November 2026`. Text in single quotes is kept as is.
  An empty `pattern` returns `""`.
- `locale`: language and country, such as `"de_DE"` or `"ja_JP"`, for the names of days and months. `""` uses
  Windows' language. `"C"` gives plain English names and digits, useful for dates you parse back into numbers.

## Used by

YASB's own Clock widget, listed in [Widgets](./Widgets).
