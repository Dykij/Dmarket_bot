"""
Tests for ASCII docstrings in keyboard modules.

Validates that docstrings contain visual ASCII diagrams for Telegram UI.
"""

import ast
import inspect
from pathlib import Path

import pytest


class TestASCIIDocstrings:
    """Tests for ASCII docstrings in keyboard modules."""

    @pytest.fixture()
    def keyboards_dir(self):
        """Get keyboards directory path."""
        return Path(__file__).parent.parent / "src" / "telegram_bot" / "keyboards"

    @pytest.fixture()
    def keyboard_modules(self, keyboards_dir):
        """Get list of keyboard module files."""
        return list(keyboards_dir.glob("*.py"))

    def test_keyboards_directory_exists(self, keyboards_dir):
        """Test that keyboards directory exists."""
        assert keyboards_dir.exists(), "keyboards directory should exist"

    def test_arbitrage_py_exists(self, keyboards_dir):
        """Test that arbitrage.py exists."""
        arb_path = keyboards_dir / "arbitrage.py"
        assert arb_path.exists(), "arbitrage.py should exist"

    def test_alerts_py_exists(self, keyboards_dir):
        """Test that alerts.py exists."""
        alerts_path = keyboards_dir / "alerts.py"
        assert alerts_path.exists(), "alerts.py should exist"

    def test_settings_py_exists(self, keyboards_dir):
        """Test that settings.py exists."""
        settings_path = keyboards_dir / "settings.py"
        assert settings_path.exists(), "settings.py should exist"

    def _has_ascii_diagram(self, docstring: str) -> bool:
        """Check if docstring contains ASCII diagram markers."""
        if not docstring:
            return False

        # Look for box-drawing characters
        box_chars = ["┌", "┐", "└", "┘", "├", "┤", "│", "─", "┬", "┴", "┼"]
        return any(char in docstring for char in box_chars)

    def _extract_functions_with_docstrings(self, file_path: Path):
        """Extract functions and their docstrings from a Python file."""
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                docstring = ast.get_docstring(node)
                functions.append({"name": node.name, "docstring": docstring, "line": node.lineno})

        return functions

    def test_arbitrage_functions_have_ascii_docstrings(self, keyboards_dir):
        """Test that arbitrage keyboard functions have ASCII diagrams."""
        arb_path = keyboards_dir / "arbitrage.py"
        functions = self._extract_functions_with_docstrings(arb_path)

        # Functions that should have ASCII diagrams
        expected_functions = [
            "get_arbitrage_keyboard",
            "get_modern_arbitrage_keyboard",
            "get_auto_arbitrage_keyboard",
        ]

        for func_name in expected_functions:
            func = next((f for f in functions if f["name"] == func_name), None)
            assert func is not None, f"Function {func_name} not found"
            assert func["docstring"] is not None, f"{func_name} should have docstring"
            assert self._has_ascii_diagram(func["docstring"]), (
                f"{func_name} docstring should contain ASCII diagram"
            )

    def test_alerts_functions_have_ascii_docstrings(self, keyboards_dir):
        """Test that alerts keyboard functions have ASCII diagrams."""
        alerts_path = keyboards_dir / "alerts.py"
        functions = self._extract_functions_with_docstrings(alerts_path)

        expected_functions = ["get_alert_keyboard", "get_alert_type_keyboard"]

        for func_name in expected_functions:
            func = next((f for f in functions if f["name"] == func_name), None)
            assert func is not None, f"Function {func_name} not found"
            assert func["docstring"] is not None, f"{func_name} should have docstring"
            assert self._has_ascii_diagram(func["docstring"]), (
                f"{func_name} docstring should contain ASCII diagram"
            )

    def test_settings_functions_have_ascii_docstrings(self, keyboards_dir):
        """Test that settings keyboard functions have ASCII diagrams."""
        settings_path = keyboards_dir / "settings.py"
        functions = self._extract_functions_with_docstrings(settings_path)

        expected_functions = ["get_settings_keyboard", "get_language_keyboard"]

        for func_name in expected_functions:
            func = next((f for f in functions if f["name"] == func_name), None)
            assert func is not None, f"Function {func_name} not found"
            assert func["docstring"] is not None, f"{func_name} should have docstring"
            assert self._has_ascii_diagram(func["docstring"]), (
                f"{func_name} docstring should contain ASCII diagram"
            )

    def test_ascii_diagrams_have_proper_structure(self, keyboards_dir):
        """Test that ASCII diagrams have proper box structure."""
        # Test one file in detail
        arb_path = keyboards_dir / "arbitrage.py"
        functions = self._extract_functions_with_docstrings(arb_path)

        for func in functions:
            if func["docstring"] and self._has_ascii_diagram(func["docstring"]):
                docstring = func["docstring"]

                # Should have top border
                assert "┌" in docstring or "╔" in docstring, (
                    f"{func['name']}: ASCII diagram should have top border"
                )

                # Should have bottom border
                assert "└" in docstring or "╚" in docstring, (
                    f"{func['name']}: ASCII diagram should have bottom border"
                )

                # Should have vertical lines
                assert "│" in docstring or "║" in docstring, (
                    f"{func['name']}: ASCII diagram should have vertical lines"
                )

    def test_docstrings_have_telegram_ui_marker(self, keyboards_dir):
        """Test that docstrings have 'Telegram UI:' marker."""
        files_to_check = [
            keyboards_dir / "arbitrage.py",
            keyboards_dir / "alerts.py",
            keyboards_dir / "settings.py",
        ]

        for file_path in files_to_check:
            functions = self._extract_functions_with_docstrings(file_path)

            # Check at least one function has the marker
            has_marker = any(
                func["docstring"] and "Telegram UI:" in func["docstring"] for func in functions
            )

            assert has_marker, f"{file_path.name} should have 'Telegram UI:' marker in docstrings"

    def test_docstrings_use_emojis(self, keyboards_dir):
        """Test that docstrings use emojis for visual clarity."""
        arb_path = keyboards_dir / "arbitrage.py"
        functions = self._extract_functions_with_docstrings(arb_path)

        # Check that at least some functions use emojis
        has_emojis = False
        for func in functions:
            if func["docstring"]:
                # Common emojis used in UI
                common_emojis = ["🔍", "🎮", "📊", "⚙️", "🤖", "◀️", "➕", "🔔"]
                if any(emoji in func["docstring"] for emoji in common_emojis):
                    has_emojis = True
                    break

        assert has_emojis, "At least some docstrings should use emojis"

    def test_all_keyboard_functions_have_docstrings(self, keyboards_dir):
        """Test that all public keyboard functions have docstrings."""
        keyboard_files = [
            keyboards_dir / "arbitrage.py",
            keyboards_dir / "alerts.py",
            keyboards_dir / "settings.py",
        ]

        for file_path in keyboard_files:
            functions = self._extract_functions_with_docstrings(file_path)

            # Check public functions (not starting with _)
            public_functions = [f for f in functions if not f["name"].startswith("_")]

            for func in public_functions:
                assert func["docstring"] is not None, (
                    f"{file_path.name}::{func['name']} should have docstring"
                )
                assert len(func["docstring"]) > 20, (
                    f"{file_path.name}::{func['name']} docstring should be meaningful"
                )


class TestDocstringQuality:
    """Tests for overall docstring quality."""

    def test_docstrings_follow_google_style(self):
        """Test that docstrings follow Google style guide."""
        from src.telegram_bot.keyboards import arbitrage

        # Check get_arbitrage_keyboard as example
        func = arbitrage.get_arbitrage_keyboard
        docstring = inspect.getdoc(func)

        assert docstring is not None
        # Should have Returns section
        assert "Returns:" in docstring or "Returns" in docstring

    def test_docstrings_include_return_type(self):
        """Test that docstrings document return type."""
        from src.telegram_bot.keyboards import arbitrage

        func = arbitrage.get_arbitrage_keyboard
        docstring = inspect.getdoc(func)

        assert "InlineKeyboardMarkup" in docstring, "Docstring should mention return type"
