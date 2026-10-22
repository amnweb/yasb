"""Registry key paths YASB opens, grouped by hive."""

# HKEY_CURRENT_USER
RUN_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
PERSONALIZE_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
USER_FONTS_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
IDENTITY_USER_PROPERTIES_KEY = r"Software\Microsoft\IdentityCRL\UserExtendedProperties"
DESKTOP_KEY = r"Control Panel\Desktop"
COLORS_KEY = r"Control Panel\Colors"

# HKEY_LOCAL_MACHINE
WINDOWS_NT_CURRENT_VERSION_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
POWER_SCHEMES_KEY = r"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes"
KEYBOARD_LAYOUTS_KEY = r"SYSTEM\CurrentControlSet\Control\Keyboard Layouts"
APP_USER_MODEL_ID_KEY = r"SOFTWARE\Classes\AppUserModelId"
CONTROL_PANEL_NAMESPACE_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\ControlPanel\NameSpace"
ACCOUNT_PICTURE_USERS_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\AccountPicture\Users"
WER_LOCAL_DUMPS_KEY = r"SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps"
EVERYTHING_KEY = r"SOFTWARE\voidtools\Everything"
EVERYTHING_WOW64_KEY = r"SOFTWARE\WOW6432Node\voidtools\Everything"

# HKEY_CLASSES_ROOT
CLSID_KEY = "CLSID"
