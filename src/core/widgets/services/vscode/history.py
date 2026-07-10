import json
import logging
import os
import sqlite3
import urllib.parse


def _uri_to_windows_path(uri: str) -> str:
    parsed = urllib.parse.urlparse(uri)
    path = urllib.parse.unquote(parsed.path)
    if path.startswith("/"):
        path = path[1:]
    if ":" in path:
        drive_part, rest = path.split(":", 1)
        drive_part = drive_part.capitalize()
        path = f"{drive_part}:{rest}"
    return path


def _is_remote_uri(uri: str | None) -> bool:
    return isinstance(uri, str) and uri.startswith("vscode-remote://")


def _remote_uri_display_path(uri: str) -> str:
    parsed = urllib.parse.urlparse(uri)
    authority = urllib.parse.unquote(parsed.netloc)
    path = urllib.parse.unquote(parsed.path)

    if authority.lower().startswith("wsl+"):
        distro = authority[4:]
        return f"WSL: {distro} - {path}" if distro else f"WSL - {path}"

    return f"{authority} - {path}" if authority else (path or uri)


def _recent_uri_to_workspace(uri: str, workspace_type: str, remote_authority: str | None = None) -> dict | None:
    if _is_remote_uri(uri):
        return {
            "type": workspace_type,
            "path": uri,
            "display_path": _remote_uri_display_path(uri),
            "is_remote": True,
            "remote_authority": remote_authority,
        }

    local_path = _uri_to_windows_path(uri)
    if os.path.exists(local_path):
        return {
            "type": workspace_type,
            "path": local_path,
            "display_path": local_path,
            "is_remote": False,
        }

    return None


def _add_recent_uri(
    result_list: list[dict], uri: str, workspace_type: str, remote_authority: str | None = None
) -> None:
    workspace_data = _recent_uri_to_workspace(uri, workspace_type, remote_authority)
    if workspace_data:
        result_list.append(workspace_data)


def load_recent_workspaces(state_file_path: str) -> list[dict]:
    try:
        with sqlite3.connect(state_file_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM ItemTable WHERE key = 'history.recentlyOpenedPathsList'")
            result = cursor.fetchone()
            result_list = []
            if result:
                paths_data = json.loads(result[0]).get("entries", [])
                for entry in paths_data:
                    if isinstance(entry, dict):
                        remote_auth = entry.get("remoteAuthority")
                        if entry.get("folderUri"):
                            _add_recent_uri(result_list, entry.get("folderUri"), "folder", remote_auth)
                        if entry.get("fileUri"):
                            _add_recent_uri(result_list, entry.get("fileUri"), "file", remote_auth)
                    else:
                        logging.error("Unexpected entry type: %s", type(entry))
            else:
                logging.debug("No recent workspaces found in %s", state_file_path)
            return result_list
    except Exception as e:
        logging.error("Error loading recent VS Code workspaces: %s", e)
        return []


def get_history_modified_time(state_file_path: str) -> float:
    try:
        mtime = os.path.getmtime(state_file_path)
        wal_path = state_file_path + "-wal"
        if os.path.exists(wal_path):
            mtime = max(mtime, os.path.getmtime(wal_path))
        return mtime
    except OSError:
        return 0
