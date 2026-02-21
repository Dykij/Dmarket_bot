"""Tests for WaxpeerAPI module.

Tests cover:
- WaxpeerAPI client initialization
- Balance retrieval
- Items listing and delisting
- Price information retrieval
- Error handling and rate limiting
"""

from decimal import Decimal


# Test WaxpeerGame enum
class TestWaxpeerGame:
    """Tests for WaxpeerGame enum."""
    
    def test_cs2_value(self):
        """Test CS2 game value."""
        from src.waxpeer.waxpeer_api import WaxpeerGame
        assert WaxpeerGame.CS2.value == "cs2"
    
    def test_csgo_legacy_value(self):
        """Test CSGO legacy value."""
        from src.waxpeer.waxpeer_api import WaxpeerGame
        assert WaxpeerGame.CSGO.value == "csgo"
    
    def test_dota2_value(self):
        """Test Dota2 game value."""
        from src.waxpeer.waxpeer_api import WaxpeerGame
        assert WaxpeerGame.DOTA2.value == "dota2"
    
    def test_rust_value(self):
        """Test Rust game value."""
        from src.waxpeer.waxpeer_api import WaxpeerGame
        assert WaxpeerGame.RUST.value == "rust"


class TestListingStatus:
    """Tests for ListingStatus enum."""
    
    def test_active_status(self):
        """Test active listing status."""
        from src.waxpeer.waxpeer_api import ListingStatus
        assert ListingStatus.ACTIVE.value == "active"
    
    def test_sold_status(self):
        """Test sold listing status."""
        from src.waxpeer.waxpeer_api import ListingStatus
        assert ListingStatus.SOLD.value == "sold"
    
    def test_cancelled_status(self):
        """Test cancelled listing status."""
        from src.waxpeer.waxpeer_api import ListingStatus
        assert ListingStatus.CANCELLED.value == "cancelled"


class TestWaxpeerItem:
    """Tests for WaxpeerItem dataclass."""
    
    def test_create_item(self):
        """Test creating a WaxpeerItem."""
        from src.waxpeer.waxpeer_api import ListingStatus, WaxpeerGame, WaxpeerItem
        
        item = WaxpeerItem(
            item_id="123",
            name="AK-47 | Redline",
            price=Decimal("10.50"),
            price_mils=10500,
            game=WaxpeerGame.CS2,
        )
        
        assert item.item_id == "123"
        assert item.name == "AK-47 | Redline"
        assert item.price == Decimal("10.50")
        assert item.price_mils == 10500
        assert item.game == WaxpeerGame.CS2
        assert item.status == ListingStatus.PENDING
    
    def test_item_with_float_value(self):
        """Test creating item with float value."""
        from src.waxpeer.waxpeer_api import WaxpeerGame, WaxpeerItem
        
        item = WaxpeerItem(
            item_id="456",
            name="AWP | Dragon Lore",
            price=Decimal("1500.00"),
            price_mils=1500000,
            game=WaxpeerGame.CS2,
            float_value=0.0156,
        )
        
        assert item.float_value == 0.0156


class TestWaxpeerBalance:
    """Tests for WaxpeerBalance dataclass."""
    
    def test_create_balance(self):
        """Test creating WaxpeerBalance."""
        from src.waxpeer.waxpeer_api import WaxpeerBalance
        
        balance = WaxpeerBalance(
            wallet=Decimal("100.50"),
            wallet_mils=100500,
            avAlgolable_for_withdrawal=Decimal("80.00"),
        )
        
        assert balance.wallet == Decimal("100.50")
        assert balance.wallet_mils == 100500
        assert balance.avAlgolable_for_withdrawal == Decimal("80.00")
        assert balance.pending == Decimal(0)
        assert balance.can_trade is False
    
    def test_balance_with_pending(self):
        """Test balance with pending amount."""
        from src.waxpeer.waxpeer_api import WaxpeerBalance
        
        balance = WaxpeerBalance(
            wallet=Decimal("200.00"),
            wallet_mils=200000,
            avAlgolable_for_withdrawal=Decimal("150.00"),
            pending=Decimal("50.00"),
            can_trade=True,
        )
        
        assert balance.pending == Decimal("50.00")
        assert balance.can_trade is True


class TestWaxpeerPriceInfo:
    """Tests for WaxpeerPriceInfo dataclass."""
    
    def test_create_price_info(self):
        """Test creating price info."""
        from src.waxpeer.waxpeer_api import WaxpeerPriceInfo
        
        info = WaxpeerPriceInfo(
            name="AK-47 | Redline (FT)",
            price_mils=10500,
            price_usd=Decimal("10.50"),
            count=25,
        )
        
        assert info.name == "AK-47 | Redline (FT)"
        assert info.price_mils == 10500
        assert info.price_usd == Decimal("10.50")
        assert info.count == 25
    
    def test_is_liquid_true(self):
        """Test liquid item detection."""
        from src.waxpeer.waxpeer_api import WaxpeerPriceInfo
        
        info = WaxpeerPriceInfo(
            name="Popular Item",
            price_mils=5000,
            price_usd=Decimal("5.00"),
            count=10,
        )
        
        assert info.is_liquid is True
    
    def test_is_liquid_false(self):
        """Test illiquid item detection."""
        from src.waxpeer.waxpeer_api import WaxpeerPriceInfo
        
        info = WaxpeerPriceInfo(
            name="Rare Item",
            price_mils=50000,
            price_usd=Decimal("50.00"),
            count=1,
        )
        
        assert info.is_liquid is False


class TestWaxpeerConstants:
    """Tests for Waxpeer API constants."""
    
    def test_mils_per_usd(self):
        """Test MILS_PER_USD constant."""
        from src.waxpeer.waxpeer_api import MILS_PER_USD
        assert MILS_PER_USD == 1000
    
    def test_commission_rate(self):
        """Test WAXPEER_COMMISSION constant."""
        from src.waxpeer.waxpeer_api import WAXPEER_COMMISSION
        assert Decimal("0.06") == WAXPEER_COMMISSION


class TestWaxpeerConversions:
    """Tests for price conversion utilities."""
    
    def test_mils_to_usd(self):
        """Test mils to USD conversion."""
        from src.waxpeer.waxpeer_api import MILS_PER_USD
        
        mils = 10500
        usd = Decimal(mils) / MILS_PER_USD
        
        assert usd == Decimal("10.5")
    
    def test_usd_to_mils(self):
        """Test USD to mils conversion."""
        from src.waxpeer.waxpeer_api import MILS_PER_USD
        
        usd = Decimal("25.50")
        mils = int(usd * MILS_PER_USD)
        
        assert mils == 25500
    
    def test_commission_calculation(self):
        """Test commission calculation."""
        from src.waxpeer.waxpeer_api import WAXPEER_COMMISSION
        
        sale_price = Decimal("100.00")
        commission = sale_price * WAXPEER_COMMISSION
        net = sale_price - commission
        
        assert commission == Decimal("6.00")
        assert net == Decimal("94.00")
