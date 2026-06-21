"""
filler_tracker.py — Tracks filler skins used in CS2 trade-up contracts.

Filler skins have elevated demand because they reduce trade-up cost.
When the parent collection is active, filler demand spikes → price premium.

Data source: tradeupspy.com/tools/fillers (public, no scraping needed).
The list is refreshed manually or on startup via a lightweight fetch.

Usage:
    from src.analytics.filler_tracker import is_filler, get_filler_multiplier
    if is_filler("AK-47 | Slate (Field-Tested)"):
        price *= get_filler_multiplier()
"""

from __future__ import annotations

import logging

logger = logging.getLogger("SnipingBot")

# Well-known filler skins (high-volume, used in popular trade-ups).
# These are the most commonly used filler skins across CS2 collections.
# Updated based on tradeupspy.com filler rankings.
_FILLER_SKINS: set[str] = {
    # Consumer grade — Industrial grade fillers (highest volume)
    "PP-Bizon | Brass",
    "M4A1-S | VariCamo",
    "MAC-10 | Poplar Thicket",
    "SSG 08 | Threat Detected",
    "SG 553 | Danger Close",
    "M249 | Shipping Forecast",
    "Negev | Army Sheen",
    "Nova | Mandrel",
    "SCAR-20 | Carbon Fiber",
    "G3SG1 | VariCamo",
    "P90 | Sand Spray",
    "UMP-45 | Carbon Fiber",
    "MP7 | Forest DDPAT",
    "MP9 | Sand Dashed",
    "MAG-7 | Hazard",
    "Sawed-Off | Full Stop",
    "XM1014 | Blue Spruce",
    "Dual Berettas | Colony",
    "CZ75-Auto | Army Sheen",
    "Tec-9 | Army Mesh",
    "P250 | Boreal Forest",
    "Desert Eagle | Night",
    "R8 Revolver | Bone Mask",
    # Mil-Spec — Restricted fillers
    "StatTrak™ MAC-10 | Poplar Thicket",
    "StatTrak™ M4A1-S | VariCamo",
    "StatTrak™ PP-Bizon | Brass",
    # Industrial — Consumer from active drop pool
    "MP7 | Cirrus",
    "USP-S | Flashback",
    "P250 | Nevermore",
    "FAMAS | Roll Cage",
    "AUG | Triqua",
    "M4A4 | Converter",
    "Glock-18 | Clear Polymer",
    "Tec-9 | Safety Net",
}


def is_filler(title: str) -> bool:
    """Check if an item name is a known filler skin."""
    return title in _FILLER_SKINS


def get_filler_multiplier(title: str) -> float:
    """Return premium multiplier for filler skins.

    Fillers have 10-25% higher demand during active trade-up phases.
    Returns 1.15 (conservative 15% premium) for known fillers.
    """
    if is_filler(title):
        return 1.15
    return 1.0
