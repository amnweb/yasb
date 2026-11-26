# Network traffic

`import Yasb`

Download and upload speed of a network adapter, data moved since the session started, and Windows' usage history
by day and hour. Updated every `updateInterval`.

All NetworkTrafficMonitor objects with the same `interfaceName` share one reader, so the shortest `updateInterval`
among them applies.

## NetworkTrafficMonitor

### Properties

#### interfaceName : string

The adapter to read: `auto` for the connection Windows uses for the internet, or an adapter name as Windows shows
it, such as `Ethernet` or `Wi-Fi`, in any case. An empty name means `auto`.

Default: `"auto"`

#### updateInterval : int

Milliseconds between two readings, from 1000 to 60000.

Default: `1000`

#### data : object `read-only`

The connection on the adapter, after the last reading:

- `connected` : bool, `true` when the adapter is up. When its counters can't be read, `true` when Windows reports
  any connectivity.
- `available` : bool, the same as `connected`.
- `internetAvailable` : bool, `true` when Windows reports the connection reaches the internet. `null` when there
  is no connection.
- `profileName` : string, network name, as Windows gives it.
- `adapterName` : string, adapter name. The network name when the adapter's counters can't be read.
- `ipAddress` : string, adapter's IPv4 address. `""` when it has none.
- `isWifi` : bool, `true` for a Wi-Fi connection.
- `interfaces` : list&lt;string&gt;, the adapter's name, or empty when there is no adapter.
- `downloadRate` : real, bytes per second received since the previous reading.
- `uploadRate` : real, bytes per second sent since the previous reading.
- `sessionDownloaded` : int, bytes received in this session.
- `sessionUploaded` : int, bytes sent in this session.
- `sessionSeconds` : int, seconds since this session started.

A session starts when the connection moves to another network or adapter, and on `reset()`. Connecting again to
the same network carries on the same session. Sessions are kept only while YASB runs.

Until the first reading, and while there is no connection, `connected` is `false`, the strings and `interfaces`
are empty, and the numbers are `0`. The first reading of a session has rates of `0`.

#### history : object `read-only`

Windows' record of the data this connection used, read again at most once a minute:

- `daily` : list&lt;object&gt;, up to the last 30 days, oldest first. Today, the sum of `hourly`, comes last while
  `hourly` has points.
- `hourly` : list&lt;object&gt;, each hour of today, from midnight to now.
- `updatedAt` : int, when it was read, in milliseconds since 1970.
- `loading` : bool, `true` while the first reading for this connection, or for a new day, is under way.

Each point in `daily` and `hourly` has:

- `stamp` : int, start of its day or hour, in milliseconds since 1970.
- `downloaded` : int, bytes received.
- `uploaded` : int, bytes sent.

Empty lists while `connected` is `false`, and when Windows has no record for the connection.

#### error : string `read-only`

`"Network statistics are unavailable."` when the last reading failed, otherwise `""`.

#### loading : bool `read-only`

`true` until the first reading arrives, and again after `interfaceName` changes to another adapter.

### Functions

#### reset()

Starts a new session on this adapter, for every NetworkTrafficMonitor that shares it. Ignored while `connected` is
`false`.

#### refresh()

Reads now, and reads `history` again without waiting for the minute to pass.

NetworkTrafficMonitor has no signals.

## Used by

YASB's own Network traffic widget, listed in [Widgets](./Widgets).
