import json
import os
from models import AppConfig, SignLanguage, LengthLimitMode

CONFIG_DIR = os.path.join(os.getenv("APPDATA", "."), "BiliSteamSign")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

_ENUM_MAP = {
    "language": SignLanguage,
    "length_limit_mode": LengthLimitMode,
}


class ConfigManager:
    def __init__(self):
        self.config = AppConfig()

    def load(self) -> AppConfig:
        if not os.path.exists(CONFIG_FILE):
            self.config = AppConfig()
            return self.config

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            self.config = AppConfig()
            return self.config

        for key, value in data.items():
            if not hasattr(self.config, key):
                continue
            if key in _ENUM_MAP:
                try:
                    value = _ENUM_MAP[key](value)
                except ValueError:
                    continue
            setattr(self.config, key, value)

        return self.config

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = {}
        defaults = AppConfig()
        for key in defaults.__dataclass_fields__:
            value = getattr(self.config, key)
            if isinstance(value, (SignLanguage, LengthLimitMode)):
                value = value.value
            if value != getattr(defaults, key):
                data[key] = value

        if data:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
