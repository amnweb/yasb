# pyright: reportPrivateUsage=false

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from urllib.parse import quote

import pytest
from winrt.windows.ui.notifications import UserNotification

from core.widgets.services.notifications import windows_notification
from core.widgets.services.notifications.windows_notification import (
    _find_image,
    _get_image_path,
    _get_xml_texts,
    _pop_toast,
    _read_items,
    _read_toast_xml,
)

CREATED = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def toast(content: str, **attributes: str) -> ET.Element:
    attrs = "".join(f' {name}="{value}"' for name, value in attributes.items())
    return ET.fromstring(f"<toast{attrs}><visual><binding template='ToastGeneric'>{content}</binding></visual></toast>")


def image(src: str) -> ET.Element:
    return ET.Element("image", src=src)


def src(element: ET.Element | None) -> str | None:
    return element.get("src") if element is not None else None


def use_history(monkeypatch: pytest.MonkeyPatch, history: dict[str, list[str | None]]):
    """Fake ToastNotificationManager.history; None is an entry Windows has emptied."""

    def entry(xml: str | None) -> SimpleNamespace:
        def get_xml() -> str:
            if xml is None:
                raise OSError("XML document must have a top level element.")
            return xml

        return SimpleNamespace(content=SimpleNamespace(get_xml=get_xml))

    def get_history_with_id(aumid: str) -> list[SimpleNamespace]:
        return [entry(xml) for xml in history.get(aumid, [])]

    manager = SimpleNamespace(history=SimpleNamespace(get_history_with_id=get_history_with_id))
    monkeypatch.setattr(windows_notification, "ToastNotificationManager", manager)


def notification(notification_id: int, aumid: str, texts: list[str], family: str = "") -> SimpleNamespace:
    binding = SimpleNamespace(get_text_elements=lambda: [SimpleNamespace(text=text) for text in texts])

    def get_binding(_kind: object) -> SimpleNamespace:
        return binding

    return SimpleNamespace(
        id=notification_id,
        creation_time=CREATED,
        app_info=SimpleNamespace(
            app_user_model_id=aumid,
            display_info=SimpleNamespace(display_name="Some App"),
            package_family_name=family,
        ),
        notification=SimpleNamespace(visual=SimpleNamespace(get_binding=get_binding)),
    )


def read_items(*notifications: object) -> list[windows_notification.NotificationItem]:
    return _read_items(cast(list[UserNotification], list(notifications)))


def test_xml_text_is_what_the_listener_returns():
    xml = toast(
        "<text>Title</text><text>Body</text><text placement='attribution'>via SMS</text>"
        "<group><subgroup><text>In a group</text></subgroup></group>"
    )
    assert _get_xml_texts(xml) == ["Title", "Body"]


def test_images_are_found_by_their_documented_placement():
    xml = toast(
        "<image src='logo' placement='appLogoOverride'/><image src='hero' placement='hero'/>"
        "<image src='inline'/><group><subgroup><image src='in a group'/></subgroup></group>"
    )
    assert src(_find_image(xml, "appLogoOverride")) == "logo"
    assert src(_find_image(xml, "hero")) == "hero"
    assert src(_find_image(xml, None)) == "inline"
    assert _find_image(toast("<text>No pictures</text>"), "hero") is None


def test_windows_8_image_templates_show_their_image_as_the_logo():
    xml = ET.fromstring(
        "<toast><visual><binding template='ToastImageAndText04'>"
        "<image id='1' src='icon'/><text id='1'>Title</text></binding></visual></toast>"
    )
    assert src(_find_image(xml, "appLogoOverride")) == "icon"
    assert _find_image(xml, None) is None
    assert _find_image(xml, "hero") is None


def test_a_blank_text_still_matches_its_toast(monkeypatch: pytest.MonkeyPatch):
    # Firefox writes an empty <text id="2">, the listener returns it as whitespace
    xml = toast("<text>Icon Notification</text><text></text>", launch="args")
    use_history(monkeypatch, {"app": [ET.tostring(xml, encoding="unicode")]})
    [item] = read_items(notification(1, "app", ["Icon Notification", "\n\t\t\t"]))
    assert (item.title, item.body, item.launch) == ("Icon Notification", "", "args")


def test_attribution_is_kept_apart_from_the_body(monkeypatch: pytest.MonkeyPatch):
    xml = toast("<text>Title</text><text>Body</text><text placement='attribution'> via www.youtube.com </text>")
    use_history(monkeypatch, {"app": [ET.tostring(xml, encoding="unicode")]})
    [item] = read_items(notification(1, "app", ["Title", "Body"]))
    assert (item.body, item.attribution) == ("Body", "via www.youtube.com")


def test_display_timestamp_replaces_the_arrival_time(monkeypatch: pytest.MonkeyPatch):
    sent = datetime(2026, 10, 23, 10, 0, tzinfo=UTC)
    toasts = [
        toast("<text>Utc</text>", displayTimestamp="2026-10-23T10:00:00Z"),
        toast("<text>Offset</text>", displayTimestamp="2026-10-23T12:00:00+02:00"),
        toast("<text>None</text>"),
    ]
    use_history(monkeypatch, {"app": [ET.tostring(t, encoding="unicode") for t in toasts]})
    items = read_items(
        notification(3, "app", ["Utc"]), notification(2, "app", ["Offset"]), notification(1, "app", ["None"])
    )
    assert [item.created_at for item in items] == [sent, sent, CREATED]


def test_toasts_with_the_same_text_are_matched_in_order():
    first, second = toast("<text>Hi</text>", launch="1"), toast("<text>Hi</text>", launch="2")
    toasts = [first, second]
    assert _pop_toast(toasts, ["Hi"]) is first
    assert _pop_toast(toasts, ["Hi"]) is second
    assert _pop_toast(toasts, ["Hi"]) is None


def test_history_skips_emptied_entries_and_stops_at_the_count(monkeypatch: pytest.MonkeyPatch):
    xml = "<toast><visual><binding><text>{}</text></binding></visual></toast>"
    use_history(monkeypatch, {"app": [xml.format(1), None, xml.format(2), xml.format(3), None]})
    assert [_get_xml_texts(t) for t in _read_toast_xml("app", 2)] == [["1"], ["2"]]
    assert _read_toast_xml("", 2) == []


def test_file_images_must_exist(tmp_path: Path):
    picture = tmp_path / "picture.png"
    picture.write_bytes(b"png")
    assert _get_image_path(image(picture.as_uri()), "app", "") == str(picture.resolve())
    assert _get_image_path(image((tmp_path / "missing.png").as_uri()), "app", "") == ""


def test_file_images_with_an_encoded_windows_path(tmp_path: Path):
    picture = tmp_path / "Screenshot 1.png"
    picture.write_bytes(b"png")
    assert _get_image_path(image("file:///" + quote(str(picture), safe="")), "app", "") == str(picture.resolve())


def test_file_images_with_a_plain_windows_path(tmp_path: Path):
    picture = tmp_path / "avatar.png"
    picture.write_bytes(b"png")
    assert _get_image_path(image(f"{tmp_path}/avatar.png"), "app", "") == str(picture.resolve())


@pytest.mark.parametrize(
    "source",
    [
        "file://server/share/picture.png",
        "file:///\\\\server\\share\\picture.png",
        "\\\\server\\share\\picture.png",
        "https://example.com/picture.png",
        "picture.png",
        "",
    ],
)
def test_web_share_and_relative_images_are_refused(source: str):
    assert _get_image_path(image(source), "app", "Family") == ""


def test_appdata_images_come_from_the_local_folder_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    local = tmp_path / "Packages" / "Family" / "LocalState"
    local.mkdir(parents=True)
    (local / "photo.png").write_bytes(b"png")
    (tmp_path / "secret.png").write_bytes(b"png")
    assert _get_image_path(image("ms-appdata:///local/photo.png"), "app", "Family") == str(
        (local / "photo.png").resolve()
    )
    assert _get_image_path(image("ms-appdata:///roaming/photo.png"), "app", "Family") == ""
    assert _get_image_path(image("ms-appdata:///local/../../../secret.png"), "app", "Family") == ""
    assert _get_image_path(image("ms-appdata:///local/photo.png"), "app", "") == ""


def test_package_images_stay_inside_the_install_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    install = tmp_path / "App_1.0"
    (install / "Assets").mkdir(parents=True)
    (install / "Assets" / "logo.png").write_bytes(b"png")
    (tmp_path / "outside.png").write_bytes(b"png")

    def get_install_folder(_aumid: str) -> Path:
        return install

    monkeypatch.setattr(windows_notification, "get_install_folder", get_install_folder)
    logo = str((install / "Assets" / "logo.png").resolve())
    assert _get_image_path(image("ms-appx:///Assets/logo.png"), "app", "Family") == logo
    assert _get_image_path(image("ms-appx:///../outside.png"), "app", "Family") == ""
    assert _get_image_path(image("ms-appx:///Assets/logo.png"), "app", "") == ""


def test_web_images_come_from_the_copy_windows_downloaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    wpnidm = tmp_path / "Microsoft" / "Windows" / "Notifications" / "wpnidm"
    wpnidm.mkdir(parents=True)
    (wpnidm / "photo.jpg").write_bytes(b"jpg")
    (tmp_path / "outside.jpg").write_bytes(b"jpg")
    downloads = {
        "https://cdn.example.com/photo.jpg?x=1": str(wpnidm / "photo.jpg"),
        "https://cdn.example.com/outside.jpg": str(tmp_path / "outside.jpg"),
    }

    def get_downloaded_image(url: str) -> str:
        return downloads.get(url, "")

    monkeypatch.setattr(windows_notification, "_get_downloaded_image", get_downloaded_image)
    photo = str((wpnidm / "photo.jpg").resolve())
    assert _get_image_path(image("https://cdn.example.com/photo.jpg?x=1"), "app", "") == photo
    assert _get_image_path(image("https://cdn.example.com/other.jpg"), "app", "") == ""
    assert _get_image_path(image("https://cdn.example.com/outside.jpg"), "app", "") == ""


def test_items_get_launch_and_images_from_their_own_toast(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"png")
    newest = (
        "<toast launch='https://example.com/2' activationType='protocol'><visual><binding>"
        f"<text>Hi</text><image placement='appLogoOverride' hint-crop='circle' src='{logo.as_uri()}'/>"
        "</binding></visual></toast>"
    )
    older = "<toast launch='args-1'><visual><binding><text>Hi</text></binding></visual></toast>"
    use_history(monkeypatch, {"app": [newest, older, None]})

    items = read_items(notification(2, "app", ["Hi"]), notification(1, "app", ["Hi"]))

    assert [(i.id, i.launch, i.activation_type) for i in items] == [
        (2, "https://example.com/2", "protocol"),
        (1, "args-1", "foreground"),
    ]
    assert (items[0].logo, items[0].logo_circle) == (str(logo.resolve()), True)
    assert (items[1].logo, items[1].logo_circle) == ("", False)


def test_first_text_is_the_title_and_the_rest_the_body(monkeypatch: pytest.MonkeyPatch):
    use_history(monkeypatch, {})
    [item] = read_items(notification(1, "app", ["Title", "Line 1", "Line 2"]))
    assert (item.title, item.body, item.app_name, item.created_at) == ("Title", "Line 1\nLine 2", "Some App", CREATED)
    assert (item.launch, item.activation_type) == ("", "foreground")


def test_a_sender_windows_cannot_name_still_shows(monkeypatch: pytest.MonkeyPatch):
    use_history(monkeypatch, {})

    class Nameless:
        id = 7
        creation_time = CREATED
        notification = notification(0, "", ["Hello"]).notification

        @property
        def app_info(self) -> SimpleNamespace:
            raise OSError("E_NOTIMPL")

    [item] = read_items(Nameless())
    assert (item.id, item.aumid, item.app_name, item.title) == (7, "", "", "Hello")
