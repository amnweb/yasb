import json
import logging
import threading
import urllib.error
import urllib.request
from typing import Any, Callable

from PyQt6.QtCore import QTimer


class GitHubDataManager:
    """
    Centralized manager for GitHub API data.
    """

    _shared_data: list[dict[str, Any]] = []
    _callbacks: list[Callable] = []
    _lock = threading.Lock()
    _timer: QTimer | None = None
    _timer_interval: int = 300000  # Default 5 minutes
    _token: str | None = None
    _only_unread: bool = True
    _max_notification: int = 50
    _reason_filters: list[str] | None = None
    _show_comment_count: bool = False

    @classmethod
    def initialize(
        cls,
        token: str,
        only_unread: bool = True,
        max_notification: int = 50,
        update_interval: int = 300,
        reason_filters: list[str] | None = None,
        show_comment_count: bool = False,
    ) -> None:
        """
        Initialize the manager with settings and start the timer.
        """
        if cls._timer is not None:
            return

        cls._token = token
        cls._only_unread = only_unread
        cls._max_notification = max_notification
        cls._timer_interval = update_interval * 1000
        cls._show_comment_count = show_comment_count
        if reason_filters:
            cls._reason_filters = [reason.lower() for reason in reason_filters if reason]
        else:
            cls._reason_filters = None

        # Create and start timer
        cls._timer = QTimer()
        cls._timer.setInterval(cls._timer_interval)
        cls._timer.timeout.connect(cls._on_timer)
        cls._timer.start()

        cls._on_timer()
        logging.info("GitHubDataManager started...")

    @classmethod
    def stop(cls) -> None:
        """Stop the manager's timer."""
        if cls._timer is not None:
            cls._timer.stop()
            cls._timer = None

    @classmethod
    def _on_timer(cls) -> None:
        """Called by QTimer - triggers data fetch."""
        if cls._token:
            cls.fetch_notifications(
                cls._token,
                cls._only_unread,
                cls._max_notification,
                cls._reason_filters,
                cls._show_comment_count,
            )

    @classmethod
    def refresh(cls) -> None:
        """Trigger an immediate data refresh (same as a timer tick)."""
        cls._on_timer()

    @classmethod
    def register_callback(cls, callback: Callable) -> None:
        """Register a callback to be called when data is updated."""
        with cls._lock:
            if callback not in cls._callbacks:
                cls._callbacks.append(callback)

    @classmethod
    def unregister_callback(cls, callback: Callable) -> None:
        """Unregister a callback."""
        with cls._lock:
            if callback in cls._callbacks:
                cls._callbacks.remove(callback)

    @classmethod
    def get_data(cls) -> list[dict[str, Any]]:
        """Get the current shared notification data."""
        with cls._lock:
            return cls._shared_data.copy()

    @classmethod
    def fetch_notifications(
        cls,
        token: str,
        only_unread: bool = True,
        max_notification: int = 50,
        reason_filters: list[str] | None = None,
        show_comment_count: bool = False,
    ) -> None:
        """
        Fetch notifications from GitHub API in a background thread.
        After fetching, calls all registered callbacks with the new data.
        """

        def _fetch():
            try:
                notifications = cls._get_github_notifications(
                    token,
                    only_unread,
                    max_notification,
                    reason_filters,
                    show_comment_count,
                )
                with cls._lock:
                    cls._shared_data = notifications

                # Notify all callbacks
                with cls._lock:
                    callbacks = cls._callbacks.copy()

                for callback in callbacks:
                    try:
                        callback(notifications)
                    except Exception as e:
                        logging.error(f"GitHubDataManager error calling callback: {e}")

            except Exception as e:
                logging.error(f"GitHubDataManager error fetching notifications: {e}")

        threading.Thread(target=_fetch, daemon=True).start()

    @classmethod
    def mark_as_read(cls, notification_id: str, token: str | None = None) -> None:
        """
        Mark a single notification as read.
        - Always syncs to GitHub API in a background thread.
        - Updates local shared data and notifies bar widget callbacks only
          when the given token matches the bar widget's token.
        """
        effective_token = token or cls._token

        # Update local data only if same account as bar widget
        if effective_token and effective_token == cls._token:
            with cls._lock:
                for notification in cls._shared_data:
                    if notification["id"] == notification_id:
                        notification["unread"] = False
                        break
                data_copy = cls._shared_data.copy()
                callbacks = cls._callbacks.copy()

            for callback in callbacks:
                try:
                    callback(data_copy)
                except Exception as e:
                    logging.error(f"GitHubDataManager error calling callback: {e}")

        # Sync to GitHub API in background
        if effective_token:
            threading.Thread(
                target=lambda: cls._sync_notification_read(notification_id, effective_token), daemon=True
            ).start()

    @classmethod
    def _sync_notification_read(cls, notification_id: str, token: str) -> None:
        """Sync single notification as read with GitHub API."""
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        url = f"https://api.github.com/notifications/threads/{notification_id}"
        req = urllib.request.Request(url, headers=headers, method="PATCH")
        try:
            with urllib.request.urlopen(req):
                pass
        except urllib.error.HTTPError as e:
            logging.error(f"GitHubDataManager HTTP error marking notification as read: {e.code} - {e.reason}")
        except urllib.error.URLError:
            logging.error("GitHubDataManager no internet connection. Unable to mark notification as read.")
        except Exception as e:
            logging.error(f"GitHubDataManager error marking notification as read: {e}")

    @classmethod
    def mark_all_as_read(cls, token: str) -> None:
        """
        Mark all notifications as read.
        - Always syncs to GitHub API in a background thread.
        - Updates local shared data and notifies bar widget callbacks only
          when the given token matches the bar widget's token.
        """
        # Update local data only if same account as bar widget
        if token and token == cls._token:
            with cls._lock:
                for notification in cls._shared_data:
                    notification["unread"] = False
                data_copy = cls._shared_data.copy()
                callbacks = cls._callbacks.copy()

            for callback in callbacks:
                try:
                    callback(data_copy)
                except Exception as e:
                    logging.error(f"GitHubDataManager error calling callback: {e}")

        # Sync to GitHub API in background
        def _sync():
            try:
                from datetime import datetime, timezone

                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "Content-Type": "application/json",
                }
                last_read_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                data = json.dumps({"last_read_at": last_read_at}).encode("utf-8")
                url = "https://api.github.com/notifications"
                req = urllib.request.Request(url, headers=headers, data=data, method="PUT")
                with urllib.request.urlopen(req):
                    logging.info("GitHubDataManager marked all notifications as read on GitHub")
            except urllib.error.HTTPError as e:
                logging.error(f"GitHubDataManager HTTP error marking all as read: {e.code} - {e.reason}")
            except urllib.error.URLError:
                logging.error("GitHubDataManager no internet connection. Unable to mark all as read.")
            except Exception as e:
                logging.error(f"GitHubDataManager error marking all as read: {e}")

        threading.Thread(target=_sync, daemon=True).start()

    @classmethod
    def _get_github_notifications(
        cls,
        token: str,
        only_unread: bool,
        max_notification: int,
        reason_filters: list[str] | None = None,
        show_comment_count: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch notifications from GitHub API. Returns [] on any error."""
        try:
            return cls._get_all_notifications(token, only_unread, max_notification, reason_filters, show_comment_count)
        except urllib.error.URLError:
            logging.error("GitHubDataManager no internet connection. Unable to fetch notifications.")
            return []
        except urllib.error.HTTPError as e:
            logging.error(f"GitHubDataManager HTTP error occurred: {e.code} - {e.reason}")
            return []
        except Exception as e:
            logging.error(f"GitHubDataManager an unexpected error occurred: {str(e)}")
            return []

    @classmethod
    def fetch_all_notifications(cls, token: str, max_notification: int = 100) -> list[dict[str, Any]]:
        """Fetch all notifications (read + unread) for a given token.

        This is the public entry point for on-demand fetching by the quick launch
        provider and any other consumer.  Unlike ``_get_github_notifications`` this
        method lets exceptions propagate so callers can show proper error messages.
        """
        return cls._get_all_notifications(token, only_unread=False, max_notification=max_notification)

    @staticmethod
    def _parse_link_header(header: str) -> dict[str, str]:
        """Parse the GitHub ``Link`` header into a dict of rel -> URL."""
        links: dict[str, str] = {}
        for part in header.split(","):
            section = part.split(";")
            if len(section) < 2:
                continue
            url = section[0].strip().strip("<>")
            for param in section[1:]:
                param = param.strip()
                if param.startswith('rel="') and param.endswith('"'):
                    rel = param[5:-1]
                    links[rel] = url
        return links

    @classmethod
    def _get_all_notifications(
        cls,
        token: str,
        only_unread: bool,
        max_notification: int,
        reason_filters: list[str] | None = None,
        show_comment_count: bool = False,
    ) -> list[dict[str, Any]]:
        """Core fetch + GraphQL enrichment logic. Raises on network/API errors."""
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        per_page = min(max_notification, 50)  # GitHub API caps per_page at 50
        params = {
            "all": "false" if only_unread else "true",
            "participating": "false",
            "per_page": per_page,
        }

        url = "https://api.github.com/notifications"
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        next_url: str | None = f"{url}?{query_string}"

        all_notifications: list[dict] = []
        while next_url and len(all_notifications) < max_notification:
            req = urllib.request.Request(next_url, headers=headers)
            with urllib.request.urlopen(req) as response:
                page = json.loads(response.read().decode())
                all_notifications.extend(page)

                # Check for next page via Link header
                link_header = response.getheader("Link")
                if link_header:
                    links = cls._parse_link_header(link_header)
                    next_url = links.get("next")
                else:
                    next_url = None

        # Trim to requested maximum
        all_notifications = all_notifications[:max_notification]

        result = []
        if all_notifications:
            for notification in all_notifications:
                # Extract nested values once
                repository = notification["repository"]
                subject = notification["subject"]
                repo_full_name = repository["full_name"]
                subject_type = subject["type"]
                subject_url = subject["url"]
                if subject_type == "PullRequest":
                    github_url = subject_url.replace("api.github.com/repos", "github.com").replace("/pulls/", "/pull/")
                elif subject_type == "Release":
                    github_url = f"https://github.com/{repo_full_name}/releases"
                elif subject_type in ("Issue", "Discussion"):
                    github_url = subject_url.replace("api.github.com/repos", "github.com")
                elif subject_type == "CheckSuite":
                    # CheckSuite notifications don't provide a direct URL in the API
                    github_url = f"https://github.com/{repo_full_name}/actions"
                else:
                    github_url = repository["html_url"]

                result.append(
                    {
                        "id": notification["id"],
                        "repository": repo_full_name,
                        "title": subject["title"],
                        "type": subject_type,
                        "url": github_url,
                        "unread": notification["unread"],
                        "reason": notification.get("reason", ""),
                        "comment_count": None,
                        "updated_at": notification.get("updated_at", ""),
                        "__subject_api_url": subject_url,
                    }
                )

        # Filter by reason (set lookup is O(1) vs list lookup O(n))
        if reason_filters:
            normalized_filters = {reason.lower() for reason in reason_filters if reason}
            if normalized_filters:
                result = [item for item in result if item.get("reason", "").lower() in normalized_filters]

        if token:
            cls._enrich_notifications(
                token,
                result,
                include_comment_count=show_comment_count,
            )

        for item in result:
            item.pop("__subject_api_url", None)

        return result

    @classmethod
    def _enrich_notifications(
        cls,
        token: str,
        notifications: list[dict[str, Any]],
        *,
        include_comment_count: bool,
    ) -> None:
        query_parts: list[str] = []
        alias_map: dict[str, tuple[dict[str, Any], str]] = {}

        for index, notification in enumerate(notifications):
            subject_type = notification.get("type")
            subject_url = notification.get("__subject_api_url")
            if subject_type not in {"Issue", "PullRequest", "Discussion"} or not subject_url:
                continue

            parsed = cls._parse_subject_metadata(subject_url)
            if not parsed:
                continue

            owner, repo, number = parsed
            alias = f"n{index}"

            # Build GraphQL fragment based on type
            if subject_type == "Issue":
                fields = "state comments { totalCount }" if include_comment_count else "state"
                fragment = f'{alias}: repository(owner: "{owner}", name: "{repo}") {{ issue(number: {number}) {{ {fields} }} }}'
            elif subject_type == "PullRequest":
                if include_comment_count:
                    fields = "state mergedAt isDraft comments { totalCount } reviewThreads { totalCount }"
                else:
                    fields = "state mergedAt isDraft"
                fragment = f'{alias}: repository(owner: "{owner}", name: "{repo}") {{ pullRequest(number: {number}) {{ {fields} }} }}'
            elif subject_type == "Discussion":
                fields = "isAnswered comments { totalCount }" if include_comment_count else "isAnswered"
                fragment = f'{alias}: repository(owner: "{owner}", name: "{repo}") {{ discussion(number: {number}) {{ {fields} }} }}'
            else:
                continue

            query_parts.append(fragment)
            alias_map[alias] = (notification, subject_type)

        if not query_parts:
            return

        selection = "\n".join(query_parts)
        graphql_query = f"query {{\n{selection}}}"
        payload = json.dumps({"query": graphql_query}).encode("utf-8")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        request = urllib.request.Request("https://api.github.com/graphql", data=payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(request) as response:
                data = json.loads(response.read().decode())

            if data.get("errors"):
                logging.warning("GitHubDataManager GraphQL errors: %s", data["errors"])
                return

            result_data = data.get("data", {})
            for alias, (notification, subject_type) in alias_map.items():
                repo_data = result_data.get(alias)
                if not repo_data:
                    continue

                if subject_type == "Issue":
                    issue_data = repo_data.get("issue")
                    if not issue_data:
                        continue

                    state_value = issue_data.get("state")
                    if isinstance(state_value, str):
                        notification["issue_state"] = state_value.lower()
                    else:
                        notification.pop("issue_state", None)

                    if include_comment_count and issue_data.get("comments") is not None:
                        total_count = issue_data["comments"].get("totalCount")
                        if isinstance(total_count, int):
                            notification["comment_count"] = total_count
                elif subject_type == "PullRequest":
                    pr_data = repo_data.get("pullRequest")
                    if not pr_data:
                        continue

                    state_value = pr_data.get("state")
                    if isinstance(state_value, str):
                        notification["pull_request_state"] = state_value.lower()
                    else:
                        notification.pop("pull_request_state", None)

                    notification["pull_request_is_merged"] = bool(pr_data.get("mergedAt"))

                    is_draft_value = pr_data.get("isDraft")
                    if isinstance(is_draft_value, bool):
                        notification["pull_request_is_draft"] = is_draft_value
                    else:
                        notification.pop("pull_request_is_draft", None)

                    if include_comment_count:
                        base_comments = pr_data.get("comments", {}).get("totalCount")
                        review_threads = pr_data.get("reviewThreads", {}).get("totalCount")
                        total_comments = 0
                        if isinstance(base_comments, int):
                            total_comments += base_comments
                        if isinstance(review_threads, int):
                            total_comments += review_threads
                        notification["comment_count"] = total_comments
                elif subject_type == "Discussion":
                    discussion_data = repo_data.get("discussion")
                    if not discussion_data:
                        continue

                    is_answered_value = discussion_data.get("isAnswered")
                    if isinstance(is_answered_value, bool):
                        notification["discussion_is_answered"] = is_answered_value
                    else:
                        notification.pop("discussion_is_answered", None)

                    if include_comment_count and discussion_data.get("comments") is not None:
                        total_count = discussion_data["comments"].get("totalCount")
                        if isinstance(total_count, int):
                            notification["comment_count"] = total_count
        except urllib.error.HTTPError as exc:
            logging.error(
                "GitHubDataManager GraphQL HTTP error: %s - %s", getattr(exc, "code", "?"), getattr(exc, "reason", "")
            )
        except urllib.error.URLError:
            logging.error("GitHubDataManager no internet connection. Unable to enrich notifications via GraphQL.")
        except Exception as exc:
            logging.error("GitHubDataManager unexpected error enriching notifications: %s", exc)

    @staticmethod
    def _parse_subject_metadata(subject_url: str) -> tuple[str, str, int] | None:
        try:
            cleaned_url = subject_url.rstrip("/")
            parts = cleaned_url.split("/")
            if len(parts) < 8:
                return None
            owner = parts[4]
            repo = parts[5]
            identifier = parts[-1]
            number = int(identifier.split("?")[0])
            return owner, repo, number
        except IndexError, ValueError:
            return None
