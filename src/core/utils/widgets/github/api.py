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

    @classmethod
    def initialize(
        cls, token: str, only_unread: bool = True, max_notification: int = 50, update_interval: int = 300
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
            cls.fetch_notifications(cls._token, cls._only_unread, cls._max_notification)

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
    def fetch_notifications(cls, token: str, only_unread: bool = True, max_notification: int = 50) -> None:
        """
        Fetch notifications from GitHub API in a background thread.
        After fetching, calls all registered callbacks with the new data.
        """

        def _fetch():
            try:
                notifications = cls._get_github_notifications(token, only_unread, max_notification)
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
    def _get_github_notifications(cls, token: str, only_unread: bool, max_notification: int) -> list[dict[str, Any]]:
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
                    repo_full_name = notification["repository"]["full_name"]
                    subject_type = notification["subject"]["type"]
                    subject_url = notification["subject"]["url"]
                    unread = notification["unread"]

                    if subject_type == "Issue":
                        github_url = subject_url.replace("api.github.com/repos", "github.com")
                    elif subject_type == "PullRequest":
                        github_url = subject_url.replace("api.github.com/repos", "github.com").replace(
                            "/pulls/", "/pull/"
                        )
                    elif subject_type == "Release":
                        github_url = f"https://github.com/{repo_full_name}/releases"
                    elif subject_type == "Discussion":
                        github_url = subject_url.replace("api.github.com/repos", "github.com")
                    else:
                        github_url = notification["repository"]["html_url"]

                    result.append(
                        {
                            "id": notification["id"],
                            "repository": repo_full_name,
                            "title": notification["subject"]["title"],
                            "type": subject_type,
                            "url": github_url,
                            "unread": unread,
                        }
                    )

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
