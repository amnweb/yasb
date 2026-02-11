import logging
import os
import webbrowser

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult


class AppsProvider(BaseProvider):
    """Search and launch installed applications."""

    name = "apps"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._service = None

    @property
    def service(self):
        if self._service is None:
            from core.utils.widgets.quick_launch.service import QuickLaunchService

            self._service = QuickLaunchService.instance()
        return self._service

    def match(self, text: str) -> bool:
        return True

    def get_results(self, text: str) -> list[ProviderResult]:
        svc = self.service
        show_recent = self.config.get("show_recent", True)
        max_recent = self.config.get("max_recent", 10)
        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        if not text_stripped:
            if show_recent:
                # Recent apps first (up to max_recent), then the rest alphabetically
                recent = []
                rest = []
                for name, path, extra in svc.apps:
                    key = f"{name}::{path}"
                    s = svc.get_frecency_score(key)
                    if s > 0:
                        recent.append((s, name, path, extra))
                    else:
                        rest.append((name, path, extra))
                recent.sort(key=lambda x: x[0], reverse=True)
                rest.sort(key=lambda a: a[0].lower())
                apps = [(n, p, e) for _, n, p, e in recent[:max_recent]] + rest
            else:
                apps = sorted(svc.apps, key=lambda a: a[0].lower())
        else:
            # Search query: filter by name, boost frecency
            apps = [(n, p, e) for n, p, e in svc.apps if text_lower in n.lower()]
            if show_recent:

                def score(app: tuple) -> float:
                    name, path, _ = app
                    key = f"{name}::{path}"
                    s = svc.get_frecency_score(key)
                    if name.lower().startswith(text_lower):
                        s += 50
                    return s

                apps.sort(key=score, reverse=True)

        show_path = self.config.get("show_path", False)
        results = []
        for name, path, _ in apps:
            app_key = f"{name}::{path}"
            icon_path = svc.icon_paths.get(app_key, "")
            if show_path:
                desc = path[5:] if path.startswith("UWP::") else path
            else:
                desc = ""
            results.append(
                ProviderResult(
                    title=name,
                    description=desc,
                    icon_path=icon_path,
                    provider=self.name,
                    id=app_key,
                    action_data={"name": name, "path": path},
                )
            )
        return results

    def execute(self, result: ProviderResult) -> bool:
        name = result.action_data.get("name", "")
        path = result.action_data.get("path", "")
        try:
            if path.startswith("UWP::"):
                aumid = path.replace("UWP::", "")
                os.startfile(f"shell:AppsFolder\\{aumid}")
            elif path.startswith(("http://", "https://")):
                webbrowser.open(path)
            elif os.path.isfile(path):
                os.startfile(path)
            else:
                logging.warning(f"Quick Launch: path not found: {path}")
            self.service.record_recent(name, path)
        except Exception as e:
            logging.error(f"Failed to launch {name}: {e}")
        return True
