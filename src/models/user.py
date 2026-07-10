"""User model."""
from dataclasses import dataclass


@dataclass
class User:
    telegram_id: int
    username: str
    first_name: str | None = None
    last_name: str | None = None
    language_code: str = "en"
    is_active: bool | None = True

    def to_dict(self) -> dict:
        return {
            "telegram_id": self.telegram_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "language_code": self.language_code,
            "is_active": self.is_active,
        }


@dataclass
class UserSettings:
    user_id: str
    default_game: str | None = None
    notifications_enabled: bool = True
    language: str = "en"
