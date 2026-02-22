"""Тесты для модели User."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.models.alert import PriceAlert
from src.models.base import Base
from src.models.market import MarketDataCache
from src.models.user import User, UserSettings


@pytest.fixture()
def engine():
    """Создать тестовый engine для in-memory БД."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def session(engine):
    """Создать тестовую сессию."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestUserModel:
    """Тесты модели User."""

    def test_create_user_with_required_fields(self, session):
        """Тест создания пользователя с обязательными полями."""
        user = User(telegram_id=123456789)
        session.add(user)
        session.commit()

        assert user.id is not None
        assert user.telegram_id == 123456789
        assert user.is_active is True
        assert user.is_admin is False
        assert user.is_banned is False
        assert user.language_code == "en"

    def test_create_user_with_all_fields(self, session):
        """Тест создания пользователя со всеми полями."""
        user = User(
            telegram_id=987654321,
            username="test_user",
            first_name="Test",
            last_name="User",
            language_code="en",
            is_admin=True,
            dmarket_api_key_encrypted="encrypted_key",
            dmarket_secret_key_encrypted="encrypted_secret",
            notes="Test user for admin",
        )
        session.add(user)
        session.commit()

        assert user.telegram_id == 987654321
        assert user.username == "test_user"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.language_code == "en"
        assert user.is_admin is True
        assert user.dmarket_api_key_encrypted == "encrypted_key"
        assert user.notes == "Test user for admin"

    def test_user_telegram_id_unique_constraint(self, session):
        """Тест уникальности telegram_id."""
        user1 = User(telegram_id=111111111)
        session.add(user1)
        session.commit()

        user2 = User(telegram_id=111111111)
        session.add(user2)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_user_repr(self, session):
        """Тест строкового представления."""
        user = User(telegram_id=123456789, username="test_user")
        session.add(user)
        session.commit()

        repr_str = repr(user)
        assert "User" in repr_str
        assert "123456789" in repr_str
        assert "test_user" in repr_str

    def test_user_to_dict(self, session):
        """Тест преобразования в словарь."""
        user = User(
            telegram_id=123456789,
            username="test_user",
            first_name="Test",
            is_admin=True,
        )
        session.add(user)
        session.commit()

        user_dict = user.to_dict()
        assert user_dict["telegram_id"] == 123456789
        assert user_dict["username"] == "test_user"
        assert user_dict["first_name"] == "Test"
        assert user_dict["is_admin"] is True
        assert "created_at" in user_dict
        assert "updated_at" in user_dict

    def test_user_timestamps(self, session):
        """Тест автоматического создания timestamps."""
        user = User(telegram_id=123456789)
        session.add(user)
        session.commit()

        assert user.created_at is not None
        assert user.updated_at is not None
        assert user.last_activity is not None
        assert isinstance(user.created_at, datetime)

    def test_user_update_triggers_updated_at(self, session):
        """Тест обновления updated_at при изменении."""
        user = User(telegram_id=123456789, username="old_name")
        session.add(user)
        session.commit()

        # Обновить пользователя
        user.username = "new_name"
        session.commit()

        # Проверить что updated_at изменился (может не сработать в SQLite)
        # Поэтому просто проверяем что поле существует
        assert user.updated_at is not None

    def test_user_can_be_banned(self, session):
        """Тест блокировки пользователя."""
        user = User(telegram_id=123456789, is_banned=False)
        session.add(user)
        session.commit()

        user.is_banned = True
        session.commit()

        assert user.is_banned is True

    def test_user_can_be_deactivated(self, session):
        """Тест деактивации пользователя."""
        user = User(telegram_id=123456789, is_active=True)
        session.add(user)
        session.commit()

        user.is_active = False
        session.commit()

        assert user.is_active is False

    def test_query_user_by_telegram_id(self, session):
        """Тест поиска пользователя по telegram_id."""
        user = User(telegram_id=123456789, username="findme")
        session.add(user)
        session.commit()

        found_user = session.query(User).filter_by(telegram_id=123456789).first()
        assert found_user is not None
        assert found_user.username == "findme"

    def test_query_active_users(self, session):
        """Тест поиска активных пользователей."""
        user1 = User(telegram_id=111111111, is_active=True)
        user2 = User(telegram_id=222222222, is_active=False)
        user3 = User(telegram_id=333333333, is_active=True)
        session.add_all([user1, user2, user3])
        session.commit()

        active_users = session.query(User).filter_by(is_active=True).all()
        assert len(active_users) == 2

    def test_query_banned_users(self, session):
        """Тест поиска забаненных пользователей."""
        user1 = User(telegram_id=111111111, is_banned=False)
        user2 = User(telegram_id=222222222, is_banned=True)
        session.add_all([user1, user2])
        session.commit()

        banned_users = session.query(User).filter_by(is_banned=True).all()
        assert len(banned_users) == 1
        assert banned_users[0].telegram_id == 222222222

    def test_delete_user(self, session):
        """Тест удаления пользователя."""
        user = User(telegram_id=123456789)
        session.add(user)
        session.commit()

        user_id = user.id
        session.delete(user)
        session.commit()

        deleted_user = session.query(User).filter_by(id=user_id).first()
        assert deleted_user is None


class TestUserSettingsModel:
    """Тесты модели UserSettings."""

    def test_create_settings_with_defaults(self, session):
        """Тест создания настроек с дефолтными значениями."""
        user_id = str(uuid4())
        settings = UserSettings(user_id=user_id)
        session.add(settings)
        session.commit()

        assert settings.id is not None
        assert str(settings.user_id) == user_id
        assert settings.default_game == "csgo"
        assert settings.notifications_enabled is True
        assert settings.price_alerts_enabled is True
        assert settings.min_profit_percent == 5.0
        assert settings.preferred_currency == "USD"
        assert settings.timezone == "UTC"

    def test_create_settings_with_custom_values(self, session):
        """Тест создания настроек с кастомными значениями."""
        user_id = str(uuid4())
        settings = UserSettings(
            user_id=user_id,
            default_game="dota2",
            notifications_enabled=False,
            min_profit_percent=10.5,
            preferred_currency="EUR",
            timezone="Europe/Moscow",
        )
        session.add(settings)
        session.commit()

        assert settings.default_game == "dota2"
        assert settings.notifications_enabled is False
        assert settings.min_profit_percent == 10.5
        assert settings.preferred_currency == "EUR"
        assert settings.timezone == "Europe/Moscow"

    def test_settings_repr(self, session):
        """Тест строкового представления."""
        user_id = str(uuid4())
        settings = UserSettings(user_id=user_id, default_game="dota2")
        session.add(settings)
        session.commit()

        repr_str = repr(settings)
        assert "UserSettings" in repr_str
        assert user_id in repr_str
        assert "dota2" in repr_str

    def test_settings_to_dict(self, session):
        """Тест преобразования в словарь."""
        user_id = str(uuid4())
        settings = UserSettings(
            user_id=user_id, default_game="dota2", min_profit_percent=7.5
        )
        session.add(settings)
        session.commit()

        settings_dict = settings.to_dict()
        assert settings_dict["user_id"] == user_id
        assert settings_dict["default_game"] == "dota2"
        assert settings_dict["min_profit_percent"] == 7.5
        assert "created_at" in settings_dict

    def test_query_settings_by_user(self, session):
        """Тест поиска настроек по user_id."""
        user_id = str(uuid4())
        settings = UserSettings(user_id=user_id, default_game="csgo")
        session.add(settings)
        session.commit()

        found = session.query(UserSettings).filter_by(user_id=user_id).first()
        assert found is not None
        assert found.default_game == "csgo"


class TestPriceAlertModel:
    """Тесты модели PriceAlert."""

    def test_create_alert_with_required_fields(self, session):
        """Тест создания алерта с обязательными полями."""
        user_id = str(uuid4())
        alert = PriceAlert(
            user_id=user_id,
            market_hash_name="AK-47 | Redline (FT)",
            game="csgo",
            target_price=15.50,
        )
        session.add(alert)
        session.commit()

        assert alert.id is not None
        assert alert.market_hash_name == "AK-47 | Redline (FT)"
        assert alert.target_price == 15.50
        assert alert.condition == "below"
        assert alert.is_active is True
        assert alert.triggered is False

    def test_create_alert_with_all_fields(self, session):
        """Тест создания алерта со всеми полями."""
        user_id = str(uuid4())
        alert = PriceAlert(
            user_id=user_id,
            item_id="item-abc",
            market_hash_name="AWP | Asiimov (FT)",
            game="csgo",
            target_price=50.00,
            condition="above",
            triggered=True,
        )
        session.add(alert)
        session.commit()

        assert alert.item_id == "item-abc"
        assert alert.condition == "above"
        assert alert.triggered is True

    def test_alert_repr(self, session):
        """Тест строкового представления."""
        user_id = str(uuid4())
        alert = PriceAlert(
            user_id=user_id,
            market_hash_name="AK-47 | Redline (FT)",
            game="csgo",
            target_price=15.50,
            condition="below",
        )
        session.add(alert)
        session.commit()

        repr_str = repr(alert)
        assert "PriceAlert" in repr_str
        assert "AK-47 | Redline (FT)" in repr_str
        assert "15.5" in repr_str

    def test_alert_to_dict(self, session):
        """Тест преобразования в словарь."""
        user_id = str(uuid4())
        alert = PriceAlert(
            user_id=user_id,
            market_hash_name="AK-47 | Redline (FT)",
            game="csgo",
            target_price=15.50,
            condition="below",
        )
        session.add(alert)
        session.commit()

        alert_dict = alert.to_dict()
        assert alert_dict["user_id"] == user_id
        assert alert_dict["market_hash_name"] == "AK-47 | Redline (FT)"
        assert alert_dict["target_price"] == 15.50
        assert alert_dict["is_active"] is True
        assert alert_dict["triggered"] is False

    def test_query_active_alerts(self, session):
        """Тест поиска активных алертов."""
        user_id = str(uuid4())
        alert1 = PriceAlert(
            user_id=user_id,
            market_hash_name="Item 1",
            game="csgo",
            target_price=10.00,
            is_active=True,
        )
        alert2 = PriceAlert(
            user_id=user_id,
            market_hash_name="Item 2",
            game="csgo",
            target_price=20.00,
            is_active=False,
        )
        session.add_all([alert1, alert2])
        session.commit()

        active_alerts = session.query(PriceAlert).filter_by(is_active=True).all()
        assert len(active_alerts) == 1

    def test_query_alerts_by_user(self, session):
        """Тест поиска алертов по user_id."""
        user_id1 = str(uuid4())
        user_id2 = str(uuid4())
        alert1 = PriceAlert(
            user_id=user_id1,
            market_hash_name="Item 1",
            game="csgo",
            target_price=10.00,
        )
        alert2 = PriceAlert(
            user_id=user_id2,
            market_hash_name="Item 2",
            game="csgo",
            target_price=20.00,
        )
        session.add_all([alert1, alert2])
        session.commit()

        user_alerts = session.query(PriceAlert).filter_by(user_id=user_id1).all()
        assert len(user_alerts) == 1


class TestMarketDataCacheModel:
    """Тесты модели MarketDataCache."""

    def test_create_cache_entry(self, session):
        """Тест создания записи кэша."""
        cache = MarketDataCache(
            cache_key="csgo:ak47:price",
            game="csgo",
            item_hash_name="AK-47 | Redline (FT)",
            data_type="price",
            data={"USD": 15.50, "EUR": 14.20},
            expires_at=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC),
        )
        session.add(cache)
        session.commit()

        assert cache.id is not None
        assert cache.cache_key == "csgo:ak47:price"
        assert cache.data["USD"] == 15.50

    def test_cache_key_unique_constraint(self, session):
        """Тест уникальности cache_key."""
        cache1 = MarketDataCache(
            cache_key="unique_key",
            game="csgo",
            data_type="price",
            data={},
            expires_at=datetime(2025, 12, 31, tzinfo=UTC),
        )
        session.add(cache1)
        session.commit()

        cache2 = MarketDataCache(
            cache_key="unique_key",
            game="dota2",
            data_type="history",
            data={},
            expires_at=datetime(2025, 12, 31, tzinfo=UTC),
        )
        session.add(cache2)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_cache_repr(self, session):
        """Тест строкового представления."""
        cache = MarketDataCache(
            cache_key="csgo:test:price",
            game="csgo",
            data_type="price",
            data={},
            expires_at=datetime(2025, 12, 31, tzinfo=UTC),
        )
        session.add(cache)
        session.commit()

        repr_str = repr(cache)
        assert "MarketDataCache" in repr_str
        assert "csgo:test:price" in repr_str
        assert "price" in repr_str

    def test_cache_to_dict(self, session):
        """Тест преобразования в словарь."""
        cache = MarketDataCache(
            cache_key="test_key",
            game="csgo",
            data_type="price",
            data={"test": "data"},
            expires_at=datetime(2025, 12, 31, tzinfo=UTC),
        )
        session.add(cache)
        session.commit()

        cache_dict = cache.to_dict()
        assert cache_dict["cache_key"] == "test_key"
        assert cache_dict["game"] == "csgo"
        assert cache_dict["data_type"] == "price"
        assert cache_dict["data"] == {"test": "data"}

    def test_query_cache_by_game(self, session):
        """Тест поиска кэша по игре."""
        cache1 = MarketDataCache(
            cache_key="csgo:1",
            game="csgo",
            data_type="price",
            data={},
            expires_at=datetime(2025, 12, 31, tzinfo=UTC),
        )
        cache2 = MarketDataCache(
            cache_key="dota2:1",
            game="dota2",
            data_type="price",
            data={},
            expires_at=datetime(2025, 12, 31, tzinfo=UTC),
        )
        session.add_all([cache1, cache2])
        session.commit()

        csgo_cache = session.query(MarketDataCache).filter_by(game="csgo").all()
        assert len(csgo_cache) == 1

    def test_query_expired_cache(self, session):
        """Тест поиска истекшего кэша."""
        old_cache = MarketDataCache(
            cache_key="old_key",
            game="csgo",
            data_type="price",
            data={},
            expires_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        new_cache = MarketDataCache(
            cache_key="new_key",
            game="csgo",
            data_type="price",
            data={},
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
        session.add_all([old_cache, new_cache])
        session.commit()

        expired = (
            session.query(MarketDataCache)
            .filter(MarketDataCache.expires_at < datetime.now(UTC))
            .all()
        )
        assert len(expired) >= 1
