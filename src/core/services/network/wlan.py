import logging
import re
from collections.abc import Callable
from ctypes import POINTER, addressof, byref, c_void_p, create_unicode_buffer
from ctypes.wintypes import DWORD, HANDLE, LPWSTR
from dataclasses import dataclass
from enum import StrEnum

from winrt.windows.devices.wifi import WiFiAdapter, WiFiAvailableNetwork, WiFiConnectionStatus, WiFiReconnectionKind
from winrt.windows.security.credentials import PasswordCredential

from core.utils.win32.bindings.wlanapi import (
    WlanCloseHandle,
    WlanDeleteProfile,
    WlanEnumInterfaces,
    WlanFreeMemory,
    WlanGetAvailableNetworkList,
    WlanGetProfile,
    WlanOpenHandle,
    WlanReasonCodeToString,
    WlanRegisterNotification,
    WlanScan,
    WlanSetProfile,
)
from core.utils.win32.constants import (
    ACCESS_DENIED,
    ERROR_NDIS_DOT11_POWER_STATE_INVALID,
    ERROR_SUCCESS,
    WLAN_AVAILABLE_NETWORK_CONNECTED,
    WLAN_AVAILABLE_NETWORK_HAS_PROFILE,
    WLAN_NOTIFICATION_SOURCE_ACM,
    WLAN_NOTIFICATION_SOURCE_NONE,
)
from core.utils.win32.error_check import format_error_message
from core.utils.win32.structs import (
    GUID,
    WLAN_AVAILABLE_NETWORK,
    WLAN_AVAILABLE_NETWORK_LIST,
    WLAN_INTERFACE_INFO,
    WLAN_INTERFACE_INFO_LIST,
    WLAN_NOTIFICATION_CALLBACK,
    WLAN_NOTIFICATION_DATA,
)
from core.utils.win32.typecheck import CPointer

logger = logging.getLogger("network")

CONNECTION_MODE = re.compile(r"<connectionMode>(.*?)</connectionMode>", re.IGNORECASE)


class ScanStatus(StrEnum):
    SUCCESS = "success"
    ACCESS_DENIED = "accessDenied"
    ADAPTER_OFF = "adapterOff"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass
class WifiNetwork:
    # "" for networks that hide their name
    ssid: str
    quality: int
    secured: bool
    connected: bool
    # The saved profile, "" when Windows has none
    profile: str = ""
    auto_connect: bool = False


def _ssid(network: WLAN_AVAILABLE_NETWORK) -> str:
    raw = bytes(network.dot11Ssid.ucSSID[: network.dot11Ssid.uSSIDLength])
    try:
        ssid = raw.decode("utf-8")
    except UnicodeDecodeError:
        ssid = raw.decode("latin-1", errors="replace")
    return ssid if ssid.strip() else ""


class WlanClient:
    """WLAN handle opened on demand. Use one worker thread; calls can block. Notifications run on a system thread and
    their data is only valid during the call."""

    def __init__(
        self,
        on_notification: Callable[[WLAN_NOTIFICATION_DATA], None] | None = None,
        source: int = WLAN_NOTIFICATION_SOURCE_ACM,
    ):
        self._handle = HANDLE()
        self._on_notification = on_notification
        self._source = source
        # Keep the callback alive while Windows may call it.
        self._callback = WLAN_NOTIFICATION_CALLBACK(self._notify) if on_notification else None
        # Windows accepted the notification registration; MSM needs location access.
        self.notifying = False

    def open(self) -> bool:
        if self._handle.value is not None:
            return True
        version = DWORD()
        result = WlanOpenHandle(2, None, byref(version), byref(self._handle))
        if result != ERROR_SUCCESS:
            self._handle = HANDLE()
            logger.debug("WLAN service unavailable: %s", format_error_message(result))
            return False
        if self._callback is not None:
            result = WlanRegisterNotification(self._handle, self._source, True, self._callback, None, None, None)
            self.notifying = result == ERROR_SUCCESS
            # Signal changes need location access, so Windows refusing them is expected.
            if result not in (ERROR_SUCCESS, ACCESS_DENIED):
                logger.debug("Could not register for WLAN notifications: %s", format_error_message(result))
        return True

    def close(self) -> None:
        if self._handle.value is None:
            return
        if self._callback is not None:
            WlanRegisterNotification(self._handle, WLAN_NOTIFICATION_SOURCE_NONE, True, None, None, None, None)
        # Wait for any in-progress notification callback.
        WlanCloseHandle(self._handle, None)
        self._handle = HANDLE()
        self.notifying = False

    def _notify(self, data: CPointer[WLAN_NOTIFICATION_DATA], _context: c_void_p) -> None:
        if self._on_notification is not None:
            self._on_notification(data.contents)

    def _interfaces(self) -> list[GUID]:
        pointer = POINTER(WLAN_INTERFACE_INFO_LIST)()
        result = WlanEnumInterfaces(self._handle, None, byref(pointer))
        if result != ERROR_SUCCESS:
            logger.debug("Could not list WLAN interfaces: %s", format_error_message(result))
            return []
        try:
            info = pointer.contents
            interfaces = (WLAN_INTERFACE_INFO * int(info.dwNumberOfItems)).from_address(addressof(info.InterfaceInfo))
            return [GUID.from_buffer_copy(interface.InterfaceGuid) for interface in interfaces]
        finally:
            WlanFreeMemory(pointer)

    def scan(self) -> ScanStatus:
        """Ask every adapter to scan; SCAN_COMPLETE or SCAN_FAIL follows."""
        if not self.open():
            return ScanStatus.UNAVAILABLE
        interfaces = self._interfaces()
        if not interfaces:
            return ScanStatus.UNAVAILABLE
        for interface in interfaces:
            result = WlanScan(self._handle, byref(interface), None, None, None)
            if result == ERROR_SUCCESS:
                continue
            if result == ACCESS_DENIED:
                return ScanStatus.ACCESS_DENIED
            if result == ERROR_NDIS_DOT11_POWER_STATE_INVALID:
                return ScanStatus.ADAPTER_OFF
            logger.debug("Could not scan for Wi-Fi networks: %s", format_error_message(result))
            return ScanStatus.ERROR
        return ScanStatus.SUCCESS

    def _available(self, interface: GUID) -> list[WLAN_AVAILABLE_NETWORK]:
        """Copies of the latest scan results on an interface; empty when Windows refuses, as without location access."""
        pointer = POINTER(WLAN_AVAILABLE_NETWORK_LIST)()
        result = WlanGetAvailableNetworkList(self._handle, byref(interface), 0, None, byref(pointer))
        if result != ERROR_SUCCESS:
            # Without location access or with the radio off, Windows refuses; the scan reports both.
            if result not in (ACCESS_DENIED, ERROR_NDIS_DOT11_POWER_STATE_INVALID):
                logger.debug("Could not list Wi-Fi networks: %s", format_error_message(result))
            return []
        try:
            listing = pointer.contents
            entries = (WLAN_AVAILABLE_NETWORK * int(listing.dwNumberOfItems)).from_address(addressof(listing.Network))
            return [WLAN_AVAILABLE_NETWORK.from_buffer_copy(entry) for entry in entries]
        finally:
            WlanFreeMemory(pointer)

    def networks(self, profiles: bool = True) -> list[WifiNetwork]:
        """Return the latest scan results by SSID, optionally reading auto-connect settings."""
        if not self.open():
            return []
        found: dict[str, WifiNetwork] = {}
        for interface in self._interfaces():
            for entry in self._available(interface):
                self._add(found, interface, entry, profiles)
        return list(found.values())

    def connected_qualities(self) -> dict[str, int]:
        """The signal quality of each interface's connected network, by interface id."""
        if not self.open():
            return {}
        qualities: dict[str, int] = {}
        for interface in self._interfaces():
            entries = self._available(interface)
            quality = next(
                (int(entry.wlanSignalQuality) for entry in entries if entry.dwFlags & WLAN_AVAILABLE_NETWORK_CONNECTED),
                None,
            )
            if quality is not None:
                qualities[str(interface.to_uuid())] = quality
        return qualities

    def _add(
        self, found: dict[str, WifiNetwork], interface: GUID, entry: WLAN_AVAILABLE_NETWORK, profiles: bool
    ) -> None:
        # Windows lists a network once per saved profile and once without a profile.
        ssid = _ssid(entry)
        connected = bool(entry.dwFlags & WLAN_AVAILABLE_NETWORK_CONNECTED)
        profile = entry.strProfileName if entry.dwFlags & WLAN_AVAILABLE_NETWORK_HAS_PROFILE else ""
        network = found.setdefault(ssid, WifiNetwork(ssid, 0, False, False))
        network.quality = max(network.quality, int(entry.wlanSignalQuality))
        network.secured = network.secured or bool(entry.bSecurityEnabled)
        if profile and (connected or not network.profile):
            network.profile = profile
            network.auto_connect = profiles and self._auto_connect(interface, profile)
        network.connected = network.connected or connected

    def _profile_xml(self, interface: GUID, profile: str) -> str:
        xml = LPWSTR()
        result = WlanGetProfile(self._handle, byref(interface), profile, None, byref(xml), None, None)
        try:
            return (xml.value or "") if result == ERROR_SUCCESS else ""
        finally:
            if xml:
                WlanFreeMemory(xml)

    def _auto_connect(self, interface: GUID, profile: str) -> bool:
        match = CONNECTION_MODE.search(self._profile_xml(interface, profile))
        return match is None or match.group(1).lower() == "auto"

    def forget(self, profile: str) -> None:
        if not self.open():
            return
        for interface in self._interfaces():
            result = WlanDeleteProfile(self._handle, byref(interface), profile, None)
            if result != ERROR_SUCCESS:
                logger.debug("Could not forget the network: %s", format_error_message(result))

    def set_auto_connect(self, profile: str, auto_connect: bool) -> None:
        if not self.open():
            return
        mode = f"<connectionMode>{'auto' if auto_connect else 'manual'}</connectionMode>"
        for interface in self._interfaces():
            xml = self._profile_xml(interface, profile)
            if not xml:
                continue
            reason = DWORD()
            result = WlanSetProfile(
                self._handle, byref(interface), 0, CONNECTION_MODE.sub(mode, xml), None, True, None, byref(reason)
            )
            if result != ERROR_SUCCESS:
                text = create_unicode_buffer(256)
                WlanReasonCodeToString(reason.value, len(text), text, None)
                logger.debug("Could not change the profile: %s", text.value)


def _adapter() -> WiFiAdapter | None:
    adapters = WiFiAdapter.find_all_adapters_async().get()
    return adapters[0] if adapters else None


def _find(adapter: WiFiAdapter, ssid: str) -> WiFiAvailableNetwork | None:
    return next((network for network in adapter.network_report.available_networks if network.ssid == ssid), None)


def connect(ssid: str, password: str, auto_connect: bool, hidden: bool = False) -> WiFiConnectionStatus:
    """Connect using the password, or a saved profile if empty. Wait for Windows to respond."""
    adapter = _adapter()
    if adapter is None:
        return WiFiConnectionStatus.NETWORK_NOT_AVAILABLE
    # Find hidden networks by empty SSID, then connect using the entered SSID.
    network = _find(adapter, "" if hidden else ssid)
    if network is None:
        adapter.scan_async().get()
        network = _find(adapter, "" if hidden else ssid)
    if network is None:
        return WiFiConnectionStatus.NETWORK_NOT_AVAILABLE
    kind = WiFiReconnectionKind.AUTOMATIC if auto_connect else WiFiReconnectionKind.MANUAL
    credential = PasswordCredential()
    if password:
        credential.password = password
    if hidden:
        result = adapter.connect_async(network, kind, credential, ssid).get()
    elif password:
        result = adapter.connect_async(network, kind, credential).get()
    else:
        result = adapter.connect_async(network, kind).get()
    return result.connection_status


def disconnect() -> None:
    if (adapter := _adapter()) is not None:
        adapter.disconnect()
