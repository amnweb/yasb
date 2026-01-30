"""
Windows Battery API
"""

import ctypes
import logging
from ctypes import byref, c_long, c_void_p, create_string_buffer, sizeof, wstring_at
from ctypes.wintypes import DWORD, ULONG
from dataclasses import dataclass
from typing import Optional

from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.bindings.setupapi import setupapi
from core.utils.win32.constants import (
    BATTERY_INFO_LEVEL_INFORMATION,
    BATTERY_INFO_LEVEL_TEMPERATURE,
    BATTERY_UNKNOWN_CAPACITY,
    BATTERY_UNKNOWN_RATE,
    BATTERY_UNKNOWN_VOLTAGE,
    DIGCF_DEVICEINTERFACE,
    DIGCF_PRESENT,
    FILE_ATTRIBUTE_NORMAL,
    FILE_SHARE_READ,
    FILE_SHARE_WRITE,
    GENERIC_READ,
    GENERIC_WRITE,
    GUID_DEVCLASS_BATTERY,
    INVALID_HANDLE_VALUE,
    IOCTL_BATTERY_QUERY_INFORMATION,
    IOCTL_BATTERY_QUERY_STATUS,
    IOCTL_BATTERY_QUERY_TAG,
    OPEN_EXISTING,
    POWER_TIME_UNKNOWN,
    POWER_TIME_UNLIMITED,
)
from core.utils.win32.structs import (
    BATTERY_INFORMATION,
    BATTERY_QUERY_INFORMATION,
    BATTERY_STATUS,
    BATTERY_WAIT_STATUS,
    GUID,
    SP_DEVICE_INTERFACE_DATA,
    SP_DEVICE_INTERFACE_DETAIL_DATA_W,
    SYSTEM_POWER_STATUS,
)


@dataclass
class BatteryData:
    """Complete battery information."""

    percent: int
    is_charging: bool
    power_plugged: bool
    time_remaining: int
    rate: Optional[float]
    voltage: Optional[float]
    capacity: Optional[int]
    full_capacity: Optional[int]
    designed_capacity: Optional[int]
    temperature: Optional[float]
    cycle_count: Optional[int]
    chemistry: Optional[str]
    health_percent: Optional[float]


class BatteryAPI:
    """
    Singleton class to access battery information
    """

    _instance: Optional["BatteryAPI"] = None
    _initialized: bool = False

    def __new__(cls) -> "BatteryAPI":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if BatteryAPI._initialized:
            return
        BatteryAPI._initialized = True

        self._battery_guid = GUID()
        self._battery_guid.Data1 = GUID_DEVCLASS_BATTERY[0]
        self._battery_guid.Data2 = GUID_DEVCLASS_BATTERY[1]
        self._battery_guid.Data3 = GUID_DEVCLASS_BATTERY[2]
        for i, b in enumerate(GUID_DEVCLASS_BATTERY[3]):
            self._battery_guid.Data4[i] = b

        self._device_path: Optional[str] = None
        self._last_error_logged: bool = False

    @classmethod
    def instance(cls) -> "BatteryAPI":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_battery_device_path(self) -> Optional[str]:
        """Get the device path for the first battery."""
        if self._device_path:
            return self._device_path

        h_dev_info = setupapi.SetupDiGetClassDevsW(
            byref(self._battery_guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
        )

        if h_dev_info == INVALID_HANDLE_VALUE:
            return None

        try:
            interface_data = SP_DEVICE_INTERFACE_DATA()
            interface_data.cbSize = sizeof(SP_DEVICE_INTERFACE_DATA)

            if not setupapi.SetupDiEnumDeviceInterfaces(
                h_dev_info, None, byref(self._battery_guid), 0, byref(interface_data)
            ):
                return None

            required_size = DWORD(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(
                h_dev_info, byref(interface_data), None, 0, byref(required_size), None
            )

            if required_size.value == 0:
                return None

            buffer_size = required_size.value
            buffer = create_string_buffer(buffer_size)

            detail_data = ctypes.cast(buffer, ctypes.POINTER(SP_DEVICE_INTERFACE_DETAIL_DATA_W))
            detail_data.contents.cbSize = 8 if sizeof(c_void_p) == 8 else 6

            if not setupapi.SetupDiGetDeviceInterfaceDetailW(
                h_dev_info, byref(interface_data), buffer, buffer_size, None, None
            ):
                return None

            path_offset = 4
            device_path = wstring_at(ctypes.addressof(buffer) + path_offset)
            self._device_path = device_path
            return device_path

        finally:
            setupapi.SetupDiDestroyDeviceInfoList(h_dev_info)

    def _get_basic_status(self) -> Optional[tuple[int, bool, bool, int]]:
        """Get basic battery status from GetSystemPowerStatus."""
        status = SYSTEM_POWER_STATUS()
        if not kernel32.GetSystemPowerStatus(byref(status)):
            return None

        if (status.BatteryFlag & 0x80) or status.BatteryLifePercent == 255:
            return None

        percent = int(status.BatteryLifePercent)
        power_plugged = status.ACLineStatus == 1
        is_charging = bool(status.BatteryFlag & 0x08) or (power_plugged and percent < 100)

        if status.BatteryLifeTime == 0xFFFFFFFF:
            time_remaining = POWER_TIME_UNLIMITED if power_plugged else POWER_TIME_UNKNOWN
        else:
            time_remaining = int(status.BatteryLifeTime)

        return percent, is_charging, power_plugged, time_remaining

    def _get_extended_info(self, device_path: str) -> dict:
        """Get extended battery info via IOCTL."""
        result = {
            "rate": None,
            "voltage": None,
            "capacity": None,
            "full_capacity": None,
            "designed_capacity": None,
            "temperature": None,
            "cycle_count": None,
            "chemistry": None,
        }

        h_battery = kernel32.CreateFileW(
            device_path,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )

        if h_battery == INVALID_HANDLE_VALUE:
            return result

        try:
            bytes_returned = DWORD(0)
            wait_timeout = ULONG(0)
            battery_tag = ULONG(0)

            if not kernel32.DeviceIoControl(
                h_battery,
                IOCTL_BATTERY_QUERY_TAG,
                byref(wait_timeout),
                sizeof(wait_timeout),
                byref(battery_tag),
                sizeof(battery_tag),
                byref(bytes_returned),
                None,
            ):
                return result

            if battery_tag.value == 0:
                return result

            query_info = BATTERY_QUERY_INFORMATION()
            query_info.BatteryTag = battery_tag.value
            query_info.InformationLevel = BATTERY_INFO_LEVEL_INFORMATION
            query_info.AtRate = 0

            battery_info = BATTERY_INFORMATION()
            if kernel32.DeviceIoControl(
                h_battery,
                IOCTL_BATTERY_QUERY_INFORMATION,
                byref(query_info),
                sizeof(query_info),
                byref(battery_info),
                sizeof(battery_info),
                byref(bytes_returned),
                None,
            ):
                if battery_info.DesignedCapacity != BATTERY_UNKNOWN_CAPACITY:
                    result["designed_capacity"] = battery_info.DesignedCapacity
                if battery_info.FullChargedCapacity != BATTERY_UNKNOWN_CAPACITY:
                    result["full_capacity"] = battery_info.FullChargedCapacity
                if battery_info.CycleCount > 0:
                    result["cycle_count"] = battery_info.CycleCount

                chemistry = battery_info.Chemistry.decode("ascii", errors="ignore").strip("\x00")
                if chemistry:
                    result["chemistry"] = chemistry

            # Query battery status (rate, voltage, current capacity)
            wait_status = BATTERY_WAIT_STATUS()
            wait_status.BatteryTag = battery_tag.value
            wait_status.Timeout = 0
            wait_status.PowerState = 0
            wait_status.LowCapacity = 0
            wait_status.HighCapacity = 0xFFFFFFFF

            battery_status = BATTERY_STATUS()
            if kernel32.DeviceIoControl(
                h_battery,
                IOCTL_BATTERY_QUERY_STATUS,
                byref(wait_status),
                sizeof(wait_status),
                byref(battery_status),
                sizeof(battery_status),
                byref(bytes_returned),
                None,
            ):
                if battery_status.Rate != BATTERY_UNKNOWN_RATE:
                    rate_mw = c_long(battery_status.Rate).value
                    result["rate"] = rate_mw / 1000.0  # mW to W

                if battery_status.Voltage != BATTERY_UNKNOWN_VOLTAGE:
                    result["voltage"] = battery_status.Voltage / 1000.0  # mV to V

                if battery_status.Capacity != BATTERY_UNKNOWN_CAPACITY:
                    result["capacity"] = battery_status.Capacity

            # Query temperature if supported
            query_info.InformationLevel = BATTERY_INFO_LEVEL_TEMPERATURE
            temperature = ULONG(0)
            if kernel32.DeviceIoControl(
                h_battery,
                IOCTL_BATTERY_QUERY_INFORMATION,
                byref(query_info),
                sizeof(query_info),
                byref(temperature),
                sizeof(temperature),
                byref(bytes_returned),
                None,
            ):
                if temperature.value > 0:
                    # Temperature is in tenths of Kelvin
                    kelvin = temperature.value / 10.0
                    celsius = kelvin - 273.15
                    if -40 <= celsius <= 100:  # Sanity check
                        result["temperature"] = round(celsius, 1)

        except Exception as e:
            if not self._last_error_logged:
                logging.debug(f"Error getting extended battery info: {e}")
                self._last_error_logged = True
        finally:
            kernel32.CloseHandle(h_battery)

        return result

    def get_status(self) -> Optional[BatteryData]:
        """
        Get comprehensive battery status.

        Returns:
            BatteryData with all available information, or None if no battery.
        """
        basic = self._get_basic_status()
        if basic is None:
            return None

        percent, is_charging, power_plugged, time_remaining = basic

        device_path = self._get_battery_device_path()
        if device_path:
            extended = self._get_extended_info(device_path)
        else:
            extended = {
                "rate": None,
                "voltage": None,
                "capacity": None,
                "full_capacity": None,
                "designed_capacity": None,
                "temperature": None,
                "cycle_count": None,
                "chemistry": None,
            }

        health_percent = None
        if extended["full_capacity"] and extended["designed_capacity"]:
            if extended["designed_capacity"] > 0:
                health_percent = round((extended["full_capacity"] / extended["designed_capacity"]) * 100, 1)

        return BatteryData(
            percent=percent,
            is_charging=is_charging,
            power_plugged=power_plugged,
            time_remaining=time_remaining,
            rate=extended["rate"],
            voltage=extended["voltage"],
            capacity=extended["capacity"],
            full_capacity=extended["full_capacity"],
            designed_capacity=extended["designed_capacity"],
            temperature=extended["temperature"],
            cycle_count=extended["cycle_count"],
            chemistry=extended["chemistry"],
            health_percent=health_percent,
        )

    def is_available(self) -> bool:
        """Check if a battery is present in the system."""
        status = SYSTEM_POWER_STATUS()
        if not kernel32.GetSystemPowerStatus(byref(status)):
            return False
        return not ((status.BatteryFlag & 0x80) or status.BatteryLifePercent == 255)
