# Frequently Asked Questions

## Installation Issues

### Q: Why aren't the icons showing up correctly?
**A:** This usually happens because:
- Required Nerd Fonts are not installed or other font defined in styles.css
- Recommended [JetBrainsMono Nerd Font](https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.zip)
- Restart YASB after font installation

### Q: Why doesn't the blur effect work?
**A:** Check these points:
- Windows 10/11 transparency effects are enabled in system settings
- The `blur_effect` is enabled in config.yaml
- Your GPU drivers are updated
- Windows composition is enabled

## Configuration Issues

### Q: Where are the configuration files located?
**A:** Default location: `C:/Users/{username}/.config/yasb/`
Required files:
- `config.yaml` - Main configuration
- `styles.css` - Visual styling

### Q: How to set custom configuration directory?
**A:** Set the `YASB_CONFIG_HOME` environment variable to the desired directory path.

### Q: YASB crashes after updating?
**A:** After updates:
- Check release notes for breaking changes
- Compare your config with the latest example config
- Backup your configs before updating

### Q: How to reset YASB settings?
**A:** Delete the `config.yaml` and `styles.css` files in the config directory. YASB will create new default files on the next run.

### Q: How to change the bar position?
**A:** Modify the `position` value in `config.yaml`:
- `top` - Top of the screen
- `bottom` - Bottom of the screen

### Q: How to check for updates?
**A:** Run `yasbc update` in the terminal to check for updates.

### Q: How to change the bar size?
**A:** Adjust the bar `width` and `height` value in `config.yaml` to change the bar size.

### Q: How to check logs for errors?
**A:** Check the `yasb.log` file in the config directory for errors, or run `yasbc logs` in the terminal.


## Widget Issues

### Q: Weather widget not working?
**A:** Verify:
- Valid API key from [weatherapi.com](https://www.weatherapi.com)
- Correct `api_key` and `location` in settings
- Active internet connection

### Q: Missing applications in Taskbar widget?
**A:** Note:
- Only shows running applications with visible windows
- Check filter settings in `config.yaml`

## Performance Issues

### Q: High CPU usage?
**A:** Common causes:
- Low `update_interval` values
- Too many real-time widgets

### Q: Delayed startup?
**A:** Solutions:
- Use `yasbc enable-autostart --task` to create a scheduled task for YASB
- Check startup programs for conflicts

## Styling Issues

### Q: How to customize appearance?
**A:** Edit `styles.css`:
```css
.yasb-bar { /* Main bar */ }
.widget { /* All widgets */ }
.clock-widget { /* Specific widget */ }
```

### Q: CSS not working?
**A:** Limitations:
- Basic CSS properties supported
- No advanced CSS3 features
- Check syntax in styles.css
- Restart YASB after changes


## Getting Help

- Check the [Wiki](https://github.com/amnweb/yasb/wiki)
- Join [Discord](https://discord.gg/qkeunvBFgX)
- Open an [issue](https://github.com/amnweb/yasb/issues)