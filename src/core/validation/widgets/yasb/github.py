from enum import StrEnum

from pydantic import Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class Corner(StrEnum):
    """Enum for notification dot position corners."""

    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class NotificationDotConfig(CustomBaseModel):
    enabled: bool = True
    corner: Corner = Corner.BOTTOM_LEFT
    color: str = "red"
    margin: list[int] = [1, 1]


class GithubMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    show_categories: bool = False
    categories_order: list[str] = [
        "PullRequest",
        "Issue",
        "CheckSuite",
        "Release",
        "Discussion",
    ]


class GithubIconsConfig(CustomBaseModel):
    issue: str = "\uf41b"
    issue_closed: str = "\uf41d"
    pull_request: str = "\uea64"
    pull_request_closed: str = "\uebda"
    pull_request_merged: str = "\uf17f"
    pull_request_draft: str = "\uebdb"
    release: str = "\uea84"
    discussion: str = "\uf442"
    discussion_answered: str = "\uf4c0"
    checksuite: str = "\uf418"
    default: str = "\uea84"
    github_logo: str = "\uea84"
    comment: str = "\uf41f"


class GithubConfig(CustomBaseModel):
    label: str = "{icon}"
    label_alt: str = "{data} Notifications"
    update_interval: int = Field(default=600, ge=60, le=3600)
    token: str = ""
    tooltip: bool = True
    max_notification: int = 30
    only_unread: bool = False
    show_comment_count: bool = False
    max_field_size: int = 100
    reason_filters: list[str] = []
    notification_dot: NotificationDotConfig = NotificationDotConfig()
    menu: GithubMenuConfig = GithubMenuConfig()
    icons: GithubIconsConfig = GithubIconsConfig()
    animation: AnimationConfig = AnimationConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    container_padding: PaddingConfig = PaddingConfig()
    keybindings: list[KeybindingConfig] = []
