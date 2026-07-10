"""Unified strategy system."""
from typing import Any


def get_strategy_config_preset(preset_name: str = "default") -> dict[str, Any]:
    """Get a strategy configuration preset."""
    presets = {
        "default": {
            "min_spread_pct": 5.0,
            "max_position_risk_pct": 15.0,
            "kelly_fraction": 0.5,
        },
        "aggressive": {
            "min_spread_pct": 3.0,
            "max_position_risk_pct": 20.0,
            "kelly_fraction": 0.75,
        },
        "conservative": {
            "min_spread_pct": 10.0,
            "max_position_risk_pct": 10.0,
            "kelly_fraction": 0.25,
        },
    }
    return presets.get(preset_name, presets["default"])
