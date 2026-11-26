# Environment

`import Yasb` · a singleton: use it by its name, without creating it

Reads an environment variable, so a token or a password can stay in YASB's `.env` file instead of a widget file
you share.

Guide: [Writing widgets](./Writing-Widgets#keep-a-token-out-of-the-file)

## Example

Put the token in `%USERPROFILE%\.config\yasb\.env`, one `NAME=value` per line:

```text
GITHUB_TOKEN=your-token
```

Then read it where the widget needs it. Here it is the GitHub widget's `token` option, in the copy that
`yasbc addons install Github` writes:

```qml
// %USERPROFILE%\.config\yasb\widgets\Github\Github.qml
import Yasb
import Yasb.Widgets

Github {
    settings {
        token: Environment.value("GITHUB_TOKEN")
    }
}
```

OBS's `password` option can come from it the same way, such as `Environment.value("OBS_PASSWORD")`.

## The .env file

YASB reads `.env` from your config folder once, when it starts, so a change to it shows after YASB restarts or
reloads. The config folder is `%USERPROFILE%\.config\yasb`, or the folder in the `YASB_CONFIG_HOME` environment
variable.

## Environment

### Functions

#### value(name: string) : string

The value of the environment variable `name`, from `.env` or from Windows. `""` when it isn't set.

Environment has no properties or signals.

## Used by

The options of YASB's own GitHub and OBS widgets, when you set them this way.
