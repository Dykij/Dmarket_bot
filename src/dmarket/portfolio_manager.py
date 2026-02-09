"""Portfolio management system for DMarket trading.

Provides comprehensive portfolio tracking and analysis:
- Track all user assets (inventory + market listings)
- Calculate portfolio metrics (value, allocation, risk)
- Provide rebalancing recommendations
- Monitor concentration risk
- Generate portfolio reports

Part of P1-23: Portfolio management system.

Usage:
    ```python
    from src.dmarket.portfolio_manager import PortfolioManager

    # Create portfolio manager
    pm = PortfolioManager(api_client=api)

    # Get portfolio snapshot
    snapshot = await pm.get_portfolio_snapshot()
    print(f"Total value: ${snapshot.total_value_usd:.2f}")

    # Get risk analysis
    risk = await pm.analyze_risk()
    print(f"Concentration risk: {risk.concentration_score:.2f}")

    # Get rebalancing recommendations
    recommendations = await pm.get_rebalancing_recommendations()
    for rec in recommendations:
        print(f"{rec.action}: {rec.item_name} - {rec.reason}")
    ```
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI


logger = logging.getLogger(__name__)


class AssetType(StrEnum):
    """Type of asset in portfolio."""

    INVENTORY = "inventory"  # Items in user's inventory (not listed)
    LISTED = "listed"  # Items listed for sale on market
    TARGET = "target"  # Active buy orders (targets)
    CASH = "cash"  # USD balance


class RiskLevel(StrEnum):
    """Risk level classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RebalanceAction(StrEnum):
    """Recommended rebalancing action."""

    SELL = "sell"
    BUY = "buy"
    HOLD = "hold"
    REDUCE_PRICE = "reduce_price"
    INCREASE_PRICE = "increase_price"
    CANCEL_TARGET = "cancel_target"


@dataclass
class PortfolioAsset:
    """Single asset in the portfolio.

    Attributes:
        item_id: Unique item identifier
        item_name: Human-readable item name
        asset_type: Type of asset (inventory, listed, target, cash)
        quantity: Number of items
        unit_price: Price per item in USD
        total_value: Total value in USD
        game: Game the item belongs to
        category: Item category (e.g., Rifle, Knife, Sticker)
        listed_price: Price if listed on market (None if not listed)
        market_price: Current market price
        acquisition_date: When item was acquired
        days_held: Number of days held
        profit_loss: Unrealized profit/loss in USD
        profit_loss_percent: Unrealized profit/loss as percentage
    """

    item_id: str
    item_name: str
    asset_type: AssetType
    quantity: int
    unit_price: float
    total_value: float
    game: str = "csgo"
    category: str = "Other"
    listed_price: float | None = None
    market_price: float | None = None
    acquisition_date: datetime | None = None
    days_held: int = 0
    profit_loss: float = 0.0
    profit_loss_percent: float = 0.0


@dataclass
class PortfolioSnapshot:
    """Complete portfolio snapshot.

    Attributes:
        timestamp: When snapshot was taken
        total_value_usd: Total portfolio value in USD
        cash_balance: USD cash balance
        inventory_value: Value of inventory items
        listed_value: Value of listed items
        targets_value: Value locked in targets (buy orders)
        assets: List of all assets
        asset_count: Total number of unique assets
        game_distribution: Value distribution by game
        category_distribution: Value distribution by category
    """

    timestamp: datetime
    total_value_usd: float
    cash_balance: float
    inventory_value: float
    listed_value: float
    targets_value: float
    assets: list[PortfolioAsset] = field(default_factory=list)
    asset_count: int = 0
    game_distribution: dict[str, float] = field(default_factory=dict)
    category_distribution: dict[str, float] = field(default_factory=dict)


@dataclass
class RiskAnalysis:
    """Portfolio risk analysis results.

    Attributes:
        overall_risk: Overall risk level
        concentration_score: 0-100, higher = more concentrated
        single_item_risk: Percentage in single largest item
        single_game_risk: Percentage in single game
        illiquidity_risk: Percentage in illiquid items
        stale_items_risk: Percentage in items held > 30 days
        diversification_score: 0-100, higher = better diversified
        risk_factors: List of identified risk factors
        recommendations: Risk mitigation recommendations
    """

    overall_risk: RiskLevel
    concentration_score: float
    single_item_risk: float
    single_game_risk: float
    illiquidity_risk: float
    stale_items_risk: float
    diversification_score: float
    risk_factors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class RebalanceRecommendation:
    """Single rebalancing recommendation.

    Attributes:
        action: Recommended action
        item_id: Item to act on
        item_name: Human-readable item name
        current_value: Current value in portfolio
        target_value: Target value after rebalancing
        quantity: Number of items to buy/sell
        priority: 1-5, higher = more urgent
        reason: Explanation for recommendation
        expected_impact: Expected impact on portfolio
    """

    action: RebalanceAction
    item_id: str
    item_name: str
    current_value: float
    target_value: float
    quantity: int
    priority: int
    reason: str
    expected_impact: str


@dataclass
class PortfolioConfig:
    """Configuration for portfolio management.

    Attributes:
        max_single_item_percent: Maximum % in single item (default 20%)
        max_single_game_percent: Maximum % in single game (default 50%)
        max_stale_days: Days before item is considered stale (default 30)
        max_target_days: Days before target is considered stale (default 7)
        min_liquidity_score: Minimum liquidity score (default 0.3)
        target_cash_percent: Target cash allocation (default 20%)
        rebalance_threshold: Threshold % for rebalancing (default 5%)
        default_game_id: Default game ID for inventory queries (default "a8db" = CS:GO)
        inventory_limit: Maximum items to fetch per query (default 100)
    """

    max_single_item_percent: float = 20.0
    max_single_game_percent: float = 50.0
    max_stale_days: int = 30
    max_target_days: int = 7
    min_liquidity_score: float = 0.3
    target_cash_percent: float = 20.0
    rebalance_threshold: float = 5.0
    default_game_id: str = "a8db"  # CS:GO
    inventory_limit: int = 100


class PortfolioManager:
    """Portfolio management system for DMarket trading.

    Provides:
    - Real-time portfolio tracking
    - Risk analysis and scoring
    - Rebalancing recommendations
    - Performance metrics
    - Diversification analysis
    """

    def __init__(
        self,
        api_client: DMarketAPI | None = None,
        config: PortfolioConfig | None = None,
    ) -> None:
        """Initialize portfolio manager.

        Args:
            api_client: DMarket API client for fetching data
            config: Portfolio configuration
        """
        self._api = api_client
        self._config = config or PortfolioConfig()
        self._cache: dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes cache
        self._last_snapshot: PortfolioSnapshot | None = None
        self._last_snapshot_time: datetime | None = None

    async def get_portfolio_snapshot(self, force_refresh: bool = False) -> PortfolioSnapshot:
        """Get current portfolio snapshot.

        Args:
            force_refresh: Force refresh from API (ignore cache)

        Returns:
            Complete portfolio snapshot
        """
        # Check cache
        if not force_refresh and self._last_snapshot and self._last_snapshot_time:
            cache_age = (datetime.now(UTC) - self._last_snapshot_time).total_seconds()
            if cache_age < self._cache_ttl:
                return self._last_snapshot

        logger.info("Fetching portfolio snapshot")

        # Initialize values
        cash_balance = 0.0
        inventory_items: list[dict[str, Any]] = []
        listed_items: list[dict[str, Any]] = []
        targets: list[dict[str, Any]] = []

        # Fetch data from API if available
        if self._api:
            try:
                # Get balance - API returns balance in USD directly
                balance_data = await self._api.get_balance()
                cash_balance = float(balance_data.get("balance", 0))

                # Get inventory (use configurable game_id and limit)
                inventory_data = await self._api.get_user_inventory(
                    game_id=self._config.default_game_id,
                    limit=self._config.inventory_limit,
                )
                inventory_items = inventory_data.get("objects", [])

                # Get listed items (on market)
                offers_data = await self._api.get_user_offers(limit=self._config.inventory_limit)
                listed_items = offers_data.get("objects", [])

                # Get active targets
                targets_data = await self._api.get_user_targets()
                targets = targets_data.get("Items", [])

            except Exception as e:
                logger.exception("Error fetching portfolio data: %s", e)

        # Build portfolio assets
        assets: list[PortfolioAsset] = []

        # Process inventory items
        for item in inventory_items:
            asset = self._parse_inventory_item(item)
            if asset:
                assets.append(asset)

        # Process listed items
        for item in listed_items:
            asset = self._parse_listed_item(item)
            if asset:
                assets.append(asset)

        # Process targets
        for target in targets:
            asset = self._parse_target(target)
            if asset:
                assets.append(asset)

        # Calculate totals
        inventory_value = sum(a.total_value for a in assets if a.asset_type == AssetType.INVENTORY)
        listed_value = sum(a.total_value for a in assets if a.asset_type == AssetType.LISTED)
        targets_value = sum(a.total_value for a in assets if a.asset_type == AssetType.TARGET)
        total_value = cash_balance + inventory_value + listed_value + targets_value

        # Calculate distributions
        game_dist: dict[str, float] = {}
        category_dist: dict[str, float] = {}

        for asset in assets:
            game_dist[asset.game] = game_dist.get(asset.game, 0) + asset.total_value
            category_dist[asset.category] = category_dist.get(asset.category, 0) + asset.total_value

        # Create snapshot
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(UTC),
            total_value_usd=total_value,
            cash_balance=cash_balance,
            inventory_value=inventory_value,
            listed_value=listed_value,
            targets_value=targets_value,
            assets=assets,
            asset_count=len(assets),
            game_distribution=game_dist,
            category_distribution=category_dist,
        )

        # Cache snapshot
        self._last_snapshot = snapshot
        self._last_snapshot_time = datetime.now(UTC)

        logger.info(
            "Portfolio snapshot: total=$%.2f, assets=%d, cash=$%.2f",
            total_value,
            len(assets),
            cash_balance,
        )

        return snapshot

    def _parse_inventory_item(self, item: dict[str, Any]) -> PortfolioAsset | None:
        """Parse inventory item into PortfolioAsset."""
        try:
            item_id = item.get("itemId", item.get("assetId", ""))
            title = item.get("title", "Unknown")
            price_data = item.get("price", {})

            # Get price in USD (convert from cents)
            if isinstance(price_data, dict):
                unit_price = float(price_data.get("USD", 0)) / 100
            else:
                unit_price = 0.0

            # Get suggested price as market price
            suggested = item.get("suggestedPrice", {})
            if isinstance(suggested, dict):
                market_price = float(suggested.get("USD", 0)) / 100
            else:
                market_price = unit_price

            # Calculate profit/loss
            if unit_price > 0 and market_price > 0:
                profit_loss = market_price - unit_price
                profit_loss_percent = (profit_loss / unit_price) * 100
            else:
                profit_loss = 0.0
                profit_loss_percent = 0.0

            # Extract category from title
            category = self._extract_category(title)

            return PortfolioAsset(
                item_id=item_id,
                item_name=title,
                asset_type=AssetType.INVENTORY,
                quantity=1,
                unit_price=unit_price,
                total_value=unit_price,
                game=item.get("gameId", "csgo"),
                category=category,
                market_price=market_price,
                profit_loss=profit_loss,
                profit_loss_percent=profit_loss_percent,
            )
        except Exception as e:
            logger.warning("Error parsing inventory item: %s", e)
            return None

    def _parse_listed_item(self, item: dict[str, Any]) -> PortfolioAsset | None:
        """Parse listed item into PortfolioAsset."""
        try:
            item_id = item.get("itemId", item.get("offerId", ""))
            title = item.get("title", "Unknown")

            # Get listed price
            price_data = item.get("price", {})
            if isinstance(price_data, dict):
                listed_price = float(price_data.get("USD", 0)) / 100
            else:
                listed_price = 0.0

            # Extract category from title
            category = self._extract_category(title)

            return PortfolioAsset(
                item_id=item_id,
                item_name=title,
                asset_type=AssetType.LISTED,
                quantity=1,
                unit_price=listed_price,
                total_value=listed_price,
                game=item.get("gameId", "csgo"),
                category=category,
                listed_price=listed_price,
            )
        except Exception as e:
            logger.warning("Error parsing listed item: %s", e)
            return None

    def _parse_target(self, target: dict[str, Any]) -> PortfolioAsset | None:
        """Parse target (buy order) into PortfolioAsset."""
        try:
            target_id = target.get("TargetID", "")
            title = target.get("Title", "Unknown")

            # Get target price
            price = target.get("Price", {})
            if isinstance(price, dict):
                target_price = float(price.get("Amount", 0)) / 100
            elif isinstance(price, (int, float)):
                target_price = float(price) / 100
            else:
                target_price = 0.0

            # Get amount (number of items to buy)
            amount = target.get("Amount", 1)

            # Extract category from title
            category = self._extract_category(title)

            return PortfolioAsset(
                item_id=target_id,
                item_name=title,
                asset_type=AssetType.TARGET,
                quantity=amount,
                unit_price=target_price,
                total_value=target_price * amount,
                game=target.get("GameID", "csgo"),
                category=category,
            )
        except Exception as e:
            logger.warning("Error parsing target: %s", e)
            return None

    def _extract_category(self, title: str) -> str:
        """Extract item category from title."""
        title_lower = title.lower()

        # Define category patterns
        # Note: Order matters - more specific categories should come first
        categories = {
            "Knife": [
                "knife",
                "karambit",
                "bayonet",
                "gut",
                "flip",
                "falchion",
                "bowie",
            ],
            "Gloves": ["gloves"],
            "Sniper": ["awp", "ssg 08", "g3sg1", "scar-20"],  # AWP moved here
            "Rifle": ["ak-47", "m4a4", "m4a1-s", "famas", "galil", "sg 553", "aug"],
            "Pistol": [
                "glock",
                "usp-s",
                "p2000",
                "desert eagle",
                "five-seven",
                "tec-9",
            ],
            "SMG": ["mp9", "mac-10", "mp7", "ump-45", "p90", "pp-bizon", "mp5-sd"],
            "Shotgun": ["nova", "xm1014", "sawed-off", "mag-7"],
            "Machine Gun": ["m249", "negev"],
            "Sticker": ["sticker"],
            "Case": ["case"],
            "Key": ["key"],
            "Graffiti": ["graffiti", "sealed graffiti"],
            "Music Kit": ["music kit"],
            "Agent": ["agent"],
            "Patch": ["patch"],
        }

        for category, patterns in categories.items():
            for pattern in patterns:
                if pattern in title_lower:
                    return category

        return "Other"

    async def analyze_risk(self, snapshot: PortfolioSnapshot | None = None) -> RiskAnalysis:
        """Analyze portfolio risk.

        Args:
            snapshot: Portfolio snapshot to analyze (fetches if not provided)

        Returns:
            Risk analysis results
        """
        if snapshot is None:
            snapshot = await self.get_portfolio_snapshot()

        risk_factors: list[str] = []
        recommendations: list[str] = []

        # Calculate concentration metrics
        total_value = snapshot.total_value_usd
        if total_value <= 0:
            return RiskAnalysis(
                overall_risk=RiskLevel.LOW,
                concentration_score=0,
                single_item_risk=0,
                single_game_risk=0,
                illiquidity_risk=0,
                stale_items_risk=0,
                diversification_score=100,
                risk_factors=["Empty portfolio"],
                recommendations=["Start building your portfolio"],
            )

        # Single item concentration
        max_item_value = max((a.total_value for a in snapshot.assets), default=0)
        single_item_risk = (max_item_value / total_value) * 100

        if single_item_risk > self._config.max_single_item_percent:
            risk_factors.append(
                f"High single-item concentration: {single_item_risk:.1f}% "
                f"(max recommended: {self._config.max_single_item_percent}%)"
            )
            recommendations.append("Consider diversifying by selling some high-value items")

        # Single game concentration
        max_game_value = max(snapshot.game_distribution.values(), default=0)
        single_game_risk = (max_game_value / total_value) * 100

        if single_game_risk > self._config.max_single_game_percent:
            risk_factors.append(
                f"High single-game concentration: {single_game_risk:.1f}% "
                f"(max recommended: {self._config.max_single_game_percent}%)"
            )
            recommendations.append("Consider diversifying across different games")

        # Illiquidity risk (items with low market activity)
        illiquid_value = sum(
            a.total_value
            for a in snapshot.assets
            if a.category in {"Sticker", "Graffiti", "Case", "Key", "Music Kit", "Patch"}
        )
        illiquidity_risk = (illiquid_value / total_value) * 100

        if illiquidity_risk > 30:
            risk_factors.append(
                f"High illiquidity risk: {illiquidity_risk:.1f}% in low-liquidity items"
            )
            recommendations.append(
                "Reduce holdings in stickers, cases, and other low-liquidity items"
            )

        # Stale items risk (items held too long)
        stale_value = sum(
            a.total_value for a in snapshot.assets if a.days_held > self._config.max_stale_days
        )
        stale_items_risk = (stale_value / total_value) * 100

        if stale_items_risk > 20:
            risk_factors.append(
                f"Stale items: {stale_items_risk:.1f}% held > {self._config.max_stale_days} days"
            )
            recommendations.append("Consider reducing prices on stale items to improve turnover")

        # Cash allocation
        cash_percent = (snapshot.cash_balance / total_value) * 100
        if cash_percent < 10:
            risk_factors.append(f"Low cash reserve: {cash_percent:.1f}%")
            recommendations.append("Consider maintaining at least 10-20% in cash for opportunities")

        # Calculate concentration score (0-100, higher = more concentrated = worse)
        concentration_score = min(100, (single_item_risk + single_game_risk) / 2)

        # Calculate diversification score (inverse of concentration)
        num_assets = len(snapshot.assets)
        num_games = len(snapshot.game_distribution)
        num_categories = len(snapshot.category_distribution)

        # More assets, games, and categories = better diversification
        asset_factor = min(1.0, num_assets / 20)  # Max bonus at 20 assets
        game_factor = min(1.0, num_games / 4)  # Max bonus at 4 games
        category_factor = min(1.0, num_categories / 8)  # Max bonus at 8 categories

        diversification_score = (
            (100 - concentration_score) * 0.5
            + asset_factor * 20
            + game_factor * 15
            + category_factor * 15
        )
        diversification_score = max(0, min(100, diversification_score))

        # Determine overall risk level
        risk_score = (
            concentration_score * 0.3
            + single_item_risk * 0.2
            + illiquidity_risk * 0.2
            + stale_items_risk * 0.15
            + (100 - cash_percent) * 0.15
        )

        if risk_score < 25:
            overall_risk = RiskLevel.LOW
        elif risk_score < 50:
            overall_risk = RiskLevel.MEDIUM
        elif risk_score < 75:
            overall_risk = RiskLevel.HIGH
        else:
            overall_risk = RiskLevel.CRITICAL

        return RiskAnalysis(
            overall_risk=overall_risk,
            concentration_score=concentration_score,
            single_item_risk=single_item_risk,
            single_game_risk=single_game_risk,
            illiquidity_risk=illiquidity_risk,
            stale_items_risk=stale_items_risk,
            diversification_score=diversification_score,
            risk_factors=risk_factors,
            recommendations=recommendations,
        )

    async def get_rebalancing_recommendations(
        self,
        snapshot: PortfolioSnapshot | None = None,
        max_recommendations: int = 10,
    ) -> list[RebalanceRecommendation]:
        """Get portfolio rebalancing recommendations.

        Args:
            snapshot: Portfolio snapshot to analyze
            max_recommendations: Maximum number of recommendations

        Returns:
            List of rebalancing recommendations sorted by priority
        """
        if snapshot is None:
            snapshot = await self.get_portfolio_snapshot()

        recommendations: list[RebalanceRecommendation] = []
        total_value = snapshot.total_value_usd

        if total_value <= 0:
            return []

        # 1. Check for overconcentrated items
        for asset in snapshot.assets:
            item_percent = (asset.total_value / total_value) * 100

            if item_percent > self._config.max_single_item_percent:
                target_value = total_value * (self._config.max_single_item_percent / 100)
                excess_value = asset.total_value - target_value
                quantity_to_sell = max(1, int(excess_value / asset.unit_price))

                recommendations.append(
                    RebalanceRecommendation(
                        action=RebalanceAction.SELL,
                        item_id=asset.item_id,
                        item_name=asset.item_name,
                        current_value=asset.total_value,
                        target_value=target_value,
                        quantity=quantity_to_sell,
                        priority=5,  # Highest priority
                        reason=f"Overconcentrated: {item_percent:.1f}% of portfolio",
                        expected_impact=f"Reduce concentration by ${excess_value:.2f}",
                    )
                )

        # 2. Check for stale items (held too long)
        for asset in snapshot.assets:
            if asset.days_held > self._config.max_stale_days:
                if asset.asset_type == AssetType.LISTED:
                    # Recommend price reduction
                    recommendations.append(
                        RebalanceRecommendation(
                            action=RebalanceAction.REDUCE_PRICE,
                            item_id=asset.item_id,
                            item_name=asset.item_name,
                            current_value=asset.total_value,
                            target_value=asset.total_value * 0.95,  # 5% reduction
                            quantity=asset.quantity,
                            priority=3,
                            reason=f"Stale listing: {asset.days_held} days (>{self._config.max_stale_days})",
                            expected_impact="Improve turnover with 5% price reduction",
                        )
                    )
                elif asset.asset_type == AssetType.INVENTORY:
                    # Recommend listing for sale
                    recommendations.append(
                        RebalanceRecommendation(
                            action=RebalanceAction.SELL,
                            item_id=asset.item_id,
                            item_name=asset.item_name,
                            current_value=asset.total_value,
                            target_value=0,
                            quantity=asset.quantity,
                            priority=2,
                            reason=f"Stale inventory: {asset.days_held} days without listing",
                            expected_impact="Convert stale inventory to cash",
                        )
                    )

        # 3. Check for items with significant loss
        for asset in snapshot.assets:
            if asset.profit_loss_percent < -10:  # More than 10% loss
                recommendations.append(
                    RebalanceRecommendation(
                        action=RebalanceAction.SELL,
                        item_id=asset.item_id,
                        item_name=asset.item_name,
                        current_value=asset.total_value,
                        target_value=0,
                        quantity=asset.quantity,
                        priority=3,
                        reason=f"Significant loss: {asset.profit_loss_percent:.1f}%",
                        expected_impact="Cut losses and redeploy capital",
                    )
                )

        # 4. Check cash allocation
        cash_percent = (snapshot.cash_balance / total_value) * 100
        if cash_percent < 10:
            # Recommend selling some items to increase cash
            # Find lowest priority items to sell
            sellable = [
                a
                for a in snapshot.assets
                if a.asset_type in {AssetType.INVENTORY, AssetType.LISTED}
                and a.profit_loss_percent >= 0  # Only profitable items
            ]
            sellable.sort(key=lambda x: x.total_value)  # Sort by value, sell smallest first

            target_cash = total_value * (self._config.target_cash_percent / 100)
            needed_cash = target_cash - snapshot.cash_balance

            for asset in sellable[:3]:  # Max 3 items
                if needed_cash <= 0:
                    break

                recommendations.append(
                    RebalanceRecommendation(
                        action=RebalanceAction.SELL,
                        item_id=asset.item_id,
                        item_name=asset.item_name,
                        current_value=asset.total_value,
                        target_value=0,
                        quantity=asset.quantity,
                        priority=2,
                        reason=f"Low cash reserve: {cash_percent:.1f}% (target: {self._config.target_cash_percent}%)",
                        expected_impact=f"Increase cash by ${asset.total_value:.2f}",
                    )
                )
                needed_cash -= asset.total_value

        # 5. Check for targets that should be cancelled
        for asset in snapshot.assets:
            if asset.asset_type == AssetType.TARGET:
                # If target has been active too long, recommend cancellation
                if asset.days_held > self._config.max_target_days:
                    recommendations.append(
                        RebalanceRecommendation(
                            action=RebalanceAction.CANCEL_TARGET,
                            item_id=asset.item_id,
                            item_name=asset.item_name,
                            current_value=asset.total_value,
                            target_value=0,
                            quantity=asset.quantity,
                            priority=2,
                            reason=f"Stale target: {asset.days_held} days without fill (>{self._config.max_target_days})",
                            expected_impact=f"Free up ${asset.total_value:.2f} in locked funds",
                        )
                    )

        # Sort by priority (highest first) and limit
        recommendations.sort(key=lambda x: -x.priority)
        return recommendations[:max_recommendations]

    async def get_performance_metrics(
        self,
        period_days: int = 30,
    ) -> dict[str, Any]:
        """Get portfolio performance metrics over a period.

        Args:
            period_days: Number of days to analyze

        Returns:
            Performance metrics dictionary
        """
        snapshot = await self.get_portfolio_snapshot()

        # Calculate basic metrics
        total_value = snapshot.total_value_usd
        cash_percent = (snapshot.cash_balance / total_value * 100) if total_value > 0 else 0

        # Calculate unrealized P&L
        total_profit_loss = sum(a.profit_loss for a in snapshot.assets)
        profitable_items = sum(1 for a in snapshot.assets if a.profit_loss > 0)
        losing_items = sum(1 for a in snapshot.assets if a.profit_loss < 0)

        # Asset allocation
        inventory_percent = (snapshot.inventory_value / total_value * 100) if total_value > 0 else 0
        listed_percent = (snapshot.listed_value / total_value * 100) if total_value > 0 else 0
        targets_percent = (snapshot.targets_value / total_value * 100) if total_value > 0 else 0

        return {
            "period_days": period_days,
            "total_value_usd": total_value,
            "cash_balance": snapshot.cash_balance,
            "cash_percent": cash_percent,
            "inventory_value": snapshot.inventory_value,
            "inventory_percent": inventory_percent,
            "listed_value": snapshot.listed_value,
            "listed_percent": listed_percent,
            "targets_value": snapshot.targets_value,
            "targets_percent": targets_percent,
            "asset_count": snapshot.asset_count,
            "unrealized_pnl": total_profit_loss,
            "profitable_items": profitable_items,
            "losing_items": losing_items,
            "win_rate": (
                (profitable_items / snapshot.asset_count * 100) if snapshot.asset_count > 0 else 0
            ),
            "game_distribution": snapshot.game_distribution,
            "category_distribution": snapshot.category_distribution,
        }

    def format_portfolio_report(self, snapshot: PortfolioSnapshot, risk: RiskAnalysis) -> str:
        """Format portfolio report for Telegram message.

        Args:
            snapshot: Portfolio snapshot
            risk: Risk analysis

        Returns:
            Formatted markdown string
        """
        lines = [
            "📊 *Portfolio Report*",
            "",
            f"💰 *Total Value:* ${snapshot.total_value_usd:.2f}",
            (
                f"💵 Cash: ${snapshot.cash_balance:.2f} ({snapshot.cash_balance / snapshot.total_value_usd * 100:.1f}%)"
                if snapshot.total_value_usd > 0
                else ""
            ),
            f"📦 Inventory: ${snapshot.inventory_value:.2f}",
            f"🏷️ Listed: ${snapshot.listed_value:.2f}",
            f"🎯 Targets: ${snapshot.targets_value:.2f}",
            "",
            f"📈 *Assets:* {snapshot.asset_count}",
        ]

        # Game distribution
        if snapshot.game_distribution:
            lines.extend(("", "🎮 *By Game:*"))
            for game, value in sorted(snapshot.game_distribution.items(), key=lambda x: -x[1]):
                percent = (
                    (value / snapshot.total_value_usd * 100) if snapshot.total_value_usd > 0 else 0
                )
                lines.append(f"  • {game}: ${value:.2f} ({percent:.1f}%)")

        # Risk section
        risk_emoji = {
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🟠",
            RiskLevel.CRITICAL: "🔴",
        }

        lines.extend([
            "",
            f"⚠️ *Risk Level:* {risk_emoji.get(risk.overall_risk, '⚪')} {risk.overall_risk.value.upper()}",
            f"📊 Diversification: {risk.diversification_score:.0f}/100",
            f"🎯 Concentration: {risk.concentration_score:.0f}%",
        ])

        # Risk factors
        if risk.risk_factors:
            lines.extend(("", "⚠️ *Risk Factors:*"))
            for factor in risk.risk_factors[:3]:
                lines.append(f"  • {factor}")

        # Recommendations
        if risk.recommendations:
            lines.extend(("", "💡 *Recommendations:*"))
            for rec in risk.recommendations[:3]:
                lines.append(f"  • {rec}")

        return "\n".join(lines)


# Convenience functions for external use
async def get_portfolio_summary(api_client: DMarketAPI) -> dict[str, Any]:
    """Get a quick portfolio summary.

    Args:
        api_client: DMarket API client

    Returns:
        Dictionary with portfolio summary
    """
    pm = PortfolioManager(api_client=api_client)
    snapshot = await pm.get_portfolio_snapshot()
    risk = await pm.analyze_risk(snapshot)

    return {
        "total_value": snapshot.total_value_usd,
        "cash": snapshot.cash_balance,
        "assets": snapshot.asset_count,
        "risk_level": risk.overall_risk.value,
        "diversification": risk.diversification_score,
    }


async def get_rebalancing_actions(api_client: DMarketAPI) -> list[dict[str, Any]]:
    """Get rebalancing actions for portfolio.

    Args:
        api_client: DMarket API client

    Returns:
        List of recommended actions
    """
    pm = PortfolioManager(api_client=api_client)
    recommendations = await pm.get_rebalancing_recommendations()

    return [
        {
            "action": rec.action.value,
            "item": rec.item_name,
            "priority": rec.priority,
            "reason": rec.reason,
        }
        for rec in recommendations
    ]
