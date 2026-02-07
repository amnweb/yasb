from typing import Any

from pydantic import BaseModel, PrivateAttr, model_validator


class PreserveOrderMixin(BaseModel):
    """Mixin that can be added (first) to a Model to preserve dictionary order from the original data"""

    _input_order: list[str] = PrivateAttr(default_factory=list)

    @model_validator(mode="wrap")
    @classmethod
    def _preserve_input_order(cls, data: Any, handler: Any) -> Any:
        detected_order = list(data.keys()) if isinstance(data, dict) else []  # type: ignore
        instance = handler(data)
        if detected_order and isinstance(instance, cls):
            instance._input_order = detected_order
        return instance

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        result = super().model_dump(**kwargs)
        if self._input_order:
            return {k: result[k] for k in self._input_order if k in result}
        return result
