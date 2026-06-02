import tkinter as tk
from tkinter import ttk
import threading


class LoginWindow:
    def __init__(self, parent, bili_client, on_success, logger):
        self.window = tk.Toplevel(parent)
        self.window.title("BiliSteamSign - 扫码登录B站")
        self.window.geometry("360x400")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        self.bili = bili_client
        self.on_success = on_success
        self.log = logger
        self._polling = False
        self._qrcode_key = None
        self._poll_fail_count = 0

        self._build_ui()
        self._generate_qr()

    def _build_ui(self):
        self._qr_canvas = tk.Canvas(self.window, width=240, height=240, bg="white")
        self._qr_canvas.pack(pady=15)

        self._qr_status = tk.StringVar(value="正在生成二维码...")
        ttk.Label(self.window, textvariable=self._qr_status, wraplength=320).pack(pady=5)

        self._qr_timer = tk.StringVar(value="")
        ttk.Label(self.window, textvariable=self._qr_timer).pack()

        ttk.Button(self.window, text="刷新二维码", command=self._generate_qr).pack(pady=15)

    def _generate_qr(self):
        self.bili.session.cookies.clear()
        self._stop_polling()
        self._qr_canvas.delete("all")
        self._qr_status.set("正在生成二维码...")
        self._qr_timer.set("")

        def _gen():
            qrcode_key, url = self.bili.generate_qr_code()
            if not qrcode_key or not url:
                self.log.error("QR code generation failed")
                self.window.after(0, lambda: self._qr_status.set("生成失败，请重试"))
                return
            self._qrcode_key = qrcode_key
            self.log.info("QR code generated")
            self.window.after(0, lambda: self._draw_qr(url))

        threading.Thread(target=_gen, daemon=True).start()

    def _draw_qr(self, url: str):
        try:
            import qrcode
            qr = qrcode.QRCode(box_size=6, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            matrix = qr.get_matrix()

            size = len(matrix)
            cell = min(240 // size, 10)
            offset_x = (240 - size * cell) // 2
            offset_y = (240 - size * cell) // 2

            self._qr_canvas.delete("all")
            for row in range(size):
                for col in range(size):
                    x1 = offset_x + col * cell
                    y1 = offset_y + row * cell
                    x2 = x1 + cell
                    y2 = y1 + cell
                    color = "black" if matrix[row][col] else "white"
                    self._qr_canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")

            self._qr_status.set("请使用B站APP扫描二维码")
            self._start_polling()
            self._start_countdown(180)
        except ImportError:
            self._qr_status.set("请安装 qrcode 库: pip install qrcode")

    def _start_countdown(self, seconds: int):
        self._countdown_remaining = seconds

        def _tick():
            if not self._polling:
                return
            if self._countdown_remaining <= 0:
                self._qr_timer.set("已过期，请点击刷新")
                self._stop_polling()
                return
            m, s = divmod(self._countdown_remaining, 60)
            self._qr_timer.set(f"倒计时: {m:02d}:{s:02d}")
            self._countdown_remaining -= 1
            self.window.after(1000, _tick)

        _tick()

    def _start_polling(self):
        self._polling = True
        self._poll_fail_count = 0
        self._poll_loop()

    def _stop_polling(self):
        self._polling = False

    def _poll_loop(self):
        if not self._polling or not self._qrcode_key:
            return

        def _do_poll():
            result = self.bili.poll_qr_status(self._qrcode_key)
            self.window.after(0, lambda: self._handle_poll_result(result))

        threading.Thread(target=_do_poll, daemon=True).start()

    def _handle_poll_result(self, result: dict):
        if not self._polling:
            return

        status = result.get("status")
        if status != "waiting":
            self.log.info(f"QR poll status: {status}")

        if status == "confirmed":
            self._polling = False
            self._qr_timer.set("")
            cookies = result.get("cookies", {})
            sessdata = cookies.get("SESSDATA", "")
            bili_jct = cookies.get("bili_jct", "")
            uid = cookies.get("DedeUserID", "")

            if not all([sessdata, bili_jct, uid]):
                self.log.error(f"QR login cookie incomplete: {sorted(cookies)}")
                self._qr_status.set("登录失败：Cookie不完整")
                return

            from credential_store import CredentialStore
            self.bili.set_cookies(sessdata, bili_jct, uid)
            CredentialStore.save(sessdata, bili_jct, uid)
            self._qr_status.set("登录成功！")
            self.log.info("QR code login successful")
            self.window.after(500, self._on_success)
            return

        if status == "scanned":
            self._qr_status.set("已扫描，请在手机上确认...")
        elif status == "expired":
            self._polling = False
            self._qr_status.set("二维码已过期，请点击刷新")
            return
        elif status == "error":
            self._poll_fail_count += 1
            self.log.warning(
                f"QR poll failed ({self._poll_fail_count}/3): {result.get('message', '')}"
            )
            if self._poll_fail_count >= 3:
                self._poll_fail_count = 0
                self.window.after(10000, self._poll_loop)
                return

        self.window.after(3000, self._poll_loop)

    def _on_success(self):
        self.on_success()
        self.window.destroy()
