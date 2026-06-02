import json
import os
import time
import requests
import winreg

CACHE_DIR = os.path.join(os.getenv("APPDATA", "."), "BiliSteamSign")
CACHE_FILE = os.path.join(CACHE_DIR, "game_cache.json")

STEAM_API_URL = "https://store.steampowered.com/api/appdetails"
MIN_REQUEST_INTERVAL = 1.0
MAX_HOURLY_REQUESTS = 200


class GameResolver:
    def __init__(self):
        self._cache: dict[int, dict] = {}
        self._last_request_time = 0.0
        self._hourly_count = 0
        self._hourly_start = time.time()
        self._load_cache()

    def resolve(self, appid: int, prefer_chinese: bool = True) -> str:
        if appid in self._cache:
            entry = self._cache[appid]
            key = "zh" if prefer_chinese else "en"
            fallback_key = "en" if prefer_chinese else "zh"
            return entry.get(key) or entry.get(fallback_key) or f"Unknown App ({appid})"

        name = self._read_registry(appid)
        if name:
            self._cache[appid] = {"zh": name, "en": name}
            self._save_cache()
            return name

        name = self._fetch_steam_api(appid)
        if name:
            self._save_cache()
            key = "zh" if prefer_chinese else "en"
            entry = self._cache.get(appid, {})
            return entry.get(key) or entry.get("en") or f"Unknown App ({appid})"

        return f"Unknown App ({appid})"

    def has_chinese_name(self, appid: int) -> bool:
        if appid not in self._cache:
            self.resolve(appid, prefer_chinese=True)
        entry = self._cache.get(appid, {})
        return bool(entry.get("zh"))

    def _read_registry(self, appid: int) -> str | None:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                rf"Software\Valve\Steam\Apps\{appid}"
            )
            name, _ = winreg.QueryValueEx(key, "Name")
            winreg.CloseKey(key)
            return name if name else None
        except (FileNotFoundError, OSError):
            return None

    def _fetch_steam_api(self, appid: int) -> str | None:
        now = time.time()
        if now - self._hourly_start >= 3600:
            self._hourly_count = 0
            self._hourly_start = now
        if self._hourly_count >= MAX_HOURLY_REQUESTS:
            return None

        elapsed = now - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)

        for attempt in range(3):
            try:
                self._last_request_time = time.time()
                self._hourly_count += 1

                resp_zh = requests.get(
                    STEAM_API_URL,
                    params={"appids": appid, "cc": "cn", "l": "schinese"},
                    headers={"User-Agent": "BiliSteamSign/1.0"},
                    timeout=10,
                )
                if resp_zh.status_code == 429:
                    time.sleep(2 ** (attempt + 1))
                    continue

                data_zh = resp_zh.json()
                app_data = data_zh.get(str(appid), {})

                if not app_data.get("success"):
                    return None

                name_zh = app_data["data"].get("name", "")

                name_en = ""
                try:
                    resp_en = requests.get(
                        STEAM_API_URL,
                        params={"appids": appid, "cc": "us", "l": "english"},
                        headers={"User-Agent": "BiliSteamSign/1.0"},
                        timeout=10,
                    )
                    data_en = resp_en.json()
                    app_data_en = data_en.get(str(appid), {})
                    if app_data_en.get("success"):
                        name_en = app_data_en["data"].get("name", "")
                except requests.RequestException:
                    pass

                self._cache[appid] = {
                    "zh": name_zh or name_en,
                    "en": name_en or name_zh,
                }
                return name_zh or name_en or None

            except requests.RequestException:
                if attempt < 2:
                    time.sleep(2 ** (attempt + 1))

        return None

    def _load_cache(self):
        if not os.path.exists(CACHE_FILE):
            return
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for k, v in raw.items():
                try:
                    self._cache[int(k)] = v
                except (ValueError, TypeError):
                    pass
        except (json.JSONDecodeError, OSError):
            pass

    def _save_cache(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        data = {str(k): v for k, v in self._cache.items()}
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
