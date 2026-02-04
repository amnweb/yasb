# Keybindings

YASB supports global keyboard shortcuts (hotkeys) to trigger widget actions. Keybindings are configured per-widget in the widget's `options` section. This feature uses native Windows low-level keyboard hooks and requires no third-party dependencies.

## Overview

- **Per-widget instance**: Keybindings are tied to the specific widget name in your config (e.g., `clock` vs `clock_2`)
- **Multiple keybindings**: A single widget can have multiple keybindings for different actions
- **Screen-aware**: Hotkeys trigger the widget on the currently focused screen
- **Zero overhead**: If no keybindings are defined, no hotkey listener is started

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
| `win`, `windows`, `super`, `meta` | Either Windows key (left or right) |
| `lwin`, `leftwin`, `left_win` | Left Windows key only |
| `rwin`, `rightwin`, `right_win` | Right Windows key only |
| `alt` | Either Alt key (left or right) |
| `lalt`, `leftalt`, `left_alt` | Left Alt key only |
| `ralt`, `rightalt`, `right_alt` | Right Alt key only |
| `ctrl`, `control` | Either Control key (left or right) |
| `lctrl`, `leftctrl`, `left_ctrl` | Left Control key only |
| `rctrl`, `rightctrl`, `right_ctrl` | Right Control key only |
| `shift` | Shift key |

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

## Win Key Specificity

YASB supports distinguishing between the left and right Windows keys:

| Configuration | Behavior |
|--------------|----------|
| `"win+c"` | Triggered by **either** left or right Win key + C |
| `"lwin+c"` | Triggered **only** by left Win key + C |
| `"rwin+c"` | Triggered **only** by right Win key + C |

### Example: Different Actions for Left/Right Win

```yaml
clock:
  type: "yasb.clock.ClockWidget"
  options:
    keybindings:
      - keys: "lwin+c"
        action: "toggle_calendar"
      - keys: "rwin+c"
        action: "toggle_label"
```

## Alt/Ctrl Key Specificity

Similarly, you can distinguish between left and right Alt or Ctrl keys:

| Configuration | Behavior |
|--------------|----------|
| `"alt+x"` | Triggered by **either** left or right Alt key + X |
| `"lalt+x"` | Triggered **only** by left Alt key + X |
| `"ralt+x"` | Triggered **only** by right Alt key + X |
| `"ctrl+x"` | Triggered by **either** left or right Ctrl key + X |
| `"lctrl+x"` | Triggered **only** by left Ctrl key + X |
| `"rctrl+x"` | Triggered **only** by right Ctrl key + X |

### Example: Left Alt vs Right Alt

```yaml
volume:
  type: "yasb.volume.VolumeWidget"
  options:
    keybindings:
      - keys: "lalt+v"
        action: "toggle_menu"
      - keys: "ralt+v"
        action: "toggle_mute"
```

## Extra Modifier Rejection

YASB uses **exact modifier matching**. If you register `alt+x`, pressing `ctrl+alt+x` will **not** trigger it because Ctrl is an extra modifier that wasn't specified.

| Registered | User Presses | Result |
|------------|--------------|--------|
| `alt+x` | Alt + X | Triggers |
| `alt+x` | Ctrl + Alt + X | Blocked (extra Ctrl) |
| `ctrl+alt+x` | Ctrl + Alt + X | Triggers |
| `ctrl+alt+x` | Ctrl + Alt + Shift + X | Blocked (extra Shift) |

This prevents accidental triggers when using similar hotkeys in other applications.

## Limitations

### No Multi-Key Combos

YASB only supports **modifier + single key** combinations. You cannot bind multiple non-modifier keys together:

| Configuration | Valid |
|--------------|-------|
| `"alt+a"` | Yes |
| `"ctrl+shift+f1"` | Yes |
| `"a+b"` | No - two non-modifier keys |
| `"ctrl+a+b"` | No - two non-modifier keys |

### Modifier-Only Hotkeys Not Supported

You cannot use a modifier key alone as a hotkey:

| Configuration | Valid |
|--------------|-------|
| `"ctrl"` | No - no main key |
| `"alt+shift"` | No - no main key |
| `"win+a"` | Yes |

### Press Order Matters

Hotkeys are triggered when the **main key** is pressed while modifiers are held. This means:

- Hold Alt, then press X → Triggers `alt+x`
- Hold X, then press Alt → Does NOT trigger `alt+x`

This is standard behavior for all hotkey systems (Windows `RegisterHotKey`, AutoHotkey, etc.).

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

To avoid conflicts, use unique key combinations for each widget action.

## Troubleshooting

### Hotkey Not Working

1. **Check the logs**: Enable debug logging to see if the hotkey is being registered
2. **Verify key names**: Ensure you're using supported key names from the tables above
3. **Check for conflicts**: Another application might be using the same hotkey
4. **Elevated apps**: If an elevated (admin) application has focus, hotkeys may not be captured due to Windows UIPI security. This is normal - hotkeys will work again once a non-elevated window has focus

### Hotkey Conflicts with Windows

Some key combinations are reserved by Windows and may not work:
- `win+l` (Lock screen)
- `ctrl+alt+del` (Security options)

Consider using alternative combinations or disabling the Windows shortcuts via Group Policy if needed.

### Keybinding Not in Config

If you don't define any `keybindings` in your widget options, the hotkey listener won't start at all. When keybindings are configured, the listener uses a low-level keyboard hook which has negligible overhead.
