# Media

`import Yasb`

What's playing in any app that reports to Windows: track, cover, position, with playback controls. Follows the
player Windows reports as current. `switchSession()` picks another player until Windows changes its current one.
All NowPlaying objects share one connection to Windows' media sessions.

## NowPlaying

### Properties

#### positionInterval : int

Milliseconds between `position` updates while playing. At least 50.

Default: `1000`

#### available : bool `read-only`

`true` when there is a player. Without one, text properties are `""`, numbers `0`, `repeat` is `none`, and the
rest `false`.

#### sessionCount : int `read-only`

Number of players Windows knows.

#### appId : string `read-only`

Player's app id in Windows.

#### appName : string `read-only`

Player's app name.

#### process : string `read-only`

Player's program.

#### title : string `read-only`

Track title.

#### artist : string `read-only`

Track artist.

#### albumTitle : string `read-only`

Album title.

#### thumbnail : string `read-only`

Image URL of the cover. `""` when the player gives none.

#### playing : bool `read-only`

`true` while playing.

#### position : real `read-only`

Position in the track, in seconds. Updates every `positionInterval` while playing, never past `duration`.

#### duration : real `read-only`

Track length, in seconds. `0` when the player doesn't say.

#### canPlayPause : bool `read-only`

`true` when `playPause()` works.

#### canPrevious : bool `read-only`

`true` when `previous()` works.

#### canNext : bool `read-only`

`true` when `next()` works.

#### canSeek : bool `read-only`

`true` when `seek()` works and the track length is known.

#### canShuffle : bool `read-only`

`true` when `toggleShuffle()` works.

#### canRepeat : bool `read-only`

`true` when `cycleRepeat()` works.

#### shuffle : bool `read-only`

`true` when shuffle is on.

#### repeat : string `read-only`

Repeat mode: `none`, `track` or `list`.

### Functions

#### playPause()

Plays or pauses.

#### previous()

Previous track.

#### next()

Next track.

#### seek(seconds: real)

Goes to this position, in seconds.

#### toggleShuffle()

Turns shuffle on or off.

#### cycleRepeat()

Next repeat mode: `none` → `list` → `track` → `none`.

#### switchSession(direction: int)

Picks the next player for `1`, or the previous for `-1`. Kept until Windows changes its current player.

#### openApp()

Brings the player's app to the front.

## Used by

YASB's own Media widget, listed in [Widgets](./Widgets).
