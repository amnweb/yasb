import logging
import os
import threading
import time
import urllib.error

from core.utils.shell_utils import shell_open
from core.utils.utilities import get_relative_time
from core.utils.widgets.github.api import GitHubDataManager
from core.utils.widgets.quick_launch.base_provider import (
    BaseProvider,
    ProviderMenuAction,
    ProviderMenuActionResult,
    ProviderResult,
)
from core.utils.widgets.quick_launch.providers.resources.icons import (
    GITHUB_CHECKSUITE,
    GITHUB_DEFAULT,
    GITHUB_DISCUSSION,
    GITHUB_ISSUE_CLOSED,
    GITHUB_ISSUE_OPEN,
    GITHUB_PR_CLOSED,
    GITHUB_PR_DRAFT,
    GITHUB_PR_MERGED,
    GITHUB_PR_OPEN,
    GITHUB_RELEASE,
    ICON_GITHUB,
)

_REASON_LABELS: dict[str, str] = {
    "assign": "Assigned",
    "author": "Author",
    "comment": "Comment",
    "ci_activity": "CI Activity",
    "invitation": "Invitation",
    "manual": "Manual",
    "mention": "Mentioned",
    "review_requested": "Review requested",
    "security_alert": "Security alert",
    "state_change": "State change",
    "subscribed": "Subscribed",
    "team_mention": "Team mention",
    "approval_requested": "Approval requested",
}


def _resolve_icon(notification: dict) -> str:
    """Pick the right colored SVG icon for a notification."""
    ntype = notification.get("type", "")
    if ntype == "Issue":
        state = (notification.get("issue_state") or "").lower()
        return GITHUB_ISSUE_CLOSED if state == "closed" else GITHUB_ISSUE_OPEN
    elif ntype == "PullRequest":
        if notification.get("pull_request_is_merged"):
            return GITHUB_PR_MERGED
        pr_state = (notification.get("pull_request_state") or "").lower()
        if pr_state == "closed":
            return GITHUB_PR_CLOSED
        if notification.get("pull_request_is_draft"):
            return GITHUB_PR_DRAFT
        return GITHUB_PR_OPEN
    elif ntype == "Discussion":
        return GITHUB_DISCUSSION
    elif ntype == "Release":
        return GITHUB_RELEASE
    elif ntype == "CheckSuite":
        return GITHUB_CHECKSUITE
    return GITHUB_DEFAULT


class GithubNotificationsProvider(BaseProvider):
    """Browse GitHub notifications.

    Activate with the prefix (default ``gh``).
    Shows notifications grouped by unread/read status.
    Clicking opens in browser and marks as read.
    """

    name = "github_notifications"
    display_name = "GitHub"
    icon = ICON_GITHUB
    input_placeholder = "GitHub Notifications"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        token_cfg = self.config.get("token", "env")
        self._token: str = os.getenv("YASB_GITHUB_TOKEN", "") if token_cfg == "env" else token_cfg

        # Local cache — uses GitHubDataManager for all API calls but keeps its own
        # data copy.  None means "never fetched yet"; empty list means
        # "fetched but nothing came back (or error)".
        self._cached_data: list[dict] | None = None
        self._fetching = False
        self._fetch_error: str | None = None
        self._cache_time: float = 0
        self._cache_ttl: float = 60  # Keep cache for 60 seconds after popup closes

    def on_deactivate(self) -> None:
        """Record deactivation time; cache stays valid for ``_cache_ttl`` seconds."""
        self._cache_time = time.monotonic()

    def _fetch_in_background(self):
        """Fetch notifications via GitHubDataManager in a background thread."""

        def _do_fetch():
            try:
                data = GitHubDataManager.fetch_all_notifications(self._token)
                self._cached_data = data
                self._fetch_error = None
                # Refresh bar widget so it picks up the latest data (only if there are unread items)
                if self._token and self._token == GitHubDataManager._token:
                    if any(n.get("unread") for n in data):
                        GitHubDataManager.refresh()
            except urllib.error.HTTPError as e:
                self._cached_data = []
                self._fetch_error = f"HTTP {e.code}: {e.reason}"
                logging.error(f"GitHub notifications provider: HTTP error: {e.code} - {e.reason}")
            except urllib.error.URLError:
                self._cached_data = []
                self._fetch_error = "No internet connection"
                logging.error("GitHub notifications provider: no internet connection.")
            except Exception as e:
                self._cached_data = []
                self._fetch_error = str(e)
                logging.error(f"GitHub notifications provider: {e}")
            finally:
                self._fetching = False
                if self.request_refresh:
                    try:
                        self.request_refresh()
                    except Exception:
                        pass

        self._fetching = True
        threading.Thread(target=_do_fetch, daemon=True).start()

    def match(self, text: str) -> bool:
        if self.prefix:
            stripped = text.strip()
            return stripped == self.prefix or stripped.startswith(self.prefix + " ")
        return True

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        if not self._token:
            return [
                ProviderResult(
                    title="GitHub token not configured",
                    description="Set YASB_GITHUB_TOKEN env variable or add token in config",
                    icon_char=ICON_GITHUB,
                    provider=self.name,
                )
            ]

        # Invalidate stale cache
        if (
            self._cached_data is not None
            and self._cache_time
            and (time.monotonic() - self._cache_time) > self._cache_ttl
        ):
            self._cached_data = None
            self._fetch_error = None

        # Fetch fresh data when cache is empty (first call or after popup was closed)
        if self._cached_data is None:
            if not self._fetching:
                self._fetch_in_background()
            return [
                ProviderResult(
                    title="Fetching notifications...",
                    description="Loading from GitHub",
                    icon_char=ICON_GITHUB,
                    provider=self.name,
                    is_loading=True,
                )
            ]

        # Show error if the last fetch failed and returned no data
        if self._fetch_error and not self._cached_data:
            return [
                ProviderResult(
                    title="Failed to fetch notifications",
                    description=self._fetch_error,
                    icon_char=ICON_GITHUB,
                    provider=self.name,
                )
            ]

        notifications = self._cached_data or []
        query = self.get_query_text(text).strip().lower()

        # Filter by query if user typed something after prefix
        if query:
            notifications = [
                n
                for n in notifications
                if query in n.get("title", "").lower()
                or query in n.get("repository", "").lower()
                or query in n.get("type", "").lower()
                or query in n.get("reason", "").lower()
            ]

        # Split into unread and read, sorted by most recent first
        unread = sorted(
            [n for n in notifications if n.get("unread")], key=lambda n: n.get("updated_at", ""), reverse=True
        )
        read = sorted(
            [n for n in notifications if not n.get("unread")], key=lambda n: n.get("updated_at", ""), reverse=True
        )

        results: list[ProviderResult] = []

        if unread:
            results.append(
                ProviderResult(
                    title="Unread",
                    provider=self.name,
                    is_separator=True,
                )
            )
            for n in unread:
                results.append(self._notification_to_result(n))

        if read:
            # Only show the "Read" separator when there are also unread items
            if unread:
                results.append(
                    ProviderResult(
                        title="Read",
                        provider=self.name,
                        is_separator=True,
                    )
                )
            for n in read:
                results.append(self._notification_to_result(n))

        if not results:
            return [
                ProviderResult(
                    title="No notifications",
                    description="You're all caught up!",
                    icon_char=ICON_GITHUB,
                    provider=self.name,
                )
            ]

        return results

    def execute(self, result: ProviderResult) -> bool | None:
        data = result.action_data
        url = data.get("url", "")
        notification_id = data.get("notification_id", "")

        if url:
            shell_open(url)

        # Mark as read via GitHub API and sync bar widget if same token
        if notification_id and data.get("unread"):
            # Update local cache immediately so UI reflects the change
            if self._cached_data:
                for n in self._cached_data:
                    if n["id"] == notification_id:
                        n["unread"] = False
                        break
            GitHubDataManager.mark_as_read(notification_id, token=self._token)

        return True

    def get_context_menu_actions(self, result: ProviderResult) -> list[ProviderMenuAction]:
        data = result.action_data
        actions: list[ProviderMenuAction] = []
        if data.get("url"):
            actions.append(ProviderMenuAction(id="copy_url", label="Copy URL"))
        if data.get("unread"):
            actions.append(ProviderMenuAction(id="mark_read", label="Mark as read"))
        actions.append(ProviderMenuAction(id="mark_all_read", label="Mark all as read", separator_before=True))
        actions.append(ProviderMenuAction(id="refresh", label="Refresh"))
        return actions

    def execute_context_menu_action(self, action_id: str, result: ProviderResult) -> ProviderMenuActionResult:
        data = result.action_data

        if action_id == "copy_url":
            url = data.get("url", "")
            if url:
                from PyQt6.QtWidgets import QApplication

                clipboard = QApplication.clipboard()
                if clipboard:
                    clipboard.setText(url)
            return ProviderMenuActionResult()

        if action_id == "mark_read":
            nid = data.get("notification_id", "")
            if nid:
                if self._cached_data:
                    for n in self._cached_data:
                        if n["id"] == nid:
                            n["unread"] = False
                            break
                GitHubDataManager.mark_as_read(nid, token=self._token)
            return ProviderMenuActionResult(refresh_results=True)

        if action_id == "mark_all_read":
            if self._cached_data:
                for n in self._cached_data:
                    n["unread"] = False
            GitHubDataManager.mark_all_as_read(self._token)
            return ProviderMenuActionResult(refresh_results=True)

        if action_id == "refresh":
            self._cached_data = None
            self._fetch_error = None
            self._cache_time = 0
            return ProviderMenuActionResult(refresh_results=True)

        return ProviderMenuActionResult()

    def get_query_text(self, text: str) -> str:
        if self.prefix and text.strip().startswith(self.prefix):
            return text.strip()[len(self.prefix) :].strip()
        return text.strip()

    def _notification_to_result(self, notification: dict) -> ProviderResult:
        """Convert a GitHub notification dict to a ProviderResult."""
        title = notification.get("title", "")
        repo = notification.get("repository", "")
        reason = _REASON_LABELS.get(notification.get("reason", ""), notification.get("reason", ""))
        updated_at = notification.get("updated_at", "")
        short_time = get_relative_time(updated_at, short=True)
        ntype = notification.get("type", "")

        # Build description: #number · repo · Reason   time
        desc_parts: list[str] = []
        # Try to extract number from URL
        url = notification.get("url", "")
        number = ""
        if url:
            # URLs like https://github.com/user/repo/pull/123
            parts = url.rstrip("/").split("/")
            if parts and parts[-1].isdigit():
                number = f"#{parts[-1]}"

        if number:
            desc_parts.append(number)
        if repo:
            desc_parts.append(repo)
        if reason:
            desc_parts.append(reason)
        desc = " · ".join(desc_parts)
        if short_time:
            desc = f"{desc}  {short_time}" if desc else short_time

        icon_svg = _resolve_icon(notification)

        return ProviderResult(
            title=f"{ntype}: {title}" if ntype else title,
            description=desc,
            icon_char=icon_svg,
            provider=self.name,
            action_data={
                "url": notification.get("url", ""),
                "notification_id": notification.get("id", ""),
                "unread": notification.get("unread", False),
            },
        )
