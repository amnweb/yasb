"""Toast images, read from the Windows notification database.

The listener hands out only the text elements of a toast, so the images a notification
carries cannot be reached through it. Windows itself keeps the raw toast XML in a SQLite
database of its own, and the images it draws are local files referenced from that payload.
This module reads the payload and turns those references into file paths. A source Windows
had to fetch over the network is looked up in the record it keeps of its own downloads, so
nothing here goes to the network either. It never decodes an image: that is the GUI thread's
job, the same way app icons are already handled.

A picture is copied aside the first time it is seen, because the file the payload points at
usually does not last as long as the notification does.
"""

import hashlib
import logging
import os
import shutil
import sqlite3
import winreg
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from core.utils.system import app_data_path
from core.utils.win32.packages import installed_path, package_family_name

_LOCAL_APP_DATA = Path(os.environ.get("LOCALAPPDATA", ""))
NOTIFICATION_DATABASE = _LOCAL_APP_DATA / "Microsoft" / "Windows" / "Notifications" / "wpndatabase.db"
# Windows keeps the database open, so it is only ever opened read-only and released again
CONNECT_TIMEOUT = 0.5
# Toast images are small by design, anything past this is decoding cost with nothing to show
MAX_IMAGE_BYTES = 8 * 1024 * 1024
# Smaller than the header of any image format, so the file cannot be one
MIN_IMAGE_BYTES = 32
# ms-appdata:///<root>/ names the per package folders that live under LOCALAPPDATA\Packages
APPDATA_ROOTS = {"local": "LocalState", "roaming": "RoamingState", "temp": "TempState"}
# Packaged resources are stored per display scale, so the plain name is often missing
SCALE_QUALIFIERS = ("", ".scale-200", ".scale-100", ".scale-150", ".scale-400")
# Windows notes every toast image it downloads here, which is what makes a remote source
# reachable without asking the network for it a second time
DOWNLOAD_RECORD = r"Software\Microsoft\Windows\CurrentVersion\PushNotifications\wpnidm"
DOWNLOAD_URL_PREFIX = "wpnidm:"
# Where the copies live. A notification outlives the file it was drawn from, so this is
# what the menu actually reads once the sender has cleaned up after itself
CACHE_DIRECTORY = "notification_images"
# Enough of the source to tell two pictures of the same notification apart
SOURCE_KEY_LENGTH = 12

# (registry write time, url -> file), rebuilt only once Windows has touched the record
_downloads: tuple[int, dict[str, str]] | None = None
# The kept copies whose notification was missing from the last read, see _prune_kept
_missing: set[str] = set()


@dataclass(frozen=True, slots=True)
class ToastImages:
    """The images of a single toast, as local file paths.

    Plain types only: these travel from the listener thread to the GUI thread, like the
    notification they belong to.
    """

    app_logo: str = ""  # placement="appLogoOverride"
    app_logo_circle: bool = False  # hint-crop="circle"
    hero: str = ""  # placement="hero"
    inline: tuple[str, ...] = ()  # everything else, in payload order


@dataclass(frozen=True, slots=True)
class ToastPayload:
    """What one stored toast payload says, beyond the text the listener already hands out."""

    images: ToastImages = ToastImages()
    launch: str = ""  # What the shell hands the sender when the notification is clicked
    activation_type: str = ""  # How it is handed over: protocol, foreground, background


@dataclass(frozen=True, slots=True)
class ToastDetails:
    """What the database holds for one toast on top of the text the listener hands out."""

    images: ToastImages = ToastImages()
    # How the database spells the sender, together with the name and icon Windows heads it
    # with. A browser files one sender per website, which is the grouping the Notification
    # Center shows and the only place a site's own name and icon are to be had
    sender: str = ""
    sender_name: str = ""
    sender_icon: str = ""
    launch: str = ""
    activation_type: str = ""


def read_toast_details(senders: dict[int, str]) -> dict[int, ToastDetails]:
    """Return what the database holds for the given notifications, keyed by notification id.

    `senders` maps a notification id to the AUMID that sent it, which is needed both to
    resolve package relative sources and to confirm the row is the notification we asked
    for. Notifications the database has no row for are left out of the result.
    """
    # Before anything else, so an emptied Notification Center takes the copies with it
    _prune_kept(senders)
    if not senders or not NOTIFICATION_DATABASE.is_file():
        return {}

    try:
        rows = _read_payloads(list(senders))
    except (sqlite3.Error, OSError) as e:
        logging.debug("Failed to read the notification database: %s", e)
        return {}

    details: dict[int, ToastDetails] = {}
    for notification_id, payload, primary_id, sender_icon, sender_name in rows:
        aumid = senders.get(notification_id, "")
        # The id is the only link between the listener and the database, so a row whose
        # sender disagrees is treated as somebody else's notification rather than trusted
        if aumid and primary_id and not _same_sender(aumid, primary_id):
            logging.debug("Notification %s is held for %s, not %s", notification_id, primary_id, aumid)
            continue
        parsed = _parse_payload(payload, aumid, notification_id)
        details[notification_id] = ToastDetails(
            parsed.images,
            primary_id,
            sender_name,
            # The picture in the payload is written by the sender and often deleted once
            # the toast has been drawn, while this one is kept by Windows for as long as
            # the sender is registered. It is what the Notification Center heads a website
            # with, and what is left once the sender has cleaned up after itself
            _resolve_src(sender_icon, primary_id or aumid) if sender_icon else "",
            parsed.launch,
            parsed.activation_type,
        )
    return details


def _same_sender(aumid: str, primary_id: str) -> bool:
    """Whether a stored row belongs to the sender the listener named.

    The two do not always spell it the same way. A browser files a website's notifications
    under an identifier of its own for that site, while the listener reports them as coming
    from the browser, so the names agree only as far as the package they share.
    """
    if aumid.casefold() == primary_id.casefold():
        return True
    family_name = package_family_name(aumid)
    return bool(family_name) and family_name.casefold() == package_family_name(primary_id).casefold()


def _read_payloads(notification_ids: list[int]) -> list[tuple[int, bytes, str, str, str]]:
    """Read the stored payloads in one query, without taking a write lock on the database.

    What Windows registered for the sender comes along with them. The icon is one a browser
    registers per website, and it outlives the picture the toast itself points at; the name
    is the one the Notification Center heads the group with, which is worth having for a
    sender the listener will not name.
    """
    placeholders = ",".join("?" * len(notification_ids))
    query = (
        "SELECT n.Id, n.Payload, h.PrimaryId, "
        "MAX(CASE WHEN a.AssetKey = 'IconUri' THEN a.AssetValue END), "
        "MAX(CASE WHEN a.AssetKey = 'DisplayName' THEN a.AssetValue END) "
        "FROM Notification n "
        "LEFT JOIN NotificationHandler h ON h.RecordId = n.HandlerId "
        "LEFT JOIN HandlerAssets a ON a.HandlerId = h.RecordId "
        f"WHERE n.Type = 'toast' AND n.PayloadType = 'Xml' AND n.Id IN ({placeholders}) "
        "GROUP BY n.Id"
    )
    uri = f"file:{quote(NOTIFICATION_DATABASE.as_posix())}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=CONNECT_TIMEOUT)
    try:
        return [
            (row[0], row[1], row[2] or "", row[3] or "", row[4] or "")
            for row in connection.execute(query, notification_ids)
        ]
    finally:
        connection.close()


def _parse_payload(payload: bytes | str, aumid: str, notification_id: int) -> ToastPayload:
    """Pull the images and the launch string out of a toast payload.

    Only the first image of each placement is kept, which is the one Windows draws.
    """
    try:
        root = ET.fromstring(payload.decode("utf-8") if isinstance(payload, bytes) else payload)
    except (ET.ParseError, UnicodeDecodeError, TypeError) as e:
        logging.debug("Unreadable toast payload: %s", e)
        return ToastPayload()

    app_logo = ""
    app_logo_circle = False
    hero = ""
    inline: list[str] = []

    for element in root.iter("image"):
        src = element.get("src", "")
        placement = (element.get("placement") or "").casefold()
        if placement == "applogooverride":
            if app_logo:
                continue
            role = "logo"
        elif placement == "hero":
            if hero:
                continue
            role = "hero"
        else:
            role = f"inline{len(inline)}"

        path = _keep(notification_id, role, src, _resolve_src(src, aumid))
        if not path:
            # Worth saying out loud: this is a picture Windows goes on showing and the menu
            # cannot, because the file the sender named was gone before it could be copied
            logging.debug("Notification %s has no readable %s image at %s", notification_id, role, src)
            continue
        if role == "logo":
            app_logo = path
            app_logo_circle = (element.get("hint-crop") or "").casefold() == "circle"
        elif role == "hero":
            hero = path
        else:
            inline.append(path)

    return ToastPayload(
        ToastImages(app_logo, app_logo_circle, hero, tuple(inline)),
        (root.get("launch") or "").strip(),
        (root.get("activationType") or "").strip(),
    )


def _keep(notification_id: int, role: str, src: str, resolved: str) -> str:
    """The copy of a toast image kept for as long as the notification is there.

    The file a payload points at belongs to the sender and is normally deleted as soon as
    the toast has been drawn: a browser writes the picture a website asked for into a
    temporary file and clears it out within seconds, while the notification itself sits in
    the Notification Center for as long as nobody dismisses it. Reading the payload again
    later then finds nothing, and the item silently drops to whatever the fallbacks can
    offer, which is not the picture Windows goes on showing.

    So the first read takes a copy and every read after it is served from that copy. The
    copies are named after the notification and the source they were taken from, and the
    ones whose notification has gone are deleted, which keeps this bounded by what the
    Notification Center itself holds.
    """
    kept = _kept_path(notification_id, role, src, resolved)
    if kept is None:
        return resolved
    if kept.is_file():
        return str(kept)
    if not resolved:
        return ""
    try:
        shutil.copyfile(resolved, kept)
    except OSError as e:
        logging.debug("Failed to keep a copy of %s: %s", resolved, e)
        return resolved
    return str(kept)


def _kept_path(notification_id: int, role: str, src: str, resolved: str) -> Path | None:
    """Where the copy of one image of one notification belongs, or None with nowhere to put it."""
    if not src:
        return None
    try:
        directory = app_data_path(CACHE_DIRECTORY)
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logging.debug("No place to keep toast images: %s", e)
        return None
    # The suffix is only there to keep the folder readable, nothing opens these by name
    suffix = Path(resolved or src).suffix[:8]
    source_key = hashlib.sha1(src.encode("utf-8", "replace")).hexdigest()[:SOURCE_KEY_LENGTH]
    return directory / f"{notification_id}-{role}-{source_key}{suffix}"


def _prune_kept(senders: dict[int, str]) -> None:
    """Drop the copies of notifications that are no longer in the Notification Center.

    A copy goes once its notification has been missing from two reads in a row rather than
    from one. The copy is all that is left of the picture, so a single read that comes back
    short must not be able to take it for good: if the next read brings the notification
    back, the copy is still there to be drawn. A notification that has really gone is still
    missing the next time, which is soon, since opening the menu is itself a read.
    """
    global _missing
    missing: set[str] = set()
    try:
        directory = app_data_path(CACHE_DIRECTORY)
        if not directory.is_dir():
            return
        for kept in directory.iterdir():
            notification_id, _, _ = kept.name.partition("-")
            if notification_id.isdigit() and int(notification_id) in senders:
                continue
            if kept.name not in _missing:
                missing.add(kept.name)
                continue
            try:
                kept.unlink()
            except OSError as e:
                logging.debug("Failed to drop the kept copy %s: %s", kept.name, e)
    except OSError as e:
        logging.debug("Failed to go through the kept toast images: %s", e)
    _missing = missing


def _resolve_src(src: str, aumid: str) -> str:
    """Turn the src of a toast image into a local file path, or an empty string if it has none."""
    src = src.strip()
    scheme = src.split(":", 1)[0].casefold() if ":" in src else ""

    if not src:
        return ""
    if scheme in ("http", "https"):
        return _resolve_downloaded(src)
    if scheme == "file":
        return _verify(_file_url_to_path(src))
    if scheme == "ms-appdata":
        return _resolve_appdata(src, aumid)
    if scheme == "ms-appx":
        return _resolve_appx(src, aumid)
    return _verify(Path(os.path.expandvars(src)))


def _file_url_to_path(src: str) -> Path:
    """Turn a file: url into a path, whichever way the sender happened to write it.

    Senders are not consistent about this. A screenshot tool writes the separators as
    backslashes and percent encodes them along with the colon after the drive letter, which
    the standard conversion does not recognise as a drive at all and turns into a path that
    cannot be opened.
    """
    parsed = urlparse(src)
    path = unquote(parsed.path).replace("\\", "/")
    if parsed.netloc:
        return Path(f"//{parsed.netloc}{path}")
    # A drive letter arrives as /C:/..., which is not a path until the leading slash goes
    if len(path) > 2 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    return Path(path)


def _resolve_appdata(src: str, aumid: str) -> str:
    """Resolve ms-appdata:///local/... against the sending package's own data folder."""
    family_name = package_family_name(aumid)
    if not family_name or not _LOCAL_APP_DATA.name:
        return ""

    root_name, _, relative = urlparse(src).path.lstrip("/").partition("/")
    folder = APPDATA_ROOTS.get(root_name.casefold())
    if not folder or not relative:
        return ""

    root = _LOCAL_APP_DATA / "Packages" / family_name / folder
    return _verify(root / unquote(relative), root)


def _resolve_appx(src: str, aumid: str) -> str:
    """Resolve ms-appx:///Assets/... against the sending package's install folder."""
    root = installed_path(package_family_name(aumid))
    relative = unquote(urlparse(src).path.lstrip("/"))
    if root is None or not relative:
        return ""

    candidate = root / relative
    for qualifier in SCALE_QUALIFIERS:
        path = candidate if not qualifier else candidate.with_name(f"{candidate.stem}{qualifier}{candidate.suffix}")
        verified = _verify(path, root)
        if verified:
            return verified
    return ""


def _resolve_downloaded(url: str) -> str:
    """Find the copy Windows downloaded for a remote source, without fetching it again.

    Messaging apps send the sender's picture as an https URL, so this is the difference
    between showing a contact photo and showing the app icon. Windows has already fetched
    it to draw the toast, and notes where it put it. YASB never asks the network itself:
    requesting one of these would tell the sender when the menu was opened.
    """
    cached = _read_download_record().get(url, "")
    return _verify(Path(cached)) if cached else ""


def _read_download_record() -> dict[str, str]:
    """The url to file map Windows keeps, re-read only when it has changed."""
    global _downloads
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, DOWNLOAD_RECORD) as key:
            entries, _, written = winreg.QueryInfoKey(key)
            if _downloads is None or _downloads[0] != written:
                _downloads = (written, _read_download_entries(key, entries))
    except OSError as e:
        logging.debug("No record of downloaded toast images: %s", e)
        return {}
    return _downloads[1]


def _read_download_entries(key: winreg.HKEYType, entries: int) -> dict[str, str]:
    downloads: dict[str, str] = {}
    for index in range(entries):
        try:
            with winreg.OpenKey(key, winreg.EnumKey(key, index)) as entry:
                url = str(winreg.QueryValueEx(entry, "Url")[0])
                path = str(winreg.QueryValueEx(entry, "LocalPath")[0])
        except OSError:
            # An entry can be dropped while it is being enumerated, the rest are still good
            continue
        url = url.removeprefix(DOWNLOAD_URL_PREFIX)
        if url and path:
            downloads[url] = path
    return downloads


def _verify(path: Path, root: Path | None = None) -> str:
    """Accept a path only if it points at a readable file sized like a toast image.

    A package relative source is checked against the folder it was resolved from as well,
    since the payload is written by the sending app and can walk out of it.
    """
    # A network share is refused before it is touched: resolving one is already a request
    # to that host, and one that offers it the user's credentials. What Windows downloads
    # or keeps for a toast is always on a local drive, so only a payload written to make
    # the menu reach out would name one
    if path.drive.startswith(("\\\\", "//")):
        logging.debug("Toast image is on a network path: %s", path)
        return ""
    try:
        resolved = path.resolve()
        if root is not None and not resolved.is_relative_to(root.resolve()):
            logging.debug("Toast image escapes its package folder: %s", path)
            return ""
        # A missing file is the normal case here, senders clean their temporary images up,
        # and one caught mid-cleanup is empty rather than gone. Both count as no image, so
        # whatever the caller would fall back to is used instead of a failed decode
        if not resolved.is_file() or not MIN_IMAGE_BYTES <= resolved.stat().st_size <= MAX_IMAGE_BYTES:
            return ""
    except (OSError, ValueError) as e:
        logging.debug("Unusable toast image path: %s", e)
        return ""
    return str(resolved)
