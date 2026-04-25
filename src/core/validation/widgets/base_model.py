from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from core.validation.deprecation import handle_deprecated_fields


class CustomBaseModel(BaseModel):
    # This is required to prohibit extra fields in the config
    model_config = ConfigDict(extra="forbid", validate_default=True)

    @model_validator(mode="before")
    @classmethod
    def _check_deprecations(cls, data: Any) -> Any:
        return handle_deprecated_fields(cls, data)


class CallbacksConfig(CustomBaseModel):
    on_left: str = "do_nothing"
    on_middle: str = "do_nothing"
    on_right: str = "do_nothing"


class KeybindingConfig(CustomBaseModel):
    keys: str
    action: str
    screen: Literal["active", "cursor", "primary"] = "active"
