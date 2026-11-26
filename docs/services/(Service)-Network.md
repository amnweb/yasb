# Network

`import Yasb`

The internet connection of any kind (Wi-Fi, Ethernet, mobile broadband, or another adapter such as a VPN's), with its
signal and whether it reaches the internet. It also covers Wi-Fi: nearby networks, the Wi-Fi switch, and joining,
leaving and forgetting networks.

Two types:

- [NetworkConnections](#networkconnections): the one connection Windows uses for the internet. Not a list of all
  connections.
- [WifiNetworks](#wifinetworks): Wi-Fi only: the switch, and nearby networks as a list. See
  [Row fields](#row-fields).

## NetworkConnections

Updates when Windows reports a network change. All NetworkConnections objects share one watcher.

### Properties

#### signalInterval : int

Milliseconds between signal readings for mobile connections, and for Wi-Fi while YASB has no location access, 500
to 60000. With location access, Windows reports Wi-Fi signal changes by itself.

Default: `1000`

#### primary : object `read-only`

The connection Windows reports as its internet connection.

- `kind` : string, `wifi` (Wi-Fi), `ethernet` (cable), `mobile` (mobile broadband), `other` (any other adapter,
  such as a VPN's), or `none` (no connection, or Windows gives no adapter for it).
- `name` : string, network name, as Windows gives it.
- `ssid` : string, Wi-Fi SSID. `""` for other kinds.
- `mobileType` : string, `5G`, `LTE`, `3G` or `2G` for mobile. `""` for other kinds.
- `adapter` : string, network adapter name.
- `adapterId` : string, adapter id in Windows.
- `ipAddress` : string, adapter's IP address.
- `connectivity` : string, `none`, `local` (local network only), `constrained` (needs a sign-in page) or
  `internet`.
- `metered` : bool, `true` for a metered connection.
- `signal` : int, signal, 0 to 100. `-1` for connections without a signal, such as Ethernet.

No functions or signals.

## WifiNetworks

Networks are only populated while `watching` is `true` (for example while a popup is open), because scanning is costly.

### Properties

#### watching : bool

When `true`, nearby networks are scanned and kept up to date. Turning it on scans at once if Wi-Fi is on.

Default: `false`

#### networks : list `read-only`

Nearby Wi-Fi networks, only while `watching`: connected first, then by signal, hidden networks last. See
[Row fields](#row-fields).

#### available : bool `read-only`

`true` when the PC has a Wi-Fi adapter. Known after the first scan.

#### enabled : bool `read-only`

`true` when Wi-Fi is on.

#### scanning : bool `read-only`

`true` while scanning, at most 10 seconds.

#### connecting : bool `read-only`

`true` while joining a network.

#### connectingTo : string `read-only`

SSID of the network being joined. `""` for a hidden network or when none.

#### error : string `read-only`

Last error, `""` when none. Scan errors stay until the next scan, other errors are cleared after 4 seconds.

- `accessDenied`: YASB has no location access.
- `scanFailed`: the scan failed.
- `radioDenied`: Windows didn't allow YASB to turn Wi-Fi on or off.
- `connectFailed`, `invalidCredential`, `networkNotAvailable`, `timeout`, `accessRevoked` or
  `unsupportedAuthenticationProtocol`: joining failed, and why.

### Functions

#### scan()

Scans now. Ignored while a scan is running.

#### setEnabled(on: bool)

Turns Wi-Fi on or off, like Windows' Wi-Fi switch. Windows may ask the user the first time.

#### connectTo(ssid: string, password: string, autoConnect: bool)

Joins the network with this `ssid` (from a row of `networks`). An empty `password` uses the one Windows saved.
`autoConnect` sets whether Windows joins it automatically later. Ignored while another network is being joined.

#### connectHidden(ssid: string, password: string, autoConnect: bool)

Joins a hidden network by the `ssid` the user types.

#### disconnectNetwork()

Leaves the current Wi-Fi network.

#### forget(ssid: string)

Deletes the network's profile, with its password, from Windows.

#### setAutoConnect(ssid: string, autoConnect: bool)

Sets whether Windows joins this known network automatically. If it is the current network, YASB joins it again,
because Windows disconnects when its profile changes.

### Row fields

Fields of each row in `networks`, as `required property` in a delegate. Rows update in place.

#### ssid : string

SSID. Used by the functions. `""` for a hidden network.

#### hidden : bool

`true` when the network hides its SSID.

#### quality : int

Signal, 0 to 100.

#### secured : bool

`true` when it needs a password.

#### connected : bool

`true` when Wi-Fi is on this network.

#### known : bool

`true` when Windows has a profile for it, so `connectTo()` needs no password.

#### autoConnect : bool

`true` when Windows joins it automatically.

`networks` also has `count`, the number of networks.

## Used by

YASB's own Network widget, listed in [Widgets](./Widgets).
