"""Wrappers for Direct3D 11, and for the composition interop that fills drawing surfaces through it"""

import ctypes
from ctypes import HRESULT, POINTER, WINFUNCTYPE, WinDLL, byref, c_void_p
from ctypes.wintypes import HANDLE, HMODULE, POINT, RECT, UINT
from typing import TYPE_CHECKING, cast

import comtypes
from comtypes import COMMETHOD, GUID

from core.utils.win32.structs import D3D11_BOX

d3d11 = WinDLL("d3d11", use_last_error=True)

D3D_DRIVER_TYPE_HARDWARE = 1
D3D11_CREATE_DEVICE_BGRA_SUPPORT = 0x20
D3D11_SDK_VERSION = 7
IID_ID3D11Texture2D = GUID("{6F15AAF2-D208-4E89-9AB4-489535D34F9C}")

d3d11.D3D11CreateDevice.argtypes = [
    c_void_p,
    UINT,
    HMODULE,
    UINT,
    c_void_p,
    UINT,
    UINT,
    POINTER(POINTER(comtypes.IUnknown)),
    POINTER(UINT),
    POINTER(POINTER(comtypes.IUnknown)),
]
d3d11.D3D11CreateDevice.restype = HRESULT

# ID3D11DeviceContext::UpdateSubresource is slot 48 of its vtable: as a comtypes interface, the 45 methods before it
# would all have to be declared
_UPDATE_SUBRESOURCE_SLOT = 48
_UpdateSubresource = WINFUNCTYPE(None, c_void_p, c_void_p, UINT, POINTER(D3D11_BOX), c_void_p, UINT, UINT)


# https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-d3d11createdevice
def D3D11CreateDevice() -> tuple[comtypes.IUnknown, comtypes.IUnknown]:
    """A hardware device that can draw BGRA surfaces, and its immediate context."""
    device, context = POINTER(comtypes.IUnknown)(), POINTER(comtypes.IUnknown)()
    d3d11.D3D11CreateDevice(
        None,
        D3D_DRIVER_TYPE_HARDWARE,
        None,
        D3D11_CREATE_DEVICE_BGRA_SUPPORT,
        None,
        0,
        D3D11_SDK_VERSION,
        byref(device),
        None,
        byref(context),
    )
    return cast(comtypes.IUnknown, device), cast(comtypes.IUnknown, context)


# https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-updatesubresource
def UpdateSubresource(
    context: comtypes.IUnknown, resource: comtypes.IUnknown, box: D3D11_BOX, data: int, row_pitch: int
) -> None:
    """Copies rows of row_pitch bytes from data into box of the resource's first subresource."""
    method = ctypes.cast(context, POINTER(POINTER(c_void_p)))[0][_UPDATE_SUBRESOURCE_SLOT]
    _UpdateSubresource(method)(context, resource, 0, byref(box), data, row_pitch, 0)


# https://learn.microsoft.com/en-us/windows/win32/api/windows.ui.composition.interop/nn-windows-ui-composition-interop-icompositorinterop
class ICompositorInterop(comtypes.IUnknown):
    _iid_ = GUID("{25297D5C-3AD4-4C9C-B5CF-E36A38512330}")
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "CreateCompositionSurfaceForHandle",
            (["in"], HANDLE, "swapChain"),
            (["out"], POINTER(POINTER(comtypes.IUnknown)), "result"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "CreateCompositionSurfaceForSwapChain",
            (["in"], POINTER(comtypes.IUnknown), "swapChain"),
            (["out"], POINTER(POINTER(comtypes.IUnknown)), "result"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "CreateGraphicsDevice",
            (["in"], POINTER(comtypes.IUnknown), "renderingDevice"),
            (["out"], POINTER(POINTER(comtypes.IUnknown)), "result"),
        ),
    ]

    if TYPE_CHECKING:

        def CreateGraphicsDevice(self, renderingDevice: comtypes.IUnknown) -> comtypes.IUnknown: ...


# https://learn.microsoft.com/en-us/windows/win32/api/windows.ui.composition.interop/nn-windows-ui-composition-interop-icompositiongraphicsdeviceinterop
class ICompositionGraphicsDeviceInterop(comtypes.IUnknown):
    _iid_ = GUID("{A116FF71-F8BF-4C8A-9C98-70779A32A9C8}")
    _methods_ = [
        COMMETHOD([], HRESULT, "GetRenderingDevice", (["out"], POINTER(POINTER(comtypes.IUnknown)), "value")),
        COMMETHOD([], HRESULT, "SetRenderingDevice", (["in"], POINTER(comtypes.IUnknown), "value")),
    ]

    if TYPE_CHECKING:

        def SetRenderingDevice(self, value: comtypes.IUnknown) -> None: ...


# https://learn.microsoft.com/en-us/windows/win32/api/windows.ui.composition.interop/nn-windows-ui-composition-interop-icompositiondrawingsurfaceinterop
class ICompositionDrawingSurfaceInterop(comtypes.IUnknown):
    _iid_ = GUID("{FD04E6E3-FE0C-4C3C-AB19-A07601A576EE}")
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "BeginDraw",
            (["in"], POINTER(RECT), "updateRect"),
            (["in"], POINTER(GUID), "iid"),
            (["out"], POINTER(POINTER(comtypes.IUnknown)), "updateObject"),
            (["out"], POINTER(POINT), "updateOffset"),
        ),
        COMMETHOD([], HRESULT, "EndDraw"),
    ]

    if TYPE_CHECKING:

        def BeginDraw(self, updateRect: RECT | None, iid: GUID) -> tuple[comtypes.IUnknown, POINT]: ...
        def EndDraw(self) -> None: ...
