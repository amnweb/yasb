"""Classic Bluetooth audio connect/disconnect via KS property oneshots."""

import ctypes
import threading
import time
from ctypes import HRESULT, POINTER, Structure, byref, c_ulong, c_void_p, c_wchar_p

from comtypes import CLSCTX_ALL, COMMETHOD, GUID, CoCreateInstance, IUnknown
from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
from pycaw.constants import AudioDeviceState, CLSID_MMDeviceEnumerator
from pycaw.pycaw import AudioUtilities

IID_IDeviceTopology = GUID("{2A07407E-6497-4A18-9787-32F79BD0D98F}")
IID_IConnector = GUID("{9C2C4058-23F5-41DE-877A-DF3AF236A09E}")
IID_IKsControl = GUID("{28F54685-06FD-11D2-B27A-00A0C9223196}")

KSPROPSETID_BtAudio = GUID("{7FA06C40-B8F6-4C7E-8556-E8C33A12E54D}")
KSPROPERTY_ONESHOT_RECONNECT = 0
KSPROPERTY_ONESHOT_DISCONNECT = 1
KSPROPERTY_TYPE_GET = 0x00000001

_SETTLE_TIMEOUT_S = 10.0
_SETTLE_POLL_S = 0.25


class KSPROPERTY(Structure):
    _fields_ = [("Set", GUID), ("Id", c_ulong), ("Flags", c_ulong)]


class IDeviceTopology(IUnknown):
    _iid_ = IID_IDeviceTopology
    _methods_ = [
        COMMETHOD([], HRESULT, "GetConnectorCount", (["out"], POINTER(c_ulong))),
        COMMETHOD(
            [],
            HRESULT,
            "GetConnector",
            (["in"], c_ulong),
            (["out"], POINTER(POINTER(IUnknown))),
        ),
        COMMETHOD([], HRESULT, "GetSubunitCount", (["out"], POINTER(c_ulong))),
        COMMETHOD(
            [],
            HRESULT,
            "GetSubunit",
            (["in"], c_ulong),
            (["out"], POINTER(POINTER(IUnknown))),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetPartById",
            (["in"], c_ulong),
            (["out"], POINTER(POINTER(IUnknown))),
        ),
        COMMETHOD([], HRESULT, "GetDeviceId", (["out"], POINTER(c_wchar_p))),
        COMMETHOD([], HRESULT, "GetSignalPath"),
    ]


class IConnector(IUnknown):
    _iid_ = IID_IConnector
    _methods_ = [
        COMMETHOD([], HRESULT, "GetType", (["out"], POINTER(c_ulong))),
        COMMETHOD([], HRESULT, "GetDataFlow", (["out"], POINTER(c_ulong))),
        COMMETHOD([], HRESULT, "ConnectTo", (["in"], POINTER(IUnknown))),
        COMMETHOD([], HRESULT, "Disconnect"),
        COMMETHOD([], HRESULT, "IsConnected", (["out"], POINTER(c_ulong))),
        COMMETHOD([], HRESULT, "GetConnectedTo", (["out"], POINTER(POINTER(IUnknown)))),
        COMMETHOD([], HRESULT, "GetConnectorIdConnectedTo", (["out"], POINTER(c_wchar_p))),
        COMMETHOD([], HRESULT, "GetDeviceIdConnectedTo", (["out"], POINTER(c_wchar_p))),
    ]


class IKsControl(IUnknown):
    _iid_ = IID_IKsControl
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "KsProperty",
            (["in"], POINTER(KSPROPERTY), "Property"),
            (["in"], c_ulong, "PropertyLength"),
            (["in"], c_void_p, "PropertyData"),
            (["in"], c_ulong, "DataLength"),
            (["out"], POINTER(c_ulong), "BytesReturned"),
        ),
        COMMETHOD([], HRESULT, "KsMethod"),
        COMMETHOD([], HRESULT, "KsEvent"),
    ]


def _mac_hex(address: str | int) -> str:
    if isinstance(address, int):
        return f"{address:012X}"
    return "".join(c for c in address.upper() if c in "0123456789ABCDEF")


def _id_has_mac(device_id: str, mac: str) -> bool:
    if len(mac) != 12:
        return False
    compact = device_id.upper().replace(":", "").replace("-", "").replace("_", "")
    return mac in compact


def _oneshot(ks: IKsControl, prop_id: int) -> bool:
    prop = KSPROPERTY(KSPROPSETID_BtAudio, prop_id, KSPROPERTY_TYPE_GET)
    try:
        ks.KsProperty(byref(prop), ctypes.sizeof(KSPROPERTY), None, 0)
        return True
    except Exception:
        return False


def _matching_endpoints(device_name: str):
    needle = (device_name or "").casefold().strip()
    if not needle:
        return
    for device in AudioUtilities.GetAllDevices():
        if needle in (device.FriendlyName or "").casefold():
            yield device


def audio_is_connected(device_name: str) -> bool | None:
    """True if any endpoint Active; False if all Unplugged; None if no endpoints."""
    seen = False
    for device in _matching_endpoints(device_name):
        seen = True
        if device.state == AudioDeviceState.Active:
            return True
    return False if seen else None


def _activate_ks(enumerator: IMMDeviceEnumerator, device_id: str) -> IKsControl | None:
    try:
        ks_dev = enumerator.GetDevice(device_id)
        return ks_dev.Activate(IID_IKsControl, CLSCTX_ALL, None).QueryInterface(IKsControl)
    except Exception:
        return None


def _ks_controls(address: str | int, device_name: str = "") -> list[IKsControl]:
    mac = _mac_hex(address)
    name_needle = (device_name or "").casefold().strip()
    enumerator = CoCreateInstance(CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, CLSCTX_ALL)
    found: list[IKsControl] = []
    seen: set[str] = set()

    for device in AudioUtilities.GetAllDevices():
        friendly = (device.FriendlyName or "").casefold()
        try:
            itopo = device._dev.Activate(IID_IDeviceTopology, CLSCTX_ALL, None).QueryInterface(IDeviceTopology)
            count = itopo.GetConnectorCount()
        except Exception:
            continue

        for ci in range(count):
            try:
                conn = itopo.GetConnector(ci).QueryInterface(IConnector)
                other_id = conn.GetDeviceIdConnectedTo()
            except Exception:
                continue

            other_id_s = str(other_id) if other_id else ""
            if "bth" not in other_id_s.lower():
                continue
            mac_ok = _id_has_mac(other_id_s, mac)
            name_ok = bool(name_needle) and name_needle in friendly
            if not mac_ok and not name_ok:
                continue
            if other_id_s in seen:
                continue
            seen.add(other_id_s)

            ks = _activate_ks(enumerator, other_id_s)
            if ks is not None:
                found.append(ks)

    return found


def _wait_audio_state(
    device_name: str,
    want_connected: bool,
    cancel: threading.Event | None,
) -> str | None:
    """None when audio matches want_connected; else cancelled/timeout."""
    deadline = time.monotonic() + _SETTLE_TIMEOUT_S
    while time.monotonic() < deadline:
        if cancel is not None and cancel.is_set():
            return "cancelled"
        if audio_is_connected(device_name) == want_connected:
            return None
        if cancel is not None:
            if cancel.wait(timeout=_SETTLE_POLL_S):
                return "cancelled"
        else:
            time.sleep(_SETTLE_POLL_S)
    return "timeout"


def set_audio_connection(
    address: str | int,
    *,
    connect: bool,
    device_name: str = "",
    cancel: threading.Event | None = None,
) -> str | None:
    """None = done; else error reason. Disconnect always oneshots."""
    current = audio_is_connected(device_name)
    if current is None:
        return "not_audio_device"
    if connect and current is True:
        return None

    controls = _ks_controls(address, device_name)
    if not controls:
        return "no_ks_controls"

    prop = KSPROPERTY_ONESHOT_RECONNECT if connect else KSPROPERTY_ONESHOT_DISCONNECT
    sent = False
    for ks in controls:
        if _oneshot(ks, prop):
            sent = True
    if not sent:
        return "oneshot_failed"

    return _wait_audio_state(device_name, connect, cancel)
