# YASB CLI

`yasbc` comes with YASB and works it from a terminal: it starts, stops and reloads YASB, shows and hides bars,
installs addons, and backs up your config with [YASB Cloud](./Cloud). Each command below prints the same help with
`--help`.

## yasbc

```text
The command-line interface for YASB Reborn

Usage: yasbc [OPTIONS] [COMMAND]

Commands:
  start                Start the application
  stop                 Stop the application
  reload               Reload the application
  enable-autostart     Enable autostart on system boot
  disable-autostart    Disable autostart on system boot
  enable-crash-dumps   Enable crash dumps for troubleshooting
  disable-crash-dumps  Disable crash dumps
  monitor-information  Show information about connected monitors
  show-bar             Show the bar on all or a specific screen
  hide-bar             Hide the bar on all or a specific screen
  toggle-bar           Toggle the bar on all or a specific screen
  set-channel          Switch release channels
  update               Update the application
  log                  Tail yasb process logs (cancel with Ctrl-C)
  reset                Restore default config files and clear cache
  cloud                Back up and restore your config with YASB Cloud
  addons               Search, install, update and list widgets, themes, layouts and configs
  config-dir           Open config directory in file explorer
  help                 Print this message or the help of the given command

Options:
  -v, --version  Print version
  -c, --config   Print config directory path
  -h, --help     Print help
```

## yasbc start

```text
Start the application

Usage: yasbc start [OPTIONS]

Options:
  -s, --silent  Silence print messages
  -h, --help    Print help
```

## yasbc stop

```text
Stop the application

Usage: yasbc stop [OPTIONS]

Options:
  -s, --silent  Silence print messages
  -f, --force   Force stop the application
  -h, --help    Print help
```

## yasbc reload

```text
Reload the application

Usage: yasbc reload [OPTIONS]

Options:
  -s, --silent  Silence print messages
  -h, --help    Print help
```

## yasbc enable-autostart

```text
Enable autostart on system boot

Usage: yasbc enable-autostart [OPTIONS]

Options:
      --task  Enable autostart as a scheduled task
  -h, --help  Print help
```

## yasbc disable-autostart

```text
Disable autostart on system boot

Usage: yasbc disable-autostart [OPTIONS]

Options:
      --task  Disable autostart as a scheduled task
  -h, --help  Print help
```

## yasbc enable-crash-dumps

```text
Enable crash dumps for troubleshooting

Usage: yasbc enable-crash-dumps [OPTIONS]

Options:
  -h, --help  Print help
```

## yasbc disable-crash-dumps

```text
Disable crash dumps

Usage: yasbc disable-crash-dumps [OPTIONS]

Options:
  -h, --help  Print help
```

## yasbc monitor-information

```text
Show information about connected monitors

Usage: yasbc monitor-information [OPTIONS]

Options:
  -h, --help  Print help
```

## yasbc show-bar

```text
Show the bar on all or a specific screen

Usage: yasbc show-bar [OPTIONS]

Options:
  -s, --screen <SCREEN>  Screen name (optional)
  -h, --help             Print help
```

## yasbc hide-bar

```text
Hide the bar on all or a specific screen

Usage: yasbc hide-bar [OPTIONS]

Options:
  -s, --screen <SCREEN>  Screen name (optional)
  -h, --help             Print help
```

## yasbc toggle-bar

```text
Toggle the bar on all or a specific screen

Usage: yasbc toggle-bar [OPTIONS]

Options:
  -s, --screen <SCREEN>  Screen name (optional)
  -h, --help             Print help
```

## yasbc set-channel

```text
Switch release channels

Usage: yasbc set-channel [OPTIONS] <TARGET_CHANNEL>

Arguments:
  <TARGET_CHANNEL>  'stable' for tested releases or 'preview' for the latest updates [possible values: stable, preview]

Options:
  -h, --help  Print help
```

## yasbc update

```text
Update the application

Usage: yasbc update [OPTIONS]

Options:
  -h, --help  Print help
```

## yasbc log

```text
Tail yasb process logs (cancel with Ctrl-C)

Usage: yasbc log [OPTIONS]

Options:
  -h, --help  Print help
```

## yasbc reset

```text
Restore default config files and clear cache

Usage: yasbc reset [OPTIONS]

Options:
  -h, --help  Print help
```

## yasbc cloud

```text
Back up and restore your YASB configuration

Usage: yasbc cloud [OPTIONS] [COMMAND]

Commands:
  auth     Sign in through your browser
  logout   Sign out on this machine
  status   Show the signed-in account, plan and usage
  list     List your backups
  backup   Back up the configuration directory now
  restore  Replace the configuration with a backup
  save     Save a backup to a folder without restoring it
  delete   Delete a backup from YASB Cloud
  share    Publish a backup and print its link
  unshare  Stop sharing a backup
  help     Print this message or the help of the given command

Options:
  -h, --help  Print help
```

## yasbc cloud auth

```text
Sign in through your browser

Usage: yasbc cloud auth [OPTIONS]

Options:
  -h, --help  Print help
```

## yasbc cloud logout

```text
Sign out on this machine

Usage: yasbc cloud logout [OPTIONS]

Options:
  -h, --help  Print help
```

## yasbc cloud status

```text
Show the signed-in account, plan and usage

Usage: yasbc cloud status [OPTIONS]

Options:
  -h, --help  Print help
```

## yasbc cloud list

```text
List your backups

Usage: yasbc cloud list [OPTIONS]

Options:
  -s, --search <SEARCH>  Only backups whose note or PC name contains this
  -p, --page <PAGE>      Which page to show, 50 per page
  -h, --help             Print help
```

## yasbc cloud backup

```text
Back up the configuration directory now

Usage: yasbc cloud backup [OPTIONS]

Options:
  -n, --note <NOTE>  Label for this backup
  -h, --help         Print help
```

## yasbc cloud restore

```text
Replace the configuration with a backup

Usage: yasbc cloud restore [OPTIONS] <BACKUP>

Arguments:
  <BACKUP>  Backup id from `yasbc cloud list`, or `latest`

Options:
  -y, --yes   Skip the confirmation
  -h, --help  Print help
```

## yasbc cloud save

```text
Save a backup to a folder without restoring it

Usage: yasbc cloud save [OPTIONS] <BACKUP> <FOLDER>

Arguments:
  <BACKUP>  Backup id from `yasbc cloud list`, or `latest`
  <FOLDER>  Where to write it

Options:
  -h, --help  Print help
```

## yasbc cloud delete

```text
Delete a backup from YASB Cloud

Usage: yasbc cloud delete [OPTIONS] <BACKUP>

Arguments:
  <BACKUP>  Backup id from `yasbc cloud list`, or `latest`

Options:
  -y, --yes   Skip the confirmation
  -h, --help  Print help
```

## yasbc cloud share

```text
Publish a backup and print its link

Usage: yasbc cloud share [OPTIONS] <BACKUP>

Arguments:
  <BACKUP>  Backup id from `yasbc cloud list`, or `latest`

Options:
  -h, --help  Print help
```

## yasbc cloud unshare

```text
Stop sharing a backup

Usage: yasbc cloud unshare [OPTIONS] <BACKUP>

Arguments:
  <BACKUP>  Backup id from `yasbc cloud list`, or `latest`

Options:
  -h, --help  Print help
```

## yasbc addons

```text
Search, install, update and list widgets, themes, layouts and configs

Usage: yasbc addons [OPTIONS] [COMMAND]

Commands:
  search   Search YASB's widgets and the addons repository
  install  Install an addon, or YASB's own widget to change its settings
  update   List updates for your copies of YASB's widgets and your addons, or update them
  list     List your widgets and installed themes, layouts and config
  help     Print this message or the help of the given command

Options:
  -h, --help  Print help
```

## yasbc addons search

```text
Search YASB's widgets and the addons repository

Usage: yasbc addons search [OPTIONS] [TEXT]

Arguments:
  [TEXT]  Look for this in the name, id, description, author or type

Options:
  -h, --help  Print help
```

## yasbc addons install

```text
Install an addon, or YASB's own widget to change its settings

Usage: yasbc addons install [OPTIONS] <ID>

Arguments:
  <ID>  The addon, such as amnweb.clock, its GitHub link, or YASB's widget, such as clock

Options:
      --version <VERSION>  Install this version, not the newest
      --full               Install YASB's whole widget, not only its settings
      --force              Replace it if you have it
  -h, --help               Print help
```

## yasbc addons update

```text
List updates for your copies of YASB's widgets and your addons, or update them

Usage: yasbc addons update [OPTIONS] [ID]

Arguments:
  [ID]  Update this widget, theme or layout

Options:
      --all   Update all of them
  -h, --help  Print help
```

## yasbc addons list

```text
List your widgets and installed themes, layouts and config

Usage: yasbc addons list [OPTIONS]

Options:
  -h, --help  Print help
```

## yasbc config-dir

```text
Open config directory in file explorer

Usage: yasbc config-dir [OPTIONS]

Options:
  -h, --help  Print help
```
