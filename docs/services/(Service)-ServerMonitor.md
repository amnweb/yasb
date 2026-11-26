# Server monitor

`import Yasb`

Whether your servers and websites answer, how fast, and how long their certificates last, with Windows
notifications when they go offline. Checked every `interval` seconds set with `configure()`. All ServerChecks
objects with the same settings share one check.

## ServerChecks

Nothing is checked until `configure()` is called with at least one server.

### Properties

#### results : list `read-only`

The servers after the last check, in the order given. Each is an object:

- `name` : string, the server's name, or its URL when it has none.
- `url` : string, the URL checked, with `https://` or `http://` added when it had no scheme.
- `status` : string, `Online` when the server answered with a code below 500, otherwise `Offline`.
- `response_time` : int, milliseconds until it answered. `null` when it didn't.
- `response_code` : int, the HTTP status code. `null` when it didn't answer.
- `ssl` : int, days until its certificate expires. `null` when not checked.

#### loading : bool `read-only`

`true` while the servers are checked.

#### configured : bool `read-only`

`true` when `configure()` was given at least one server.

#### error : string `read-only`

`"Could not check servers."` when the last check failed, otherwise `""`.

#### updated : date `read-only`

When the last check ended. Invalid before the first.

### Functions

#### configure(servers: list, sslVerify: bool, sslCheck: bool, timeout: int, interval: int, sslWarning: int, notifyOffline: bool, notifySsl: bool)

Sets what to check. Settings no other ServerChecks uses are checked at once.

- `servers`: each a URL, or an object with `url` and an optional `name`. Empty URLs are skipped.
- `sslVerify`: `true` checks each server's certificate and host name, `false` accepts any certificate.
- `sslCheck`: `true` adds `https://` to a server without a scheme, and reads how long the certificate of each
  online HTTPS server lasts. `false` adds `http://`.
- `timeout`: seconds each server has to answer, from 1 to 30.
- `interval`: seconds from the end of one check to the next, from 10 to 36000.
- `sslWarning`: days, from 1 to 365. See `notifySsl`.
- `notifyOffline`: `true` shows a Windows notification after a check that finds servers offline. Not while the
  PC has no network.
- `notifySsl`: `true` shows a Windows notification after a check that finds a certificate expiring in fewer than
  `sslWarning` days.

#### refresh()

Checks now. Ignored while a check is under way.

ServerChecks has no signals.

## Used by

YASB's own Server monitor widget, listed in [Widgets](./Widgets).
