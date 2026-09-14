from typing import Literal

from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class DeepSeekUsageCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_menu"
    on_middle: str = "refresh"
    on_right: str = "toggle_label"


class DeepSeekUsageMenuConfig(CustomBaseModel):
    # Path to an image shown at the left of the popup header. The mark already identifies
    # the widget on the bar, so repeating it here lets a pinned or detached popup say what it
    # belongs to on its own. Blank leaves the header as it was.
    icon: str = ""
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: Literal["up", "down"] = "down"
    offset_top: int = 6
    offset_left: int = 0
    show_breakdown: bool = True
    pin_icon: str = ""
    unpin_icon: str = ""


class DeepSeekSpendHistoryConfig(CustomBaseModel):
    enabled: bool = True
    default_period: Literal["today", "week", "month", "year"] = "today"
    show_graph: bool = True
    show_graph_grid: bool = False
    week_starts_on: Literal["monday", "sunday"] = "monday"
    # DeepSeek spends granted (free) credit before topped-up credit, so a granted
    # balance falling looks identical to one expiring. False counts only money
    # actually paid, which makes the ledger immune to an expiring grant.
    count_granted_as_spend: bool = True


class DeepSeekBudgetConfig(CustomBaseModel):
    enabled: bool = False
    amount: float = Field(default=0.0, ge=0.0)
    period: Literal["today", "week", "month", "year"] = "month"


class DeepSeekUsageConfig(CustomBaseModel):
    label: str = "DeepSeek {balance}"
    label_alt: str = "DeepSeek {today_spend} today"
    # "env" reads YASB_DEEPSEEK_API_KEY, then DEEPSEEK_API_KEY. A literal key works
    # too, but puts a secret in a file that is often committed to dotfiles.
    api_key: str = "env"
    currency: Literal["auto", "CNY", "USD"] = "auto"
    currency_symbol: str = ""  # blank derives one from the currency (CNY -> ¥, USD -> $)
    decimal_places: int = Field(default=2, ge=0, le=6)
    update_interval: int = Field(default=60, ge=30, le=3600)
    cache_ttl: int = Field(default=120, ge=0, le=3600)
    low_balance_threshold: float = Field(default=0.0, ge=0.0)
    # DeepSeek's API returns no account identity, so unlike the Claude and Codex widgets
    # there is no e-mail to read. Set account_label to whatever names the account to you;
    # left blank, the header falls back to a masked fingerprint of the key in use.
    show_account: bool = True
    account_label: str = ""
    spend_history: DeepSeekSpendHistoryConfig = DeepSeekSpendHistoryConfig()
    budget: DeepSeekBudgetConfig = DeepSeekBudgetConfig()
    low_icon: str = ""  # nf-fa-warning, shown via {low}
    stale_icon: str = ""
    tooltip: bool = True
    callbacks: DeepSeekUsageCallbacksConfig = DeepSeekUsageCallbacksConfig()
    menu: DeepSeekUsageMenuConfig = DeepSeekUsageMenuConfig()
    keybindings: list[KeybindingConfig] = []
