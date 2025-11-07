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
    def mark_as_read(cls, notification_id: str, sync_to_github: bool = False, token: str = None) -> None:
        """
        Mark a notification as read in the shared data and notify all widgets.
        Optionally sync with GitHub API in background thread.
        """
        with cls._lock:
            for notification in cls._shared_data:
                if notification["id"] == notification_id:
                    notification["unread"] = False
                    break

            # Get current data and callbacks
            data_copy = cls._shared_data.copy()
            callbacks = cls._callbacks.copy()

        # Notify all callbacks about the change
        for callback in callbacks:
            try:
                callback(data_copy)
            except Exception as e:
                logging.error(f"GitHubDataManager error calling callback: {e}")

        # Optionally sync with GitHub API in background
        if sync_to_github and token:
            threading.Thread(target=lambda: cls._sync_notification_read(notification_id, token), daemon=True).start()

    @classmethod
    def _sync_notification_read(cls, notification_id: str, token: str) -> None:
        """Sync single notification as read with GitHub API."""
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        url = f"https://api.github.com/notifications/threads/{notification_id}"
        req = urllib.request.Request(url, headers=headers, method="PATCH")
        try:
            with urllib.request.urlopen(req):
                pass  # Successfully marked as read on GitHub
        except urllib.error.HTTPError as e:
            logging.error(f"GitHubDataManager HTTP Error marking notification as read: {e.code} - {e.reason}")
        except Exception as e:
            logging.error(f"GitHubDataManager Error marking notification as read: {e}")

    @classmethod
    def mark_all_as_read(cls, token: str) -> None:
        """
        Mark all unread notifications as read.
        Uses GitHub's single API call to mark all notifications as read at once.
        """
        with cls._lock:
            # Mark all as read locally
            for notification in cls._shared_data:
                notification["unread"] = False

            # Get current data and callbacks
            data_copy = cls._shared_data.copy()
            callbacks = cls._callbacks.copy()

        # Notify all callbacks about the change
        for callback in callbacks:
            try:
                callback(data_copy)
            except Exception as e:
                logging.error(f"GitHubDataManager Error calling callback: {e}")

        # Sync with GitHub API in background thread using single API call
        def _sync_to_github():
            try:
                from datetime import datetime, timezone

                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "Content-Type": "application/json",
                }
                # ISO 8601 timestamp for last_read_at
                last_read_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                data = json.dumps({"last_read_at": last_read_at}).encode("utf-8")

                url = "https://api.github.com/notifications"
                req = urllib.request.Request(url, headers=headers, data=data, method="PUT")

                with urllib.request.urlopen(req):
                    logging.info("GitHubDataManager marked all notifications as read on GitHub")
            except urllib.error.HTTPError as e:
                logging.error(f"GitHubDataManager HTTP error marking all as read: {e.code} - {e.reason}")
            except Exception as e:
                logging.error(f"GitHubDataManager Error marking all as read on GitHub: {e}")

        threading.Thread(target=_sync_to_github, daemon=True).start()

    @classmethod
    def _get_github_notifications(
        cls,
        token: str,
        only_unread: bool,
        max_notification: int,
        reason_filters: list[str] | None = None,
        show_comment_count: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch notifications from GitHub API."""
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        params = {
            "all": "false" if only_unread else "true",
            "participating": "false",
            "per_page": max_notification,
        }

        url = "https://api.github.com/notifications"
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"{url}?{query_string}"

        req = urllib.request.Request(full_url, headers=headers)

        try:
            with urllib.request.urlopen(req) as response:
                notifications = json.loads(response.read().decode())

            result = []
            if notifications:
                for notification in notifications:
                    # Extract nested values once
                    repository = notification["repository"]
                    subject = notification["subject"]
                    repo_full_name = repository["full_name"]
                    subject_type = subject["type"]
                    subject_url = subject["url"]
                    if subject_type == "PullRequest":
                        github_url = subject_url.replace("api.github.com/repos", "github.com").replace(
                            "/pulls/", "/pull/"
                        )
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
        except (IndexError, ValueError):
            return None
