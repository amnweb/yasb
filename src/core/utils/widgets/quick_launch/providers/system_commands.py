import logging

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult
from core.utils.widgets.quick_launch.providers.resources.icons import (
    ICON_HIBERNATE,
    ICON_LOCK,
    ICON_RESTART,
    ICON_SHUTDOWN,
    ICON_SIGN_OUT,
    ICON_SLEEP,
    ICON_SYSTEM,
)

_SYSTEM_COMMANDS = [
    {
        "keywords": ["shutdown", "shut down", "power off", "turn off"],
        "title": "Shutdown",
        "description": "Shut down the computer",
        "icon": ICON_SHUTDOWN,
        "action": "shutdown",
    },
    {
        "keywords": ["restart", "reboot"],
        "title": "Restart",
        "description": "Restart the computer",
        "icon": ICON_RESTART,
        "action": "restart",
    },
    {
        "keywords": ["sleep", "stand by", "standby"],
        "title": "Sleep",
        "description": "Put the computer to sleep",
        "icon": ICON_SLEEP,
        "action": "sleep",
    },
    {
        "keywords": ["hibernate"],
        "title": "Hibernate",
        "description": "Hibernate the computer",
        "icon": ICON_HIBERNATE,
        "action": "hibernate",
    },
    {
        "keywords": ["lock", "lock screen"],
        "title": "Lock",
        "description": "Lock the workstation",
        "icon": ICON_LOCK,
        "action": "lock",
    },
    {
        "keywords": ["sign out", "signout", "log out", "logout", "log off", "logoff"],
        "title": "Sign out",
        "description": "Sign out of the current session",
        "icon": ICON_SIGN_OUT,
        "action": "signout",
    },
    {
        "keywords": ["force shutdown", "force shut down"],
        "title": "Force Shutdown",
        "description": "Force shutdown (skip app close prompts)",
        "icon": ICON_SHUTDOWN,
        "action": "force_shutdown",
    },
    {
        "keywords": ["force restart", "force reboot"],
        "title": "Force Restart",
        "description": "Force restart (skip app close prompts)",
        "icon": ICON_RESTART,
        "action": "force_restart",
    },
]


class SystemCommandsProvider(BaseProvider):
    """Provide system commands like shutdown, restart, lock, sleep."""

    name = "system_commands"
    display_name = "System Commands"
    input_placeholder = "Search system commands..."
    icon = ICON_SYSTEM

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._power_ops = None

    @property
    def power_ops(self):
        if self._power_ops is None:
            from core.utils.widgets.power_menu.power_commands import PowerOperations

            self._power_ops = PowerOperations()
        return self._power_ops

    def match(self, text: str) -> bool:
        text = text.strip()
        if self.prefix and text.startswith(self.prefix):
            return True
        # Also match if the text directly matches a system command keyword
        text_lower = text.lower()
        if len(text_lower) >= 3:
            for cmd in _SYSTEM_COMMANDS:
                for kw in cmd["keywords"]:
                    if text_lower in kw or kw.startswith(text_lower):
                        return True
        return False

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = (
            self.get_query_text(text).lower() if self.prefix and text.startswith(self.prefix) else text.strip().lower()
        )

        if not query:
            return [
                ProviderResult(
                    title=cmd["title"],
                    description=cmd["description"],
                    icon_char=cmd["icon"],
                    provider=self.name,
                    action_data={"action": cmd["action"]},
                )
                for cmd in _SYSTEM_COMMANDS
            ]

        results = []
        for cmd in _SYSTEM_COMMANDS:
            match_score = 0
            for kw in cmd["keywords"]:
                if query == kw:
                    match_score = 100
                    break
                if kw.startswith(query):
                    match_score = max(match_score, 80)
                elif query in kw:
                    match_score = max(match_score, 60)

            if match_score > 0:
                results.append(
                    (
                        match_score,
                        ProviderResult(
                            title=cmd["title"],
                            description=cmd["description"],
                            icon_char=cmd["icon"],
                            provider=self.name,
                            action_data={"action": cmd["action"]},
                        ),
                    )
                )

        results.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in results]

    def execute(self, result: ProviderResult) -> bool:
        action = result.action_data.get("action", "")
        ops = self.power_ops
        try:
            action_map = {
                "shutdown": ops.shutdown,
                "restart": ops.restart,
                "sleep": ops.sleep,
                "hibernate": ops.hibernate,
                "lock": ops.lock,
                "signout": ops.signout,
                "force_shutdown": ops.force_shutdown,
                "force_restart": ops.force_restart,
            }
            fn = action_map.get(action)
            if fn:
                fn()
        except Exception as e:
            logging.error(f"System command '{action}' failed: {e}")
        return True
