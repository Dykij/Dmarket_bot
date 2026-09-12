"""Tests for SnipingLoop initialization."""

from src.core.target_sniping.core import SnipingLoop
from unittest.mock import Mock

def test_sniping_loop_init_attributes():
    client = Mock()
    loop = SnipingLoop(client)
    
    # Check that attributes exist and are of correct type
    assert hasattr(loop, "_background_tasks")
    assert isinstance(loop._background_tasks, set)
    
    assert hasattr(loop, "_failed_offer_ids")
    assert isinstance(loop._failed_offer_ids, dict)
    
    assert hasattr(loop, "_permanent_failures")
    assert isinstance(loop._permanent_failures, set)
    
    assert hasattr(loop, "_failure_counts")
    assert isinstance(loop._failure_counts, dict)
