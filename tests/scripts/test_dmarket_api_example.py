#!/usr/bin/env python3
"""Tests for dmarket_api_example.py script.

Version: 1.0.0
Updated: 28 December 2025
"""

from unittest.mock import patch

import pytest


class TestGetApiKeys:
    """Tests for get_api_keys function."""

    def test_get_api_keys_success(self) -> None:
        """Test successful API key retrieval."""
        with patch.dict(
            "os.environ",
            {
                "DMARKET_PUBLIC_KEY": "test_public_key_12345",
                "DMARKET_SECRET_KEY": "test_secret_key_67890",
            },
        ):
            # Import inside test to avoid import errors
            import sys

            # Clear cached module
            if "scripts.dmarket_api_example" in sys.modules:
                del sys.modules["scripts.dmarket_api_example"]

            try:
                from scripts.dmarket_api_example import get_api_keys

                public_key, secret_key = get_api_keys()

                assert public_key == "test_public_key_12345"
                assert secret_key == "test_secret_key_67890"
            except ImportError:
                pytest.skip("Cannot import due to missing dependencies")

    def test_get_api_keys_missing_public(self) -> None:
        """Test missing public key."""
        try:
            from scripts.dmarket_api_example import get_api_keys
        except ImportError:
            pytest.skip("Cannot import due to missing dependencies")
            return

        with (
            patch.dict(
                "os.environ",
                {"DMARKET_SECRET_KEY": "test_secret"},
                clear=True,
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            get_api_keys()

        assert exc_info.value.code == 1


class TestParseArgs:
    """Tests for parse_args function."""

    def test_parse_args_default(self) -> None:
        """Test default arguments."""
        try:
            from scripts.dmarket_api_example import parse_args
        except ImportError:
            pytest.skip("Cannot import due to missing dependencies")
            return

        with patch("sys.argv", ["dmarket_api_example.py"]):
            args = parse_args()

            assert args.game == "csgo"
            assert args.limit == 5
            assert args.demo_only is False

    def test_parse_args_game(self) -> None:
        """Test --game argument."""
        try:
            from scripts.dmarket_api_example import parse_args
        except ImportError:
            pytest.skip("Cannot import due to missing dependencies")
            return

        with patch("sys.argv", ["dmarket_api_example.py", "--game", "dota2"]):
            args = parse_args()

            assert args.game == "dota2"

    def test_parse_args_limit(self) -> None:
        """Test --limit argument."""
        try:
            from scripts.dmarket_api_example import parse_args
        except ImportError:
            pytest.skip("Cannot import due to missing dependencies")
            return

        with patch("sys.argv", ["dmarket_api_example.py", "--limit", "10"]):
            args = parse_args()

            assert args.limit == 10

    def test_parse_args_demo_only(self) -> None:
        """Test --demo-only argument."""
        try:
            from scripts.dmarket_api_example import parse_args
        except ImportError:
            pytest.skip("Cannot import due to missing dependencies")
            return

        with patch("sys.argv", ["dmarket_api_example.py", "--demo-only"]):
            args = parse_args()

            assert args.demo_only is True

    def test_parse_args_all_games(self) -> None:
        """Test all supported games."""
        try:
            from scripts.dmarket_api_example import parse_args
        except ImportError:
            pytest.skip("Cannot import due to missing dependencies")
            return

        for game in ["csgo", "dota2", "tf2", "rust"]:
            with patch("sys.argv", ["dmarket_api_example.py", "--game", game]):
                args = parse_args()
                assert args.game == game
