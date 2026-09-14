"""Virtual desktop self-check.

Windows drives virtual desktops through undocumented COM interfaces whose GUIDs
and vtable layouts changed several times between Windows 10 and Windows 11. The
widget keeps one interface set per build tier and picks the right one at runtime.
Picking the wrong one fails quietly: the widget stops updating, or a menu entry
does nothing, with no error to go on.

There is no practical way to test that from here. A tier cannot be exercised
without a machine running that build, and mocking the shell proves nothing, since
what the real shell does is the entire question. So rather than trying to test
every build ourselves, this script reports what one machine actually does.

Run it on any machine where the widget misbehaves and attach the output to the
bug report. It prints the build number, which tier was selected and how many COM
probes that took, which capabilities the build has, and a pass or fail line for
every call the widget makes.

    pip install comtypes
    cd src
    python -m core.widgets.services.windows_desktops.selfcheck
    python -m core.widgets.services.windows_desktops.selfcheck --full

Without --full nothing is modified. With --full it creates a scratch desktop,
renames it, switches to it and back, moves the focused window there and back, and
toggles both pin states. Every change is undone and the scratch desktop deleted
before the summary prints, so the desktops you start with are the ones you end
with.
"""

import ctypes
import sys
import time
import traceback
from ctypes.wintypes import MSG

from core.utils.win32.bindings.user32 import user32

# PeekMessage removes the message from the queue after retrieving it.
PM_REMOVE = 0x0001

results: list[tuple[str, bool, str]] = []


def record(name: str, fn) -> object:
    """Run one check, record pass or fail, and return its value."""
    try:
        value = fn()
    except Exception as e:
        results.append((name, False, f"{type(e).__name__}: {e}"))
        return None
    results.append((name, True, "" if value is None else str(value)))
    return value


def pump(seconds: float = 1.2) -> None:
    """Dispatch Windows messages so COM can deliver notifications."""
    message = MSG()
    end = time.time() + seconds
    while time.time() < end:
        while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        time.sleep(0.01)


def main(full: bool = False) -> int:
    from core.widgets.services.windows_desktops import interfaces as vd
    from core.widgets.services.windows_desktops.com import get_api
    from core.widgets.services.windows_desktops.notification import DesktopEvent, DesktopNotificationListener

    version = sys.getwindowsversion()
    print(f"Windows {version.major}.{version.minor} build {version.build}")
    print(f"platform version {'.'.join(str(p) for p in version.platform_version)}")
    print(f"Python {sys.version.split()[0]}\n")

    probes = {"count": 0}
    original_probe = vd._manager_available

    def counting_probe(provider, iid):
        probes["count"] += 1
        return original_probe(provider, iid)

    vd._manager_available = counting_probe
    tier = record("resolve tier", vd.resolve_tier)
    vd._manager_available = original_probe
    print(f"tier {tier}, resolved with {probes['count']} COM probe(s)")

    api = get_api()
    record("acquire COM interfaces", api.available)
    record("supports desktop names", lambda: api.supports_names)
    record("supports per-desktop wallpaper", lambda: api.supports_wallpaper)
    record("IVirtualDesktopManagerInternal2", lambda: api._ensure().manager2 is not None)

    desktops = record("list desktops", api.list_desktops)
    current = record("read current desktop", api.current_guid)
    record("desktop count", api.count)
    if desktops:
        print("\ndesktops:")
        for d in desktops:
            mark = "  <- current" if d.guid == current else ""
            print(f"   {d.number}. name={d.name!r} {d.guid}{mark}")
        record("current desktop is in the list", lambda: any(d.guid == current for d in desktops))
        record("resolve a desktop by GUID", lambda: api._find(desktops[0].guid) is not None)

    from core.utils.win32.bindings.user32 import GetForegroundWindow

    hwnd = GetForegroundWindow()
    view = record("view for foreground window", lambda: api.try_view_for_hwnd(hwnd))
    if view is not None:
        record("read window pin state", lambda: api.is_view_pinned(view))
        record("read app pin state", lambda: api.is_app_pinned(view))

    events: list[DesktopEvent] = []
    listener = DesktopNotificationListener(events.append, api)
    registered = record("register for notifications", listener.start)

    if full and desktops and registered:
        print("\n--- full mode: creating a scratch desktop ---")

        scratch = None
        try:
            scratch = record("create desktop", api.create)
            pump()
            record("CREATED notification", lambda: DesktopEvent.CREATED in events)

            if scratch:
                events.clear()
                if api.supports_names:
                    record("rename desktop", lambda: api.rename(scratch, "__yasb_selfcheck__"))
                    pump()
                    record(
                        "rename reflected",
                        lambda: any(d.guid == scratch and d.name == "__yasb_selfcheck__" for d in api.list_desktops()),
                    )
                    record("RENAMED notification", lambda: DesktopEvent.RENAMED in events)

                events.clear()
                record("switch desktop", lambda: api.switch_to(scratch))
                pump()
                record("switch took effect", lambda: api.current_guid() == scratch)
                record("CURRENT_CHANGED notification", lambda: DesktopEvent.CURRENT_CHANGED in events)

                record("switch back", lambda: api.switch_to(current))
                pump()

                if view is not None:
                    # Window operations, on the window that had focus at start.
                    # Each is undone immediately afterwards.
                    def desktop_of_window() -> str:
                        return str(api.view_for_hwnd(hwnd).GetVirtualDesktopId())

                    home = desktop_of_window()
                    record("move window to another desktop", lambda: api.move_view(api.view_for_hwnd(hwnd), scratch))
                    pump(0.8)
                    record("window moved", lambda: desktop_of_window() == scratch)
                    record("move window back", lambda: api.move_view(api.view_for_hwnd(hwnd), home))
                    pump(0.8)
                    record("window moved back", lambda: desktop_of_window() == home)

                    was_pinned = api.is_view_pinned(api.view_for_hwnd(hwnd))
                    record("pin window", lambda: api.pin_view(api.view_for_hwnd(hwnd)))
                    pump(0.4)
                    record("window reports pinned", lambda: api.is_view_pinned(api.view_for_hwnd(hwnd)) is True)
                    record("unpin window", lambda: api.unpin_view(api.view_for_hwnd(hwnd)))
                    pump(0.4)
                    record(
                        "window pin state restored",
                        lambda: api.is_view_pinned(api.view_for_hwnd(hwnd)) == was_pinned,
                    )

                    was_app_pinned = api.is_app_pinned(api.view_for_hwnd(hwnd))
                    record("pin app", lambda: api.pin_app(api.view_for_hwnd(hwnd)))
                    pump(0.4)
                    record("app reports pinned", lambda: api.is_app_pinned(api.view_for_hwnd(hwnd)) is True)
                    record("unpin app", lambda: api.unpin_app(api.view_for_hwnd(hwnd)))
                    pump(0.4)
                    record(
                        "app pin state restored",
                        lambda: api.is_app_pinned(api.view_for_hwnd(hwnd)) == was_app_pinned,
                    )
        finally:
            if scratch:
                try:
                    if api.current_guid() != current:
                        api.switch_to(current)
                        pump(0.6)
                    events.clear()
                    record("remove desktop", lambda: api.remove(scratch, current))
                    pump()
                    record("DESTROYED notification", lambda: DesktopEvent.DESTROYED in events)
                except Exception:
                    print("cleanup failed:")
                    traceback.print_exc()

        final = api.list_desktops()
        record(
            "original desktops restored",
            lambda: [(d.guid, d.name) for d in final] == [(d.guid, d.name) for d in desktops],
        )
        record("original desktop still active", lambda: api.current_guid() == current)

    listener.stop()

    print()
    failed = 0
    for name, ok, detail in results:
        if not ok:
            failed += 1
        print(f"  {'OK  ' if ok else 'FAIL'} {name}" + (f"  {detail}" if detail else ""))

    print(f"\n{len(results) - failed}/{len(results)} checks passed on build {version.build}, tier {tier}")
    if failed:
        print("Please report this output at https://github.com/amnweb/yasb/issues")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(full="--full" in sys.argv))
