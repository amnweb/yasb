# Process

`import Yasb`

Runs a program or command line and gives what it printed: as text, as JSON, or line by line while it runs. Runs on
`run()`, or every `interval` while `active`. Each Process runs its own program and stops it when the Process is
destroyed or YASB quits.

## Process

### Properties

#### command : var

A command line, as a string, or a list of the program and its arguments. A list runs the program without cmd.exe.
Nothing runs while it is empty.

Default: `""`

#### shell : bool

When `true`, a command line runs through cmd.exe, so pipes and built-in commands such as `echo` work. A list
never does.

Default: `true`

#### workingDirectory : string

Folder the program runs in. `""` for YASB's own.

Default: `""`

#### interval : int

Milliseconds from the end of one run to the start of the next. `0` runs only on `run()`. When it is above `0`,
the first run starts at once.

Default: `0`

#### active : bool

When `false`, interval runs pause, for example while the widget is hidden. A run already in progress continues. Turning
it on runs at once when `interval` is above `0`.

Default: `true`

#### timeout : int

Milliseconds a run may take before its program is stopped. `0` for no limit.

Default: `0`

#### format : string

How the output is given:

- `text`: the whole output in `output`, once the run ends.
- `json`: the same, and the output parsed in `data`.
- `lines`: each line in `output` and `received`, as it is printed.
- `jsonLines`: each line parsed in `data` and `received`, as it is printed. Empty lines are skipped.

Any other value is taken as `text`.

Default: `"text"`

#### encoding : string

Encoding of the output, such as `utf-8` or `cp1252`. `""` tries UTF-8, then the console code page.

Default: `""`

#### output : var `read-only`

With `text` and `json`, the whole output of the last successful run, with line ends as `\n` and the last ones removed.
With `lines`, the last line. `""` before the first run.

#### errorOutput : string `read-only`

What the last run printed to its error output, up to its first MB.

#### data : var `read-only`

With `json`, the output parsed. With `jsonLines`, the last line parsed. `null` before, and with other formats.

#### exitCode : int `read-only`

Exit code of the last run. `-1` when it could not start.

#### running : bool `read-only`

`true` while a run is in progress.

#### error : string `read-only`

The error from the last run, or `""` if it succeeded. A failed run keeps the last good `output` and `data`.

- `Could not start <program>: <reason>`: the program could not start.
- `Exited with code <code>`, followed by the first line of `errorOutput` when there is one.
- `Stopped after <timeout> ms`: it took longer than `timeout`.
- `Stopped`: `kill()` stopped it.
- `Printed more than 16 MB`: the output, or with `lines` and `jsonLines` one line, was too long.
- `The output is not JSON: <reason>`: with `json`.
- `A line is not JSON: <reason>`: with `jsonLines`. The run goes on, and the next line that parses clears it.
- `Unknown encoding <encoding>`: `encoding` is not a known encoding.

#### lastRun : real `read-only`

When the last run started, in milliseconds since 1970. `0` before.

#### duration : int `read-only`

Milliseconds the last run took.

### Functions

#### run()

Starts a run. Ignored while one is running, or while `command` is empty.

#### start()

Opens the program and leaves it running, as for an app: no output, `exitCode` or `running`. Never through
cmd.exe.

#### kill()

Stops the running program. Programs it started keep running, so a command line run through cmd.exe can continue after
cmd.exe is stopped. Use a list for long-running commands.

### Signals

#### received(value: var)

Each line as it is printed, with `lines` as a string and with `jsonLines` parsed. Not sent for a line that is not
JSON.

#### finished(exitCode: int)

A run succeeded. `exitCode` is always `0`, as any other code is an error.

#### failed(error: string)

A run ended with an error, the same text as `error`.
