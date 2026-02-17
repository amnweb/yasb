# Keybindings

YASB supports global keyboard shortcuts (hotkeys) to trigger widget actions. Keybindings are configured per-widget in the widget's `options` section. This feature uses the native Windows `RegisterHotKey` API and requires no third-party dependencies.

## Overview

- **Per-widget instance**: Keybindings are tied to the specific widget name in your config (e.g., `clock` vs `clock_2`)
- **Multiple keybindings**: A single widget can have multiple keybindings for different actions
- **Screen-aware**: Hotkeys trigger the widget on the currently focused screen
- **Zero overhead**: If no keybindings are defined, no hotkey listener is started
- **No auto-repeat**: Holding a hotkey fires only once (uses `MOD_NOREPEAT`)

## Configuration

Add a `keybindings` list to any widget's options. Each keybinding requires:
- `keys`: The key combination (e.g., `"win+c"`, `"ctrl+shift+f1"`)
- `action`: The callback action to trigger (e.g., `"toggle_calendar"`, `"toggle_label"`)

### Basic Example

```yaml
clock:
  type: "yasb.clock.ClockWidget"
  options:
    label: "{%H:%M}"
    keybindings:
      - keys: "win+c"
        action: "toggle_calendar"
      - keys: "ctrl+shift+t"
        action: "toggle_label"
```

### Multiple Widgets Example

```yaml
clock:
  type: "yasb.clock.ClockWidget"
  options:
    keybindings:
      - keys: "win+c"
        action: "toggle_calendar"

volume:
  type: "yasb.volume.VolumeWidget"
  options:
    keybindings:
      - keys: "win+v"
        action: "toggle_menu"
```

## Supported Keys

### Modifier Keys

| Key Name | Description |
|----------|-------------|
| `win`, `windows`, `super`, `meta` | Windows key |
| `alt` | Alt key |
| `ctrl`, `control` | Control key |
| `shift` | Shift key |

> **Note:** `RegisterHotKey` does not distinguish between left and right modifier keys.

### Function Keys

| Key Name | Description |
|----------|-------------|
| `f1` - `f24` | Function keys F1 through F24 |

### Letter and Number Keys

| Key Name | Description |
|----------|-------------|
| `a` - `z` | Letter keys (case-insensitive) |
| `0` - `9` | Number keys |

### Special Keys

| Key Name | Aliases | Description |
|----------|---------|-------------|
| `space` | | Spacebar |
| `tab` | | Tab key |
| `enter`, `return` | | Enter/Return key |
| `esc`, `escape` | | Escape key |
| `backspace` | | Backspace key |
| `delete`, `del` | | Delete key |
| `insert`, `ins` | | Insert key |
| `home` | | Home key |
| `end` | | End key |
| `pageup`, `pgup` | | Page Up key |
| `pagedown`, `pgdn` | | Page Down key |
| `pause` | | Pause key |
| `capslock`, `caps` | | Caps Lock key |
| `numlock` | | Num Lock key |
| `scrolllock` | | Scroll Lock key |
| `printscreen`, `prtsc` | | Print Screen key |

### Arrow Keys

| Key Name | Description |
|----------|-------------|
| `left` | Left arrow |
| `up` | Up arrow |
| `right` | Right arrow |
| `down` | Down arrow |

### Numpad Keys

| Key Name | Description |
|----------|-------------|
| `numpad0` - `numpad9` | Numpad number keys |
| `multiply` | Numpad * |
| `add` | Numpad + |
| `subtract` | Numpad - |
| `decimal` | Numpad . |
| `divide` | Numpad / |

### Punctuation and Symbol Keys

| Key Name | Description |
|----------|-------------|
| `semicolon` | ; key |
| `equal`, `equals` | = key |
| `comma` | , key |
| `minus` | - key |
| `period` | . key |
| `slash` | / key |
| `backquote`, `grave` | \` key |
| `bracketleft` | [ key |
| `bracketright` | ] key |
| `backslash` | \\ key |
| `quote` | ' key |

## Limitations

### No Multi-Key Combos

YASB only supports **modifier + single key** combinations. You cannot bind multiple non-modifier keys together:

| Configuration | Valid |
|--------------|-------|
| `"alt+a"` | Yes |
| `"ctrl+shift+f1"` | Yes |
| `"a+b"` | No - two non-modifier keys |
| `"f13+h"` | No - two non-modifier keys |

### Windows Key Limitations

Windows Explorer pre-registers many `Win+key` shortcuts (e.g., `Win+S`, `Win+W`, `Win+Shift+S`). `RegisterHotKey` cannot override these - the registration will silently fail. Use `Alt`, `Ctrl`, or `Ctrl+Shift` based combinations instead for reliable hotkeys.

### Modifier-Only Hotkeys Not Supported

You cannot use a modifier key alone as a hotkey:

| Configuration | Valid |
|--------------|-------|
| `"ctrl"` | No - no main key |
| `"alt+shift"` | No - no main key |
| `"win+a"` | Yes |

### Extra Modifiers Don't Block

Unlike a low-level hook, `RegisterHotKey` does **not** reject extra modifiers. If you register `alt+x`, pressing `ctrl+alt+x` **will also trigger it**. Keep this in mind when choosing key combinations.

## Available Actions

Each widget has its own set of available callback actions. Common actions include:

| Action | Description |
|--------|-------------|
| `toggle_label` | Toggle between primary and alternate label |
| `toggle_menu` | Show/hide the widget's menu |
| `update_label` | Force refresh the widget label |
| `do_nothing` | No action (useful for disabling) |

Refer to individual widget documentation for widget-specific actions. For example, the Clock widget supports:
- `toggle_calendar` - Show/hide calendar popup
- `toggle_label` - Toggle between label formats
- `next_timezone` - Cycle to next timezone
- `context_menu` - Show context menu

## Screen Targeting

When a hotkey is triggered, YASB determines which screen's widget should respond based on:
1. The currently focused window's screen
2. If no window is focused, falls back to the primary screen

This means pressing `win+c` will toggle the calendar on the monitor where you're currently working.

## Conflict Handling

If the same key combination is assigned to multiple widgets, YASB will:
1. Log a warning message indicating the conflict
2. Use the **last** defined keybinding (later widgets override earlier ones)

```
WARNING: Hotkey conflict: 'win+c' is already assigned to 'yasb.clock.ClockWidget',
overriding with 'yasb.volume.VolumeWidget'
```

If another application has already registered the same hotkey with Windows, YASB will log a warning and that hotkey will not work.

To avoid conflicts, use unique key combinations for each widget action.

## Troubleshooting

### Hotkey Not Working

1. **Check the logs**: Enable debug logging to see if the hotkey was registered successfully
2. **Verify key names**: Ensure you're using supported key names from the tables above
3. **Check for conflicts**: Another application may have registered the same combination - `RegisterHotKey` is first-come-first-served
4. **Reserved Windows combos**: `Win+L` (lock screen) and `Ctrl+Alt+Delete` cannot be overridden

### Hotkey Registered but Not Responding

If the log shows the hotkey was registered successfully but it doesn't trigger:
- Ensure the widget has the corresponding action callback
- Check that the widget's `keybindings` config matches the expected action name
