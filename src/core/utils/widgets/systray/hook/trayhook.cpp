#include <windows.h>

#define WM_YASB_UNHOOK (WM_APP + 1)

// Global state
WNDPROC g_OldWndProc = NULL;
HANDLE g_hPipe = INVALID_HANDLE_VALUE;
HMODULE g_hModule = NULL;
CRITICAL_SECTION g_PipeCS;
volatile LONG g_Detaching = 0;
HANDLE g_hUnhookDoneEvent = NULL;

#define MAX_ICON_WIDTH 256
#define MAX_ICON_HEIGHT 256

#pragma pack(push, 1)
struct PipeMessageHeader {
    DWORD type; // 1 = text, 2 = COPYDATA
};

struct PipeCopyDataMessage {
    PipeMessageHeader header;
    DWORDLONG dwData;
    DWORD cbData; // size of NOTIFYICONDATA payload
    DWORD iconWidth;
    DWORD iconHeight;
    DWORD iconDataSize; // 0 = no icon, >0 = RGBA bytes follow
};

struct NOTIFYICONDATA32 {
    DWORD cbSize;
    DWORD hWnd;
    DWORD uID;
    DWORD uFlags;
    DWORD uCallbackMessage;
    DWORD hIcon;
    WCHAR szTip[128];
    DWORD dwState;
    DWORD dwStateMask;
    WCHAR szInfo[256];
    union {
        UINT uTimeout;
        UINT uVersion;
    } DUMMYUNIONNAME;
    WCHAR szInfoTitle[64];
    DWORD dwInfoFlags;
    GUID guidItem;
    DWORD hBalloonIcon;
};

struct SHELLTRAYDATA {
    DWORD dwSignature;
    DWORD dwMessage;
    NOTIFYICONDATA32 nid;
};
#pragma pack(pop)

void ConnectToPipe() {
    EnterCriticalSection(&g_PipeCS);
    if (g_hPipe == INVALID_HANDLE_VALUE) {
        g_hPipe = CreateFileW(L"\\\\.\\pipe\\yasb_systray_monitor", GENERIC_WRITE, 0, NULL, OPEN_EXISTING,
                              FILE_FLAG_OVERLAPPED, NULL);
    }
    LeaveCriticalSection(&g_PipeCS);
}

bool ExtractIconRGBA(HICON hIcon, BYTE *&outRGBA, DWORD &outSize, DWORD &outWidth, DWORD &outHeight) {
    ICONINFO iconInfo = {};
    if (!GetIconInfo(hIcon, &iconInfo))
        return false;

    BITMAP bitmap = {};
    if (!GetObject(iconInfo.hbmColor, sizeof(bitmap), &bitmap)) {
        DeleteObject(iconInfo.hbmMask);
        DeleteObject(iconInfo.hbmColor);
        return false;
    }

    outWidth = (DWORD)bitmap.bmWidth;
    outHeight = (DWORD)bitmap.bmHeight;

    if (outWidth == 0 || outHeight == 0 || outWidth > MAX_ICON_WIDTH || outHeight > MAX_ICON_HEIGHT) {
        DeleteObject(iconInfo.hbmMask);
        DeleteObject(iconInfo.hbmColor);
        return false;
    }

    BITMAPINFOHEADER bitmapInfo = {};
    bitmapInfo.biSize = sizeof(bitmapInfo);
    bitmapInfo.biWidth = outWidth;
    bitmapInfo.biHeight = -(LONG)outHeight;
    bitmapInfo.biPlanes = 1;
    bitmapInfo.biBitCount = 32;
    bitmapInfo.biCompression = BI_RGB;

    DWORD pixelCount = outWidth * outHeight;
    outSize = pixelCount * 4;

    outRGBA = (BYTE *)HeapAlloc(GetProcessHeap(), 0, outSize);
    if (!outRGBA) {
        DeleteObject(iconInfo.hbmMask);
        DeleteObject(iconInfo.hbmColor);
        return false;
    }

    HDC hdc = CreateCompatibleDC(NULL);
    BOOL ok = GetDIBits(hdc, iconInfo.hbmColor, 0, outHeight, outRGBA, (BITMAPINFO *)&bitmapInfo, DIB_RGB_COLORS) ==
              (int)outHeight;

    bool isMaskBased = true;
    for (DWORD i = 0; i < pixelCount; i++) {
        if (outRGBA[i * 4 + 3] != 0) {
            isMaskBased = false;
            break;
        }
    }

    BYTE *maskBytes = NULL;
    BOOL maskOk = FALSE;
    if (isMaskBased && iconInfo.hbmMask) {
        maskBytes = (BYTE *)HeapAlloc(GetProcessHeap(), 0, outSize);
        if (maskBytes) {
            maskOk = GetDIBits(hdc, iconInfo.hbmMask, 0, outHeight, maskBytes, (BITMAPINFO *)&bitmapInfo,
                               DIB_RGB_COLORS) == (int)outHeight;
        }
    }
    DeleteDC(hdc);

    if (ok) {
        for (DWORD i = 0; i < pixelCount; i++) {
            BYTE b = outRGBA[i * 4 + 0];
            BYTE g = outRGBA[i * 4 + 1];
            BYTE r = outRGBA[i * 4 + 2];
            BYTE a = outRGBA[i * 4 + 3];

            if (isMaskBased) {
                if (maskOk && maskBytes) {
                    a = (maskBytes[i * 4] == 255) ? 0 : 255;
                } else {
                    a = 255; // mask fetch failed, assume fully opaque
                }
            }

            outRGBA[i * 4 + 0] = r;
            outRGBA[i * 4 + 1] = g;
            outRGBA[i * 4 + 2] = b;
            outRGBA[i * 4 + 3] = a;
        }
    } else {
        HeapFree(GetProcessHeap(), 0, outRGBA);
        outRGBA = NULL;
        outSize = 0;
        ok = FALSE;
    }

    if (maskBytes)
        HeapFree(GetProcessHeap(), 0, maskBytes);

    DeleteObject(iconInfo.hbmMask);
    DeleteObject(iconInfo.hbmColor);
    return ok;
}

void InternalWriteToPipe(void *buffer, DWORD totalSize) {
    ConnectToPipe();

    EnterCriticalSection(&g_PipeCS);
    if (g_hPipe != INVALID_HANDLE_VALUE) {
        DWORD written;
        OVERLAPPED overlapped = {0};
        overlapped.hEvent = CreateEvent(NULL, TRUE, FALSE, NULL);

        if (overlapped.hEvent) {
            if (!WriteFile(g_hPipe, buffer, totalSize, &written, &overlapped)) {
                if (GetLastError() == ERROR_IO_PENDING) {
                    // Wait for a maximum of 500ms for the write to complete to avoid blocking Explorer UI
                    if (WaitForSingleObject(overlapped.hEvent, 500) != WAIT_OBJECT_0) {
                        CancelIo(g_hPipe);
                        CloseHandle(g_hPipe);
                        g_hPipe = INVALID_HANDLE_VALUE;
                    }
                } else {
                    CloseHandle(g_hPipe);
                    g_hPipe = INVALID_HANDLE_VALUE;
                }
            }
            CloseHandle(overlapped.hEvent);
        }
    }
    LeaveCriticalSection(&g_PipeCS);
}

void SendTextToPipe(const char *msg) {
    size_t msgLen = strlen(msg);
    size_t totalSize = sizeof(PipeMessageHeader) + msgLen;
    char *buffer = (char *)malloc(totalSize);
    if (buffer) {
        PipeMessageHeader header = {1}; // 1 = text
        memcpy(buffer, &header, sizeof(header));
        memcpy(buffer + sizeof(header), msg, msgLen);
        InternalWriteToPipe(buffer, (DWORD)totalSize);
        free(buffer);
    }
}

void SendCopyDataToPipe(PCOPYDATASTRUCT pcds) {
    if (!pcds)
        return;

    BYTE *iconRGBA = NULL;
    DWORD iconSize = 0, iconWidth = 0, iconHeight = 0;

    SHELLTRAYDATA *trayData = (SHELLTRAYDATA *)pcds->lpData;
    if (!trayData) {
        return;
    }

    NOTIFYICONDATA32 *nid = &trayData->nid;
    if (nid && (nid->uFlags & NIF_ICON) && nid->hIcon) {
        HICON hIconCopy = CopyIcon((HICON)(ULONG_PTR)nid->hIcon);
        if (hIconCopy) {
            // We are processing icons directly to avoid stale hIcon handles on Python side
            ExtractIconRGBA(hIconCopy, iconRGBA, iconSize, iconWidth, iconHeight);
            DestroyIcon(hIconCopy);
        }
    }

    PipeCopyDataMessage msg = {};
    msg.header.type = 2;
    msg.dwData = pcds->dwData;
    msg.cbData = (DWORD)pcds->cbData;
    msg.iconWidth = iconWidth;
    msg.iconHeight = iconHeight;
    msg.iconDataSize = iconSize;

    size_t totalSize = sizeof(msg) + msg.cbData + msg.iconDataSize;
    char *buffer = (char *)malloc(totalSize);
    if (buffer) {
        char *cursor = buffer;
        memcpy(cursor, &msg, sizeof(msg));
        cursor += sizeof(msg);
        if (msg.cbData > 0 && pcds->lpData) {
            memcpy(cursor, pcds->lpData, msg.cbData);
            cursor += msg.cbData;
        }
        if (msg.iconDataSize > 0) {
            memcpy(cursor, iconRGBA, msg.iconDataSize);
        }

        InternalWriteToPipe(buffer, (DWORD)totalSize);
        free(buffer);
    }

    if (iconRGBA) {
        HeapFree(GetProcessHeap(), 0, iconRGBA);
    }
}

void DebugOutput(const char *msg) {
    SendTextToPipe(msg);
    OutputDebugStringA(msg);
}

// Filters out non-explorer.exe systray windows just in case
HWND FindRealSystray() {
    HWND hRealTray = NULL;
    WORD tries = 0;

    while (true) {
        hRealTray = FindWindowExW(0, hRealTray, L"Shell_TrayWnd", NULL);
        if (hRealTray == NULL || hRealTray == INVALID_HANDLE_VALUE) {
            if (tries > 20) {
                DebugOutput("[DLL] Failed to find real systray window. Giving up.\n");
                break;
            }
            tries++;
            char buf[256];
            wsprintf(buf, "[DLL] Failed to find real systray window. Retrying... %d\n", tries);
            DebugOutput(buf);
            Sleep(50);
            continue;
        }

        DWORD pid;
        GetWindowThreadProcessId(hRealTray, &pid);
        if (pid != GetCurrentProcessId()) {
            continue;
        }

        return hRealTray;
    }
    return 0;
}

LRESULT CALLBACK ManualSubclassProc(HWND hWnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
    // Cache the old window proc locally in case we unhook below
    WNDPROC oldProc = g_OldWndProc;

    // Watchdog posts this message. Because it's posted (not sent), it is only
    // dequeued by the top-level GetMessage loop AFTER all nested SendMessage
    // dispatches have unwound — so no ManualSubclassProc frames remain on the
    // stack when we process it.
    if (uMsg == WM_YASB_UNHOOK) {
        if (oldProc) {
            SetWindowLongPtrW(hWnd, GWLP_WNDPROC, (LONG_PTR)oldProc);
            g_OldWndProc = NULL;
        }
        // Signal the watchdog that unhook is complete and it's safe to unload
        if (g_hUnhookDoneEvent) {
            SetEvent(g_hUnhookDoneEvent);
        }
        return 0;
    }

    // Explorer is tearing down the tray window — restore the original wndproc
    if (uMsg == WM_NCDESTROY) {
        if (oldProc) {
            SetWindowLongPtrW(hWnd, GWLP_WNDPROC, (LONG_PTR)oldProc);
            g_OldWndProc = NULL;
        }
        // Close the pipe so the Python side gets a broken-pipe signal
        EnterCriticalSection(&g_PipeCS);
        if (g_hPipe != INVALID_HANDLE_VALUE) {
            CloseHandle(g_hPipe);
            g_hPipe = INVALID_HANDLE_VALUE;
        }
        LeaveCriticalSection(&g_PipeCS);
    }

    // Don't do any pipe I/O once we're detaching
    if (!g_Detaching && uMsg == WM_COPYDATA) {
        PCOPYDATASTRUCT pcds = (PCOPYDATASTRUCT)lParam;
        if (pcds && pcds->dwData == 1) {
            SendCopyDataToPipe(pcds);
        }
    }

    return CallWindowProc(oldProc, hWnd, uMsg, wParam, lParam);
}

// Monitors a named mutex held by the Python host process.
// If the host crashes or exits, the OS releases the
// mutex automatically, and this thread detects it and self-detaches the DLL.
DWORD WINAPI WatchdogThread(LPVOID lpParam) {
    HANDLE hMutex = OpenMutexW(SYNCHRONIZE, FALSE, L"Global\\YASBTrayHookAlive");
    if (!hMutex) {
        // Mutex doesn't exist — host is already gone
        DebugOutput("[DLL] Watchdog: host mutex not found, self-detaching.\n");
    } else {
        DebugOutput("[DLL] Watchdog active. Sleeping until host drops.\n");

        // Wait FOREVER until the host exits (WAIT_OBJECT_0) or crashes (WAIT_ABANDONED)
        DWORD result = WaitForSingleObject(hMutex, INFINITE);

        if (result == WAIT_ABANDONED || result == WAIT_OBJECT_0) {
            DebugOutput("[DLL] Watchdog: Host gone, self-detaching.\n");
        } else {
            DebugOutput("[DLL] Watchdog: wait failed/lost, self-detaching.\n");
        }

        CloseHandle(hMutex);
    }

    // Stop pipe I/O in the subclass proc before we tear things down
    InterlockedExchange(&g_Detaching, 1);
    OutputDebugStringA("[DLL] Detach: g_Detaching set.\n");

    // 1. Unhook the wndproc via PostMessage.
    //    Unlike SendMessage, PostMessage places the message in the queue.
    //    It is only dequeued when the UI thread returns to its top-level
    //    GetMessage loop — AFTER all nested SendMessage dispatches (autohide
    //    animations, etc.) have fully unwound. This guarantees no
    //    ManualSubclassProc frames are on the stack when we process it.
    HWND hTray = FindRealSystray();
    if (hTray && g_OldWndProc) {
        OutputDebugStringA("[DLL] Detach: PostMessage WM_YASB_UNHOOK...\n");
        PostMessageW(hTray, WM_YASB_UNHOOK, 0, 0);
        // Wait for the UI thread to process the posted message and signal completion
        DWORD waitResult = WaitForSingleObject(g_hUnhookDoneEvent, 5000);
        if (waitResult == WAIT_OBJECT_0) {
            OutputDebugStringA("[DLL] Detach: Unhook confirmed by UI thread.\n");
        } else {
            OutputDebugStringA("[DLL] Detach: Unhook wait timed out!\n");
        }
    } else {
        OutputDebugStringA("[DLL] Detach: No tray or wndproc to unhook.\n");
    }

    // 2. Close the pipe
    EnterCriticalSection(&g_PipeCS);
    if (g_hPipe != INVALID_HANDLE_VALUE) {
        FlushFileBuffers(g_hPipe);
        CloseHandle(g_hPipe);
        g_hPipe = INVALID_HANDLE_VALUE;
    }
    LeaveCriticalSection(&g_PipeCS);
    OutputDebugStringA("[DLL] Detach: Pipe closed.\n");

    // 3. Clean up the event
    if (g_hUnhookDoneEvent) {
        CloseHandle(g_hUnhookDoneEvent);
        g_hUnhookDoneEvent = NULL;
    }

    // 4. Safe to unload — the wndproc is restored and no DLL code is on any stack
    OutputDebugStringA("[DLL] Detach: FreeLibraryAndExitThread now.\n");
    FreeLibraryAndExitThread(g_hModule, 0);
    return 0;
}

DWORD WINAPI InitThread(LPVOID lpParam) {
    // Create the event before connecting — watchdog will need it
    g_hUnhookDoneEvent = CreateEventW(NULL, TRUE, FALSE, NULL);

    g_hPipe = CreateFileW(L"\\\\.\\pipe\\yasb_systray_monitor", GENERIC_WRITE, 0, NULL, OPEN_EXISTING,
                          FILE_FLAG_OVERLAPPED, NULL);
    if (g_hPipe != INVALID_HANDLE_VALUE) {
        DebugOutput("[DLL] Pipeline connected.\n");
        HWND hTray = FindRealSystray();
        if (hTray) {
            DWORD windowPid;
            GetWindowThreadProcessId(hTray, &windowPid);
            if (windowPid == GetCurrentProcessId()) {
                g_OldWndProc = (WNDPROC)SetWindowLongPtrW(hTray, GWLP_WNDPROC, (LONG_PTR)ManualSubclassProc);
                if (g_OldWndProc) {
                    DebugOutput("[DLL] Successfully subclassed Shell_TrayWnd\n");
                }
            }
        }
    }
    // Start the watchdog to self-detach if the host process dies
    CreateThread(NULL, 0, WatchdogThread, NULL, 0, NULL);
    return 0;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    if (ul_reason_for_call == DLL_PROCESS_ATTACH) {
        InitializeCriticalSection(&g_PipeCS);
        DisableThreadLibraryCalls(hModule); // Removes the overhead of `DLL_THREAD_ATTACH` and `DLL_THREAD_DETACH` calls
        g_hModule = hModule;                // Save before any threads start
        CreateThread(NULL, 0, InitThread, NULL, 0, NULL);
    } else if (ul_reason_for_call == DLL_PROCESS_DETACH) {
        DeleteCriticalSection(&g_PipeCS);
    }
    return TRUE;
}
