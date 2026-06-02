from dataclasses import dataclass, field
from enum import Enum


class GameState(Enum):
    IDLE = "idle"
    STEAM_GAME = "steam_game"
    NON_STEAM_GAME = "non_steam"


class SignLanguage(Enum):
    CHINESE = "chinese"
    CHINESE_STRICT = "chinese_strict"
    ENGLISH = "english"


class LengthLimitMode(Enum):
    OFF = "off"
    CUSTOM = "custom"
    AUTO = "auto"


@dataclass
class SteamStatus:
    appid: int = 0
    game_name: str = ""
    state: GameState = GameState.IDLE


@dataclass
class AppConfig:
    enabled: bool = True
    language: SignLanguage = SignLanguage.CHINESE
    steam_poll_interval: int = 10
    sign_sync_cooldown: int = 60
    stability_confirm_count: int = 2
    excluded_games: list = field(default_factory=lambda: [
        "Wallpaper Engine", "OBS Studio"
    ])
    length_limit_mode: LengthLimitMode = LengthLimitMode.AUTO
    custom_length_limit: int = 32
    exclude_non_steam: bool = True
    auto_start: bool = False
    notify_enabled: bool = True
    steam_sign_template: str = "{uname} 正在玩 {game}"
    non_steam_sign_template: str = "非Steam游戏中"
    idle_sign: str = ""
