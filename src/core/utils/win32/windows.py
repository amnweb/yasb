import ctypes.wintypes

from core.event_enums import Event

user32 = ctypes.windll.user32
user32.SetWinEventHook.restype = ctypes.wintypes.HANDLE
ole32 = ctypes.windll.ole32
ole32.CoInitialize(0)
msg = ctypes.wintypes.MSG()

WinEventProcType = ctypes.WINFUNCTYPE(
    None,
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.HWND,
    ctypes.wintypes.LONG,
    ctypes.wintypes.LONG,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
)


class WinEvent(Event):
    """
    Win32user Event Constants

    More information: https://docs.microsoft.com/en-us/windows/win32/winauto/event-constants
    """

    EventMin = 0x00000001
    EventMax = 0x7FFFFFFF
    EventSystemEnd = 0x00FF
    EventObjectEnd = 0x80FF

    WinEventOutOfContext = 0x0000
    EventSystemSound = 0x0001
    EventSystemAlert = 0x0002
    EventSystemForeground = 0x0003
    EventSystemMenuStart = 0x0004
    EventSystemMenuEnd = 0x0005
    EventSystemMenuPopupStart = 0x0006
    EventSystemMenuPopupEnd = 0x0007
    EventSystemCaptureStart = 0x0008
    EventSystemCaptureEnd = 0x0009
    EventSystemDialogStart = 0x0010
    EventSystemDialogEnd = 0x0011
    EventSystemScrollingStart = 0x0012
    EventSystemScrollingEnd = 0x0013
    EventSystemSwitchStart = 0x0014
    EventSystemSwitchEnd = 0x0015
    EventSystemMinimizeStart = 0x0016
    EventSystemMinimizeEnd = 0x0017
    EventSystemMoveSizeStart = 0x000A
    EventSystemMoveSizeEnd = 0x000B
    EventSystemContextHelpStart = 0x000C
    EventSystemContextHelpEnd = 0x000D
    EventSystemDragDropStart = 0x000E
    EventSystemDragDropEnd = 0x000F

    EventObjectCreate = 0x8000
    EventObjectDestroy = 0x8001
    EventObjectShow = 0x8002
    EventObjectHide = 0x8003
    EventObjectReorder = 0x8004
    EventObjectFocus = 0x8005
    EventObjectSelection = 0x8006
    EventObjectSelectionAdd = 0x8007
    EventObjectSelectionMove = 0x8008
    EventObjectSelectionWithin = 0x8009
    EventObjectHelpChange = 0x8010
    EventObjectDefActionChange = 0x8011
    EventObjectAcceleratorChange = 0x8012
    EventObjectInvoked = 0x8013
    EventObjectTextSelectionChanged = 0x8014
    EventObjectContentScrolled = 0x8015
    EventObjectArrangementPreview = 0x8016
    EventObjectCloaked = 0x8017
    EventObjectUncloaked = 0x8018
    EventObjectLiveRegionChanged = 0x8019
    EventObjectHostedObjectsInvalidated = 0x8020
    EventObjectDragStart = 0x8021
    EventObjectDragCancel = 0x8022
    EventObjectDragComplete = 0x8023
    EventObjectDragEnter = 0x8024
    EventObjectDragLeave = 0x8025
    EventObjectDragDropped = 0x8026
    EventObjectIMEShow = 0x8027
    EventObjectIMEHide = 0x8028
    EventObjectIMEChange = 0x8029
    EventObjectTextEditConversationTargetChanged = 0x8030
    EventObjectStateChange = 0x800A
    EventObjectLocationChange = 0x800B
    EventObjectNameChange = 0x800C
    EventObjectDescriptionChange = 0x800D
    EventObjectValueChange = 0x800E
    EventObjectParentChange = 0x800F

    EventAIAStart = 0xA000
    EventAIAEnd = 0xAFFF
    EventOEMDefinedStart = 0x0101
    EventOEMDefinedEnd = 0x01FF
    EventUIAEventIdStart = 0x4E00
    EventUIAEventIdEnd = 0x4EFF
    EventUIAPropIdStart = 0x7500
    EventUIAPropIdEnd = 0x75FF
