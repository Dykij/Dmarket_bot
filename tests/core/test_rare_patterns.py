"""Тесты для модуля rare_patterns (Rare Hold).

Проверяет корректность определения редких предметов:
- Float value
- Doppler phases
- Blue Gem patterns
- Stickers
"""

from src.utils.rare_patterns import RARE_CONFIG, get_rarity_reason, is_item_rare


class TestRareFloatDetection:
    """Тесты определения редкого float."""

    def test_low_float_is_rare(self):
        """Float < 0.01 считается редким."""
        item = {"title": "AK-47 | Redline", "extra": {"floatValue": 0.005}}
        assert is_item_rare(item) is True

    def test_normal_float_not_rare(self):
        """Обычный float не считается редким."""
        item = {"title": "AK-47 | Redline", "extra": {"floatValue": 0.15}}
        assert is_item_rare(item) is False

    def test_max_float_is_rare(self):
        """Float > 0.999 считается редким."""
        item = {"title": "AK-47 | Safari Mesh", "extra": {"floatValue": 0.9999}}
        assert is_item_rare(item) is True


class TestDopplerPhaseDetection:
    """Тесты определения редких фаз Doppler."""

    def test_ruby_is_rare(self):
        """Ruby фаза считается редкой."""
        item = {"title": "Karambit | Doppler (Ruby)", "extra": {}}
        assert is_item_rare(item) is True

    def test_sapphire_is_rare(self):
        """Sapphire фаза считается редкой."""
        item = {"title": "M9 Bayonet | Doppler (Sapphire)", "extra": {}}
        assert is_item_rare(item) is True

    def test_black_pearl_is_rare(self):
        """Black Pearl фаза считается редкой."""
        item = {"title": "Butterfly Knife | Doppler (Black Pearl)", "extra": {}}
        assert is_item_rare(item) is True

    def test_phase1_not_rare(self):
        """Phase 1 не считается редкой (только Phase 2 и 4)."""
        item = {"title": "Karambit | Doppler (Phase 1)", "extra": {}}
        assert is_item_rare(item) is False

    def test_phase2_is_rare(self):
        """Phase 2 считается редкой."""
        item = {"title": "Karambit | Doppler (Phase 2)", "extra": {}}
        assert is_item_rare(item) is True


class TestBlueGemDetection:
    """Тесты определения Blue Gem паттернов."""

    def test_ak47_blue_gem_661(self):
        """AK-47 Case Hardened seed 661 (Blue Gem) считается редким."""
        item = {
            "title": "AK-47 | Case Hardened (Field-Tested)",
            "extra": {"paintSeed": 661},
        }
        assert is_item_rare(item) is True

    def test_ak47_normal_pattern(self):
        """AK-47 Case Hardened с обычным паттерном не считается редким."""
        item = {
            "title": "AK-47 | Case Hardened (Field-Tested)",
            "extra": {"paintSeed": 123},
        }
        assert is_item_rare(item) is False

    def test_karambit_blue_gem(self):
        """Karambit Case Hardened seed 387 считается редким."""
        item = {
            "title": "Karambit | Case Hardened (Minimal Wear)",
            "extra": {"paintSeed": 387},
        }
        assert is_item_rare(item) is True


class TestRarityReason:
    """Тесты получения причины редкости."""

    def test_float_reason(self):
        """Возвращает причину для редкого float."""
        item = {"title": "AWP | Dragon Lore", "extra": {"floatValue": 0.001}}
        reason = get_rarity_reason(item)
        assert reason is not None
        assert "float" in reason.lower()

    def test_doppler_reason(self):
        """Возвращает причину для редкой фазы."""
        item = {"title": "Karambit | Doppler (Ruby)", "extra": {}}
        reason = get_rarity_reason(item)
        assert reason is not None
        assert "doppler" in reason.lower()

    def test_pattern_reason(self):
        """Возвращает причину для редкого паттерна."""
        item = {
            "title": "AK-47 | Case Hardened",
            "extra": {"paintSeed": 661, "floatValue": 0.5},
        }
        reason = get_rarity_reason(item)
        assert reason is not None
        assert "паттерн" in reason.lower() or "pattern" in reason.lower()

    def test_no_reason_for_normal_item(self):
        """Для обычного предмета причины нет."""
        item = {"title": "P250 | Sand Dune", "extra": {"floatValue": 0.3}}
        reason = get_rarity_reason(item)
        assert reason is None


class TestRareConfig:
    """Тесты конфигурации редкости."""

    def test_config_has_required_keys(self):
        """Конфиг содержит все необходимые ключи."""
        assert "max_float_to_hold" in RARE_CONFIG
        assert "rare_phases" in RARE_CONFIG
        assert "rare_patterns" in RARE_CONFIG

    def test_rare_phases_not_empty(self):
        """Список редких фаз не пустой."""
        assert len(RARE_CONFIG["rare_phases"]) > 0

    def test_rare_patterns_not_empty(self):
        """Словарь редких паттернов не пустой."""
        assert len(RARE_CONFIG["rare_patterns"]) > 0

    def test_max_float_is_reasonable(self):
        """Порог float разумный (< 0.1)."""
        assert RARE_CONFIG["max_float_to_hold"] < 0.1
