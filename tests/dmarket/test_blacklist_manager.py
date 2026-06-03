"""Tests for blacklist_manager module.

This module tests the BlacklistManager class for filtering
problematic sellers and items.
"""


import pytest


class TestBlacklistManager:
    """Tests for BlacklistManager class."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create BlacklistManager instance."""
        from src.dmarket.blacklist_manager import BlacklistManager
        blacklist_file = tmp_path / "blacklist.json"
        return BlacklistManager(
            config={},
            blacklist_file=str(blacklist_file),
        )

    def test_init(self, manager):
        """Test initialization."""
        assert manager is not None
        assert isinstance(manager.blacklisted_sellers, set)
        assert isinstance(manager.forbidden_keywords, list)

    def test_add_seller_to_blacklist(self, manager):
        """Test adding seller to blacklist."""
        seller_id = "seller123"

        manager.add_seller_to_blacklist(seller_id)

        assert seller_id in manager.blacklisted_sellers

    def test_remove_seller_from_blacklist(self, manager):
        """Test removing seller from blacklist."""
        seller_id = "seller123"
        manager.blacklisted_sellers.add(seller_id)

        result = manager.remove_seller_from_blacklist(seller_id)

        assert result is True
        assert seller_id not in manager.blacklisted_sellers

    def test_remove_seller_not_in_blacklist(self, manager):
        """Test removing seller that is not in blacklist."""
        result = manager.remove_seller_from_blacklist("nonexistent")
        assert result is False

    def test_is_seller_blacklisted(self, manager):
        """Test checking if seller is blacklisted."""
        manager.blacklisted_sellers.add("bad_seller")

        assert manager.is_seller_blacklisted("bad_seller") is True
        assert manager.is_seller_blacklisted("good_seller") is False

    def test_add_forbidden_keyword(self, manager):
        """Test adding forbidden keyword."""
        manager.add_forbidden_keyword("scam")

        assert "scam" in manager.forbidden_keywords

    def test_remove_forbidden_keyword(self, manager):
        """Test removing forbidden keyword."""
        manager.forbidden_keywords.append("test")

        result = manager.remove_forbidden_keyword("test")

        assert result is True
        assert "test" not in manager.forbidden_keywords

    def test_is_item_forbidden(self, manager):
        """Test detecting forbidden keywords in item names."""
        manager.forbidden_keywords = ["souvenir", "stattrak fake"]

        assert manager.is_item_forbidden("AWP | Souvenir Dragon Lore") is True
        assert manager.is_item_forbidden("AWP | Dragon Lore") is False

    def test_should_skip_item_valid(self, manager):
        """Test checking if item is valid (not blacklisted)."""
        item = {
            "title": "AK-47 | Redline",
            "sellerId": "good_seller",
        }

        should_skip, reason = manager.should_skip_item(item)

        assert should_skip is False

    def test_should_skip_item_blacklisted_seller(self, manager):
        """Test checking item with blacklisted seller."""
        manager.blacklisted_sellers.add("bad_seller")
        item = {
            "title": "AK-47 | Redline",
            "sellerId": "bad_seller",
        }

        should_skip, reason = manager.should_skip_item(item)

        assert should_skip is True
        assert "blacklisted" in reason.lower()

    def test_should_skip_item_forbidden_keyword(self, manager):
        """Test checking item with forbidden keyword."""
        manager.forbidden_keywords = ["souvenir"]
        item = {
            "title": "AWP | Souvenir Dragon Lore",
            "sellerId": "seller123",
        }

        should_skip, reason = manager.should_skip_item(item)

        assert should_skip is True
        assert "keyword" in reason.lower()

    def test_record_failure_increments(self, manager):
        """Test failure counter incrementing."""
        seller_id = "seller123"

        manager.record_failure(seller_id)
        assert manager._failure_counter[seller_id] == 1

        manager.record_failure(seller_id)
        assert manager._failure_counter[seller_id] == 2

    def test_record_failure_auto_blacklists(self, manager):
        """Test automatic blacklisting after repeated failures."""
        seller_id = "failing_seller"
        manager._failure_threshold = 3

        # Simulate failures until threshold
        for _ in range(3):
            manager.record_failure(seller_id)

        assert manager.is_seller_blacklisted(seller_id) is True

    def test_reset_failure_counter(self, manager):
        """Test resetting failure counter."""
        seller_id = "seller123"
        manager._failure_counter[seller_id] = 5

        manager.reset_failure_counter(seller_id)

        assert seller_id not in manager._failure_counter

    def test_get_blacklist_summary(self, manager):
        """Test getting blacklist summary."""
        manager.blacklisted_sellers = {"s1", "s2", "s3"}
        manager.forbidden_keywords = ["k1", "k2"]

        summary = manager.get_blacklist_summary()

        assert summary["blacklisted_sellers_count"] == 3
        assert summary["forbidden_keywords_count"] == 2
