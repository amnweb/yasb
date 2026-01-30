from core.validation.widgets.base_model import AnimationConfig, CustomBaseModel, PaddingConfig, ShadowConfig


class AppConfig(CustomBaseModel):
    icon: str
    launch: str
    name: str | None = None


class ApplicationsWidgetConfig(CustomBaseModel):
    label: str
    class_name: str = ""
    image_icon_size: int = 14
    app_list: list[AppConfig]
    animation: AnimationConfig = AnimationConfig()
    tooltip: bool = True
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    container_padding: PaddingConfig = PaddingConfig()
