"""Core Audio COM interfaces (audioclient.h, devicetopology.h, ks.h)"""

from ctypes import POINTER, c_ubyte, c_uint32, c_uint64, c_ulong, c_void_p, c_wchar_p
from typing import TYPE_CHECKING, Any

from comtypes import (  # pyright: ignore[reportMissingTypeStubs]
    COMMETHOD,  # pyright: ignore[reportUnknownVariableType]
    GUID,
    HRESULT,
    IUnknown,
)

from core.utils.win32.structs import KSPROPERTY

IID_IAudioClient = GUID("{1CB9AD4C-DBFA-4C32-B178-C2F568A703B2}")
IID_IAudioCaptureClient = GUID("{C8ADBD64-E71E-48A0-A4DE-185C395CD317}")
IID_IDeviceTopology = GUID("{2A07407E-6497-4A18-9787-32F79BD0D98F}")
IID_IConnector = GUID("{9C2C4058-23F5-41DE-877A-DF3AF236A09E}")
IID_IKsControl = GUID("{28F54685-06FD-11D2-B27A-00A0C9223196}")


# https://learn.microsoft.com/en-us/windows/win32/api/audioclient/nn-audioclient-iaudiocaptureclient
class IAudioCaptureClient(IUnknown):
    _iid_ = IID_IAudioCaptureClient
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "GetBuffer",
            (["out"], POINTER(POINTER(c_ubyte)), "ppData"),
            (["out"], POINTER(c_uint32), "pNumFramesToRead"),
            (["out"], POINTER(c_uint32), "pdwFlags"),
            (["out"], POINTER(c_uint64), "pu64DevicePosition"),
            (["out"], POINTER(c_uint64), "pu64QPCPosition"),
        ),
        COMMETHOD([], HRESULT, "ReleaseBuffer", (["in"], c_uint32, "NumFramesRead")),
        COMMETHOD(
            [],
            HRESULT,
            "GetNextPacketSize",
            (["out"], POINTER(c_uint32), "pNumFramesInNextPacket"),
        ),
    ]

    if TYPE_CHECKING:

        def GetBuffer(self) -> tuple[Any, int, int, int, int]: ...
        def ReleaseBuffer(self, NumFramesRead: int) -> None: ...
        def GetNextPacketSize(self) -> int: ...


# https://learn.microsoft.com/en-us/windows/win32/api/devicetopology/nn-devicetopology-idevicetopology
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
    ]
    if TYPE_CHECKING:

        def GetConnectorCount(self) -> int: ...
        def GetConnector(self, nIndex: int) -> IUnknown: ...


# https://learn.microsoft.com/en-us/windows/win32/api/devicetopology/nn-devicetopology-iconnector
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
    if TYPE_CHECKING:

        def GetType(self) -> int: ...
        def GetDataFlow(self) -> int: ...
        def ConnectTo(self, pConnectTo: IUnknown) -> None: ...
        def Disconnect(self) -> None: ...
        def IsConnected(self) -> int: ...
        def GetConnectedTo(self) -> IUnknown: ...
        def GetConnectorIdConnectedTo(self) -> str: ...
        def GetDeviceIdConnectedTo(self) -> str: ...


# https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ks/nn-ks-ikscontrol
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
    ]
    if TYPE_CHECKING:

        def KsProperty(self, Property: Any, PropertyLength: int, PropertyData: Any, DataLength: int) -> int: ...
