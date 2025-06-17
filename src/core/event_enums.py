from enum import Enum, EnumMeta


class MetaEvent(EnumMeta):
    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        return True


class Event(Enum, metaclass=MetaEvent):
    pass


class KomorebiEvent(Event):
    KomorebiConnect = "KomorebiConnect"
    KomorebiUpdate = "KomorebiUpdate"
    KomorebiDisconnect = "KomorebiDisconnect"
    FocusWorkspaceNumber = "FocusWorkspaceNumber"
    FocusMonitorWorkspaceNumber = "FocusMonitorWorkspaceNumber"
    FocusChange = "FocusChange"
    ChangeLayout = "ChangeLayout"
    ToggleTiling = "ToggleTiling"
    ToggleMonocle = "ToggleMonocle"
    ToggleMaximize = "ToggleMaximize"
    TogglePause = "TogglePause"
    ToggleWorkspaceLayer = "ToggleWorkspaceLayer"
    EnsureWorkspaces = "EnsureWorkspaces"
    CycleFocusMonitor = "CycleFocusMonitor"
    CycleFocusWorkspace = "CycleFocusWorkspace"
    FocusMonitorNumber = "FocusMonitorNumber"
    ReloadConfiguration = "ReloadConfiguration"
    WatchConfiguration = "WatchConfiguration"
    Manage = "Manage"
    Unmanage = "Unmanage"
    Cloak = "Cloak"
    CloseWorkspace = "CloseWorkspace"
    MoveContainerToMonitorNumber = "MoveContainerToMonitorNumber"
    MoveContainerToWorkspaceNumber = "MoveContainerToWorkspaceNumber"
    MoveWorkspaceToMonitorNumber = "MoveWorkspaceToMonitorNumber"
    NewWorkspace = "NewWorkspace"
    SendContainerToMonitorNumber = "SendContainerToMonitorNumber"
    SendContainerToWorkspaceNumber = "SendContainerToWorkspaceNumber"
    WorkspaceName = "WorkspaceName"
    StackWindow = "StackWindow"
    UnstackWindow = "UnstackWindow"
    CycleStack = "CycleStack"
    FocusStackWindow = "FocusStackWindow"
    TitleUpdate = "TitleUpdate"
