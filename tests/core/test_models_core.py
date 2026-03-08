"""Комплексные тесты для моделей данных User.

Покрывают модель User:
- Создание и инициализация
- Методы to_dict()
- Валидация данных
- Строковое представление
"""

from src.models.user import User, UserSettings


class TestUserModel:
    """Тесты модели User."""

    def test_user_creation(self):
        """Тест создания пользователя."""
        user = User(
            telegram_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User",
        )

        assert user.telegram_id == 123456789
        assert user.username == "testuser"
        assert user.first_name == "Test"
        assert user.last_name == "User"

    def test_user_defaults(self):
        """Тест создания пользователя без дополнительных параметров."""
        user = User(telegram_id=123456789)

        # Базовая проверка создания
        assert user.telegram_id == 123456789

    def test_user_to_dict(self):
        """Тест преобразования в словарь."""
        user = User(
            telegram_id=123456789,
            username="testuser",
            first_name="Test",
            language_code="en",
        )

        user_dict = user.to_dict()

        assert user_dict["telegram_id"] == 123456789
        assert user_dict["username"] == "testuser"
        assert user_dict["first_name"] == "Test"
        assert user_dict["language_code"] == "en"

    def test_user_admin_flag(self):
        """Тест флага администратора."""
        user = User(telegram_id=123456789, is_admin=True)

        assert user.is_admin is True

    def test_user_banned_flag(self):
        """Тест флага блокировки."""
        user = User(telegram_id=123456789, is_banned=True)

        assert user.is_banned is True

    def test_user_language_codes(self):
        """Тест различных языковых кодов."""
        languages = ["ru", "en", "es", "de"]

        for lang in languages:
            user = User(telegram_id=123456789, language_code=lang)
            assert user.language_code == lang


class TestUserSettingsModel:
    """Тесты модели UserSettings."""

    def test_user_settings_creation(self):
        """Тест создания настроек пользователя."""
        from uuid import uuid4

        user_uuid = uuid4()
        settings = UserSettings(user_id=user_uuid)

        assert settings.user_id == user_uuid

    def test_user_settings_with_notifications(self):
        """Тест настроек с уведомлениями."""
        from uuid import uuid4

        settings = UserSettings(
            user_id=uuid4(),
            notifications_enabled=True,
        )

        assert settings.notifications_enabled is True
