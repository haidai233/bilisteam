import threading
import winreg
from models import SteamStatus, GameState


class SteamMonitor:
    def __init__(self, poll_interval: int = 60, confirm_count: int = 2):
        self.poll_interval = poll_interval
        self.confirm_count = confirm_count
        self._stop_event = threading.Event()
        self._last_stable_appid = 0
        self._pending_appid = -1
        self._pending_count = 0
        self._callback = None
        self._steam_cache: dict[int, bool] = {}
        self._thread = None

    def get_running_appid(self) -> int:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            appid, _ = winreg.QueryValueEx(key, "RunningAppID")
            winreg.CloseKey(key)
            return appid if appid else 0
        except (FileNotFoundError, OSError):
            return 0

    def is_steam_game(self, appid: int) -> bool:
        if appid in self._steam_cache:
            return self._steam_cache[appid]
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                rf"Software\Valve\Steam\Apps\{appid}"
            )
            installed, _ = winreg.QueryValueEx(key, "Installed")
            winreg.CloseKey(key)
            is_steam = installed == 1
        except (FileNotFoundError, OSError):
            is_steam = False
        self._steam_cache[appid] = is_steam
        return is_steam

    def get_app_name(self, appid: int) -> str | None:
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

    def start(self, callback):
        self.stop()
        self._callback = callback
        self._stop_event.clear()
        self._last_stable_appid = self.get_running_appid()
        self._pending_appid = -1
        self._pending_count = 0
        if self._callback:
            self._callback(self._build_status(self._last_stable_appid))
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def get_current_status(self) -> SteamStatus:
        return self._build_status(self.get_running_appid())

    def _poll_loop(self):
        while not self._stop_event.is_set():
            current_appid = self.get_running_appid()

            if current_appid == self._last_stable_appid:
                self._pending_appid = -1
                self._pending_count = 0
            elif current_appid == self._pending_appid:
                self._pending_count += 1
                if self._pending_count >= self.confirm_count:
                    self._confirm_change(current_appid)
            else:
                self._pending_appid = current_appid
                self._pending_count = 1

            self._stop_event.wait(self.poll_interval)

    def _confirm_change(self, appid: int):
        old_appid = self._last_stable_appid
        self._last_stable_appid = appid
        self._pending_appid = -1
        self._pending_count = 0

        if self._callback:
            self._callback(self._build_status(appid))

    def _build_status(self, appid: int) -> SteamStatus:
        if appid == 0:
            return SteamStatus(state=GameState.IDLE)
        if self.is_steam_game(appid):
            return SteamStatus(appid=appid, state=GameState.STEAM_GAME)
        return SteamStatus(appid=appid, state=GameState.NON_STEAM_GAME)
