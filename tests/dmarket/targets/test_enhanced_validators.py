"""Тесты для расширенных валидаторов таргетов.

Тестируем:
- Подсчет условий в таргете
- Валидацию цен
- Валидацию атрибутов
- Проверку совместимости фильтров
- Полную валидацию таргета
"""

from src.dmarket.models.target_enhancements import (
    RarityFilter,
    RarityLevel,
    StickerFilter,
    TargetErrorCode,
)
from src.dmarket.targets.enhanced_validators import (
    count_target_conditions,
    validate_filter_compatibility,
    validate_target_attributes,
    validate_target_complete,
    validate_target_conditions,
    validate_target_price,
)


class TestCountTargetConditions:
    """Тесты подсчета условий в таргете."""

    def test_count_no_conditions(self):
        """Тест подсчета для таргета без условий."""
        target = {"Title": "Test Item", "Amount": 1, "Price": {"Amount": 1000}}

        count = count_target_conditions(target)

        assert count == 0

    def test_count_basic_attrs(self):
        """Тест подсчета базовых атрибутов."""
        target = {
            "Attrs": {
                "floatPartValue": "0.15",
                "pAlgontSeed": 123,
                "phase": "Ruby",
            }
        }

        count = count_target_conditions(target)

        assert count == 3  # float + pAlgontSeed + phase

    def test_count_multiple_pAlgont_seeds(self):
        """Тест подсчета множественных pAlgont seeds."""
        target = {"Attrs": {"pAlgontSeed": [1, 2, 3, 4, 5]}}

        count = count_target_conditions(target)

        assert count == 5  # Каждый pAlgont seed = 1 условие

    def test_count_sticker_filter(self):
        """Тест подсчета условий в фильтре стикеров."""
        sticker_filter = StickerFilter(
            sticker_names=["Sticker1", "Sticker2"],
            min_stickers=2,
            holo=True,
        )

        target = {"stickerFilter": sticker_filter}

        count = count_target_conditions(target)

        assert count == 4  # 2 names + min_stickers + holo

    def test_count_rarity_filter(self):
        """Тест подсчета условий в фильтре редкости."""
        rarity_filter = RarityFilter(
            rarity=RarityLevel.ARCANA,
            min_rarity_index=3,
            max_rarity_index=6,
        )

        target = {"rarityFilter": rarity_filter}

        count = count_target_conditions(target)

        assert count == 3  # rarity + min + max

    def test_count_combined_conditions(self):
        """Тест подсчета всех условий вместе."""
        target = {
            "Attrs": {
                "floatPartValue": "0.15",
                "pAlgontSeed": [1, 2],
            },
            "stickerFilter": StickerFilter(sticker_names=["Sticker1"], holo=True),
            "rarityFilter": RarityFilter(rarity=RarityLevel.LEGENDARY),
        }

        count = count_target_conditions(target)

        # float=1 + pAlgontSeeds=2 + stickerName=1 + holo=1 + rarity=1
        assert count == 6


class TestValidateTargetConditions:
    """Тесты валидации количества условий."""

    def test_validate_within_limit(self):
        """Тест валидации в пределах лимита."""
        target = {"Attrs": {"floatPartValue": "0.15"}}

        is_valid, message, suggestions = validate_target_conditions(target, max_conditions=10)

        assert is_valid is True
        assert "1/10" in message
        assert len(suggestions) == 0

    def test_validate_exceeds_limit(self):
        """Тест валидации превышения лимита."""
        target = {"Attrs": {"pAlgontSeed": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]}}

        is_valid, message, suggestions = validate_target_conditions(target, max_conditions=10)

        assert is_valid is False
        assert "11/10" in message
        assert "Remove 1 condition" in message
        assert len(suggestions) > 0

    def test_validate_provides_suggestions(self):
        """Тест что валидатор дает подсказки."""
        target = {
            "Attrs": {"pAlgontSeed": [1, 2, 3, 4, 5, 6]},
            "stickerFilter": StickerFilter(
                sticker_names=["S1", "S2", "S3", "S4"],
                holo=True,
                foil=True,
            ),
        }

        is_valid, message, suggestions = validate_target_conditions(target, max_conditions=10)

        assert is_valid is False
        assert any("pAlgont seed" in s.lower() for s in suggestions)


class TestValidateTargetPrice:
    """Тесты валидации цен."""

    def test_validate_valid_price(self):
        """Тест валидной цены."""
        result = validate_target_price(10.50)

        assert result.success is True
        assert "10.50" in result.reason

    def test_validate_negative_price(self):
        """Тест отрицательной цены."""
        result = validate_target_price(-5.0)

        assert result.success is False
        assert result.error_code == TargetErrorCode.PRICE_TOO_LOW

    def test_validate_zero_price(self):
        """Тест нулевой цены."""
        result = validate_target_price(0.0)

        assert result.success is False
        assert result.error_code == TargetErrorCode.PRICE_TOO_LOW

    def test_validate_price_below_min(self):
        """Тест цены ниже минимума."""
        result = validate_target_price(4.50, min_price=5.00)

        assert result.success is False
        assert result.error_code == TargetErrorCode.PRICE_TOO_LOW
        assert "4.50" in result.reason
        assert "5.00" in result.reason
        assert len(result.suggestions) > 0

    def test_validate_price_above_max(self):
        """Тест цены выше максимума."""
        result = validate_target_price(150.0, max_price=100.0)

        assert result.success is False
        assert result.error_code == TargetErrorCode.PRICE_TOO_HIGH
        assert "150.00" in result.reason


class TestValidateTargetAttributes:
    """Тесты валидации атрибутов."""

    def test_validate_no_attrs(self):
        """Тест валидации без атрибутов."""
        result = validate_target_attributes("csgo", None)

        assert result.success is True

    def test_validate_csgo_float_valid(self):
        """Тест валидного float для CS:GO."""
        result = validate_target_attributes("csgo", {"floatPartValue": "0.15"})

        assert result.success is True

    def test_validate_csgo_float_invalid(self):
        """Тест невалидного float для CS:GO."""
        result = validate_target_attributes("csgo", {"floatPartValue": "1.5"})

        assert result.success is False
        assert result.error_code == TargetErrorCode.INVALID_ATTRIBUTES
        assert "0 and 1" in result.reason

    def test_validate_csgo_pAlgont_seed_valid(self):
        """Тест валидного pAlgont seed."""
        result = validate_target_attributes("csgo", {"pAlgontSeed": 500})

        assert result.success is True

    def test_validate_csgo_pAlgont_seed_invalid(self):
        """Тест невалидного pAlgont seed."""
        result = validate_target_attributes("csgo", {"pAlgontSeed": 1500})

        assert result.success is False
        assert result.error_code == TargetErrorCode.INVALID_ATTRIBUTES

    def test_validate_dota2_float_invalid(self):
        """Тест что float не применим для Dota 2."""
        result = validate_target_attributes("dota2", {"floatPartValue": "0.15"})

        assert result.success is False
        assert result.error_code == TargetErrorCode.INVALID_ATTRIBUTES
        assert "not applicable" in result.reason


class TestValidateFilterCompatibility:
    """Тесты совместимости фильтров с игSwarm."""

    def test_validate_csgo_sticker_filter_valid(self):
        """Тест что стикеры валидны для CS:GO."""
        sticker_filter = StickerFilter(holo=True)

        result = validate_filter_compatibility("csgo", sticker_filter=sticker_filter)

        assert result.success is True

    def test_validate_dota2_sticker_filter_invalid(self):
        """Тест что стикеры невалидны для Dota 2."""
        sticker_filter = StickerFilter(holo=True)

        result = validate_filter_compatibility("dota2", sticker_filter=sticker_filter)

        assert result.success is False
        assert result.error_code == TargetErrorCode.INVALID_ATTRIBUTES
        assert "CS:GO" in result.reason

    def test_validate_dota2_rarity_filter_valid(self):
        """Тест что rarity валидна для Dota 2."""
        rarity_filter = RarityFilter(rarity=RarityLevel.ARCANA)

        result = validate_filter_compatibility("dota2", rarity_filter=rarity_filter)

        assert result.success is True

    def test_validate_csgo_rarity_filter_invalid(self):
        """Тест что rarity невалидна для CS:GO."""
        rarity_filter = RarityFilter(rarity=RarityLevel.ARCANA)

        result = validate_filter_compatibility("csgo", rarity_filter=rarity_filter)

        assert result.success is False
        assert "Dota 2/TF2" in result.reason


class TestValidateTargetComplete:
    """Тесты полной валидации таргета."""

    def test_validate_complete_valid_target(self):
        """Тест валидного таргета."""
        result = validate_target_complete(
            game="csgo",
            title="AK-47 | Redline (FT)",
            price=10.50,
            amount=1,
            attrs={"floatPartValue": "0.25"},
        )

        assert result.success is True
        assert result.metadata["game"] == "csgo"
        assert result.metadata["price"] == 10.50

    def test_validate_complete_empty_title(self):
        """Тест пустого названия."""
        result = validate_target_complete(
            game="csgo",
            title="",
            price=10.50,
        )

        assert result.success is False
        assert "empty" in result.reason.lower()

    def test_validate_complete_invalid_amount(self):
        """Тест невалидного количества."""
        result = validate_target_complete(
            game="csgo",
            title="Test Item",
            price=10.50,
            amount=150,  # > 100
        )

        assert result.success is False
        assert "100" in result.reason  # Проверяем что есть упоминание лимита

    def test_validate_complete_too_many_conditions(self):
        """Тест превышения лимита условий."""
        result = validate_target_complete(
            game="csgo",
            title="Test Item",
            price=10.50,
            attrs={"pAlgontSeed": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]},
            max_conditions=10,
        )

        assert result.success is False
        assert result.error_code == TargetErrorCode.TOO_MANY_CONDITIONS
        assert len(result.suggestions) > 0

    def test_validate_complete_with_filters(self):
        """Тест с фильтрами."""
        result = validate_target_complete(
            game="csgo",
            title="AK-47 | Redline (FT)",
            price=10.50,
            sticker_filter=StickerFilter(holo=True, min_stickers=2),
        )

        assert result.success is True
