# Environment

`import Yasb` · a singleton: use it by its name, without creating it

Reads environment variables, so tokens and passwords can live in YASB's `.env` file instead of in widget files you
share.

Guide: [Writing widgets](./Writing-Widgets#keep-a-token-out-of-the-file)

## Example

Put the token in `%USERPROFILE%\.config\yasb\.env`, one `NAME=value` per line:

```text
GITHUB_TOKEN=your-token
```

Then read it where the widget needs it. For example, the `token` option in the GitHub widget copy that
`yasbc addons install Github` creates:

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

OBS's `password` option works the same way: `Environment.value("OBS_PASSWORD")`.

## The .env file

YASB reads `.env` from your config folder once, at startup. Restart or reload YASB after you change it. The config
folder is `%USERPROFILE%\.config\yasb`, or the folder in the `YASB_CONFIG_HOME` environment variable.

## Environment

### Functions

#### value(name: string) : string

The value of the environment variable `name`, from `.env` or from Windows. `""` when it isn't set.

Environment has no properties or signals.

## Used by

The built-in GitHub and OBS widgets, if you set their options this way.
