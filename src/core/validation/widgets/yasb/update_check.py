from pydantic import Field

from core.validation.widgets.base_model import CustomBaseModel, ShadowConfig


class UpdateConfig(CustomBaseModel):
    enabled: bool = False
    label: str = "{count}"
    tooltip: bool = True
    exclude: list[str] = []


class WindowsUpdateConfig(UpdateConfig):
    interval: int = Field(default=1440, ge=30, le=10080)


class WingetUpdateConfig(UpdateConfig):
    interval: int = Field(default=240, ge=10, le=10080)


class ScoopUpdateConfig(UpdateConfig):
    interval: int = Field(default=240, ge=10, le=10080)


class UpdateCheckWidgetConfig(CustomBaseModel):
    windows_update: WindowsUpdateConfig = WindowsUpdateConfig()
    winget_update: WingetUpdateConfig = WingetUpdateConfig()
    scoop_update: ScoopUpdateConfig = ScoopUpdateConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
