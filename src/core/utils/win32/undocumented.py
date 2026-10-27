"""Windows values that no SDK header or Microsoft documentation defines."""

from uuid import UUID

from core.utils.win32.structs import DEVPROPKEY, GUID

# SetWindowCompositionAttribute
WCA_ACCENT_POLICY = 19
ACCENT_DISABLED = 0
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4

# DwmSetWindowAttribute, before DWMWA_SYSTEMBACKDROP_TYPE existed
DWMWA_MICA_EFFECT = 1029

# DwmpActivateLivePreview trigger (LivePreviewTrigger): 1 ShowDesktop, 2 WinSpace, 3 Superbar (taskbar
# thumbnail hover), 4 AltTab, 5 SuperbarTouch, 6 ShowDesktopTouch
LPT_SUPERBAR = 3

# SetPreferredAppMode
PREFERRED_APP_MODE_ALLOW_DARK = 1

# Sent to Progman to create the WorkerW window behind the desktop icons
WM_SPAWN_WORKER = 0x052C

# WNF state names for RtlSubscribeWnfStateChangeNotification
WNF_SHEL_NOTIFICATION_TOTAL = 0x0D83063EA3B8D035  # Windows 11: Action Center toast total
WNF_SHEL_NOTIFICATIONS = 0x0D83063EA3BC1035  # Windows 10: unread/badge count
WNF_SHEL_QUIETHOURS_ACTIVE_PROFILE_CHANGED = 0x0D83063EA3BF1C75

# Power mode overlay schemes
POWER_MODE_BALANCED = GUID()
POWER_MODE_BEST_EFFICIENCY = GUID.from_string("961CC777-2547-4F9D-8174-7D86181B8A7A")
POWER_MODE_BEST_PERFORMANCE = GUID.from_string("DED574B5-45A0-4F42-8737-46345C09C238")

# Battery level of a Bluetooth device
DEVPKEY_Bluetooth_Battery = DEVPROPKEY(GUID.from_string("104EA319-6EE2-4701-BD47-8DDBF425BBE5"), 2)

# Windows' own tray icons
TRAY_BATTERY_ICON_GUID = UUID("7820ae75-23e3-4229-82c1-e41cb67d5b9c")
TRAY_VOLUME_ICON_GUID = UUID("7820ae73-23e3-4229-82c1-e41cb67d5b9c")
TRAY_NETWORK_ICON_GUID = UUID("7820ae74-23e3-4229-82c1-e41cb67d5b9c")
