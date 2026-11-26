# Power menu

`import Yasb`

The signed-in user, how long Windows has been running, and functions to lock, sign out, sleep, hibernate, restart
and shut down. The user's details are read once and shared by all PowerSession objects.

## PowerSession

### Properties

#### userName : string `read-only`

The user's display name, or the account name when there is none.

#### email : string `read-only`

The account's email address. `""` when Windows has none.

#### accountType : string `read-only`

`Administrator` or `Standard User`.

#### avatar : url `read-only`

The user's account picture, in its largest size, or Windows' default user picture. Empty when neither is found.

#### uptime : int `read-only`

Seconds since Windows started, as of the last `refresh()`. `0` until then.

### Functions

#### refresh()

Reads `uptime` again.

#### run(action: string)

Runs the action:

- `lock`: locks the PC.
- `signout`: YASB quits, then Windows signs out.
- `sleep`: puts the PC to sleep.
- `hibernate`: hibernates the PC.
- `restart`: YASB quits, then Windows restarts.
- `shutdown`: YASB quits, then Windows shuts down, as `shutdown /s /hybrid`.
- `force_restart`: like `restart`, as `shutdown /r /f /t 0`.
- `force_shutdown`: like `shutdown`, as `shutdown /s /f /t 0`.

Any other value is ignored.

PowerSession has no signals.

## Used by

YASB's own Power menu widget, listed in [Widgets](./Widgets).
