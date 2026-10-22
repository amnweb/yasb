"""
Windows Network API wrapper
"""

import ctypes
import socket
from ctypes import byref, wintypes
from typing import Literal, NamedTuple, TypedDict, overload

from core.utils.win32.bindings.iphlpapi import iphlpapi
from core.utils.win32.constants import (
    AF_INET,
    AF_UNSPEC,
    ERROR_BUFFER_OVERFLOW,
    ERROR_SUCCESS,
    GAA_FLAG_INCLUDE_PREFIX,
    GAA_FLAG_SKIP_ANYCAST,
    GAA_FLAG_SKIP_DNS_SERVER,
    GAA_FLAG_SKIP_MULTICAST,
    IF_TYPE_SOFTWARE_LOOPBACK,
)
from core.utils.win32.structs import (
    IP_ADAPTER_ADDRESSES,
    MIB_IF_ROW2,
    SOCKADDR,
    SOCKADDR_IN,
)
from core.utils.win32.typecheck import CPointer


class IOCounters(NamedTuple):
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int


class AddressInfo(NamedTuple):
    family: int
    address: str
    netmask: str | None
    broadcast: str | None
    ptp: str | None


class _InterfaceStats(TypedDict):
    index: int
    type: int
    mtu: int
    oper_status: int
    in_octets: int
    out_octets: int
    in_ucast_pkts: int
    out_ucast_pkts: int
    in_nucast_pkts: int
    out_nucast_pkts: int
    in_errors: int
    out_errors: int
    in_discards: int
    out_discards: int


class _AdapterInfo(TypedDict):
    if_index: int
    if_type: int
    oper_status: int
    addresses: list[AddressInfo]


def _get_interface_stats_by_index(if_index: int) -> _InterfaceStats | None:
    """Get interface statistics by index using GetIfEntry2 (64-bit counters)"""
    try:
        row = MIB_IF_ROW2()
        row.InterfaceIndex = if_index

        result = iphlpapi.GetIfEntry2(byref(row))
        if result != ERROR_SUCCESS:
            return None

        return {
            "index": row.InterfaceIndex,
            "type": row.Type,
            "mtu": row.Mtu,
            "oper_status": row.OperStatus,
            "in_octets": row.InOctets,
            "out_octets": row.OutOctets,
            "in_ucast_pkts": row.InUcastPkts,
            "out_ucast_pkts": row.OutUcastPkts,
            "in_nucast_pkts": row.InNUcastPkts,
            "out_nucast_pkts": row.OutNUcastPkts,
            "in_errors": row.InErrors,
            "out_errors": row.OutErrors,
            "in_discards": row.InDiscards,
            "out_discards": row.OutDiscards,
        }
    except Exception:
        return None


def _extract_ipv4_address(sockaddr_ptr: CPointer[SOCKADDR]) -> str | None:
    """Extract IPv4 address from SOCKADDR pointer"""
    if not sockaddr_ptr:
        return None

    try:
        sockaddr = sockaddr_ptr.contents
        if sockaddr.sa_family == AF_INET:
            sockaddr_in = ctypes.cast(sockaddr_ptr, ctypes.POINTER(SOCKADDR_IN)).contents
            addr_bytes = bytes(sockaddr_in.sin_addr)
            return socket.inet_ntoa(addr_bytes)
    except Exception:
        pass

    return None


def _get_adapters_info() -> dict[str, _AdapterInfo]:
    """
    Get adapter information using GetAdaptersAddresses.
    Returns a dict mapping FriendlyName to adapter info (including IfIndex).
    """
    flags = GAA_FLAG_INCLUDE_PREFIX | GAA_FLAG_SKIP_ANYCAST | GAA_FLAG_SKIP_MULTICAST | GAA_FLAG_SKIP_DNS_SERVER

    # First call to get required buffer size
    size = wintypes.ULONG(0)
    result = iphlpapi.GetAdaptersAddresses(AF_UNSPEC, flags, None, None, byref(size))

    if result != ERROR_BUFFER_OVERFLOW and result != ERROR_SUCCESS:
        return {}

    # Allocate buffer
    buffer = (ctypes.c_byte * size.value)()
    adapter = ctypes.cast(buffer, ctypes.POINTER(IP_ADAPTER_ADDRESSES))

    result = iphlpapi.GetAdaptersAddresses(AF_UNSPEC, flags, None, adapter, byref(size))
    if result != ERROR_SUCCESS:
        return {}

    adapters: dict[str, _AdapterInfo] = {}
    current = adapter

    while current:
        try:
            adapter_data = current.contents
            friendly_name = adapter_data.FriendlyName
            if_index = adapter_data.IfIndex
            if_type = adapter_data.IfType
            oper_status = adapter_data.OperStatus

            # Get IPv4 addresses
            addr_list: list[AddressInfo] = []
            unicast = adapter_data.FirstUnicastAddress
            while unicast:
                try:
                    unicast_data = unicast.contents
                    ip_addr = _extract_ipv4_address(unicast_data.Address.lpSockaddr)
                    if ip_addr:
                        addr_info = AddressInfo(
                            family=socket.AF_INET,
                            address=ip_addr,
                            netmask=None,
                            broadcast=None,
                            ptp=None,
                        )
                        addr_list.append(addr_info)
                    unicast = unicast_data.Next
                except Exception:
                    break

            if friendly_name and if_index > 0:
                adapters[friendly_name] = {
                    "if_index": if_index,
                    "if_type": if_type,
                    "oper_status": oper_status,
                    "addresses": addr_list,
                }

            current = adapter_data.Next
        except Exception:
            break

    return adapters


class NetworkAPI:
    """Windows Network API wrapper"""

    _cached_adapters: dict[str, _AdapterInfo] | None = None
    _cache_time = 0.0
    _cache_ttl = 1.0  # Cache for 1 second

    @classmethod
    def _get_adapters(cls, force_refresh: bool = False) -> dict[str, _AdapterInfo]:
        """Get adapter info with caching"""
        import time

        current_time = time.time()

        if not force_refresh and cls._cached_adapters and (current_time - cls._cache_time) < cls._cache_ttl:
            return cls._cached_adapters

        adapters = _get_adapters_info()

        if adapters:
            cls._cached_adapters = adapters
            cls._cache_time = current_time

        return adapters or {}

    @overload
    @classmethod
    def net_io_counters(cls, pernic: Literal[False] = False) -> IOCounters: ...

    @overload
    @classmethod
    def net_io_counters(cls, pernic: Literal[True]) -> dict[str, IOCounters]: ...

    @classmethod
    def net_io_counters(cls, pernic: bool = False) -> IOCounters | dict[str, IOCounters]:
        """Get network I/O statistics."""
        try:
            adapters = cls._get_adapters()

            if not adapters:
                return {} if pernic else IOCounters(0, 0, 0, 0, 0, 0, 0, 0)

            if pernic:
                result: dict[str, IOCounters] = {}
                for friendly_name, adapter_info in adapters.items():
                    if adapter_info.get("if_type") == IF_TYPE_SOFTWARE_LOOPBACK:
                        continue

                    stats = _get_interface_stats_by_index(adapter_info["if_index"])
                    if stats:
                        result[friendly_name] = IOCounters(
                            bytes_sent=stats["out_octets"],
                            bytes_recv=stats["in_octets"],
                            packets_sent=stats["out_ucast_pkts"] + stats["out_nucast_pkts"],
                            packets_recv=stats["in_ucast_pkts"] + stats["in_nucast_pkts"],
                            errin=stats["in_errors"],
                            errout=stats["out_errors"],
                            dropin=stats["in_discards"],
                            dropout=stats["out_discards"],
                        )
                return result

            else:
                total_sent = 0
                total_recv = 0
                total_pkts_sent = 0
                total_pkts_recv = 0
                total_errin = 0
                total_errout = 0
                total_dropin = 0
                total_dropout = 0

                for friendly_name, adapter_info in adapters.items():
                    if adapter_info.get("if_type") == IF_TYPE_SOFTWARE_LOOPBACK:
                        continue

                    stats = _get_interface_stats_by_index(adapter_info["if_index"])
                    if stats:
                        total_sent += stats["out_octets"]
                        total_recv += stats["in_octets"]
                        total_pkts_sent += stats["out_ucast_pkts"] + stats["out_nucast_pkts"]
                        total_pkts_recv += stats["in_ucast_pkts"] + stats["in_nucast_pkts"]
                        total_errin += stats["in_errors"]
                        total_errout += stats["out_errors"]
                        total_dropin += stats["in_discards"]
                        total_dropout += stats["out_discards"]

                return IOCounters(
                    bytes_sent=total_sent,
                    bytes_recv=total_recv,
                    packets_sent=total_pkts_sent,
                    packets_recv=total_pkts_recv,
                    errin=total_errin,
                    errout=total_errout,
                    dropin=total_dropin,
                    dropout=total_dropout,
                )
        except Exception:
            return {} if pernic else IOCounters(0, 0, 0, 0, 0, 0, 0, 0)

    @classmethod
    def get_interface_ip(cls, interface_name: str) -> str | None:
        """Get the IPv4 address of a specific interface by FriendlyName"""
        try:
            adapters = cls._get_adapters()
            if interface_name in adapters:
                addresses = adapters[interface_name].get("addresses", [])
                for addr in addresses:
                    if addr.family == socket.AF_INET:
                        return addr.address
        except Exception:
            pass
        return None
