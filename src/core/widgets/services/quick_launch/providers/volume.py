"""Volume control provider for Quick Launch."""

import logging
import re

from core.widgets.services.quick_launch.base_provider import BaseProvider, ProviderResult
from core.widgets.services.quick_launch.providers.resources.icons import ICON_VOLUME, ICON_VOLUME_DOWN, ICON_VOLUME_UP
from core.widgets.services.volume.service import AudioOutputService


class VolumeProvider(BaseProvider):
    """Control system volume via Quick Launch commands."""

    name = "volume"
    display_name = "Volume"
    input_placeholder = "Volume: up, down, mute, or a number..."
    icon = ICON_VOLUME

    # Pattern: optional sign + digits
    _NUM_RE = re.compile(r"^[+-]?\d+$")

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.step: int = self.config.get("step", 5)
        self._service = AudioOutputService()

    # ── Audio helpers (delegate to AudioOutputService) ─────────────────

    def _get_volume(self) -> tuple[int | None, bool]:
        """Return (volume_percent, is_muted) or (None, False) on failure."""
        volume = self._service.get_volume_interface()
        if volume is None:
            return None, False
        try:
            level = volume.GetMasterVolumeLevelScalar()
            muted = volume.GetMute() != 0
            return round(level * 100), muted
        except Exception as e:
            logging.debug("Failed to read volume: %s", e)
            return None, False

    def _set_volume(self, percent: int) -> bool:
        """Set volume to percent (0-100). Returns True on success."""
        volume = self._service.get_volume_interface()
        if volume is None:
            return False
        try:
            current = volume.GetMute()
            if current:
                volume.SetMute(not current, None)
            clamped = max(0, min(100, percent))
            volume.SetMasterVolumeLevelScalar(clamped / 100, None)
            return True
        except Exception as e:
            logging.error("Failed to set volume: %s", e)
            return False

    def _toggle_mute(self) -> bool | None:
        """Toggle mute. Returns new mute state or None on failure."""
        volume = self._service.get_volume_interface()
        if volume is None:
            return None
        try:
            current = volume.GetMute()
            volume.SetMute(not current, None)
            return not current
        except Exception as e:
            logging.error("Failed to toggle mute: %s", e)
            return None

    def _set_mute(self, muted: bool) -> bool:
        """Set mute state. Returns True on success."""
        volume = self._service.get_volume_interface()
        if volume is None:
            return False
        try:
            volume.SetMute(muted, None)
            return True
        except Exception as e:
            logging.error("Failed to set mute: %s", e)
            return False

    # ── Provider interface ─────────────────────────────────────────────

    def match(self, text: str) -> bool:
        text = text.strip()
        if self.prefix and text.startswith(self.prefix + " "):
            return True
        if self.prefix and text == self.prefix:
            return True
        return False

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text).strip().lower()

        # No query: show interactive menu
        if not query:
            return self._show_menu()

        # Parse command
        parts = query.split(None, 1)
        cmd = parts[0] if parts else ""

        if cmd == "up":
            return self._preview_change(self.step)
        elif cmd == "down":
            return self._preview_change(-self.step)
        elif cmd == "mute":
            return self._preview_toggle_mute()
        elif cmd == "unmute":
            return self._preview_set_mute(False)
        elif cmd == "max":
            return self._preview_set(100)
        elif cmd == "half":
            return self._preview_set(50)
        elif cmd == "min":
            return self._preview_set(0)
        elif self._NUM_RE.match(cmd):
            return self._parse_number(cmd)
        else:
            return [
                ProviderResult(
                    title=f"Unknown command: {cmd}",
                    description="Use: up, down, mute, unmute, max, min, half, or a number",
                    icon_char=ICON_VOLUME,
                    provider=self.name,
                )
            ]

    def execute(self, result: ProviderResult) -> bool | None:
        action = result.action_data.get("action")

        if action == "set":
            # Typed command (vol 50) — close popup after setting
            value = result.action_data.get("value", 0)
            self._set_volume(value)
            return True
        elif action == "up":
            # Menu button — stay open, refresh menu
            volume, _ = self._get_volume()
            if volume is not None:
                self._set_volume(volume + self.step)
            return False
        elif action == "down":
            # Menu button — stay open, refresh menu
            volume, _ = self._get_volume()
            if volume is not None:
                self._set_volume(volume - self.step)
            return False
        elif action == "toggle_mute":
            # Menu button — stay open, refresh menu
            self._toggle_mute()
            return False
        elif action == "unmute":
            # Menu button — stay open, refresh menu
            self._set_mute(False)
            return False
        elif action == "select_device":
            # Menu button — stay open, refresh menu
            device_id = result.action_data.get("device_id")
            if device_id:
                self._service.set_default_device(device_id)
            return False
        elif action == "refresh_menu":
            return False
        return True

    def _show_menu(self) -> list[ProviderResult]:
        """Show interactive volume control menu."""
        results: list[ProviderResult] = []

        # Current volume status
        volume, muted = self._get_volume()
        if volume is None:
            results.append(
                ProviderResult(
                    title="No audio device",
                    description="Could not detect audio output device",
                    icon_char=ICON_VOLUME,
                    provider=self.name,
                )
            )
            return results

        # Status header
        if muted:
            status_title = "Volume: Muted"
            status_desc = "Press Enter to unmute"
            mute_action = "unmute"
        else:
            status_title = f"Volume: {volume}%"
            status_desc = "Press Enter to mute"
            mute_action = "toggle_mute"

        results.append(
            ProviderResult(
                title=status_title,
                description=status_desc,
                icon_char=ICON_VOLUME,
                provider=self.name,
                action_data={"action": mute_action},
            )
        )

        # Volume Up button
        results.append(
            ProviderResult(
                title="Volume Up",
                description=f"+{self.step}% (to {min(100, volume + self.step)}%)",
                icon_char=ICON_VOLUME_UP,
                provider=self.name,
                action_data={"action": "up"},
            )
        )

        # Volume Down button
        results.append(
            ProviderResult(
                title="Volume Down",
                description=f"-{self.step}% (to {max(0, volume - self.step)}%)",
                icon_char=ICON_VOLUME_DOWN,
                provider=self.name,
                action_data={"action": "down"},
            )
        )

        # Mute/Unmute button
        if muted:
            results.append(
                ProviderResult(
                    title="Unmute",
                    description="Restore audio output",
                    icon_char="",
                    provider=self.name,
                    action_data={"action": "unmute"},
                )
            )
        else:
            results.append(
                ProviderResult(
                    title="Mute",
                    description="Silence audio output",
                    icon_char="",
                    provider=self.name,
                    action_data={"action": "toggle_mute"},
                )
            )

        # Separator before devices
        results.append(
            ProviderResult(
                title="Output Device",
                description="",
                icon_char="",
                provider=self.name,
                is_separator=True,
            )
        )

        # Device selection
        devices = self._service.get_all_devices()
        default_id = self._service.get_default_device_id()

        if not devices:
            results.append(
                ProviderResult(
                    title="No devices found",
                    description="No audio output devices available",
                    icon_char="",
                    provider=self.name,
                )
            )
        else:
            for device_id, device_name in devices:
                is_current = device_id == default_id
                results.append(
                    ProviderResult(
                        title=f"{'● ' if is_current else '  '}{device_name}",
                        description="Current device" if is_current else "Click to select",
                        icon_char="",
                        provider=self.name,
                        action_data={
                            "action": "select_device",
                            "device_id": device_id,
                        },
                    )
                )

        return results

    def _preview_change(self, delta: int) -> list[ProviderResult]:
        """Preview volume change without actually changing it."""
        volume, muted = self._get_volume()
        if volume is None:
            return [
                ProviderResult(
                    title="No audio device",
                    description="Could not detect audio output device",
                    icon_char=ICON_VOLUME,
                    provider=self.name,
                )
            ]
        new_volume = max(0, min(100, volume + delta))
        if muted:
            title = "Volume: Muted"
            desc = f"Will set to {new_volume}% and unmute"
        else:
            title = f"Volume: {new_volume}%"
            desc = f"Changed from {volume}% by {delta:+d}%"
        return [
            ProviderResult(
                title=title,
                description=desc,
                icon_char=ICON_VOLUME,
                provider=self.name,
                action_data={"action": "set", "value": new_volume},
            )
        ]

    def _preview_toggle_mute(self) -> list[ProviderResult]:
        """Preview mute toggle without actually toggling."""
        volume, muted = self._get_volume()
        if volume is None:
            return [
                ProviderResult(
                    title="No audio device",
                    description="Could not detect audio output device",
                    icon_char=ICON_VOLUME,
                    provider=self.name,
                )
            ]
        if muted:
            title = "Volume: Muted"
            desc = "Press Enter to unmute"
            action = "unmute"
        else:
            title = f"Volume: {volume}%"
            desc = "Press Enter to mute"
            action = "toggle_mute"
        return [
            ProviderResult(
                title=title,
                description=desc,
                icon_char=ICON_VOLUME,
                provider=self.name,
                action_data={"action": action},
            )
        ]

    def _preview_set_mute(self, muted: bool) -> list[ProviderResult]:
        """Preview set mute without actually setting it."""
        volume, current_mute = self._get_volume()
        if volume is None:
            return [
                ProviderResult(
                    title="No audio device",
                    description="Could not detect audio output device",
                    icon_char=ICON_VOLUME,
                    provider=self.name,
                )
            ]
        if muted:
            title = "Volume: Muted"
            desc = "Press Enter to unmute"
            action = "unmute"
        else:
            title = f"Volume: {volume}%"
            desc = "Press Enter to mute"
            action = "toggle_mute"
        return [
            ProviderResult(
                title=title,
                description=desc,
                icon_char=ICON_VOLUME,
                provider=self.name,
                action_data={"action": action},
            )
        ]

    def _preview_set(self, value: int) -> list[ProviderResult]:
        """Preview set volume without actually setting it."""
        volume, muted = self._get_volume()
        if volume is None:
            return [
                ProviderResult(
                    title="No audio device",
                    description="Could not detect audio output device",
                    icon_char=ICON_VOLUME,
                    provider=self.name,
                )
            ]
        if muted:
            title = "Volume: Muted"
            desc = f"Press Enter to set to {value}% and unmute"
        else:
            title = f"Volume: {value}%"
            desc = f"Press Enter to set to {value}%"
        return [
            ProviderResult(
                title=title,
                description=desc,
                icon_char=ICON_VOLUME,
                provider=self.name,
                action_data={"action": "set", "value": value},
            )
        ]

    def _parse_number(self, text: str) -> list[ProviderResult]:
        """Parse +/-N or absolute number as preview."""
        try:
            value = int(text)
        except ValueError:
            return [
                ProviderResult(
                    title=f"Invalid number: {text}",
                    description="Use a value between 0 and 100",
                    icon_char=ICON_VOLUME,
                    provider=self.name,
                )
            ]

        # Handle relative changes
        if text.startswith("+") or text.startswith("-"):
            volume, muted = self._get_volume()
            if volume is None:
                return [
                    ProviderResult(
                        title="No audio device",
                        description="Could not detect audio output device",
                        icon_char=ICON_VOLUME,
                        provider=self.name,
                    )
                ]
            new_volume = max(0, min(100, volume + value))
            if muted:
                title = "Volume: Muted"
                desc = f"Will set to {new_volume}% and unmute"
            else:
                title = f"Volume: {new_volume}%"
                desc = f"Changed from {volume}% by {value:+d}%"
            return [
                ProviderResult(
                    title=title,
                    description=desc,
                    icon_char=ICON_VOLUME,
                    provider=self.name,
                    action_data={"action": "set", "value": new_volume},
                )
            ]
        else:
            # Absolute value
            if value < 0 or value > 100:
                return [
                    ProviderResult(
                        title=f"Invalid volume: {value}",
                        description="Use a value between 0 and 100",
                        icon_char=ICON_VOLUME,
                        provider=self.name,
                    )
                ]
            return self._preview_set(value)
