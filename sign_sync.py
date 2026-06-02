import os
import time
import logging
import threading

from models import SteamStatus, GameState, AppConfig
from bili_client import BiliClient
from game_resolver import GameResolver
from sign_generator import SignGenerator
from credential_store import CredentialStore
from event_queue import EventQueue, Event, EventType

ORIGINAL_SIGN_FILE = os.path.join(
    os.getenv("APPDATA", "."), "BiliSteamSign", "original_sign.txt"
)


class SignSync:
    def __init__(
        self,
        bili: BiliClient,
        resolver: GameResolver,
        generator: SignGenerator,
        event_queue: EventQueue,
        logger: logging.Logger,
    ):
        self.bili = bili
        self.resolver = resolver
        self.generator = generator
        self.eq = event_queue
        self.log = logger
        self._last_sync_time = 0.0
        self._current_sign = ""
        self._original_sign = ""
        self._last_set_sign = ""
        self._uname = ""
        self._running = False
        self._config: AppConfig | None = None
        self._lock = threading.Lock()

    def start(self, config: AppConfig) -> bool:
        self._config = config

        creds = CredentialStore.load()
        if not creds:
            self.log.info("No credentials found")
            return False

        self.bili.set_cookies(*creds)

        cookies_valid, cookie_status = self.bili.check_cookies_valid()
        if not cookies_valid:
            self.log.warning(f"Cookies invalid: {cookie_status}")
            CredentialStore.clear()
            self.eq.put(Event(EventType.COOKIE_EXPIRED))
            return False
        if cookie_status == "unknown":
            self.log.warning("Could not verify cookies due to network/API error; reusing saved credentials")

        user_info = self.bili.get_user_info()
        if user_info:
            self._uname = user_info.get("uname", "")

        success, current_sign = self.bili.get_user_sign()
        if success:
            self._original_sign = current_sign
            self._current_sign = current_sign
            self._save_original_sign(current_sign)
            self.log.info(f"Original sign saved: {current_sign[:30]}...")
        else:
            self.log.error(f"Failed to read sign: {current_sign}")
            if "-799" in current_sign or "频繁" in current_sign:
                self.log.warning("Bilibili rate limited sign read; wait a moment and retry")
            return False

        self._running = True
        self.log.info("SignSync started")
        return True

    def stop(self):
        with self._lock:
            was_running = self._running
            self._running = False
            if was_running and self._config and self._original_sign:
                self._restore_original_sign()
            self.log.info("SignSync stopped")

    def on_steam_status_changed(self, status: SteamStatus):
        with self._lock:
            self._on_steam_status_changed_locked(status)

    def _on_steam_status_changed_locked(self, status: SteamStatus):
        if not self._running or not self._config:
            return
        if not self._config.enabled:
            return

        if status.state == GameState.STEAM_GAME and status.appid > 0:
            prefer_cn = True
            status.game_name = self.resolver.resolve(status.appid, prefer_cn)
            self.log.info(f"Resolved Steam game: {status.game_name} ({status.appid})")

        new_sign = self.generator.generate(status, self._config, self._original_sign, self._uname)
        if new_sign is None:
            self.log.info("Generated sign is empty; skipping update")
            return

        restore_sign = self.get_restore_sign()
        should_restore = status.state == GameState.IDLE and new_sign == restore_sign
        if should_restore:
            if self._current_sign == new_sign:
                return
            restored = self._restore_original_sign()
            if restored:
                self.eq.put(Event(EventType.SIGN_UPDATED, {
                    "sign": new_sign,
                    "status": status,
                }))
            return

        now = time.time()
        if not should_restore:
            if now - self._last_sync_time < self._config.sign_sync_cooldown:
                self.log.info("Sync cooldown active, skipping")
                return

        if new_sign == self._current_sign:
            self.log.info("Generated sign unchanged; skipping update")
            return

        success, msg = self.bili.update_sign(new_sign)
        if success:
            self._current_sign = new_sign
            self._last_set_sign = new_sign
            self._last_sync_time = time.time()
            self.log.info(f"Sign updated: {new_sign}")
            self.eq.put(Event(EventType.SIGN_UPDATED, {
                "sign": new_sign,
                "status": status,
            }))
        else:
            self.log.error(f"Sign update failed: {msg}")
            if msg == "COOKIE_EXPIRED":
                CredentialStore.clear()
                self.eq.put(Event(EventType.COOKIE_EXPIRED))
            elif msg == "RATE_LIMITED":
                self._last_sync_time = time.time() + 240

    def _restore_original_sign(self) -> bool:
        restore_sign = self.get_restore_sign()
        server_sign = ""
        success, current = self.bili.get_user_sign()
        if not success:
            self.log.error(f"Failed to read current sign before restore: {current}")
            return False
        server_sign = current

        if server_sign and self._last_set_sign and server_sign != self._last_set_sign:
            self.log.info(
                f"Sign was changed externally, keeping: {server_sign[:30]}..."
            )
            self._original_sign = server_sign
            self._current_sign = server_sign
            return False

        if restore_sign and server_sign != restore_sign:
            success, msg = self.bili.update_sign(restore_sign)
            if success:
                self._current_sign = restore_sign
                self._last_set_sign = restore_sign
                self._last_sync_time = time.time()
                self.log.info("Restore sign applied")
                return True
            else:
                self.log.error(f"Failed to restore sign: {msg}")
                return False
        changed_locally = self._current_sign != restore_sign
        self._current_sign = restore_sign
        return changed_locally

    def get_restore_sign(self) -> str:
        if self._config and self._config.idle_sign:
            return self._config.idle_sign
        return self._original_sign

    def mark_manual_sign(self, sign: str):
        with self._lock:
            self._current_sign = sign
            self._last_set_sign = sign

    def _save_original_sign(self, sign: str):
        os.makedirs(os.path.dirname(ORIGINAL_SIGN_FILE), exist_ok=True)
        with open(ORIGINAL_SIGN_FILE, "w", encoding="utf-8") as f:
            f.write(sign)

    def load_original_sign(self) -> str:
        if os.path.exists(ORIGINAL_SIGN_FILE):
            try:
                with open(ORIGINAL_SIGN_FILE, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except OSError:
                pass
        return ""

    def get_original_sign(self) -> str:
        return self._original_sign
