import tkinter as tk
from tkinter import ttk, messagebox
import os

from models import AppConfig, SignLanguage, LengthLimitMode


class SettingsWindow:
    def __init__(self, parent, config: AppConfig, on_save, on_logout, bili_client, logger):
        self.window = tk.Toplevel(parent)
        self.window.title("BiliSteamSign - 设置")
        self.window.geometry("480x520")
        self.window.resizable(False, False)
        self.window.transient(parent)

        self.config = config
        self.on_save = on_save
        self.on_logout = on_logout
        self.bili = bili_client
        self.log = logger
        self._mousewheel_callback = None

        self._build_ui()

    def _build_ui(self):
        outer = ttk.Frame(self.window)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, highlightthickness=0)
        vscroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self._frame = ttk.Frame(canvas)

        self._frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._frame, anchor="nw", width=460)
        canvas.configure(yscrollcommand=vscroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        def _on_mousewheel(event):
            if not canvas.winfo_exists():
                return
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except tk.TclError:
                pass

        self._mousewheel_callback = _on_mousewheel
        self.window.bind("<MouseWheel>", self._mousewheel_callback)
        self.window.protocol("WM_DELETE_WINDOW", self._close)

        f = self._frame
        pad = {"padx": 10, "pady": 2}

        row = 0

        # Basic
        ttk.Label(f, text="基本设置", font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 5))
        row += 1

        self._enabled_var = tk.BooleanVar(value=self.config.enabled)
        ttk.Checkbutton(f, text="启用签名同步", variable=self._enabled_var).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        ttk.Label(f, text="签名语言:").grid(row=row, column=0, sticky="w", **pad)
        self._lang_var = tk.StringVar(value=self.config.language.value)
        ttk.Combobox(f, textvariable=self._lang_var, state="readonly", width=18,
                     values=["chinese", "chinese_strict", "english"]).grid(row=row, column=1, **pad)
        row += 1

        ttk.Label(f, text="Steam检测间隔(秒):").grid(row=row, column=0, sticky="w", **pad)
        self._poll_var = tk.IntVar(value=self.config.steam_poll_interval)
        ttk.Spinbox(f, from_=5, to=300, textvariable=self._poll_var, width=8).grid(row=row, column=1, **pad)
        row += 1

        ttk.Label(f, text="签名同步冷却(秒):").grid(row=row, column=0, sticky="w", **pad)
        self._cooldown_var = tk.IntVar(value=self.config.sign_sync_cooldown)
        ttk.Spinbox(f, from_=10, to=600, textvariable=self._cooldown_var, width=8).grid(row=row, column=1, **pad)
        row += 1

        # Sign
        ttk.Separator(f, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1

        ttk.Label(f, text="签名设置", font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        ttk.Label(f, text="游戏中模板:").grid(row=row, column=0, sticky="w", **pad)
        self._steam_template_var = tk.StringVar(value=self.config.steam_sign_template)
        template_frame = ttk.Frame(f)
        template_frame.grid(row=row, column=1, sticky="ew", **pad)
        ttk.Entry(template_frame, textvariable=self._steam_template_var, width=32).pack(side="left")
        ttk.Button(template_frame, text="预设", command=self._apply_template_preset).pack(side="left", padx=5)
        row += 1

        ttk.Label(f, text="非Steam模板:").grid(row=row, column=0, sticky="w", **pad)
        self._nonsteam_template_var = tk.StringVar(value=self.config.non_steam_sign_template)
        ttk.Entry(f, textvariable=self._nonsteam_template_var, width=36).grid(row=row, column=1, sticky="ew", **pad)
        row += 1

        ttk.Label(f, text="结束后签名:").grid(row=row, column=0, sticky="w", **pad)
        self._idle_sign_var = tk.StringVar(value=self.config.idle_sign)
        ttk.Entry(f, textvariable=self._idle_sign_var, width=36).grid(row=row, column=1, sticky="ew", **pad)
        row += 1

        ttk.Label(f, text="占位符: {game}=游戏名, {appid}=游戏ID, {uname}=B站昵称").grid(
            row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        ttk.Label(f, text="长度限制:").grid(row=row, column=0, sticky="w", **pad)
        limit_frame = ttk.Frame(f)
        limit_frame.grid(row=row, column=1, **pad)
        self._limit_var = tk.StringVar(value=self.config.length_limit_mode.value)
        ttk.Combobox(limit_frame, textvariable=self._limit_var, state="readonly", width=8,
                     values=["off", "custom", "auto"]).pack(side="left")
        ttk.Label(limit_frame, text="自定义:").pack(side="left", padx=(10, 2))
        self._custom_limit_var = tk.IntVar(value=self.config.custom_length_limit)
        ttk.Spinbox(limit_frame, from_=10, to=250, textvariable=self._custom_limit_var, width=5).pack(side="left")
        row += 1

        self._exclude_nonsteam_var = tk.BooleanVar(value=self.config.exclude_non_steam)
        ttk.Checkbutton(f, text="排除非Steam游戏", variable=self._exclude_nonsteam_var).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        # Exclusion
        ttk.Separator(f, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1

        ttk.Label(f, text="排除游戏列表 (每行一个)", font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        self._excluded_text = tk.Text(f, height=4, width=50, font=("Consolas", 9))
        self._excluded_text.grid(row=row, column=0, columnspan=2, **pad)
        for game in self.config.excluded_games:
            self._excluded_text.insert(tk.END, game + "\n")
        row += 1

        # Account
        ttk.Separator(f, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1

        ttk.Label(f, text="账号", font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        self._account_var = tk.StringVar(value="检测中...")
        ttk.Label(f, textvariable=self._account_var).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        acct_btns = ttk.Frame(f)
        acct_btns.grid(row=row, column=0, columnspan=2, **pad)
        ttk.Button(acct_btns, text="重新登录", command=self._relogin).pack(side="left", padx=5)
        ttk.Button(acct_btns, text="退出登录", command=self._do_logout).pack(side="left", padx=5)
        row += 1

        # Advanced
        ttk.Separator(f, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1

        ttk.Label(f, text="高级", font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        self._notify_var = tk.BooleanVar(value=self.config.notify_enabled)
        ttk.Checkbutton(f, text="显示通知", variable=self._notify_var).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        self._autostart_var = tk.BooleanVar()
        try:
            from autostart import is_enabled
            self._autostart_var.set(is_enabled())
        except Exception:
            self._autostart_var.set(False)
        ttk.Checkbutton(f, text="开机自启", variable=self._autostart_var).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        # Buttons
        ttk.Separator(f, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1

        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="保存", command=self._save).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="取消", command=self._close).pack(side="left", padx=10)

        self._check_account()

    def _check_account(self):
        def _do():
            info = self.bili.get_user_info()
            name = info.get("uname", "") if info else ""
            self.window.after(0, lambda: self._account_var.set(
                f"当前: {name} ✓" if name else "未登录"
            ))

        import threading
        threading.Thread(target=_do, daemon=True).start()

    def _relogin(self):
        from gui_login import LoginWindow
        LoginWindow(self.window, self.bili, self._check_account, self.log)

    def _do_logout(self):
        if messagebox.askyesno("确认", "退出登录后将停止签名同步，确认？", parent=self.window):
            self.on_logout()
            self._account_var.set("未登录")

    def _save(self):
        excluded_raw = self._excluded_text.get("1.0", tk.END).strip()
        excluded = [g.strip() for g in excluded_raw.split("\n") if g.strip()]

        self.config.enabled = self._enabled_var.get()
        self.config.language = SignLanguage(self._lang_var.get())
        self.config.steam_poll_interval = self._poll_var.get()
        self.config.sign_sync_cooldown = self._cooldown_var.get()
        self.config.length_limit_mode = LengthLimitMode(self._limit_var.get())
        self.config.custom_length_limit = self._custom_limit_var.get()
        self.config.steam_sign_template = self._steam_template_var.get().strip() or "正在玩 {game}"
        self.config.non_steam_sign_template = self._nonsteam_template_var.get().strip() or "非Steam游戏中"
        self.config.idle_sign = self._idle_sign_var.get().strip()
        self.config.exclude_non_steam = self._exclude_nonsteam_var.get()
        self.config.excluded_games = excluded
        self.config.notify_enabled = self._notify_var.get()
        self.config.auto_start = self._autostart_var.get()

        try:
            from autostart import enable, disable
            import sys
            if self.config.auto_start:
                main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
                if getattr(sys, "frozen", False):
                    command = f'"{sys.executable}"'
                else:
                    pythonw_path = os.path.join(
                        os.path.dirname(sys.executable), "pythonw.exe"
                    )
                    python_path = pythonw_path if os.path.exists(pythonw_path) else sys.executable
                    command = f'"{python_path}" "{main_path}"'
                enable(command)
            else:
                disable()
        except Exception:
            pass

        self.on_save(self.config)
        self._close()

    def _apply_template_preset(self):
        menu = tk.Menu(self.window, tearoff=False)
        presets = [
            "{uname} 正在玩 {game}",
            "🎮 正在玩 {game}",
            "BiliSteamSign 正在玩 {game}",
            "Playing {game}",
            "正在玩 {game} ({appid})",
            "{uname} 正在玩 {game}",
        ]
        for template in presets:
            menu.add_command(
                label=template,
                command=lambda value=template: self._steam_template_var.set(value),
            )
        menu.tk_popup(self.window.winfo_pointerx(), self.window.winfo_pointery())

    def _close(self):
        if self._mousewheel_callback is not None:
            try:
                self.window.unbind("<MouseWheel>")
            except tk.TclError:
                pass
            self._mousewheel_callback = None
        self.window.destroy()
