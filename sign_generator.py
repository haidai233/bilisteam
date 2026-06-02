from models import AppConfig, SteamStatus, GameState, SignLanguage, LengthLimitMode

BILI_SIGN_MAX_LEN = 60


class SignGenerator:
    _TEMPLATES = {
        SignLanguage.CHINESE: {
            "steam": "正在玩 {game}",
            "non_steam": "非Steam游戏中",
        },
        SignLanguage.CHINESE_STRICT: {
            "steam": "正在玩 {game}",
            "non_steam": "非Steam游戏中",
        },
        SignLanguage.ENGLISH: {
            "steam": "Playing: {game}",
            "non_steam": "Playing Non-steam Game",
        },
    }

    def generate(self, status: SteamStatus, config: AppConfig, original_sign: str = "", uname: str = "") -> str | None:
        if status.state == GameState.IDLE:
            return config.idle_sign if config.idle_sign else original_sign

        if status.state == GameState.NON_STEAM_GAME:
            if config.exclude_non_steam:
                return None
            template = config.non_steam_sign_template or self._TEMPLATES[config.language]["non_steam"]
            sign = self._format_template(template, status, "非Steam游戏", uname)
            return self._apply_length(sign, config)

        if status.state == GameState.STEAM_GAME:
            if self._is_excluded(status.game_name, config.excluded_games):
                return None

            game_name = status.game_name

            if config.language == SignLanguage.CHINESE_STRICT:
                if not self._is_chinese(game_name):
                    game_name = f"游戏 ({status.appid})"

            template = config.steam_sign_template or self._TEMPLATES[config.language]["steam"]
            sign = self._format_template(template, status, game_name, uname)
            return self._apply_length(sign, config)

        return None

    def _is_excluded(self, game_name: str, excluded: list[str]) -> bool:
        lower_name = game_name.lower()
        return lower_name in [g.lower() for g in excluded]

    def _is_chinese(self, text: str) -> bool:
        if not text:
            return False
        for ch in text:
            if '一' <= ch <= '鿿':
                return True
        return False

    def _format_template(self, template: str, status: SteamStatus, game_name: str, uname: str = "") -> str:
        try:
            return template.format(game=game_name, appid=status.appid, uname=uname)
        except (KeyError, ValueError):
            return f"正在玩 {game_name}"

    def _apply_length(self, sign: str, config: AppConfig) -> str:
        if config.length_limit_mode == LengthLimitMode.OFF:
            return sign

        if config.length_limit_mode == LengthLimitMode.CUSTOM:
            max_len = config.custom_length_limit
        else:
            max_len = BILI_SIGN_MAX_LEN

        if len(sign) <= max_len:
            return sign
        if max_len <= 3:
            return sign[:max_len]
        return sign[:max_len - 3] + "..."
