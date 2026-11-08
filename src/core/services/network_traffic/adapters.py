"""Network adapter counters and connectivity reported by Windows."""

import ctypes
import socket
from collections.abc import Iterator, Sequence
from ctypes import byref, wintypes
from dataclasses import dataclass, replace
from typing import cast
from uuid import UUID

from winrt.windows.networking.connectivity import ConnectionProfile, NetworkAdapter, NetworkInformation

from core.utils.win32.bindings.iphlpapi import iphlpapi
from core.utils.win32.constants import (
    AF_INET,
    AF_UNSPEC,
    ERROR_BUFFER_OVERFLOW,
    ERROR_NO_DATA,
    ERROR_SUCCESS,
    GAA_FLAG_SKIP_ANYCAST,
    GAA_FLAG_SKIP_DNS_SERVER,
    GAA_FLAG_SKIP_MULTICAST,
    IF_TYPE_SOFTWARE_LOOPBACK,
)
from core.utils.win32.structs import IP_ADAPTER_ADDRESSES, MIB_IF_ROW2, SOCKADDR_IN


@dataclass(frozen=True)
class Adapter:
    key: str
    name: str
    uploaded: int
    downloaded: int
    connected: bool = False
    ip_address: str = ""
    index: int = 0


type ProfileKey = tuple[str, str]


def _adapter_id(profile: ConnectionProfile) -> str | None:
    adapter = cast(NetworkAdapter | None, profile.network_adapter)
    return str(adapter.network_adapter_id) if adapter is not None else None


def find_profile(interface: str) -> tuple[ProfileKey, ConnectionProfile] | None:
    """The network to watch: with auto the one Windows uses for internet, otherwise the one the adapter with this
    name, such as Ethernet or Wi-Fi, is connected to."""
    if interface == "auto":
        profile = cast(ConnectionProfile | None, NetworkInformation.get_internet_connection_profile())
    else:
        key = adapter_key(interface)
        profiles: Sequence[ConnectionProfile] = NetworkInformation.get_connection_profiles() if key is not None else []
        profile = next((profile for profile in profiles if _adapter_id(profile) == key), None)
    if profile is not None and (key := _adapter_id(profile)) is not None:
        return (key, profile.profile_name), profile
    return None


def adapter_key(name: str) -> str | None:
    """The id of the adapter Windows shows with this name, in any case."""
    folded = name.casefold()
    return next((key for key, adapter, _row in _adapters() if adapter.FriendlyName.casefold() == folded), None)


def read_adapter(key: str) -> Adapter | None:
    for adapter_id, adapter, row in _adapters():
        if adapter_id != key:
            continue
        address = ""
        unicast = adapter.FirstUnicastAddress
        while unicast:
            sockaddr = unicast.contents.Address.lpSockaddr
            if sockaddr and sockaddr.contents.sa_family == AF_INET:
                ipv4 = ctypes.cast(sockaddr, ctypes.POINTER(SOCKADDR_IN)).contents
                address = socket.inet_ntoa(bytes(ipv4.sin_addr))
                break
            unicast = unicast.contents.Next
        return Adapter(
            key, adapter.FriendlyName, row.OutOctets, row.InOctets, row.OperStatus == 1, address, adapter.IfIndex
        )
    return None


def read_counters(adapter: Adapter) -> Adapter | None:
    row = MIB_IF_ROW2(InterfaceIndex=adapter.index)
    if iphlpapi.GetIfEntry2(byref(row)) != ERROR_SUCCESS:
        return None
    return replace(adapter, uploaded=row.OutOctets, downloaded=row.InOctets, connected=row.OperStatus == 1)


def _adapters() -> Iterator[tuple[str, IP_ADAPTER_ADDRESSES, MIB_IF_ROW2]]:
    """Each adapter but loopback, with its id and counters."""
    # Starting with 15 KB avoids the usual extra size query. Adapters can change while reading.
    # https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getadaptersaddresses#remarks
    size = wintypes.ULONG(15 * 1024)
    flags = GAA_FLAG_SKIP_ANYCAST | GAA_FLAG_SKIP_MULTICAST | GAA_FLAG_SKIP_DNS_SERVER
    for _ in range(3):
        buffer = ctypes.create_string_buffer(size.value)
        head = ctypes.cast(buffer, ctypes.POINTER(IP_ADAPTER_ADDRESSES))
        result = iphlpapi.GetAdaptersAddresses(AF_UNSPEC, flags, None, head, byref(size))
        if result == ERROR_SUCCESS:
            break
        if result == ERROR_NO_DATA:
            return
        if result != ERROR_BUFFER_OVERFLOW:
            raise ctypes.WinError(result)
    else:
        raise OSError("Network adapters kept changing while reading their addresses")

    # The buffer stays alive while this generator runs, so the adapters it yields stay readable
    current = head
    while current:
        adapter = current.contents
        current = adapter.Next
        if not adapter.FriendlyName or adapter.IfType == IF_TYPE_SOFTWARE_LOOPBACK:
            continue
        row = MIB_IF_ROW2()
        row.InterfaceIndex = adapter.IfIndex
        # An adapter can disappear between the address and counter queries.
        if iphlpapi.GetIfEntry2(byref(row)) != ERROR_SUCCESS:
            continue
        yield str(UUID(bytes_le=bytes(row.InterfaceGuid))), adapter, row
