import ctypes
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging
import traceback

from logger import setup_logger
from config import ConfigManager
from credential_store import CredentialStore
from bili_client import BiliClient
from steam_monitor import SteamMonitor
from game_resolver import GameResolver
from sign_generator import SignGenerator
from sign_sync import SignSync
from event_queue import EventQueue, Event, EventType
from models import AppConfig

APP_NAME = "BiliSteamSign"
VERSION = "1.0.0"


def _single_instance_guard() -> bool:
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW(None, False, f"{APP_NAME}_Mutex")
    return ctypes.GetLastError() != 183


class App:
    def __init__(self):
        self.log = setup_logger()
        self.config_mgr = ConfigManager()
        self.config = self.config_mgr.load()

        self.eq = EventQueue()
        self.bili = BiliClient()
        self.resolver = GameResolver()
        self.generator = SignGenerator()
        self.monitor = SteamMonitor(
            poll_interval=self.config.steam_poll_interval,
            confirm_count=self.config.stability_confirm_count,
        )
        self.sync = SignSync(
            self.bili, self.resolver, self.generator, self.eq, self.log
        )

        self._tray = None
        self._paused = False

        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{VERSION}")
        self.root.geometry("820x340")
        self.root.resizable(True, True)

        self._build_ui()
        self._setup_tray()
        self.eq.start_polling(self.root, self._on_events)

        self.root.protocol("WM_DELETE_WINDOW", self._on_minimize)

        self.root.after(100, self._auto_start)

    def _build_ui(self):
        # Status
        status_frame = ttk.LabelFrame(self.root, text="状态", padding=10)
        status_frame.pack(fill="x", padx=10, pady=5)

        self._steam_var = tk.StringVar(value="Steam: 未检测到游戏")
        self._sign_var = tk.StringVar(value="签名: 等待同步")
        self._cookie_var = tk.StringVar(value="Cookie: 未登录")

        ttk.Label(status_frame, textvariable=self._steam_var).pack(anchor="w")
        ttk.Label(status_frame, textvariable=self._sign_var).pack(anchor="w")
        ttk.Label(status_frame, textvariable=self._cookie_var).pack(anchor="w")

        # Controls
        ctrl_frame = ttk.LabelFrame(self.root, text="控制", padding=10)
        ctrl_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(ctrl_frame, text="扫码登录", command=self._on_qr_login).pack(side="left", padx=5)
        self._start_btn = ttk.Button(ctrl_frame, text="启动同步", command=self._on_start)
        self._start_btn.pack(side="left", padx=5)
        self._stop_btn = ttk.Button(ctrl_frame, text="停止同步", command=self._on_stop, state="disabled")
        self._stop_btn.pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="手动检查", command=self._on_manual_check).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="修改签名", command=self._on_manual_sign).pack(side="left", padx=5)
        self._pause_btn = ttk.Button(ctrl_frame, text="暂停", command=self._toggle_pause)
        self._pause_btn.pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="设置", command=self._open_settings).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="退出登录", command=self._on_logout).pack(side="right", padx=5)
        ttk.Button(ctrl_frame, text="退出", command=self._on_quit).pack(side="right", padx=5)

        # Log
        log_frame = ttk.LabelFrame(self.root, text="日志", padding=5)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self._log_text = tk.Text(log_frame, height=6, state="disabled", font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scrollbar.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        handler = _TextHandler(self._log_text)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
        ))
        self.log.addHandler(handler)

    def _setup_tray(self):
        try:
            from tray_icon import TrayIcon
            self._tray = TrayIcon(
                root=self.root,
                on_show=self._show_window,
                on_quit=self._on_quit,
                on_pause=self._toggle_pause,
            )
            self._tray.start()
        except Exception as e:
            self.log.warning(f"Tray icon unavailable: {e}")

    def _auto_start(self):
        creds = CredentialStore.load()
        if creds:
            self._append_log("发现已保存的凭证，自动启动...")
            self._on_start()
        else:
            self._append_log('未登录，请点击"扫码登录"。')

    def _on_qr_login(self):
        from gui_login import LoginWindow
        LoginWindow(self.root, self.bili, self._on_qr_success, self.log)

    def _on_qr_success(self):
        self._append_log("扫码登录成功，启动同步...")
        self._on_start()

    def _on_logout(self):
        self._on_stop()
        CredentialStore.clear()
        self._cookie_var.set("Cookie: 未登录")
        self._append_log("已退出登录。")

    def _on_start(self):
        self.config = self.config_mgr.load()

        self.monitor = SteamMonitor(
            poll_interval=self.config.steam_poll_interval,
            confirm_count=self.config.stability_confirm_count,
        )

        if self.sync.start(self.config):
            self._cookie_var.set("Cookie: ✓ 有效")
            self.monitor.start(self._on_steam_change)
            self._start_btn.configure(state="disabled")
            self._stop_btn.configure(state="normal")
            self._append_log("同步已启动，正在检查当前 Steam 状态。")
            if self._tray:
                self._tray.show_balloon(APP_NAME, "签名同步已启动")
        else:
            self._cookie_var.set("Cookie: ✗ 过期或无效")
            self._append_log("启动失败，请查看控制台日志；若提示 Cookie 失效再重新登录。")

    def _on_stop(self):
        self.monitor.stop()
        self.sync.stop()
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._steam_var.set("Steam: 未检测到游戏")
        self._append_log("同步已停止。")

    def _toggle_pause(self):
        self._paused = not self._paused
        self._pause_btn.configure(text="恢复" if self._paused else "暂停")
        self._append_log("已暂停。" if self._paused else "已恢复。")
        if self._tray:
            self._tray.show_balloon(APP_NAME, "已暂停" if self._paused else "已恢复")

    def _on_manual_check(self):
        status = self.monitor.get_current_status()
        self._append_log("手动检查 Steam 状态...")
        self._on_steam_change(status)

    def _on_manual_sign(self):
        if not self.bili.bili_jct:
            messagebox.showwarning("提示", "请先登录B站")
            return
        sign_text = simpledialog.askstring("修改签名", "请输入新的B站签名:", parent=self.root)
        if sign_text is None:
            return
        sign_text = sign_text.strip()
        if not sign_text:
            messagebox.showwarning("提示", "签名不能为空")
            return
        success, msg = self.bili.update_sign(sign_text)
        if success:
            self.sync.mark_manual_sign(sign_text)
            self._sign_var.set(f"签名: {sign_text[:40]}")
            self._append_log(f"手动签名已更新: {sign_text}")
        else:
            self._append_log(f"手动签名更新失败: {msg}")
            messagebox.showerror("更新失败", msg)

    def _open_settings(self):
        from gui_settings import SettingsWindow

        def on_save(cfg: AppConfig):
            self.config = cfg
            self.config_mgr.save()
            self._append_log("设置已保存。")

        def on_logout():
            self._on_logout()

        SettingsWindow(self.root, self.config, on_save, on_logout, self.bili, self.log)

    def _on_steam_change(self, status):
        if self._paused:
            return
        if status.state.value == "idle":
            self.log.info("Steam status: idle")
        else:
            self.log.info(f"Steam status: {status.state.value}, AppID={status.appid}")
        self.eq.put(Event(EventType.STEAM_STATUS_CHANGED, status))
        self.sync.on_steam_status_changed(status)

    def _on_events(self, events: list[Event]):
        for event in events:
            if event.type == EventType.STEAM_STATUS_CHANGED:
                status = event.data
                if status.state.value == "idle":
                    self._steam_var.set("Steam: 未检测到游戏")
                else:
                    name = status.game_name or f"AppID {status.appid}"
                    self._steam_var.set(f"Steam: 正在玩 {name}")
                if self._tray:
                    self._tray.update_tooltip(
                        f"{APP_NAME} - {self._steam_var.get()}"
                    )
            elif event.type == EventType.SIGN_UPDATED:
                data = event.data
                self._sign_var.set(f"签名: {data['sign'][:40]}")
                if self._tray and self.config.notify_enabled:
                    self._tray.show_balloon("签名已更新", data['sign'][:50])
            elif event.type == EventType.COOKIE_EXPIRED:
                self._cookie_var.set("Cookie: ✗ 过期")
                self._on_stop()
                if self._tray:
                    self._tray.show_balloon("Cookie过期", "请重新登录", error=True)
                messagebox.showwarning("提示", "Cookie已过期，请重新登录")

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()

    def _on_minimize(self):
        self.root.withdraw()
        if self._tray:
            self._tray.show_balloon(APP_NAME, "程序在后台运行")

    def _on_quit(self):
        self._on_stop()
        if self._tray:
            self._tray.stop()
        self.root.destroy()

    def _append_log(self, text: str):
        self._log_text.configure(state="normal")
        self._log_text.insert(tk.END, text + "\n")
        self._log_text.see(tk.END)
        self._log_text.configure(state="disabled")

    def run(self):
        self.root.mainloop()


class _TextHandler(logging.Handler):
    def __init__(self, text_widget: tk.Text):
        super().__init__()
        self._widget = text_widget

    def emit(self, record):
        msg = self.format(record) + "\n"
        try:
            self._widget.configure(state="normal")
            self._widget.insert(tk.END, msg)
            self._widget.see(tk.END)
            self._widget.configure(state="disabled")
        except tk.TclError:
            pass


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if not _single_instance_guard():
        print(f"{APP_NAME} is already running.")
        sys.exit(0)

    app = App()
    app.run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        setup_logger().exception("Unhandled application error")
        import tkinter.messagebox as mb
        mb.showerror("BiliSteamSign", "程序发生错误，请查看日志。")
        raise
