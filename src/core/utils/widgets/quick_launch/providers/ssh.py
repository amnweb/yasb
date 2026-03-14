import logging
import os
import re
import shutil

from core.utils.shell_utils import shell_open
from core.utils.widgets.quick_launch.base_provider import (
    BaseProvider,
    ProviderMenuAction,
    ProviderMenuActionResult,
    ProviderResult,
)
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_SSH


def _parse_ssh_config(config_path: str) -> list[dict]:
    """Parse an SSH config file and return a list of host entry dicts.

    Each dict may contain: host, hostname, user, port, identityfile.
    Wildcard ``Host *`` entries are skipped.
    """
    if not os.path.isfile(config_path):
        return []

    hosts: list[dict] = []
    current: dict | None = None

    try:
        with open(config_path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as exc:
        logging.error("SSH provider: failed to read config %s: %s", config_path, exc)
        return []

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        match = re.match(r"^(\w+)\s+(.+)$", line)
        if not match:
            continue

        key = match.group(1).lower()
        value = match.group(2).strip().strip('"')

        if key == "host":
            # Flush previous entry
            if current and current.get("host") and "*" not in current["host"]:
                hosts.append(current)
            current = {"host": value} if "*" not in value else None
        elif current is not None:
            if key == "hostname":
                current["hostname"] = value
            elif key == "user":
                current["user"] = value
            elif key == "port":
                current["port"] = value
            elif key == "identityfile":
                current["identityfile"] = value

    # Flush last entry
    if current and current.get("host") and "*" not in current["host"]:
        hosts.append(current)

    return hosts


def _build_ssh_command(entry: dict) -> str:
    """Build the ssh command string for a host entry."""
    parts = ["ssh"]
    if entry.get("port"):
        parts += ["-p", entry["port"]]
    if entry.get("identityfile"):
        parts += ["-i", f'"{entry["identityfile"]}"']
    hostname = entry.get("hostname") or entry.get("host", "")
    user = entry.get("user", "")
    parts.append(f"{user}@{hostname}" if user else hostname)
    return " ".join(parts)


def _launch_ssh(host: str, ssh_cmd: str, admin: bool = False) -> None:
    """Launch an SSH session in Windows Terminal or cmd.exe as fallback."""
    verb = "runas" if admin else "open"
    if shutil.which("wt"):
        shell_open("wt", verb=verb, parameters=f'new-tab --title "SSH: {host}" -- {ssh_cmd}')
    else:
        shell_open("cmd.exe", verb=verb, parameters=f"/k {ssh_cmd}")


def _build_config_block(entry: dict) -> list[str]:
    """Return SSH config file lines for a single host block."""
    lines = [f"Host {entry['host']}\n"]
    for key, ssh_key in (
        ("hostname", "HostName"),
        ("user", "User"),
        ("port", "Port"),
        ("identityfile", "IdentityFile"),
    ):
        if entry.get(key):
            lines.append(f"    {ssh_key} {entry[key]}\n")
    return lines


def _append_ssh_entry(config_path: str, new_entry: dict) -> bool:
    """Append a new Host block to the SSH config file, creating it if needed."""
    block = _build_config_block(new_entry)
    try:
        existing = ""
        if os.path.isfile(config_path):
            with open(config_path, encoding="utf-8") as fh:
                existing = fh.read()
        with open(config_path, "a", encoding="utf-8") as fh:
            if existing and not existing.endswith("\n\n"):
                fh.write("\n" if existing.endswith("\n") else "\n\n")
            fh.writelines(block)
            fh.write("\n")
        return True
    except Exception as exc:
        logging.error("SSH provider: failed to append to config: %s", exc)
        return False


def _write_ssh_entry(config_path: str, old_host: str, new_entry: dict) -> bool:
    """Rewrite a Host block in the SSH config file with updated values.

    Other blocks, comments, and blank lines outside the replaced block are
    preserved verbatim.  Returns True on success.
    """
    try:
        with open(config_path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception as exc:
        logging.error("SSH provider: cannot read config for writing: %s", exc)
        return False

    new_lines: list[str] = []
    in_target = False
    replaced = False

    for line in lines:
        stripped = line.strip()
        host_match = re.match(r"^[Hh]ost\s+(\S+.*)$", stripped)
        if host_match:
            if in_target and not replaced:
                # Flush the replacement block before starting the next Host
                new_lines.extend(_build_config_block(new_entry))
                new_lines.append("\n")
                replaced = True
            in_target = host_match.group(1).strip() == old_host
            if in_target:
                continue  # will be written when block ends (or at EOF)
        elif in_target:
            continue  # skip old block body lines

        new_lines.append(line)

    # Handle target block at end-of-file
    if in_target and not replaced:
        new_lines.extend(_build_config_block(new_entry))
        new_lines.append("\n")

    try:
        with open(config_path, "w", encoding="utf-8") as fh:
            fh.writelines(new_lines)
        return True
    except Exception as exc:
        logging.error("SSH provider: failed to write config: %s", exc)
        return False


class SshProvider(BaseProvider):
    """Browse and launch SSH connections from ~/.ssh/config."""

    name = "ssh"
    display_name = "SSH"
    icon = ICON_SSH
    input_placeholder = "Search SSH hosts..."

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._hosts: list[dict] = []
        self._loaded = False
        self._editing_host: str | None = None

    def _edit_preview(self, entry: dict | None = None) -> dict:
        """Return a preview dict that renders as an inline SSH connection edit form."""
        e = entry or {}

        def f(id_, label, placeholder):
            return {"id": id_, "type": "text", "label": label, "placeholder": placeholder, "value": e.get(id_, "")}

        return {
            "kind": "edit",
            "action": "save_ssh_connection",
            "fields": [
                f("host", "Host alias", "e.g. myserver"),
                f("hostname", "Hostname / IP", "e.g. 192.168.1.10"),
                f("user", "User", "e.g. root"),
                f("port", "Port", "22"),
                f("identityfile", "Identity file", "e.g. ~/.ssh/id_rsa  (leave blank for default)"),
            ],
        }

    def _discover(self) -> None:
        """Load SSH hosts from the config file."""
        config_path = self.config.get("ssh_config_path") or os.path.expanduser("~/.ssh/config")
        self._hosts = _parse_ssh_config(config_path)
        self._loaded = True

    def cancel_edit(self) -> None:
        self._editing_host = None

    def on_deactivate(self) -> None:
        """Clear cache so the next popup open re-reads the config."""
        self._loaded = False
        self._hosts = []
        self._editing_host = None

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        if not self._loaded:
            self._discover()

        if not self._hosts:
            return [
                ProviderResult(
                    title="No SSH hosts found",
                    description="Add Host entries to ~/.ssh/config to see them here",
                    icon_char=ICON_SSH,
                    provider=self.name,
                ),
                self._new_connection_result(),
            ]

        query = self.get_query_text(text).strip().lower()
        if query:
            filtered = [
                h
                for h in self._hosts
                if query in h["host"].lower()
                or query in h.get("hostname", "").lower()
                or query in h.get("user", "").lower()
            ]
        else:
            filtered = self._hosts

        if not filtered:
            return [
                ProviderResult(
                    title="No matching SSH hosts",
                    description="Try a different search term",
                    icon_char=ICON_SSH,
                    provider=self.name,
                )
            ]

        results: list[ProviderResult] = []
        for entry in filtered:
            host = entry["host"]
            hostname = entry.get("hostname", "")
            user = entry.get("user", "")
            port = entry.get("port", "")
            ssh_cmd = _build_ssh_command(entry)

            desc_parts: list[str] = []
            if hostname and hostname != host:
                desc_parts.append(hostname)
            if user:
                desc_parts.append(f"user: {user}")
            if port:
                desc_parts.append(f"port: {port}")
            description = " · ".join(desc_parts) if desc_parts else ssh_cmd

            # If this host is currently being edited, show the edit form
            editing = self._editing_host == host
            results.append(
                ProviderResult(
                    title=host,
                    description=description,
                    icon_char=ICON_SSH,
                    provider=self.name,
                    action_data={
                        "host": host,
                        "ssh_cmd": ssh_cmd,
                        "hostname": hostname,
                        "user": user,
                        "port": port,
                        "identityfile": entry.get("identityfile", ""),
                    },
                    preview=self._edit_preview(entry) if editing else {},
                )
            )

        if not query:
            results.append(self._new_connection_result())

        return results

    def _new_connection_result(self) -> ProviderResult:
        """Return the fixed 'Add new connection' result with an inline edit form."""
        return ProviderResult(
            title="Add new connection",
            description="Create a new SSH host entry",
            icon_char=ICON_SSH,
            provider=self.name,
            action_data={"action": "create"},
            preview=self._edit_preview(),
        )

    def execute(self, result: ProviderResult) -> bool | None:
        if result.action_data.get("action") == "create":
            return None  # edit form is already in the preview panel
        data = result.action_data
        ssh_cmd = data.get("ssh_cmd", "")
        if not ssh_cmd:
            return None
        _launch_ssh(data.get("host", "host"), ssh_cmd)
        return True

    def get_context_menu_actions(self, result: ProviderResult) -> list[ProviderMenuAction]:
        if result.action_data.get("action") == "create":
            return []
        if not result.action_data.get("ssh_cmd"):
            return []
        return [
            ProviderMenuAction(id="open", label="Open"),
            ProviderMenuAction(id="open_admin", label="Open as Administrator"),
            ProviderMenuAction(id="copy_cmd", label="Copy SSH Command"),
            ProviderMenuAction(id="edit", label="Edit connection", separator_before=True),
        ]

    def execute_context_menu_action(self, action_id: str, result: ProviderResult) -> ProviderMenuActionResult:
        data = result.action_data
        ssh_cmd = data.get("ssh_cmd", "")
        host = data.get("host", "host")

        if action_id == "open" and ssh_cmd:
            _launch_ssh(host, ssh_cmd)
            return ProviderMenuActionResult(close_popup=True)

        if action_id == "open_admin" and ssh_cmd:
            _launch_ssh(host, ssh_cmd, admin=True)
            return ProviderMenuActionResult(close_popup=True)

        if action_id == "copy_cmd" and ssh_cmd:
            try:
                from PyQt6.QtWidgets import QApplication

                cb = QApplication.clipboard()
                if cb:
                    cb.setText(ssh_cmd)
            except Exception:
                pass
            return ProviderMenuActionResult(close_popup=False)

        if action_id == "edit":
            self._editing_host = host
            return ProviderMenuActionResult(refresh_results=True)

        return ProviderMenuActionResult()

    def handle_preview_action(self, action_id: str, result: ProviderResult, data: dict) -> ProviderMenuActionResult:
        if action_id == "cancel":
            self._editing_host = None
            return ProviderMenuActionResult(refresh_results=True)

        if action_id == "save_ssh_connection":
            new_host = data.get("host", "").strip()
            if not new_host or "*" in new_host:
                return ProviderMenuActionResult(refresh_results=True)

            new_entry = {
                "host": new_host,
                "hostname": data.get("hostname", "").strip(),
                "user": data.get("user", "").strip(),
                "port": data.get("port", "").strip(),
                "identityfile": data.get("identityfile", "").strip(),
            }

            config_path = self.config.get("ssh_config_path") or os.path.expanduser("~/.ssh/config")
            is_new = result.action_data.get("action") == "create"
            if is_new:
                success = _append_ssh_entry(config_path, new_entry)
            else:
                old_host = result.action_data.get("host", "")
                success = _write_ssh_entry(config_path, old_host, new_entry)

            if success:
                self._loaded = False
                self._hosts = []

            self._editing_host = None
            return ProviderMenuActionResult(refresh_results=True)

        return ProviderMenuActionResult()
