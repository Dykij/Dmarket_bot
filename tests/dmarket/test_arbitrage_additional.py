"""Дополнительные тесты для модуля arbitrage (для достижения 70%+ покрытия)."""

from src.dmarket.arbitrage import _calculate_commission, _group_items_by_name


class TestCalculateCommission:
    """Тесты функции _calculate_commission."""

    def test_rare_item_commission(self):
        """Тест комиссии для редкого предмета."""
        result = _calculate_commission(
            rarity="covert",
            item_type="rifle",
            popularity=0.5,
            game="csgo",
        )
        # Редкий предмет должен иметь комиссию выше базовой (7%)
        assert result > 7.0
        assert 2.0 <= result <= 15.0

    def test_common_item_commission(self):
        """Тест комиссии для обычного предмета."""
        result = _calculate_commission(
            rarity="consumer",
            item_type="pistol",
            popularity=0.5,
            game="csgo",
        )
        # Обычный предмет должен иметь комиссию ниже базовой (7%)
        assert result < 7.0
        assert 2.0 <= result <= 15.0

    def test_knife_commission(self):
        """Тест комиссии для ножа (высокая комиссия)."""
        result = _calculate_commission(
            rarity="classified",
            item_type="knife",
            popularity=0.5,
            game="csgo",
        )
        # Ножи имеют повышенную комиссию
        assert result > 7.0

    def test_gloves_commission(self):
        """Тест комиссии для перчаток."""
        result = _calculate_commission(
            rarity="extraordinary",
            item_type="gloves",
            popularity=0.5,
            game="csgo",
        )
        # Перчатки имеют повышенную комиссию
        assert result > 7.0

    def test_sticker_commission(self):
        """Тест комиссии для стикера (низкая комиссия)."""
        result = _calculate_commission(
            rarity="mil-spec",
            item_type="sticker",
            popularity=0.5,
            game="csgo",
        )
        # Стикеры имеют пониженную комиссию
        assert result < 7.0

    def test_popular_item_commission(self):
        """Тест комиссии для популярного предмета (popularity > 0.8)."""
        result = _calculate_commission(
            rarity="restricted",
            item_type="rifle",
            popularity=0.9,
            game="csgo",
        )
        # Популярные предметы имеют пониженную комиссию
        assert result < 7.0

    def test_unpopular_item_commission(self):
        """Тест комиссии для непопулярного предмета (popularity < 0.3)."""
        result = _calculate_commission(
            rarity="restricted",
            item_type="rifle",
            popularity=0.2,
            game="csgo",
        )
        # Непопулярные предметы имеют повышенную комиссию
        assert result > 7.0

    def test_dota2_commission(self):
        """Тест комиссии для Dota 2 (немного выше чем CS:GO)."""
        csgo_commission = _calculate_commission(
            rarity="rare",
            item_type="weapon",
            popularity=0.5,
            game="csgo",
        )
        dota2_commission = _calculate_commission(
            rarity="rare",
            item_type="weapon",
            popularity=0.5,
            game="dota2",
        )
        assert dota2_commission >= csgo_commission

    def test_rust_commission(self):
        """Тест комиссии для Rust (выше чем CS:GO)."""
        csgo_commission = _calculate_commission(
            rarity="rare",
            item_type="weapon",
            popularity=0.5,
            game="csgo",
        )
        rust_commission = _calculate_commission(
            rarity="rare",
            item_type="weapon",
            popularity=0.5,
            game="rust",
        )
        assert rust_commission >= csgo_commission

    def test_commission_min_max_bounds(self):
        """Тест что комиссия всегда в диапазоне 2-15%."""
        # Экстремальные значения для минимальной комиссии
        min_commission = _calculate_commission(
            rarity="consumer",
            item_type="sticker",
            popularity=0.9,
            game="csgo",
        )
        assert min_commission >= 2.0

        # Экстремальные значения для максимальной комиссии
        max_commission = _calculate_commission(
            rarity="contraband",
            item_type="knife",
            popularity=0.1,
            game="rust",
        )
        assert max_commission <= 15.0

    def test_commission_for_arcana(self):
        """Тест комиссии для Arcana (Dota 2)."""
        result = _calculate_commission(
            rarity="arcana",
            item_type="weapon",
            popularity=0.5,
            game="dota2",
        )
        # Arcana - редкий предмет с повышенной комиссией
        assert result > 7.0

    def test_commission_for_immortal(self):
        """Тест комиссии для Immortal (Dota 2)."""
        result = _calculate_commission(
            rarity="immortal",
            item_type="weapon",
            popularity=0.5,
            game="dota2",
        )
        # Immortal - редкий предмет с повышенной комиссией
        assert result > 7.0


class TestGroupItemsByName:
    """Тесты функции _group_items_by_name."""

    def test_group_items_basic(self):
        """Тест базовой группировки предметов."""
        items = [
            {"title": "AK-47 | Redline", "price": 10.0},
            {"title": "AK-47 | Redline", "price": 12.0},
            {"title": "AWP | Dragon Lore", "price": 1000.0},
        ]

        result = _group_items_by_name(items)

        assert len(result) == 2
        assert len(result["AK-47 | Redline"]) == 2
        assert len(result["AWP | Dragon Lore"]) == 1

    def test_group_items_empty_list(self):
        """Тест группировки пустого списка."""
        result = _group_items_by_name([])
        assert result == {}

    def test_group_items_missing_title(self):
        """Тест группировки предметов без поля title."""
        items = [
            {"title": "Item 1", "price": 10.0},
            {"price": 20.0},  # Нет title
            {"title": "Item 1", "price": 15.0},
            {"title": "", "price": 5.0},  # Пустой title
        ]

        result = _group_items_by_name(items)

        # Предметы без title или с пустым title должны быть пропущены
        assert len(result) == 1
        assert len(result["Item 1"]) == 2

    def test_group_items_single_item(self):
        """Тест группировки одного предмета."""
        items = [{"title": "Lone Item", "price": 100.0}]

        result = _group_items_by_name(items)

        assert len(result) == 1
        assert "Lone Item" in result
        assert len(result["Lone Item"]) == 1

    def test_group_items_preserves_all_fields(self):
        """Тест что группировка сохраняет все поля предметов."""
        items = [
            {
                "title": "Test Item",
                "price": 10.0,
                "rarity": "Rare",
                "float": 0.15,
            },
            {
                "title": "Test Item",
                "price": 12.0,
                "rarity": "Rare",
                "float": 0.25,
            },
        ]

        result = _group_items_by_name(items)

        assert len(result["Test Item"]) == 2
        assert result["Test Item"][0]["float"] == 0.15
        assert result["Test Item"][1]["float"] == 0.25

    def test_group_items_many_duplicates(self):
        """Тест группировки с множеством дубликатов."""
        items = [{"title": "Duplicate", "index": i} for i in range(100)]

        result = _group_items_by_name(items)

        assert len(result) == 1
        assert len(result["Duplicate"]) == 100

    def test_group_items_case_sensitive(self):
        """Тест что группировка чувствительна к регистру."""
        items = [
            {"title": "Item", "price": 10.0},
            {"title": "item", "price": 12.0},
            {"title": "ITEM", "price": 15.0},
        ]

        result = _group_items_by_name(items)

        # Должно быть 3 разных группы (case-sensitive)
        assert len(result) == 3
        assert "Item" in result
        assert "item" in result
        assert "ITEM" in result
