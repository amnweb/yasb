from pydantic import BaseModel, ConfigDict


class CustomBaseModel(BaseModel):
    # This is required to prohibit extra fields in the config
    model_config = ConfigDict(extra="forbid", validate_default=True)


class ShadowConfig(CustomBaseModel):
    enabled: bool = False
    color: str = "black"
    offset: list[int] = [1, 1]
    radius: int = 3


class AnimationConfig(CustomBaseModel):
    enabled: bool = True
    type: str = "fadeInOut"
    duration: int = 200


class CallbacksConfig(CustomBaseModel):
    on_left: str = "do_nothing"
    on_middle: str = "do_nothing"
    on_right: str = "do_nothing"


class KeybindingConfig(CustomBaseModel):
    keys: str
    action: str


class PaddingConfig(CustomBaseModel):
    top: int = 0
    left: int = 0
    bottom: int = 0
    right: int = 0
