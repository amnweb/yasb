# YASB CLI (Command Line Interface)

The YASB CLI is a command line interface that allows you to interact with the YASB status bar. The CLI is a powerful tool that allows you to manage your YASB bar, start, stop, enable autostart, disable autostart, reload, update and watch the logs in the terminal.

## Usage
`yasbc [command] [options]`

## Commands
- `start` - Start the status bar.
- `stop` - Stop the status bar.
- `enable-autostart` - Enable autostart for the status bar on system boot.
- `disable-autostart` - Disable autostart for the status bar on system boot.
- `reload` - Reload the status bar configuration.
- `monitor-information` - Show information about connected monitors.
- `hide-bar` - Hide the status bar.
- `show-bar` - Show the status bar.
- `toggle-bar` - Toggle the visibility of the status bar.
- `update` - Update aplicattion to the latest version.
- `log` - Show the status bar logs in the terminal.
- `reset` - Restore default config files and clear cache
- `help` - Show the help message.

## Options
- `--help` - Show the help message for the command.
- `--silent` - Disable print messages for `start`, `stop` and `reload`
- `--version` - Show the YASB version.

> **Note:**
> You can use the `--silent` option with the `start`, `stop` and `reload` commands to prevent non-error messages from being displayed.

## Autostart

To enable autostart for the status bar on system boot, use the following command:
```bash
yasbc enable-autostart
```
To disable autostart for the status bar on system boot, use the following command:
```bash
yasbc disable-autostart
```
To create task scheduler for autostart on windows, use the following command:
```bash
yasbc enable-autostart --task
```

To disable task scheduler for autostart on windows, use the following command:
```bash
yasbc disable-autostart --task
```
> **Note:**
> Creating a task scheduler for autostart on Windows requires administrator privileges.

## Show and Hide the Status Bar
To hide the status bar on all screens, use the following command:
```bash
yasbc hide-bar
```
To hide the status bar on a specific screen, use the following command:
```bash
yasbc hide-bar --screen <screen_name>
```
To show the status bar on all screens, use the following command:
```bash
yasbc show-bar
```
To show the status bar on a specific screen, use the following command:
```bash
yasbc show-bar --screen <screen_name>
```
To toggle the visibility of the status bar on all screens, use the following command:
```bash
yasbc toggle-bar
```
To toggle the visibility of the status bar on a specific screen, use the following command:
```bash
yasbc toggle-bar --screen <screen_name>
```

