# Burp Suite Widget Options

Shows whether [Burp Suite](https://portswigger.net/burp) is running on the bar, the
detected edition (Professional / Community / Enterprise / DAST), and — when the Burp REST
API is enabled — whether that service is reachable. Useful as an at-a-glance reminder that
your proxy is up before you start browsing a target.

The widget is read-only and requires no configuration in Burp for basic presence detection:
Burp Suite is detected by its window title. The optional REST-API health check probes the
service root (`GET http://host:port/`), which returns `{"burp_status": "ready"}` and needs
**no API key**, so no secrets are stored or sent.

| Option              | Type    | Default | Description |
|---------------------|---------|---------|-------------|
| `label`             | string  | `'<span>{icon}</span> {status}'` | The format string for the label. Supports the placeholders below. |
| `label_alt`         | string  | `'<span>{icon}</span> Burp {edition}'` | The alternative format string, toggled by the `toggle_label` callback. |
| `update_interval`   | integer | `5` | How often the status is refreshed, in seconds (1–3600). |
| `rest_api`          | dict    | `{enabled: true, host: '127.0.0.1', port: 1337}` | Burp REST API health-check settings. Set `enabled: false` to detect the process only. |
| `icons`             | dict    | See below | Icons for each state. |
| `status_text`       | dict    | See below | Text shown for each state via `{status}`. |
| `hide_when_offline` | boolean | `false` | Hide the widget entirely when Burp Suite is not running. |
| `tooltip`           | boolean | `true` | Whether to show a status tooltip on hover. |
| `callbacks`         | dict    | `{'on_left': 'toggle_label', 'on_middle': 'do_nothing', 'on_right': 'do_nothing'}` | Mouse-click callbacks. |

## States

The widget reports one of three states, each with its own icon, status text, and CSS class:

- **offline** — no Burp Suite window detected.
- **running** — Burp Suite is running (REST API disabled, unreachable, or not yet ready).
- **ready** — Burp Suite is running and its REST API responds with `ready`.

## Placeholders

You can use the following placeholders in `label` / `label_alt`:

- `{icon}` — the state icon (from `icons`); wrap it in a `<span>` to style it as an icon.
- `{status}` — the state text (from `status_text`).
- `{edition}` — detected edition: `Pro`, `Community`, `Enterprise`, `DAST`, or `Suite`
  (empty when offline).

## Example Configuration

```yaml
burp_suite:
  type: "yasb.burp_suite.BurpSuiteWidget"
  options:
    label: "<span>{icon}</span> {status}"
    label_alt: "<span>{icon}</span> Burp {edition}"
    update_interval: 5
    rest_api:
      enabled: true
      host: "127.0.0.1"
      port: 1337
    icons:
      offline: "󰦜"   # nf-md-shield_off_outline
      running: "󰒙"   # nf-md-shield_outline
      ready: "󰕥"     # nf-md-shield_check
    status_text:
      offline: "Offline"
      running: "Running"
      ready: "REST Ready"
    hide_when_offline: false
    tooltip: true
    callbacks:
      on_left: "toggle_label"   # switch between status and edition
      on_middle: "refresh"      # force an immediate re-check
      on_right: "do_nothing"
```

## Description of Options

- **label:** The format string for the label. Supports the placeholders listed above.
- **label_alt:** The alternative format string, toggled with the `toggle_label` callback.
- **update_interval:** How often the status is refreshed, in seconds (1–3600).
- **rest_api:** REST API health-check settings:
  - **enabled:** Whether to probe the REST API. When `false`, the widget only distinguishes
    `offline` vs `running`.
  - **host / port:** Where Burp's REST API service is bound (Settings → Suite → REST API).
- **icons:** Icons shown for each state via `{icon}`.
- **status_text:** Text shown for each state via `{status}`.
- **hide_when_offline:** Hide the widget when Burp Suite is not running.
- **tooltip:** Whether to show a status tooltip on hover.
- **callbacks:** Mouse-click callbacks. Built-in actions: `toggle_label` (swap between `label`
  and `label_alt`), `refresh` (force an immediate re-check), `do_nothing`, and `exec`.

## Enabling the Burp REST API (optional)

Presence detection works without this. To light up the `ready` state:

1. In Burp Suite, go to **Settings → Suite → REST API**.
2. Check **Service running** and note the port (default `1337`).

An API key is not required for the health check this widget performs.

## Widget Style
```css
.burp-suite-widget {}
.burp-suite-widget .widget-container {}
.burp-suite-widget .icon {}
.burp-suite-widget .label {}
/* Per-state classes are applied to both the icon and the label */
.burp-suite-widget .icon.offline {}
.burp-suite-widget .icon.running {}
.burp-suite-widget .icon.ready {}
.burp-suite-widget .label.offline {}
.burp-suite-widget .label.running {}
.burp-suite-widget .label.ready {}
```

## Example Style
```css
.burp-suite-widget {
    padding: 0 8px;
}
.burp-suite-widget .icon {
    font-size: 14px;
    margin-right: 4px;
}
.burp-suite-widget .label {
    font-size: 13px;
    color: #cdd6f4;
}
.burp-suite-widget .icon.offline,
.burp-suite-widget .label.offline { color: #6c7086; }
.burp-suite-widget .icon.running,
.burp-suite-widget .label.running { color: #fe640b; }  /* Burp orange */
.burp-suite-widget .icon.ready,
.burp-suite-widget .label.ready { color: #a6e3a1; }
```
