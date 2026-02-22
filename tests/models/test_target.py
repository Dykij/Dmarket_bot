"""Тесты для моделей Target, TradeHistory и TradingSettings."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.models.target import Base, Target, TradeHistory, TradingSettings


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


class TestTargetModel:
    """Тесты для модели Target."""

    def test_create_target_with_required_fields(self, session):
        """Тест создания таргета с обязательными полями."""
        target = Target(
            user_id=123456789,
            target_id="target_abc123",
            game="csgo",
            title="AK-47 | Redline (Field-Tested)",
            price=10.50,
        )
        session.add(target)
        session.commit()

        assert target.id is not None
        assert target.user_id == 123456789
        assert target.target_id == "target_abc123"
        assert target.game == "csgo"
        assert target.title == "AK-47 | Redline (Field-Tested)"
        assert target.price == 10.50
        assert target.amount == 1  # default
        assert target.status == "active"  # default

    def test_create_target_with_all_fields(self, session):
        """Тест создания таргета со всеми полями."""
        target = Target(
            user_id=987654321,
            target_id="target_xyz789",
            game="dota2",
            title="Arcana: Manifold Paradox",
            price=35.00,
            amount=2,
            status="active",
            attributes={"quality": "exalted", "hero": "phantom_assassin"},
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
        session.add(target)
        session.commit()

        assert target.id is not None
        assert target.amount == 2
        assert target.attributes["quality"] == "exalted"
        assert target.created_at is not None

    def test_target_id_unique_constraint(self, session):
        """Тест уникальности target_id."""
        target1 = Target(
            user_id=111,
            target_id="unique_target_123",
            game="csgo",
            title="Test Item 1",
            price=5.0,
        )
        session.add(target1)
        session.commit()

        target2 = Target(
            user_id=222,
            target_id="unique_target_123",  # Дубликат
            game="dota2",
            title="Test Item 2",
            price=10.0,
        )
        session.add(target2)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_target_repr(self, session):
        """Тест строкового представления."""
        target = Target(
            user_id=123,
            target_id="test_repr",
            game="csgo",
            title="AWP | Dragon Lore",
            price=5000.00,
        )
        session.add(target)
        session.commit()

        repr_str = repr(target)
        assert "Target" in repr_str
        assert "123" in repr_str
        assert "AWP | Dragon Lore" in repr_str
        assert "5000.00" in repr_str

    def test_target_to_dict(self, session):
        """Тест метода to_dict."""
        target = Target(
            user_id=456,
            target_id="test_dict",
            game="rust",
            title="Metal Facemask",
            price=2.50,
            amount=5,
            status="active",
            attributes={"skin": "blackout"},
        )
        session.add(target)
        session.commit()

        data = target.to_dict()
        assert data["user_id"] == 456
        assert data["target_id"] == "test_dict"
        assert data["game"] == "rust"
        assert data["title"] == "Metal Facemask"
        assert data["price"] == 2.50
        assert data["amount"] == 5
        assert data["status"] == "active"
        assert data["attributes"]["skin"] == "blackout"

    def test_query_targets_by_user(self, session):
        """Тест получения таргетов по пользователю."""
        target1 = Target(
            user_id=789, target_id="t1", game="csgo", title="Item 1", price=5.0
        )
        target2 = Target(
            user_id=789, target_id="t2", game="dota2", title="Item 2", price=10.0
        )
        target3 = Target(
            user_id=999, target_id="t3", game="csgo", title="Item 3", price=15.0
        )
        session.add_all([target1, target2, target3])
        session.commit()

        user_targets = session.query(Target).filter_by(user_id=789).all()
        assert len(user_targets) == 2
        assert all(t.user_id == 789 for t in user_targets)

    def test_query_targets_by_game(self, session):
        """Тест получения таргетов по игре."""
        target1 = Target(
            user_id=111, target_id="g1", game="csgo", title="CS Item", price=5.0
        )
        target2 = Target(
            user_id=222, target_id="g2", game="csgo", title="CS Item 2", price=10.0
        )
        target3 = Target(
            user_id=333, target_id="g3", game="dota2", title="Dota Item", price=15.0
        )
        session.add_all([target1, target2, target3])
        session.commit()

        csgo_targets = session.query(Target).filter_by(game="csgo").all()
        assert len(csgo_targets) == 2
        assert all(t.game == "csgo" for t in csgo_targets)

    def test_query_active_targets(self, session):
        """Тест получения активных таргетов."""
        target1 = Target(
            user_id=111,
            target_id="a1",
            game="csgo",
            title="Item 1",
            price=5.0,
            status="active",
        )
        target2 = Target(
            user_id=222,
            target_id="a2",
            game="csgo",
            title="Item 2",
            price=10.0,
            status="inactive",
        )
        target3 = Target(
            user_id=333,
            target_id="a3",
            game="csgo",
            title="Item 3",
            price=15.0,
            status="active",
        )
        session.add_all([target1, target2, target3])
        session.commit()

        active = session.query(Target).filter_by(status="active").all()
        assert len(active) == 2
        assert all(t.status == "active" for t in active)

    def test_update_target_status(self, session):
        """Тест обновления статуса таргета."""
        target = Target(
            user_id=555,
            target_id="upd1",
            game="csgo",
            title="Test",
            price=5.0,
            status="active",
        )
        session.add(target)
        session.commit()

        target.status = "completed"
        session.commit()

        updated = session.query(Target).filter_by(target_id="upd1").first()
        assert updated.status == "completed"

    def test_delete_target(self, session):
        """Тест удаления таргета."""
        target = Target(
            user_id=666, target_id="del1", game="csgo", title="Delete Me", price=5.0
        )
        session.add(target)
        session.commit()

        session.delete(target)
        session.commit()

        deleted = session.query(Target).filter_by(target_id="del1").first()
        assert deleted is None


class TestTradeHistoryModel:
    """Тесты для модели TradeHistory."""

    def test_create_trade_with_required_fields(self, session):
        """Тест создания записи сделки с обязательными полями."""
        trade = TradeHistory(
            user_id=123456789,
            trade_type="buy",
            item_title="AK-47 | Redline (FT)",
            price=10.50,
            game="csgo",
        )
        session.add(trade)
        session.commit()

        assert trade.id is not None
        assert trade.user_id == 123456789
        assert trade.trade_type == "buy"
        assert trade.item_title == "AK-47 | Redline (FT)"
        assert trade.price == 10.50
        assert trade.profit == 0.0  # default
        assert trade.status == "pending"  # default

    def test_create_trade_with_all_fields(self, session):
        """Тест создания записи сделки со всеми полями."""
        trade = TradeHistory(
            user_id=987654321,
            trade_type="sell",
            item_title="AWP | Asiimov (FT)",
            price=45.00,
            profit=5.50,
            game="csgo",
            status="completed",
            trade_metadata={"buyer_id": "user_abc", "transaction_id": "tx_123"},
            completed_at=datetime(2024, 1, 2, 15, 30, 0, tzinfo=UTC),
        )
        session.add(trade)
        session.commit()

        assert trade.profit == 5.50
        assert trade.status == "completed"
        assert trade.trade_metadata["buyer_id"] == "user_abc"
        assert trade.completed_at is not None

    def test_trade_repr(self, session):
        """Тест строкового представления."""
        trade = TradeHistory(
            user_id=123,
            trade_type="buy",
            item_title="M4A4 | Howl",
            price=1500.00,
            profit=150.00,
            game="csgo",
            status="completed",
        )
        session.add(trade)
        session.commit()

        repr_str = repr(trade)
        assert "TradeHistory" in repr_str
        assert "123" in repr_str
        assert "buy" in repr_str
        assert "M4A4 | Howl" in repr_str
        assert "1500.00" in repr_str

    def test_trade_to_dict(self, session):
        """Тест метода to_dict."""
        trade = TradeHistory(
            user_id=456,
            trade_type="target",
            item_title="Dragon Lore",
            price=5000.00,
            profit=500.00,
            game="csgo",
            status="completed",
            trade_metadata={"notes": "great deal"},
        )
        session.add(trade)
        session.commit()

        data = trade.to_dict()
        assert data["user_id"] == 456
        assert data["trade_type"] == "target"
        assert data["item_title"] == "Dragon Lore"
        assert data["price"] == 5000.00
        assert data["profit"] == 500.00
        assert data["status"] == "completed"
        assert data["trade_metadata"]["notes"] == "great deal"

    def test_query_trades_by_user(self, session):
        """Тест получения сделок по пользователю."""
        trade1 = TradeHistory(
            user_id=789,
            trade_type="buy",
            item_title="Item 1",
            price=5.0,
            game="csgo",
        )
        trade2 = TradeHistory(
            user_id=789,
            trade_type="sell",
            item_title="Item 2",
            price=10.0,
            game="csgo",
        )
        trade3 = TradeHistory(
            user_id=999,
            trade_type="buy",
            item_title="Item 3",
            price=15.0,
            game="csgo",
        )
        session.add_all([trade1, trade2, trade3])
        session.commit()

        user_trades = session.query(TradeHistory).filter_by(user_id=789).all()
        assert len(user_trades) == 2

    def test_query_trades_by_status(self, session):
        """Тест получения сделок по статусу."""
        trade1 = TradeHistory(
            user_id=111,
            trade_type="buy",
            item_title="Item 1",
            price=5.0,
            game="csgo",
            status="completed",
        )
        trade2 = TradeHistory(
            user_id=222,
            trade_type="buy",
            item_title="Item 2",
            price=10.0,
            game="csgo",
            status="pending",
        )
        session.add_all([trade1, trade2])
        session.commit()

        completed = session.query(TradeHistory).filter_by(status="completed").all()
        assert len(completed) == 1
        assert completed[0].status == "completed"

    def test_calculate_total_profit(self, session):
        """Тест расчета общей прибыли пользователя."""
        trades = [
            TradeHistory(
                user_id=555,
                trade_type="sell",
                item_title=f"Item {i}",
                price=10.0,
                profit=2.0,
                game="csgo",
            )
            for i in range(5)
        ]
        session.add_all(trades)
        session.commit()

        user_trades = session.query(TradeHistory).filter_by(user_id=555).all()
        total_profit = sum(t.profit for t in user_trades)
        assert total_profit == 10.0


class TestTradingSettingsModel:
    """Тесты для модели TradingSettings."""

    def test_create_settings_with_defaults(self, session):
        """Тест создания настроек со значениями по умолчанию."""
        settings = TradingSettings(user_id=123456789)
        session.add(settings)
        session.commit()

        assert settings.id is not None
        assert settings.user_id == 123456789
        assert settings.max_trade_value == 50.0
        assert settings.daily_limit == 500.0
        assert settings.min_profit_percent == 5.0
        assert settings.strategy == "balanced"
        # SQLite stores boolean as integer (0/1)
        assert not settings.auto_trading_enabled
        assert settings.notifications_enabled == 1

    def test_create_settings_with_custom_values(self, session):
        """Тест создания настроек с кастомными значениями."""
        settings = TradingSettings(
            user_id=987654321,
            max_trade_value=100.0,
            daily_limit=1000.0,
            min_profit_percent=10.0,
            strategy="aggressive",
            auto_trading_enabled=True,
            games_enabled=["csgo", "dota2", "tf2"],
            notifications_enabled=False,
        )
        session.add(settings)
        session.commit()

        assert settings.max_trade_value == 100.0
        assert settings.daily_limit == 1000.0
        assert settings.min_profit_percent == 10.0
        assert settings.strategy == "aggressive"
        # SQLite stores boolean as integer (0/1)
        assert settings.auto_trading_enabled
        assert len(settings.games_enabled) == 3
        assert not settings.notifications_enabled

    def test_user_id_unique_constraint(self, session):
        """Тест уникальности user_id."""
        settings1 = TradingSettings(user_id=111)
        session.add(settings1)
        session.commit()

        settings2 = TradingSettings(user_id=111)  # Дубликат
        session.add(settings2)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_settings_repr(self, session):
        """Тест строкового представления."""
        settings = TradingSettings(
            user_id=123, strategy="conservative", auto_trading_enabled=1
        )
        session.add(settings)
        session.commit()

        repr_str = repr(settings)
        assert "TradingSettings" in repr_str
        assert "123" in repr_str
        assert "conservative" in repr_str

    def test_settings_to_dict(self, session):
        """Тест метода to_dict."""
        settings = TradingSettings(
            user_id=456,
            max_trade_value=75.0,
            daily_limit=750.0,
            strategy="balanced",
            games_enabled=["csgo", "dota2"],
        )
        session.add(settings)
        session.commit()

        data = settings.to_dict()
        assert data["user_id"] == 456
        assert data["max_trade_value"] == 75.0
        assert data["daily_limit"] == 750.0
        assert data["strategy"] == "balanced"
        assert "csgo" in data["games_enabled"]

    def test_update_settings(self, session):
        """Тест обновления настроек."""
        settings = TradingSettings(user_id=789, strategy="conservative")
        session.add(settings)
        session.commit()

        settings.strategy = "aggressive"
        settings.max_trade_value = 200.0
        session.commit()

        updated = session.query(TradingSettings).filter_by(user_id=789).first()
        assert updated.strategy == "aggressive"
        assert updated.max_trade_value == 200.0

    def test_query_settings_by_strategy(self, session):
        """Тест получения настроек по стратегии."""
        settings1 = TradingSettings(user_id=111, strategy="conservative")
        settings2 = TradingSettings(user_id=222, strategy="aggressive")
        settings3 = TradingSettings(user_id=333, strategy="conservative")
        session.add_all([settings1, settings2, settings3])
        session.commit()

        conservative = (
            session.query(TradingSettings).filter_by(strategy="conservative").all()
        )
        assert len(conservative) == 2

    def test_toggle_auto_trading(self, session):
        """Тест переключения автоторговли."""
        settings = TradingSettings(user_id=999, auto_trading_enabled=0)
        session.add(settings)
        session.commit()

        settings.auto_trading_enabled = 1
        session.commit()

        updated = session.query(TradingSettings).filter_by(user_id=999).first()
        assert updated.auto_trading_enabled == 1
