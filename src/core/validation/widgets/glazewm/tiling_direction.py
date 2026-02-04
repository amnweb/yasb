from core.validation.widgets.base_model import CustomBaseModel, ShadowConfig


class GlazewmTilingDirectionConfig(CustomBaseModel):
    glazewm_server_uri: str = "ws://localhost:6123"
    horizontal_label: str = "\udb81\udce1"
    vertical_label: str = "\udb81\udce2"
    container_shadow: ShadowConfig = ShadowConfig()
    btn_shadow: ShadowConfig = ShadowConfig()
