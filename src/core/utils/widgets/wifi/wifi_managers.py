import ctypes as ct
import logging
import re
import threading
from ctypes import (
    POINTER,
    Array,
    WinError,
    addressof,
    byref,
    c_void_p,
    create_unicode_buffer,
    sizeof,
)
from ctypes.wintypes import DWORD, HANDLE, LPWSTR
from dataclasses import dataclass
from enum import IntFlag, StrEnum, auto

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from winrt.windows.devices.wifi import (
    WiFiAdapter,
    WiFiConnectionStatus,
    WiFiNetworkReport,
    WiFiReconnectionKind,
)
from winrt.windows.security.credentials import PasswordCredential

from core.utils.win32.bindings import (
    WlanCloseHandle,
    WlanEnumInterfaces,
    WlanFreeMemory,
    WlanGetAvailableNetworkList,
    WlanOpenHandle,
    WlanQueryInterface,
    WlanReasonCodeToString,
    WlanScan,
    WlanSetProfile,
)
from core.utils.win32.bindings.wlanapi import (
    WlanDeleteProfile,
    WlanGetProfile,
    WlanRegisterNotification,
)
from core.utils.win32.constants import (
    ACCESS_DENIED,
    ERROR_NDIS_DOT11_POWER_STATE_INVALID,
    ERROR_NOT_FOUND,
    ERROR_SUCCESS,
    WLAN_AVAILABLE_NETWORK_CONNECTED,
    WLAN_AVAILABLE_NETWORK_HAS_PROFILE,
    WLAN_INTERFACE_STATE_CONNECTED,
    WLAN_INTF_OPCODE_CURRENT_CONNECTION,
    WLAN_NOTIFICATION_SOURCE_ACM,
    WLAN_NOTIFICATION_SOURCE_NONE,
    WlanNotificationAcm,
)
from core.utils.win32.error_check import format_error_message
from core.utils.win32.structs import (
    GUID,
    WLAN_AVAILABLE_NETWORK,
    WLAN_AVAILABLE_NETWORK_LIST,
    WLAN_CONNECTION_NOTIFICATION_DATA,
    WLAN_INTERFACE_INFO,
    WLAN_INTERFACE_INFO_LIST,
    WLAN_NOTIFICATION_CALLBACK,
    WLAN_NOTIFICATION_DATA,
)
from core.utils.win32.typecheck import CPointer

logger = logging.getLogger("wifi_widget")


class WifiState(IntFlag):
    CONNECTED = auto()
    SECURED = auto()
    UNSECURED = auto()


class ScanResultStatus(StrEnum):
    SUCCESS = "Success"
    ACCESS_DENIED = "Access Denied"
    POWER_STATE_INVALID = "Power State Invalid"
    ERROR = "Error"


@dataclass
class NetworkInfo:
    ssid: str = ""
    quality: int = 0
    icon: str = ""
    state: WifiState = WifiState.UNSECURED
    auth_alg: int = 0
    profile_exists: bool = False
    auto_connect: bool = False


class WiFiConnectWorker(QThread):
    """WiFi connect worker"""

    result = pyqtSignal(WiFiConnectionStatus, str, NetworkInfo)
    error = pyqtSignal(str)

    def __init__(self, network_info: NetworkInfo, ssid: str, password: str, hidden_ssid: bool):
        super().__init__()
        self.network_info = network_info
        self.ssid = ssid
        self.password = password
        self.hidden_ssid = hidden_ssid
        threading.current_thread().name = "WiFiConnectWorker"

    def run(self):
        """Run the worker"""
        try:
            result = self._connect()
            self.result.emit(result, self.ssid, self.network_info)
        except Exception as e:
            self.error.emit(str(e))

    def _connect(self) -> WiFiConnectionStatus:
        """Connect to the WiFi network"""
        adapters = WiFiAdapter.find_all_adapters_async().get()
        if not adapters:
            raise RuntimeError("No WiFi adapter found.")
        adapter = adapters[0]
        report: WiFiNetworkReport = adapter.network_report
        reconnection_kind = (
            WiFiReconnectionKind.AUTOMATIC if self.network_info.auto_connect else WiFiReconnectionKind.MANUAL
        )
        if not self.hidden_ssid:
            return self._connect_visible(adapter, report, reconnection_kind)
        else:
            return self._connect_hidden(adapter, report, reconnection_kind)

    def _connect_visible(
        self, adapter: WiFiAdapter, report: WiFiNetworkReport, reconnect_kind: WiFiReconnectionKind
    ) -> WiFiConnectionStatus:
        """Connect to a visible WiFi network"""
        for network in report.available_networks:
            if network.ssid == self.ssid:
                if self.password:
                    cred = PasswordCredential()
                    cred.password = self.password
                    result = adapter.connect_with_password_credential_async(network, reconnect_kind, cred).get()
                else:
                    result = adapter.connect_async(network, reconnect_kind).get()
                return result.connection_status
        raise RuntimeError("Selected network not found after scan.")

    def _connect_hidden(
        self, adapter: WiFiAdapter, report: WiFiNetworkReport, reconnect_kind: WiFiReconnectionKind
    ) -> WiFiConnectionStatus:
        """Connect to a hidden WiFi network"""
        for network in report.available_networks:
            if not network.ssid:
                # Use the first hidden network as a template
                hidden_network = network
                break
        else:
            raise RuntimeError("No hidden network found after scan.")
        cred = PasswordCredential()
        cred.password = self.password
        # Use the connect_with_password_credential_and_ssid_async method
        result = adapter.connect_with_password_credential_and_ssid_async(
            hidden_network, reconnect_kind, cred, self.ssid
        ).get()
        return result.connection_status


class WifiDisconnectWorker(QThread):
    """Worker for disconnecting from Wi-Fi"""

    result = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        adapters = WiFiAdapter.find_all_adapters_async().get()
        if not adapters:
            raise RuntimeError("No WiFi adapter found.")
        adapter = adapters[0]
        adapter.disconnect()


class WiFiManager(QObject):
    """WiFi manager that holds scanning, notification and profile management logic"""

    wifi_scan_completed = pyqtSignal(ScanResultStatus, list)
    wifi_disconnected = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.wifi_updates_enabled = False  # Whether to get wifi scan results

        self._is_scanning = False
        self._is_connecting = False
        self._client_handle = HANDLE()
        self._negotiated_version = DWORD()
        self._interface_list_ptr = POINTER(WLAN_INTERFACE_INFO_LIST)()
        self._interfaces: list[WLAN_INTERFACE_INFO] = []
        self._notification_callback = WLAN_NOTIFICATION_CALLBACK(self._on_wlan_notification)

    def init_wlan(self):
        """Open the WLAN handle and register notification callback"""
        if self._client_handle.value is not None:
            self.uninit_wlan()
        result = WlanOpenHandle(2, None, byref(self._negotiated_version), byref(self._client_handle))
        if result != ERROR_SUCCESS:
            raise WinError(result)

        result = WlanRegisterNotification(
            self._client_handle,
            WLAN_NOTIFICATION_SOURCE_ACM,
            True,
            self._notification_callback,
            None,
            None,
            None,
        )
        if result != ERROR_SUCCESS:
            self.uninit_wlan()
            raise WinError(result)

    def uninit_wlan(self):
        """Clean up resources by closing the WLAN handle and unregistering the notification callback"""
        if self._client_handle:
            # Unregister notification callback
            result = WlanRegisterNotification(
                self._client_handle,
                WLAN_NOTIFICATION_SOURCE_NONE,
                True,
                None,
                None,
                None,
                None,
            )
            if result != ERROR_SUCCESS:
                raise WinError(result)
            WlanCloseHandle(self._client_handle, None)
            self._client_handle = HANDLE()

    def scan_available_networks(self):
        """Scan available WiFi networks"""
        if self._is_scanning:
            return
        self._is_scanning = True
        self.init_wlan()
        # Force a new scan on all interfaces
        interfaces_ptr, interfaces = self._get_interface_list()
        for interface in interfaces:
            result = WlanScan(self._client_handle, byref(interface.InterfaceGuid), None, None, None)
            if result != ERROR_SUCCESS:
                self._is_scanning = False
                logger.error(f"Error scanning for WiFi networks: {format_error_message(result)}")
                if result == ACCESS_DENIED:
                    self.wifi_scan_completed.emit(ScanResultStatus.ACCESS_DENIED, [])
                elif result == ERROR_NDIS_DOT11_POWER_STATE_INVALID:
                    self.wifi_scan_completed.emit(ScanResultStatus.POWER_STATE_INVALID, [])
                else:
                    self.wifi_scan_completed.emit(ScanResultStatus.ERROR, [])
                return
            logger.debug("Scanning for WiFi networks...")
        WlanFreeMemory(interfaces_ptr)

    def get_current_connection(self) -> NetworkInfo | None:
        """Get the current WiFi connection"""
        self.init_wlan()
        interfaces_ptr, interfaces = self._get_interface_list()
        network_info: NetworkInfo | None = None
        for interface in interfaces:
            # Query interface for current connection
            data_size = DWORD()
            data_ptr = c_void_p()
            opcode_value_type = DWORD()
            result = WlanQueryInterface(
                self._client_handle,
                byref(interface.InterfaceGuid),
                WLAN_INTF_OPCODE_CURRENT_CONNECTION,
                None,
                byref(data_size),
                byref(data_ptr),
                byref(opcode_value_type),
            )

            if result != ERROR_SUCCESS:
                return None
            try:
                network_list_ptr = POINTER(WLAN_AVAILABLE_NETWORK_LIST)()
                result = WlanGetAvailableNetworkList(
                    self._client_handle,
                    byref(interface.InterfaceGuid),
                    0,
                    None,
                    byref(network_list_ptr),
                )
                if result != ERROR_SUCCESS:
                    return None
                try:
                    network_info = self._find_connected_network_info(network_list_ptr, interface.InterfaceGuid)
                finally:
                    WlanFreeMemory(network_list_ptr)
            finally:
                if data_ptr:
                    WlanFreeMemory(data_ptr)
        if interfaces_ptr:
            WlanFreeMemory(interfaces_ptr)

        return network_info

    def get_available_networks(self):
        """Get available WiFi networks"""
        interfaces_ptr, interfaces = self._get_interface_list()
        networks_info: list[NetworkInfo] = []
        # Get network list from all interfaces
        for interface in interfaces:
            network_list_ptr = POINTER(WLAN_AVAILABLE_NETWORK_LIST)()
            result = WlanGetAvailableNetworkList(
                self._client_handle,
                byref(interface.InterfaceGuid),
                0,
                None,
                byref(network_list_ptr),
            )
            if result != ERROR_SUCCESS:
                logger.error(f"Error getting available networks: {result}")
                continue
            network_list = network_list_ptr.contents
            networks = (WLAN_AVAILABLE_NETWORK * int(network_list.dwNumberOfItems)).from_address(
                addressof(network_list.Network)
            )
            for network in networks:
                ssid = network.dot11Ssid
                ssid_bytes = bytes(ssid.ucSSID[: ssid.uSSIDLength])
                try:
                    ssid_str = ssid_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    ssid_str = ssid_bytes.decode("latin-1", errors="replace")

                if not ssid_str.strip():
                    ssid_str = "<Hidden Network>"

                # Check if we already have this SSID with better signal quality
                duplicate = False
                for i, existing in enumerate(networks_info):
                    if existing.ssid == ssid_str:
                        duplicate = True
                        # If this one has better signal, update the entry with the new bss list
                        if network.wlanSignalQuality > existing.quality:
                            networks_info[i].quality = network.wlanSignalQuality
                        break
                if not duplicate:
                    profile_exists = bool(network.dwFlags & WLAN_AVAILABLE_NETWORK_HAS_PROFILE)
                    auto_connect = self._is_auto_connect_profile(self._client_handle, interface.InterfaceGuid, ssid_str)
                    state = WifiState(0)
                    if network.dwFlags & WLAN_AVAILABLE_NETWORK_CONNECTED:
                        state |= WifiState.CONNECTED
                    if network.bSecurityEnabled:
                        state |= WifiState.SECURED
                    network_info = NetworkInfo(
                        ssid=ssid_str,
                        quality=network.wlanSignalQuality,
                        state=state,
                        auth_alg=network.dot11DefaultAuthAlgorithm,
                        profile_exists=profile_exists,
                        auto_connect=auto_connect,
                    )
                    networks_info.append(network_info)
            WlanFreeMemory(network_list_ptr)
        WlanFreeMemory(interfaces_ptr)
        self.wifi_scan_completed.emit(ScanResultStatus.SUCCESS, networks_info)

    def forget_network(self, profile_name: str):
        """Forget a WiFi network deleting the stored credentials"""
        interfaces_ptr = None
        try:
            interfaces_ptr, interfaces = self._get_interface_list()
            for interface in interfaces:
                result = WlanDeleteProfile(
                    self._client_handle,
                    byref(interface.InterfaceGuid),
                    profile_name,
                    None,
                )
                if result != ERROR_SUCCESS:
                    if result == ERROR_NOT_FOUND:
                        logger.debug("WiFi network profile not found")
                    else:
                        logger.debug(f"Failed to forget WiFi network: {result}")
                else:
                    logger.debug("Forgetting network profile")
        except Exception as e:
            logger.debug(f"Error forgetting WiFi network: {e}")
        finally:
            if interfaces_ptr:
                WlanFreeMemory(interfaces_ptr)

    def change_auto_connect(self, ssid: str, auto_connect: bool):
        """Change the auto-connect setting for a WiFi network"""
        try:
            interfaces_ptr, interfaces = self._get_interface_list()
            for interface in interfaces:
                is_auto_connect = self._is_auto_connect_profile(self._client_handle, interface.InterfaceGuid, ssid)
                if is_auto_connect == auto_connect:
                    continue
                wlan_profile = self._get_wlan_profile(self._client_handle, interface.InterfaceGuid, ssid)
                if not wlan_profile:
                    continue
                new_mode = "auto" if auto_connect else "manual"
                modified_xml = re.sub(
                    r"<connectionMode>(.*?)</connectionMode>",
                    f"<connectionMode>{new_mode}</connectionMode>",
                    wlan_profile,
                    flags=re.IGNORECASE,
                )
                result = self._set_wlan_profile(self._client_handle, interface.InterfaceGuid, modified_xml)
                if result:
                    logger.debug("Changed auto-connect setting")
                    return True
                else:
                    logger.debug("Failed to change auto-connect setting")
            if interfaces_ptr:
                WlanFreeMemory(interfaces_ptr)
            return False
        except Exception as e:
            logger.debug(f"Error changing auto-connect setting: {e}")
            return False

    def _on_wlan_notification(
        self,
        notification_data: CPointer[WLAN_NOTIFICATION_DATA],
        _context: c_void_p,
    ):
        """Callback for WLAN notifications handling"""
        code = notification_data.contents.NotificationCode
        if code == WlanNotificationAcm.SCAN_COMPLETE:
            if self.wifi_updates_enabled:
                self.get_available_networks()
            self._is_scanning = False
        elif code == WlanNotificationAcm.SCAN_FAIL:
            self._is_scanning = False
        elif code == WlanNotificationAcm.DISCONNECTED:
            pData = ct.cast(notification_data.contents.pData, POINTER(WLAN_CONNECTION_NOTIFICATION_DATA))
            self.wifi_disconnected.emit(pData.contents.strProfileName)

    def _get_interface_list(self) -> tuple[CPointer[WLAN_INTERFACE_INFO_LIST], Array[WLAN_INTERFACE_INFO]]:
        """Get the list of WLAN interfaces"""
        interface_list_ptr = POINTER(WLAN_INTERFACE_INFO_LIST)()
        result = WlanEnumInterfaces(self._client_handle, None, byref(self._interface_list_ptr))
        if result != ERROR_SUCCESS:
            raise WinError(result)

        interface_list = self._interface_list_ptr.contents
        interfaces = (WLAN_INTERFACE_INFO * int(interface_list.dwNumberOfItems)).from_address(
            addressof(interface_list.InterfaceInfo)
        )
        return interface_list_ptr, interfaces

    def _find_connected_network_info(
        self,
        network_list_ptr: CPointer[WLAN_AVAILABLE_NETWORK_LIST],
        interface_guid: GUID,
    ) -> NetworkInfo | None:
        """Find the connected network in the available network list"""
        network_list = network_list_ptr.contents
        networks = (WLAN_AVAILABLE_NETWORK * int(network_list.dwNumberOfItems)).from_address(
            addressof(network_list.Network)
        )

        # Find the connected network
        for network in networks:
            if not (network.dwFlags & WLAN_INTERFACE_STATE_CONNECTED):
                continue

            ssid = network.dot11Ssid
            ssid_bytes = bytes(ssid.ucSSID[: ssid.uSSIDLength])
            try:
                ssid_str = ssid_bytes.decode("utf-8")
            except UnicodeDecodeError:
                ssid_str = ssid_bytes.decode("latin-1", errors="replace")

            signal_quality = network.wlanSignalQuality
            secured = bool(network.bSecurityEnabled)

            return NetworkInfo(
                ssid=ssid_str,
                quality=signal_quality,
                state=WifiState.CONNECTED | WifiState.SECURED if secured else WifiState.CONNECTED,
                auto_connect=self._is_auto_connect_profile(self._client_handle, interface_guid, ssid_str),
            )

        return None

    def _is_auto_connect_profile(
        self,
        client_handle: HANDLE,
        interface_guid: GUID,
        profile_name: str,
    ) -> bool:
        """Get the connection mode of a WiFi network where true is auto and false is manual"""
        profile_xml = self._get_wlan_profile(client_handle, interface_guid, profile_name)
        match = re.search(r"<connectionMode>(.*?)</connectionMode>", profile_xml)
        if match:
            connection_mode = match.group(1)  # "auto" or "manual"
        else:
            connection_mode = "auto"
        return connection_mode == "auto"

    def _is_hidden_ssid(
        self,
        client_handle: HANDLE,
        interface_guid: GUID,
        profile_name: str,
    ) -> bool:
        """Get the connection mode of a WiFi network where true is hidden and false is not hidden"""
        profile_xml = self._get_wlan_profile(client_handle, interface_guid, profile_name)
        match = re.search(r"<nonBroadcast>(.*?)</nonBroadcast>", profile_xml)
        if match:
            connection_mode = match.group(1)  # "true" or "false"
        else:
            connection_mode = False
        return connection_mode == "true"

    def _modify_connection_mode(
        self,
        client_handle: HANDLE,
        interface_guid: GUID,
        ssid: str,
        connection_mode_auto: bool,
    ) -> str:
        """Get the WiFi profile XML"""
        profile_xml = self._get_wlan_profile(client_handle, interface_guid, ssid)
        pattern = r"<connectionMode>.*?</connectionMode>"
        mode = "auto" if connection_mode_auto else "manual"
        replacement = f"<connectionMode>{mode}</connectionMode>"
        modified_xml = re.sub(pattern, replacement, profile_xml, flags=re.IGNORECASE)
        return modified_xml

    def _get_wlan_profile(self, client_handle: HANDLE, interface_guid: GUID, ssid: str) -> str:
        """Get the profile XML of a WiFi network"""
        profile_str_ptr = LPWSTR()
        result = WlanGetProfile(
            client_handle,
            byref(interface_guid),
            ssid,
            None,
            byref(profile_str_ptr),
            None,
            None,
        )
        if result == ERROR_SUCCESS and profile_str_ptr.value is not None:
            return profile_str_ptr.value
        if result == ERROR_NOT_FOUND:  # No need to log this, expected behavior
            return ""
        logger.debug(f"Error getting profile: {result}")
        return ""

    def _set_wlan_profile(self, client_handle: HANDLE, interface_guid: GUID, profile_xml: str):
        try:
            reason_code = DWORD()
            result = WlanSetProfile(
                client_handle,
                byref(interface_guid),
                0,
                profile_xml,
                None,
                True,
                None,
                byref(reason_code),
            )

            if result == ERROR_SUCCESS:
                return True
            else:
                buff = create_unicode_buffer(256)
                WlanReasonCodeToString(reason_code.value, sizeof(buff), buff, None)
                logger.debug(f"Failed to create profile: {result}. Code: {reason_code.value}. Reason: {buff.value}")
                return False

        except Exception as e:
            logger.debug(f"Error creating profile: {e}")
            return False
