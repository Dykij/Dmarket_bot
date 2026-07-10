"""Advanced order system."""
from dataclasses import dataclass
from enum import Enum
from typing import Any


class DopplerPhase(str, Enum):
    """Doppler knife phases."""
    PHASE_1 = "Phase 1"
    PHASE_2 = "Phase 2"
    PHASE_3 = "Phase 3"
    PHASE_4 = "Phase 4"
    RUBY = "Ruby"
    SAPPHIRE = "Sapphire"
    EMERALD = "Emerald"
    BLACK_PEARL = "Black Pearl"


@dataclass
class FloatOrderFilter:
    """Filter for float-based orders."""
    min_float: float = 0.0
    max_float: float = 1.0
    prefer_low: bool = True


class AdvancedOrderSystem:
    """Manages advanced order types (stop-loss, take-profit, trailing stop)."""

    def __init__(self, api_client: Any = None) -> None:
        self.api = api_client


def create_float_order(
    title: str,
    price: float,
    float_filter: FloatOrderFilter | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create a float-filtered order."""
    return {
        "title": title,
        "price": price,
        "float_filter": float_filter,
    }
