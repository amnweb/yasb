from types import SimpleNamespace
from typing import Any


class FakeVolume:
    """Stands in for pycaw's IAudioEndpointVolume and ISimpleAudioVolume."""

    def __init__(self, level: float, muted: bool = False) -> None:
        self.level = level
        self.muted = muted

    def GetMasterVolumeLevelScalar(self) -> float:
        return self.level

    def SetMasterVolumeLevelScalar(self, level: float, _context: Any) -> None:
        self.level = level

    def GetMasterVolume(self) -> float:
        return self.level

    def SetMasterVolume(self, level: float, _context: Any) -> None:
        self.level = level

    def GetMute(self) -> int:
        return int(self.muted)

    def SetMute(self, muted: int, _context: Any) -> None:
        self.muted = bool(muted)


class FakeAudioService:
    """Stands in for AudioOutputService, so the tests never touch the real speakers."""

    def __init__(self) -> None:
        self.volume = FakeVolume(0.3)
        self.listeners: list[Any] = []
        self.default = "speakers"
        self.app_volume = FakeVolume(0.8)
        self.sessions: list[dict[str, Any]] = [
            {
                "name": "spotify.exe",
                "app_name": "Spotify",
                "volume_interface": self.app_volume,
                "session": None,
                "pid": 42,
            }
        ]

    def register_widget(self, widget: Any) -> None:
        self.listeners.append(widget)

    def unregister_widget(self, widget: Any) -> None:
        self.listeners.remove(widget)

    def get_volume_interface(self) -> FakeVolume:
        return self.volume

    def get_speakers(self) -> SimpleNamespace:
        return SimpleNamespace(FriendlyName="Speakers")

    def get_all_devices(self) -> list[tuple[str, str | None]]:
        return [("headphones", "Headphones"), ("speakers", "Speakers")]

    def get_default_device_id(self) -> str:
        return self.default

    def set_default_device(self, device_id: str) -> bool:
        self.default = device_id
        return True

    def get_active_audio_sessions(self, *_callbacks: Any) -> list[dict[str, Any]]:
        return self.sessions
