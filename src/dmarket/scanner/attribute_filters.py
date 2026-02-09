"""Attribute-based filtering for DMarket items.

This module provides advanced filtering capabilities for item attributes such as:
- Exterior (Factory New, Minimal Wear, Field-Tested, etc.)
- Float value ranges (0.0 - 1.0)
- Rarity (Consumer, Industrial, Mil-Spec, Restricted, Classified, Covert)
- Special features (stickers, gems, phases, patterns)

These filters enable targeting of specific item variants for more precise arbitrage.

API Documentation:
- `extra` field in /exchange/v1/market/items endpoint
- Supports hierarchical filtering with `treeFilters`

Example:
    filters = AttributeFilters()
    extra = filters.create_extra_filters(
        exterior=["factory new", "minimal wear"],
        float_range=(0.0, 0.07),
        rarity=["covert", "classified"]
    )

    # Use in API call
    items = await api.get_market_items(game="csgo", extra=extra)
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AttributeFilters:
    """Manage attribute-based filters for DMarket items.

    Provides methods to create `extra` field filters for API requests,
    enabling precise targeting of item variants.
    """

    # CS:GO/CS2 Exterior conditions
    EXTERIORS = [
        "factory new",
        "minimal wear",
        "field-tested",
        "well-worn",
        "battle-scarred",
    ]

    # Item rarity levels (common across games)
    RARITIES = [
        "consumer",  # White
        "industrial",  # Light Blue
        "mil-spec",  # Blue
        "restricted",  # Purple
        "classified",  # Pink/Magenta
        "covert",  # Red
        "contraband",  # Gold (rare, e.g., Howl)
    ]

    # Doppler phases (CS:GO knives)
    DOPPLER_PHASES = [
        "phase 1",
        "phase 2",
        "phase 3",
        "phase 4",
        "ruby",
        "sapphire",
        "black pearl",
    ]

    @staticmethod
    def create_extra_filters(
        exterior: list[str] | None = None,
        float_range: tuple[float, float] | None = None,
        rarity: list[str] | None = None,
        has_stickers: bool | None = None,
        has_gems: bool | None = None,
        phase: list[str] | None = None,
        paint_seed_range: tuple[int, int] | None = None,
    ) -> dict[str, Any]:
        """Create 'extra' field filters for API requests.

        Args:
            exterior: List of exterior conditions (e.g., ["factory new", "minimal wear"])
            float_range: Float value range as (min, max), e.g., (0.0, 0.07) for FN
            rarity: List of rarity levels (e.g., ["covert", "classified"])
            has_stickers: Filter items with stickers (True/False)
            has_gems: Filter items with gems (True/False)
            phase: Doppler phases for knives (e.g., ["ruby", "sapphire"])
            paint_seed_range: Paint seed range for patterns (e.g., (1, 1000))

        Returns:
            Dictionary of filters for `extra` parameter in API calls

        Example:
            >>> filters = AttributeFilters.create_extra_filters(
            ...     exterior=["factory new"], float_range=(0.0, 0.07), rarity=["covert"]
            ... )
            >>> print(filters)
            {
                'exterior': ['factory new'],
                'floatValue': {'min': 0.0, 'max': 0.07},
                'rarity': ['covert']
            }
        """
        filters: dict[str, Any] = {}

        if exterior:
            # Normalize to lowercase for API
            filters["exterior"] = [ext.lower() for ext in exterior]
            logger.debug("exterior_filter_added", exteriors=filters["exterior"])

        if float_range:
            min_float, max_float = float_range
            if not (0.0 <= min_float <= 1.0 and 0.0 <= max_float <= 1.0):
                raise ValueError("Float values must be between 0.0 and 1.0")
            if min_float > max_float:
                raise ValueError("min_float cannot be greater than max_float")

            filters["floatValue"] = {"min": min_float, "max": max_float}
            logger.debug("float_filter_added", range=filters["floatValue"])

        if rarity:
            # Normalize to lowercase
            filters["rarity"] = [r.lower() for r in rarity]
            logger.debug("rarity_filter_added", rarities=filters["rarity"])

        if has_stickers is not None:
            filters["stickers"] = has_stickers
            logger.debug("stickers_filter_added", value=has_stickers)

        if has_gems is not None:
            filters["gems"] = has_gems
            logger.debug("gems_filter_added", value=has_gems)

        if phase:
            # Normalize to lowercase
            filters["phase"] = [p.lower() for p in phase]
            logger.debug("phase_filter_added", phases=filters["phase"])

        if paint_seed_range:
            min_seed, max_seed = paint_seed_range
            if min_seed < 0 or max_seed < 0:
                raise ValueError("Paint seed values must be non-negative")
            if min_seed > max_seed:
                raise ValueError("min_seed cannot be greater than max_seed")

            filters["paintSeed"] = {"min": min_seed, "max": max_seed}
            logger.debug("paint_seed_filter_added", range=filters["paintSeed"])

        logger.info("extra_filters_created", filter_count=len(filters))
        return filters

    @classmethod
    def get_float_range_for_exterior(cls, exterior: str) -> tuple[float, float]:
        """Get typical float range for an exterior condition.

        Args:
            exterior: Exterior condition name

        Returns:
            Tuple of (min_float, max_float)

        Example:
            >>> AttributeFilters.get_float_range_for_exterior("factory new")
            (0.0, 0.07)
        """
        exterior_ranges = {
            "factory new": (0.00, 0.07),
            "minimal wear": (0.07, 0.15),
            "field-tested": (0.15, 0.38),
            "well-worn": (0.38, 0.45),
            "battle-scarred": (0.45, 1.00),
        }

        return exterior_ranges.get(exterior.lower(), (0.0, 1.0))

    @classmethod
    def validate_exterior(cls, exterior: str) -> bool:
        """Check if exterior is valid.

        Args:
            exterior: Exterior condition name

        Returns:
            True if valid, False otherwise
        """
        return exterior.lower() in cls.EXTERIORS

    @classmethod
    def validate_rarity(cls, rarity: str) -> bool:
        """Check if rarity is valid.

        Args:
            rarity: Rarity level name

        Returns:
            True if valid, False otherwise
        """
        return rarity.lower() in cls.RARITIES

    @classmethod
    def validate_phase(cls, phase: str) -> bool:
        """Check if Doppler phase is valid.

        Args:
            phase: Phase name

        Returns:
            True if valid, False otherwise
        """
        return phase.lower() in cls.DOPPLER_PHASES

    @staticmethod
    def format_filter_description(filters: dict[str, Any]) -> str:
        """Format filters into human-readable description.

        Args:
            filters: Dictionary of filters

        Returns:
            Human-readable string

        Example:
            >>> filters = {"exterior": ["factory new"], "floatValue": {"min": 0.0, "max": 0.07}}
            >>> AttributeFilters.format_filter_description(filters)
            'Exterior: Factory New, Float: 0.00-0.07'
        """
        parts = []

        if "exterior" in filters:
            ext_str = ", ".join(e.title() for e in filters["exterior"])
            parts.append(f"Exterior: {ext_str}")

        if "floatValue" in filters:
            fv = filters["floatValue"]
            parts.append(f"Float: {fv['min']:.2f}-{fv['max']:.2f}")

        if "rarity" in filters:
            rarity_str = ", ".join(r.title() for r in filters["rarity"])
            parts.append(f"Rarity: {rarity_str}")

        if "stickers" in filters:
            parts.append("With Stickers" if filters["stickers"] else "No Stickers")

        if "gems" in filters:
            parts.append("With Gems" if filters["gems"] else "No Gems")

        if "phase" in filters:
            phase_str = ", ".join(p.title() for p in filters["phase"])
            parts.append(f"Phase: {phase_str}")

        if "paintSeed" in filters:
            ps = filters["paintSeed"]
            parts.append(f"Pattern: {ps['min']}-{ps['max']}")

        return ", ".join(parts) if parts else "No filters"


class PresetFilters:
    """Pre-defined filter presets for common scenarios.

    Provides convenient access to common filter combinations.
    """

    @staticmethod
    def factory_new_low_float() -> dict[str, Any]:
        """Factory New items with low float (0.00-0.03).

        Best condition items, often command premium prices.
        """
        return AttributeFilters.create_extra_filters(
            exterior=["factory new"],
            float_range=(0.0, 0.03),
        )

    @staticmethod
    def high_tier_skins() -> dict[str, Any]:
        """High-tier skins (Covert and Classified).

        Most valuable regular skins, good for arbitrage.
        """
        return AttributeFilters.create_extra_filters(
            rarity=["covert", "classified"],
        )

    @staticmethod
    def ruby_sapphire_knives() -> dict[str, Any]:
        """Ruby and Sapphire Doppler knives.

        Highest value Doppler variants.
        """
        return AttributeFilters.create_extra_filters(
            phase=["ruby", "sapphire"],
        )

    @staticmethod
    def stickered_items() -> dict[str, Any]:
        """Items with stickers.

        Can have added value depending on sticker quality.
        """
        return AttributeFilters.create_extra_filters(
            has_stickers=True,
        )

    @staticmethod
    def budget_high_tier() -> dict[str, Any]:
        """High-tier but worn items for budget arbitrage.

        Covert/Classified items in FT/WW condition.
        """
        return AttributeFilters.create_extra_filters(
            exterior=["field-tested", "well-worn"],
            rarity=["covert", "classified"],
        )
