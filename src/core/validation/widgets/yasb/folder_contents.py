from core.validation.widgets.base_model import CustomBaseModel


class FolderContentsConfig(CustomBaseModel):
    path: str = r"C:\Temp"
