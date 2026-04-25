from core.validation.widgets.base_model import CustomBaseModel


class AppConfig(CustomBaseModel):
    icon: str
    launch: str
    name: str | None = None


class ApplicationsWidgetConfig(CustomBaseModel):
    label: str
    class_name: str = ""
    image_icon_size: int = 14
    app_list: list[AppConfig]

    tooltip: bool = True
