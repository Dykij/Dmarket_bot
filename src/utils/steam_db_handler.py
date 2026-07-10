"""Steam DB handler."""


class SteamDB:
    def get_settings(self) -> dict:
        return {}

    def update_steam_price(self, title: str, price: float) -> None:
        pass

    def get_steam_data(self, title: str) -> dict | None:
        return None

    def is_cache_actual(self, title: str) -> bool:
        return False

    def is_blacklisted(self, title: str) -> bool:
        return False

    def remove_from_blacklist(self, title: str) -> None:
        pass


_steam_db: SteamDB | None = None


def get_steam_db() -> SteamDB:
    global _steam_db
    if _steam_db is None:
        _steam_db = SteamDB()
    return _steam_db
