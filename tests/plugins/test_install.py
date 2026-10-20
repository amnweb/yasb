import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

from core.cli.format import Format
from core.plugins import cli, install
from core.plugins.discovery import plugin_data_path
from core.plugins.manifest import PLUGIN_API_VERSION, PluginError, PluginManifest
from tests.plugins.helpers import FIXTURE, PLUGIN_ID, WIDGET_TYPE, write_manifest, zip_folder
from tests.support.source import SRC_ROOT

INDEX_URL = "https://plugins.test/index.json"
UNREVIEWED = "This plugin isn't from the official repository. Use it only if you trust the author."


class FakeRepository:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.entries: dict[str, dict[str, Any]] = {}
        self.files: dict[str, bytes] = {}
        self.github: dict[str, bytes] = {}
        self.requests: list[str] = []
        monkeypatch.setenv("YASB_PLUGIN_INDEX_URL", INDEX_URL)
        monkeypatch.setattr(install, "fetch", self.fetch)

    def publish(self, folder: Path = FIXTURE, **changes: Any) -> None:
        manifest: dict[str, Any] = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        data = zip_folder(folder)
        path = f"plugins/{manifest['id']}/{manifest['id']}-{manifest['version']}.zip"
        self.files[path] = data
        entry = {key: manifest[key] for key in ("name", "version", "author", "description", "api", "min_yasb")}
        self.entries[manifest["id"]] = entry | {"zip": path, "sha256": hashlib.sha256(data).hexdigest()} | changes

    def on_github(self, repo: str, folder: Path = FIXTURE, ref: str = "HEAD") -> None:
        name = repo.split("/")[1]
        self.github[f"https://github.com/{repo}/archive/{ref}.zip"] = zip_folder(folder, f"{name}-{ref}/")
        manifest_url = f"https://raw.githubusercontent.com/{repo}/{ref}/manifest.json"
        self.github[manifest_url] = (folder / "manifest.json").read_bytes()

    def fetch(self, url: str) -> bytes:
        self.requests.append(url)
        if url == INDEX_URL:
            return json.dumps({"plugins": self.entries}).encode()
        if data := self.files.get(url.removeprefix("https://plugins.test/")) or self.github.get(url):
            return data
        raise PluginError(f"{url} answered 404 Not Found")


@pytest.fixture
def repo(monkeypatch: pytest.MonkeyPatch) -> FakeRepository:
    return FakeRepository(monkeypatch)


@pytest.fixture
def root(config_home: Path) -> Path:
    return config_home / "plugins"


def _version(tmp_path: Path, version: str) -> Path:
    folder = tmp_path / f"hello-{version}"
    shutil.copytree(FIXTURE, folder, ignore=shutil.ignore_patterns("__pycache__"))
    write_manifest(folder, version=version)
    return folder


def _leftovers(root: Path) -> list[str]:
    return [path.name for path in root.iterdir() if path.name.startswith(".")]


# --- from the official repository ------------------------------------------------------


def test_install_by_name(root: Path, repo: FakeRepository):
    repo.publish()

    installed = install.install(PLUGIN_ID, root)

    assert installed.official
    assert installed.directory == root / PLUGIN_ID
    assert (installed.directory / "widget.py").is_file()
    assert install.read_install_record(installed.directory) == {"source": "official", "version": "1.0.0"}
    assert repo.requests == [INDEX_URL, "https://plugins.test/plugins/hello/hello-1.0.0.zip"]
    assert _leftovers(root) == []


def test_unknown_name(root: Path, repo: FakeRepository):
    with pytest.raises(PluginError, match='There is no plugin named "nope" in the official plugin repository'):
        install.install("nope", root)


def test_disabled_plugin_cannot_be_installed(root: Path, repo: FakeRepository):
    repo.publish(disabled=True)

    with pytest.raises(PluginError, match=f'"{PLUGIN_ID}" is temporarily disabled .* cannot be installed right now'):
        install.install(PLUGIN_ID, root)

    assert repo.requests == [INDEX_URL]


def test_plugin_for_another_api_is_not_downloaded(root: Path, repo: FakeRepository):
    repo.publish(api=str(PLUGIN_API_VERSION + 1))

    with pytest.raises(PluginError, match=f"made for plugin API {PLUGIN_API_VERSION + 1}"):
        install.install(PLUGIN_ID, root)

    assert repo.requests == [INDEX_URL]


def test_plugin_for_a_newer_yasb(root: Path, repo: FakeRepository):
    repo.publish(min_yasb="99.0.0")

    with pytest.raises(PluginError, match="needs YASB 99.0.0 or newer"):
        install.install(PLUGIN_ID, root)


def test_tampered_download_is_refused(root: Path, repo: FakeRepository):
    repo.publish(sha256="0" * 64)

    with pytest.raises(PluginError, match="SHA-256 differs"):
        install.install(PLUGIN_ID, root)

    assert not root.exists()


def test_download_with_another_version_is_refused(root: Path, repo: FakeRepository):
    repo.publish(version="9.9.9")

    with pytest.raises(PluginError, match='contains "hello" 1.0.0'):
        install.install(PLUGIN_ID, root)


def test_update_installs_a_newer_version(root: Path, repo: FakeRepository, tmp_path: Path):
    repo.publish()
    install.install(PLUGIN_ID, root)
    repo.publish(_version(tmp_path, "1.1.0"))

    outcome, installed = install.update(PLUGIN_ID, root, install.fetch_index())

    assert outcome == "updated 1.0.0 -> 1.1.0"
    assert installed is not None and installed.directory == root / PLUGIN_ID
    assert install.update(PLUGIN_ID, root, install.fetch_index()) == ("up to date (1.1.0)", None)


def test_disabled_plugin_is_not_updated(root: Path, repo: FakeRepository, tmp_path: Path):
    repo.publish()
    install.install(PLUGIN_ID, root)
    repo.publish(_version(tmp_path, "1.1.0"), disabled=True)

    outcome, installed = install.update(PLUGIN_ID, root, install.fetch_index())

    assert outcome == "temporarily disabled in the official plugin repository, so it cannot be updated right now"
    assert installed is None
    plugin = install.installed_plugins(root)[PLUGIN_ID]
    assert plugin.manifest is not None and plugin.manifest.version == "1.0.0"


def test_update_of_a_plugin_that_left_the_repository(root: Path, repo: FakeRepository):
    repo.publish()
    install.install(PLUGIN_ID, root)
    repo.entries.clear()

    assert install.update(PLUGIN_ID, root, install.fetch_index())[0].startswith("no longer in the official")


# --- from GitHub -----------------------------------------------------------------------

GITHUB_REPO = "jdoe/hello"
ARCHIVE_URL = f"https://github.com/{GITHUB_REPO}/archive/HEAD.zip"


def test_install_from_github_asks_first(root: Path, repo: FakeRepository):
    repo.on_github(GITHUB_REPO)
    asked: list[tuple[str, str]] = []

    def confirm(manifest: PluginManifest, label: str) -> bool:
        asked.append((manifest.id, label))
        return True

    installed = install.install(f"https://github.com/{GITHUB_REPO}", root, confirm=confirm)

    assert asked == [(PLUGIN_ID, f"github.com/{GITHUB_REPO}")]
    assert installed.source == "github" and not installed.official
    assert installed.directory == root / PLUGIN_ID
    assert install.read_install_record(installed.directory) == {"source": "github", "url": f"github.com/{GITHUB_REPO}"}
    assert repo.requests == [ARCHIVE_URL]


def test_github_install_can_be_cancelled(root: Path, repo: FakeRepository):
    repo.on_github(GITHUB_REPO)

    with pytest.raises(install.InstallCancelled):
        install.install(f"github.com/{GITHUB_REPO}", root, confirm=lambda manifest, label: False)

    assert not root.exists()


def test_github_install_of_a_tag(root: Path, repo: FakeRepository):
    repo.on_github(GITHUB_REPO, ref="v1.0.0")

    installed = install.install(f"github.com/{GITHUB_REPO}@v1.0.0", root)

    assert install.read_install_record(installed.directory)["url"] == f"github.com/{GITHUB_REPO}@v1.0.0"


def test_github_repository_that_does_not_exist(root: Path, repo: FakeRepository):
    with pytest.raises(PluginError, match="github.com/someone/nothing doesn't exist on GitHub"):
        install.install("github.com/someone/nothing", root)


def test_github_repository_without_a_plugin(root: Path, repo: FakeRepository, tmp_path: Path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "repo" / "README.md").write_text("not a plugin", encoding="utf-8")
    repo.github[ARCHIVE_URL] = zip_folder(tmp_path / "repo", "hello-HEAD/")

    with pytest.raises(PluginError, match="no manifest.json"):
        install.install(f"github.com/{GITHUB_REPO}", root)


def test_update_from_github(root: Path, repo: FakeRepository, tmp_path: Path):
    repo.on_github(GITHUB_REPO)
    install.install(f"github.com/{GITHUB_REPO}", root)

    assert install.update(PLUGIN_ID, root, install.PluginIndex()) == ("up to date (1.0.0)", None)
    assert repo.requests.count(ARCHIVE_URL) == 1

    repo.on_github(GITHUB_REPO, _version(tmp_path, "1.1.0"))
    outcome, installed = install.update(PLUGIN_ID, root, install.PluginIndex())

    assert outcome == f"updated 1.0.0 -> 1.1.0 from github.com/{GITHUB_REPO}"
    assert installed is not None and installed.manifest.version == "1.1.0"
    assert install.read_install_record(installed.directory)["source"] == "github"


def test_github_shapes_that_are_not_github(root: Path):
    assert install.github_source("github.com/owner") is None
    assert install.github_source("gitlab.com/owner/repo") is None
    assert install.github_source("./plugins/hello") is None


# --- from a folder or a .zip -----------------------------------------------------------


def test_install_from_a_folder(root: Path):
    installed = install.install(str(FIXTURE), root)

    assert not installed.official
    assert installed.directory == root / PLUGIN_ID
    assert not (installed.directory / "__pycache__").exists()
    assert install.read_install_record(installed.directory) == {"source": "local", "path": str(FIXTURE.resolve())}
    assert list(install.installed_plugins(root)) == [PLUGIN_ID]


def test_a_folder_needs_a_path(root: Path, repo: FakeRepository):
    with pytest.raises(PluginError, match=r"install a folder or .zip by its path"):
        install.install("my-plugin", root)


def test_installing_twice_needs_force(root: Path, tmp_path: Path):
    install.install(str(FIXTURE), root)

    with pytest.raises(PluginError, match="already installed"):
        install.install(str(FIXTURE), root)

    install.install(str(_version(tmp_path, "1.1.0")), root, replace=True)
    plugin = install.installed_plugins(root)[PLUGIN_ID]
    assert plugin.manifest is not None and plugin.manifest.version == "1.1.0"
    assert _leftovers(root) == []


def test_install_from_a_zip_with_a_top_folder(root: Path, tmp_path: Path):
    archive = tmp_path / "hello.zip"
    archive.write_bytes(zip_folder(FIXTURE, "hello-main/"))

    installed = install.install(str(archive), root)

    assert installed.manifest.id == PLUGIN_ID
    assert install.read_install_record(installed.directory)["source"] == "zip"


def test_zip_entries_outside_the_plugin_are_refused(root: Path, tmp_path: Path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", (FIXTURE / "manifest.json").read_text(encoding="utf-8"))
        archive.writestr("../evil.py", "print('escaped')")
    (tmp_path / "evil.zip").write_bytes(buffer.getvalue())

    with pytest.raises(PluginError, match="points outside the plugin folder"):
        install.install(str(tmp_path / "evil.zip"), root)

    assert not root.exists()


def test_not_a_zip(root: Path, tmp_path: Path):
    (tmp_path / "broken.zip").write_text("nope", encoding="utf-8")

    with pytest.raises(PluginError, match="not a valid .zip file"):
        install.install(str(tmp_path / "broken.zip"), root)


def test_missing_path(root: Path, tmp_path: Path):
    with pytest.raises(PluginError, match="does not exist"):
        install.install(str(tmp_path / "missing"), root)


def test_incompatible_plugin_is_not_installed(root: Path, tmp_path: Path):
    folder = _version(tmp_path, "1.0.0")
    write_manifest(folder, api=str(PLUGIN_API_VERSION + 1))

    with pytest.raises(PluginError, match=f"targets plugin API {PLUGIN_API_VERSION + 1}"):
        install.install(str(folder), root)

    assert not root.exists()


def test_folder_without_a_manifest(root: Path, tmp_path: Path):
    with pytest.raises(PluginError, match="no manifest.json"):
        install.install(str(tmp_path), root)


def test_not_a_plugin_name(root: Path):
    with pytest.raises(PluginError, match="is not a plugin name"):
        install.install("Not A Plugin", root)


def test_update_skips_plugins_installed_from_a_folder(root: Path):
    install.install(str(FIXTURE), root)

    outcome, installed = install.update(PLUGIN_ID, root, install.PluginIndex())

    assert outcome.startswith(f"installed from {FIXTURE.resolve()}")
    assert installed is None


def test_remove_keeps_data_unless_purged(root: Path):
    install.install(str(FIXTURE), root)
    data = plugin_data_path(PLUGIN_ID)
    data.mkdir(parents=True)

    install.remove(PLUGIN_ID, root)
    assert not (root / PLUGIN_ID).exists()
    assert data.is_dir()

    install.install(str(FIXTURE), root)
    install.remove(PLUGIN_ID, root, purge_data=True)
    assert not data.exists()


def test_remove_a_plugin_that_is_not_installed(root: Path):
    with pytest.raises(PluginError, match="is not installed"):
        install.remove(PLUGIN_ID, root)


# --- yasbc plugin ----------------------------------------------------------------------


def test_cli_local_install_warns_and_lists(root: Path, capsys: pytest.CaptureFixture[str]):
    assert cli.run(["install", str(FIXTURE)]) == 0
    out = capsys.readouterr().out
    assert out == f"Installed {PLUGIN_ID} 1.0.0 by YASB.\n{Format.yellow}{UNREVIEWED}{Format.reset}\n"

    assert cli.run(["list"]) == 0
    assert f"{PLUGIN_ID}  1.0.0       local: {FIXTURE.resolve()}" in capsys.readouterr().out

    assert cli.run(["remove", PLUGIN_ID, "-y"]) == 0
    assert cli.run(["remove", PLUGIN_ID, "-y"]) == 1
    assert f'Error: Plugin "{PLUGIN_ID}" is not installed' in capsys.readouterr().err


def test_cli_install_leaves_the_config_alone(root: Path, config_home: Path):
    config = config_home / "config.yaml"
    config.write_text("# mine\nwidgets: {}\n", encoding="utf-8")

    assert cli.run(["install", str(FIXTURE)]) == 0

    assert config.read_text(encoding="utf-8") == "# mine\nwidgets: {}\n"


def test_cli_with_a_config_that_uses_the_plugin(root: Path, config_home: Path, capsys: pytest.CaptureFixture[str]):
    config = config_home / "config.yaml"
    text = f'bars:\n  main:\n    widgets:\n      left: ["greeting"]\nwidgets:\n  greeting:\n    type: "{WIDGET_TYPE}"\n'
    config.write_text(text, encoding="utf-8")

    assert cli.run(["install", str(FIXTURE)]) == 0
    assert "Run `yasbc reload` to load it." in capsys.readouterr().out

    assert cli.run(["remove", PLUGIN_ID, "-y"]) == 0
    assert "config.yaml still uses it (greeting). Remove it there" in capsys.readouterr().out
    assert config.read_text(encoding="utf-8") == text


def test_cli_official_install(root: Path, repo: FakeRepository, capsys: pytest.CaptureFixture[str]):
    repo.publish()

    assert cli.run(["install", PLUGIN_ID]) == 0
    out = capsys.readouterr().out
    assert UNREVIEWED not in out

    cli.run(["list"])
    assert f"{PLUGIN_ID}  1.0.0       official repository" in capsys.readouterr().out


def test_cli_github_install_asks_and_defaults_to_no(
    root: Path, repo: FakeRepository, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    repo.on_github(GITHUB_REPO)

    def press_enter(prompt: str) -> str:
        return ""

    monkeypatch.setattr("builtins.input", press_enter)

    assert cli.run(["install", f"github.com/{GITHUB_REPO}"]) == 1

    out = capsys.readouterr().out
    assert f"{PLUGIN_ID} 1.0.0 by YASB, from github.com/{GITHUB_REPO}" in out
    assert UNREVIEWED in out
    assert "Nothing was installed." in out
    assert not (root / PLUGIN_ID).exists()


def test_cli_github_install_with_yes(root: Path, repo: FakeRepository, capsys: pytest.CaptureFixture[str]):
    repo.on_github(GITHUB_REPO)

    assert cli.run(["install", f"github.com/{GITHUB_REPO}", "-y"]) == 0
    assert capsys.readouterr().out.count(UNREVIEWED) == 1

    cli.run(["list"])
    assert f"{PLUGIN_ID}  1.0.0       github.com/{GITHUB_REPO}" in capsys.readouterr().out


def test_cli_list_explains_skipped_plugins(root: Path, capsys: pytest.CaptureFixture[str]):
    install.install(str(FIXTURE), root)
    write_manifest(root / PLUGIN_ID, api="2")

    cli.run(["list"])

    assert f"{PLUGIN_ID}  skipped: it targets plugin API 2" in capsys.readouterr().out


def test_cli_search(repo: FakeRepository, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    repo.publish()
    lyrics = _version(tmp_path, "2.0.0")
    write_manifest(lyrics, id="lyrics", version="2.0.0", name="Lyrics", author="Rowan", description="Synced lyrics")
    repo.publish(lyrics, disabled=True)

    assert cli.run(["search", "rowan"]) == 0

    out = capsys.readouterr().out
    assert "lyrics  2.0.0  by Rowan  (temporarily disabled)\n    Synced lyrics" in out
    assert "hello" not in out


def test_cli_update_reports_each_plugin(root: Path, repo: FakeRepository, capsys: pytest.CaptureFixture[str]):
    repo.publish()
    install.install(PLUGIN_ID, root)

    assert cli.run(["update"]) == 0
    assert f"{PLUGIN_ID}: up to date (1.0.0)" in capsys.readouterr().out


def test_cli_update_of_local_plugins_needs_no_network(root: Path, repo: FakeRepository):
    install.install(str(FIXTURE), root)

    assert cli.run(["update"]) == 0
    assert repo.requests == []


def test_yasbc_routes_plugin_commands(tmp_path: Path):
    env = os.environ | {"YASB_CONFIG_HOME": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, str(SRC_ROOT / "cli.py"), "plugin", "path"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    assert result.stdout.strip() == str(tmp_path / "plugins")
