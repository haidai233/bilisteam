import re
from typing import Optional

import requests

BILI_SPACE_API = "https://api.bilibili.com/x/space/acc/info"
BILI_SIGN_API = "https://api.bilibili.com/x/member/web/sign/update"
BILI_NAV_API = "https://api.bilibili.com/x/web-interface/nav"
BILI_ACCOUNT_API = "https://api.bilibili.com/x/member/web/account"
QR_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
QR_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
_LOGIN_COOKIE_NAMES = ("SESSDATA", "bili_jct", "DedeUserID")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}


class BiliClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)
        self.sessdata = ""
        self.bili_jct = ""
        self.dede_user_id = ""

    def set_cookies(self, sessdata: str, bili_jct: str, dede_user_id: str):
        self.sessdata = sessdata
        self.bili_jct = bili_jct
        self.dede_user_id = dede_user_id
        self._apply_cookies()

    def _apply_cookies(self):
        self.session.cookies.set("SESSDATA", self.sessdata, domain=".bilibili.com")
        self.session.cookies.set("bili_jct", self.bili_jct, domain=".bilibili.com")
        self.session.cookies.set("DedeUserID", self.dede_user_id, domain=".bilibili.com")

    def check_cookies_valid(self) -> tuple[bool, str]:
        if not self.sessdata:
            return False, "missing"
        nav_data, nav_error = self._get_nav_data_with_error()
        if nav_data:
            return bool(nav_data.get("isLogin")), "ok"
        if nav_error == "not_logged_in":
            return False, "expired"
        return True, "unknown"

    def get_user_sign(self) -> tuple[bool, str]:
        if not self.dede_user_id:
            return False, "No UID"
        account_data = self._get_account_data()
        if account_data:
            sign = (
                account_data.get("sign")
                or account_data.get("user_sign")
                or account_data.get("usersign")
                or ""
            )
            return True, sign
        try:
            resp = self.session.get(
                BILI_SPACE_API, params={"mid": self.dede_user_id}, timeout=10
            )
            data = resp.json()
            if data.get("code") != 0:
                return False, f"API error: {data.get('code')} {data.get('message', '')}"
            return True, data["data"].get("usersign", "")
        except requests.RequestException as e:
            return False, str(e)

    def get_user_info(self) -> Optional[dict]:
        account_data = self._get_account_data()
        if account_data:
            return account_data
        if not self.dede_user_id:
            return None
        try:
            resp = self.session.get(
                BILI_SPACE_API, params={"mid": self.dede_user_id}, timeout=10
            )
            data = resp.json()
            if data.get("code") != 0:
                return None
            return data["data"]
        except requests.RequestException:
            return None

    def update_sign(self, sign_text: str) -> tuple[bool, str]:
        if not self.bili_jct:
            return False, "No csrf token"
        try:
            resp = self.session.post(
                BILI_SIGN_API,
                data={"user_sign": sign_text, "usersign": sign_text, "csrf": self.bili_jct},
                timeout=10,
            )
            data = resp.json()
            code = data.get("code", -1)
            if code == 0:
                return True, "OK"
            msg = data.get("message", "Unknown error")
            if code == -101:
                return False, "COOKIE_EXPIRED"
            if code == -509:
                return False, "RATE_LIMITED"
            if code == 500104:
                return False, "SIGN_VIOLATION"
            return False, f"API error {code}: {msg}"
        except requests.Timeout:
            return False, "TIMEOUT"
        except requests.RequestException as e:
            return False, str(e)

    def generate_qr_code(self) -> tuple[Optional[str], Optional[str]]:
        try:
            resp = self.session.get(QR_GENERATE_URL, timeout=10)
            data = resp.json()
            if data.get("code") != 0:
                return None, None
            url = data["data"]["url"]
            qrcode_key = data["data"]["qrcode_key"]
            return qrcode_key, url
        except requests.RequestException:
            return None, None

    def poll_qr_status(self, qrcode_key: str) -> dict:
        try:
            resp = self.session.get(
                QR_POLL_URL, params={"qrcode_key": qrcode_key}, timeout=10
            )
            data = resp.json()

            if data.get("code") != 0:
                return {"status": "error", "message": data.get("message", "")}

            inner = data.get("data", {})
            qr_code = inner.get("code", -1)

            if qr_code == 0:
                self._collect_response_cookies(resp)
                cookies = self._get_login_cookies()
                refresh_token = inner.get("refresh_token", "")
                return {
                    "status": "confirmed",
                    "cookies": cookies,
                    "refresh_token": refresh_token,
                }
            elif qr_code == 86101:
                return {"status": "waiting"}
            elif qr_code == 86090:
                return {"status": "scanned"}
            elif qr_code == 86038:
                return {"status": "expired"}
            else:
                return {"status": "error", "message": inner.get("message", "")}
        except requests.RequestException as e:
            return {"status": "error", "message": str(e)}

    def _collect_response_cookies(self, resp: requests.Response):
        cookie_headers = []
        raw_headers = getattr(getattr(resp, "raw", None), "headers", None)
        if raw_headers and hasattr(raw_headers, "get_all"):
            cookie_headers.extend(raw_headers.get_all("Set-Cookie"))
        if not cookie_headers:
            cookie_header = resp.headers.get("Set-Cookie", "")
            if cookie_header:
                cookie_headers.append(cookie_header)
        if not cookie_headers:
            return

        for cookie_header in cookie_headers:
            for name in _LOGIN_COOKIE_NAMES:
                match = re.search(rf"(?:^|,\s*){name}=([^;,]+)", cookie_header)
                if match:
                    self.session.cookies.set(
                        name, match.group(1), domain=".bilibili.com"
                    )

    def _get_login_cookies(self) -> dict[str, str]:
        cookies = {cookie.name: cookie.value for cookie in self.session.cookies}
        sessdata = cookies.get("SESSDATA", "")
        bili_jct = cookies.get("bili_jct", "")
        dede_user_id = cookies.get("DedeUserID", "")

        if sessdata and bili_jct and not dede_user_id:
            nav_data = self._get_nav_data()
            mid = nav_data.get("mid")
            if mid:
                dede_user_id = str(mid)
                self.session.cookies.set(
                    "DedeUserID", dede_user_id, domain=".bilibili.com"
                )

        return {
            "SESSDATA": sessdata,
            "bili_jct": bili_jct,
            "DedeUserID": dede_user_id,
        }

    def _get_nav_data(self) -> dict:
        data, _ = self._get_nav_data_with_error()
        return data

    def _get_nav_data_with_error(self) -> tuple[dict, str]:
        try:
            resp = self.session.get(BILI_NAV_API, timeout=10)
            data = resp.json()
        except requests.RequestException:
            return {}, "network"
        code = data.get("code")
        if code == -101:
            return {}, "not_logged_in"
        if code != 0:
            return {}, "api"
        return data.get("data", {}) or {}, "ok"

    def _get_account_data(self) -> dict:
        try:
            resp = self.session.get(BILI_ACCOUNT_API, timeout=10)
            data = resp.json()
        except requests.RequestException:
            return {}
        if data.get("code") != 0:
            return {}
        return data.get("data", {}) or {}
