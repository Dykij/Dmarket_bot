"""
microstructure.py — backwards-compatible shim (v14.3).

This module is now a subpackage at src/analysis/microstructure/.
Existing imports like `from src.analysis.microstructure import stoikov_micro_price`
continue to work via this shim.
"""

from src.analysis.microstructure import *
