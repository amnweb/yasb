from typing import Literal

from core.validation.widgets.base_model import CustomBaseModel


class RewriteConfig(CustomBaseModel):
    pattern: str
    replacement: str
    case: Literal["lower", "upper", "title", "capitalize"] | None = None


class StackConfig(CustomBaseModel):
    label_offline: str = "Komorebi Offline"
    label_window: str = "{title}"
    label_window_active: str = "{title}"
    label_no_window: str = ""
    label_zero_index: bool = False
    hide_if_offline: bool = False
    show_icons: Literal["focused", "always", "never"] = "never"
    icon_size: int = 16
    show_only_stack: bool = False
    max_length: int | None = None
    max_length_active: int | None = None
    max_length_overall: int | None = None
    max_length_ellipsis: str = "..."
    rewrite: list[RewriteConfig] = []
    enable_scroll_switching: bool = False
    reverse_scroll_direction: bool = False
