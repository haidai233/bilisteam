import ctypes
import ctypes.wintypes
import threading
import tkinter as tk

# --- Type aliases (must come first) ---
LRESULT = ctypes.c_ssize_t
HWND = ctypes.wintypes.HWND
UINT = ctypes.wintypes.UINT
WPARAM = ctypes.wintypes.WPARAM
LPARAM = ctypes.wintypes.LPARAM
UINT_PTR = ctypes.c_size_t

# --- Constants ---
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 1
NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_ICON = 2
NIF_TIP = 4
NIF_MESSAGE = 1
NIF_INFO = 16
NIIF_INFO = 1
NIIF_ERROR = 3
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
TPM_RETURNCMD = 0x0100
TPM_RIGHTBUTTON = 0x0002

# --- DLLs ---
shell32 = ctypes.windll.shell32
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
kernel32.GetModuleHandleW.restype = ctypes.wintypes.HMODULE
user32.DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.PostMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.PostMessageW.restype = ctypes.wintypes.BOOL
user32.RegisterClassExW.restype = ctypes.wintypes.ATOM
user32.CreateWindowExW.restype = HWND
user32.GetMessageW.argtypes = [ctypes.POINTER(ctypes.wintypes.MSG), HWND, UINT, UINT]
user32.GetMessageW.restype = ctypes.wintypes.BOOL
user32.SetForegroundWindow.argtypes = [HWND]
user32.SetForegroundWindow.restype = ctypes.wintypes.BOOL
user32.DestroyWindow.argtypes = [HWND]
user32.DestroyWindow.restype = ctypes.wintypes.BOOL
user32.PostQuitMessage.argtypes = [ctypes.c_int]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("hWnd", HWND),
        ("uID", ctypes.wintypes.UINT),
        ("uFlags", ctypes.wintypes.UINT),
        ("uCallbackMessage", ctypes.wintypes.UINT),
        ("hIcon", ctypes.wintypes.HICON),
        ("szTip", ctypes.c_wchar * 128),
        ("dwState", ctypes.wintypes.DWORD),
        ("dwStateMask", ctypes.wintypes.DWORD),
        ("szInfo", ctypes.c_wchar * 256),
        ("uVersion", ctypes.wintypes.UINT),
        ("szInfoTitle", ctypes.c_wchar * 64),
        ("dwInfoFlags", ctypes.wintypes.DWORD),
    ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.UINT),
        ("style", ctypes.wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.wintypes.HINSTANCE),
        ("hIcon", ctypes.wintypes.HICON),
        ("hCursor", ctypes.wintypes.HANDLE),
        ("hbrBackground", ctypes.wintypes.HBRUSH),
        ("lpszMenuName", ctypes.c_wchar_p),
        ("lpszClassName", ctypes.c_wchar_p),
        ("hIconSm", ctypes.wintypes.HICON),
    ]


user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.CreateWindowExW.argtypes = [
    ctypes.wintypes.DWORD,
    ctypes.c_wchar_p,
    ctypes.c_wchar_p,
    ctypes.wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    HWND,
    ctypes.wintypes.HMENU,
    ctypes.wintypes.HINSTANCE,
    ctypes.c_void_p,
]
user32.LoadIconW.argtypes = [ctypes.wintypes.HINSTANCE, ctypes.c_void_p]
user32.LoadIconW.restype = ctypes.wintypes.HICON
user32.CreatePopupMenu.argtypes = []
user32.CreatePopupMenu.restype = ctypes.wintypes.HMENU
user32.InsertMenuW.argtypes = [
    ctypes.wintypes.HMENU,
    ctypes.wintypes.UINT,
    ctypes.wintypes.UINT,
    UINT_PTR,
    ctypes.c_wchar_p,
]
user32.InsertMenuW.restype = ctypes.wintypes.BOOL
user32.TrackPopupMenu.argtypes = [
    ctypes.wintypes.HMENU,
    ctypes.wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    HWND,
    ctypes.c_void_p,
]
user32.TrackPopupMenu.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.POINTER(ctypes.wintypes.MSG)]
user32.TranslateMessage.restype = ctypes.wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(ctypes.wintypes.MSG)]
user32.DispatchMessageW.restype = LRESULT
shell32.Shell_NotifyIconW.argtypes = [
    ctypes.wintypes.DWORD,
    ctypes.POINTER(NOTIFYICONDATAW),
]
shell32.Shell_NotifyIconW.restype = ctypes.wintypes.BOOL


WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)


class TrayIcon:
    def __init__(self, root: tk.Tk, on_show=None, on_quit=None, on_pause=None):
        self._root = root
        self._on_show = on_show
        self._on_quit = on_quit
        self._on_pause = on_pause
        self._hwnd = None
        self._icon = None
        self._menu = None
        self._nid = None
        self._thread = None
        self._stop_event = threading.Event()
        self._wnd_proc_ref = None

    def start(self, tooltip: str = "BiliSteamSign"):
        self._thread = threading.Thread(target=self._run, args=(tooltip,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._hwnd:
            user32.PostMessageW(self._hwnd, 0x0010, 0, 0)

    def update_tooltip(self, text: str):
        if self._nid:
            self._nid.szTip = text[:127]
            self._nid.uFlags = NIF_TIP
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))

    def show_balloon(self, title: str, text: str, error: bool = False):
        if not self._nid:
            return
        self._nid.uFlags = NIF_INFO
        self._nid.szInfoTitle = title[:63]
        self._nid.szInfo = text[:255]
        self._nid.dwInfoFlags = NIIF_ERROR if error else NIIF_INFO
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))

    def _run(self, tooltip: str):
        hinstance = kernel32.GetModuleHandleW(None)
        class_name = "BiliSteamSignTray"

        self._wnd_proc_ref = WNDPROC(self._wnd_proc)

        wnd_class = WNDCLASSEXW()
        wnd_class.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wnd_class.lpfnWndProc = ctypes.cast(self._wnd_proc_ref, ctypes.c_void_p)
        wnd_class.hInstance = hinstance
        wnd_class.lpszClassName = class_name

        user32.RegisterClassExW(ctypes.byref(wnd_class))

        self._hwnd = user32.CreateWindowExW(
            0, class_name, "BiliSteamSign", 0, 0, 0, 0, 0,
            0, 0, hinstance, None
        )

        self._icon = user32.LoadIconW(None, 32512)

        self._nid = NOTIFYICONDATAW()
        self._nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self._nid.hWnd = self._hwnd
        self._nid.uID = 1
        self._nid.uFlags = NIF_ICON | NIF_TIP | NIF_MESSAGE
        self._nid.uCallbackMessage = WM_TRAYICON
        self._nid.hIcon = self._icon
        self._nid.szTip = tooltip[:127]
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid))

        self._menu = user32.CreatePopupMenu()
        user32.InsertMenuW(self._menu, 0, 0x400, 1001, "打开主窗口")
        user32.InsertMenuW(self._menu, 0, 0x400, 1002, "暂停同步")
        user32.InsertMenuW(self._menu, 0, 0x800, 0, None)
        user32.InsertMenuW(self._menu, 0, 0x400, 1003, "退出")

        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
            if self._stop_event.is_set():
                break

        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
        user32.DestroyWindow(self._hwnd)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAYICON:
                if lparam == WM_LBUTTONUP and self._on_show:
                    self._root.after(0, self._on_show)
                elif lparam == WM_RBUTTONUP:
                    user32.SetForegroundWindow(hwnd)
                    cmd = user32.TrackPopupMenu(
                        self._menu, TPM_RETURNCMD | TPM_RIGHTBUTTON, 0, 0, 0, hwnd, None
                    )
                    if cmd == 1001 and self._on_show:
                        self._root.after(0, self._on_show)
                    elif cmd == 1002 and self._on_pause:
                        self._root.after(0, self._on_pause)
                    elif cmd == 1003 and self._on_quit:
                        self._root.after(0, self._on_quit)
            elif msg == 0x0010:  # WM_CLOSE
                user32.PostQuitMessage(0)
                return 0
        except (OverflowError, ValueError, ctypes.ArgumentError, tk.TclError):
            pass
        try:
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        except (OverflowError, ValueError, ctypes.ArgumentError):
            return 0
