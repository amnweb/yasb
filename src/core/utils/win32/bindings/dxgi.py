"""Wrappers for dxgi win32 API functions and the DXGI adapter enumeration interfaces"""

from ctypes import POINTER, WinDLL, byref, c_long, c_void_p
from ctypes.wintypes import BOOL, HMODULE, HWND, LARGE_INTEGER, UINT
from typing import TYPE_CHECKING, cast

import comtypes  # pyright: ignore[reportMissingTypeStubs]
from comtypes import COMMETHOD, GUID, HRESULT  # pyright: ignore[reportUnknownVariableType, reportMissingTypeStubs]

from core.utils.win32.structs import DXGI_ADAPTER_DESC

dxgi = WinDLL("dxgi", use_last_error=True)

IID_IDXGIFactory1 = GUID("{770AAE78-F26F-4DBA-A829-253C83D1B387}")


# https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nn-dxgi-idxgiobject
class IDXGIObject(comtypes.IUnknown):
    _iid_ = GUID("{AEC22FB8-76F3-4639-9BE0-28EB43A67A2E}")
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "SetPrivateData",
            (["in"], POINTER(GUID), "Name"),
            (["in"], UINT, "DataSize"),
            (["in"], c_void_p, "pData"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "SetPrivateDataInterface",
            (["in"], POINTER(GUID), "Name"),
            (["in"], POINTER(comtypes.IUnknown), "pUnknown"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetPrivateData",
            (["in"], POINTER(GUID), "Name"),
            (["in", "out"], POINTER(UINT), "pDataSize"),
            (["in"], c_void_p, "pData"),
        ),
        COMMETHOD([], HRESULT, "GetParent", (["in"], POINTER(GUID), "riid"), (["out"], POINTER(c_void_p), "ppParent")),
    ]


# https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nn-dxgi-idxgiadapter
class IDXGIAdapter(IDXGIObject):
    _iid_ = GUID("{2411E7E1-12AC-4CCF-BD14-9798E8534DC0}")
    _methods_ = [
        COMMETHOD([], HRESULT, "EnumOutputs", (["in"], UINT, "Output"), (["out"], POINTER(c_void_p), "ppOutput")),
        COMMETHOD([], HRESULT, "GetDesc", (["out"], POINTER(DXGI_ADAPTER_DESC), "pDesc")),
        COMMETHOD(
            [],
            HRESULT,
            "CheckInterfaceSupport",
            (["in"], POINTER(GUID), "InterfaceName"),
            (["out"], POINTER(LARGE_INTEGER), "pUMDVersion"),
        ),
    ]

    if TYPE_CHECKING:

        def GetDesc(self) -> DXGI_ADAPTER_DESC: ...


# https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nn-dxgi-idxgifactory
class IDXGIFactory(IDXGIObject):
    _iid_ = GUID("{7B7166EC-21C7-44AE-B21A-C9AE321AE369}")
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "EnumAdapters",
            (["in"], UINT, "Adapter"),
            (["out"], POINTER(POINTER(IDXGIAdapter)), "ppAdapter"),
        ),
        COMMETHOD([], HRESULT, "MakeWindowAssociation", (["in"], HWND, "WindowHandle"), (["in"], UINT, "Flags")),
        COMMETHOD([], HRESULT, "GetWindowAssociation", (["out"], POINTER(HWND), "pWindowHandle")),
        COMMETHOD(
            [],
            HRESULT,
            "CreateSwapChain",
            (["in"], POINTER(comtypes.IUnknown), "pDevice"),
            (["in"], c_void_p, "pDesc"),
            (["out"], POINTER(c_void_p), "ppSwapChain"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "CreateSoftwareAdapter",
            (["in"], HMODULE, "Module"),
            (["out"], POINTER(POINTER(IDXGIAdapter)), "ppAdapter"),
        ),
    ]

    if TYPE_CHECKING:

        def EnumAdapters(self, Adapter: int) -> IDXGIAdapter: ...


# https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nn-dxgi-idxgifactory1
class IDXGIFactory1(IDXGIFactory):
    _iid_ = IID_IDXGIFactory1
    _methods_ = [
        COMMETHOD([], HRESULT, "EnumAdapters1", (["in"], UINT, "Adapter"), (["out"], POINTER(c_void_p), "ppAdapter")),
        COMMETHOD([], BOOL, "IsCurrent"),
    ]


dxgi.CreateDXGIFactory1.argtypes = [POINTER(GUID), POINTER(POINTER(IDXGIFactory1))]
dxgi.CreateDXGIFactory1.restype = c_long


def CreateDXGIFactory1() -> IDXGIFactory1 | None:
    factory = POINTER(IDXGIFactory1)()
    if dxgi.CreateDXGIFactory1(byref(IID_IDXGIFactory1), byref(factory)) != 0 or not factory:
        return None
    return cast(IDXGIFactory1, factory)
