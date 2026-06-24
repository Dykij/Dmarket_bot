"""Comprehensive sandbox test suite v14.8.

Splits the legacy standalone sandbox scripts into small, focused modules:
  - common.py     : shared helpers, metrics, API clients
  - test_local.py : local microstructure instrument smoke tests
  - test_pipeline.py : filter + cross-market target pipeline
  - test_live.py  : 10-minute live polling cycle
  - runner.py     : orchestrator that runs all phases

Usage:
    uv run python tests/sandbox_comprehensive/runner.py
"""
