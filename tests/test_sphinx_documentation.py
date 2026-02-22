"""
Tests for Sphinx documentation.

Validates Sphinx configuration and documentation structure.
"""

from pathlib import Path

import pytest


@pytest.fixture
def sphinx_dir():
    """Get docs-sphinx directory path."""
    return Path(__file__).parent.parent / "docs-sphinx"


class TestSphinxConfiguration:
    """Tests for Sphinx configuration."""

    def test_sphinx_directory_exists(self, sphinx_dir):
        """Test that docs-sphinx directory exists."""
        assert sphinx_dir.exists(), "docs-sphinx directory should exist"

    def test_conf_py_exists(self, sphinx_dir):
        """Test that conf.py exists."""
        conf_path = sphinx_dir / "conf.py"
        assert conf_path.exists(), "conf.py should exist"

    def test_conf_py_valid_python(self, sphinx_dir):
        """Test that conf.py is valid Python."""
        conf_path = sphinx_dir / "conf.py"
        content = conf_path.read_text(encoding='utf-8')
        
        # Try to compile (basic syntax check)
        try:
            compile(content, str(conf_path), 'exec')
        except SyntaxError as e:
            pytest.fail(f"conf.py has syntax errors: {e}")

    def test_conf_py_has_project_name(self, sphinx_dir):
        """Test that conf.py defines project name."""
        conf_path = sphinx_dir / "conf.py"
        content = conf_path.read_text(encoding='utf-8')
        assert "project = 'DMarket Telegram Bot'" in content

    def test_conf_py_has_extensions(self, sphinx_dir):
        """Test that conf.py defines extensions."""
        conf_path = sphinx_dir / "conf.py"
        content = conf_path.read_text(encoding='utf-8')
        
        required_extensions = [
            'sphinx.ext.autodoc',
            'sphinx.ext.napoleon',
            'sphinx.ext.viewcode'
        ]
        
        for ext in required_extensions:
            assert ext in content, f"{ext} should be in extensions"

    def test_index_rst_exists(self, sphinx_dir):
        """Test that index.rst exists."""
        index_path = sphinx_dir / "index.rst"
        assert index_path.exists(), "index.rst should exist"

    def test_index_rst_not_empty(self, sphinx_dir):
        """Test that index.rst is not empty."""
        index_path = sphinx_dir / "index.rst"
        content = index_path.read_text(encoding='utf-8')
        assert len(content) > 50, "index.rst should have content"

    def test_api_directory_exists(self, sphinx_dir):
        """Test that api directory exists."""
        api_dir = sphinx_dir / "api"
        assert api_dir.exists(), "api directory should exist"

    def test_telegram_bot_rst_exists(self, sphinx_dir):
        """Test that telegram_bot.rst exists."""
        rst_path = sphinx_dir / "api" / "telegram_bot.rst"
        assert rst_path.exists(), "telegram_bot.rst should exist"


class TestSphinxRequirements:
    """Tests for Sphinx requirements."""

    def test_requirements_exists(self, sphinx_dir):
        """Test that requirements.txt exists."""
        req_path = sphinx_dir / "requirements.txt"
        assert req_path.exists(), "requirements.txt should exist"

    def test_requirements_has_sphinx(self, sphinx_dir):
        """Test that requirements includes sphinx."""
        req_path = sphinx_dir / "requirements.txt"
        content = req_path.read_text()
        assert 'sphinx' in content.lower()

    def test_requirements_has_rtd_theme(self, sphinx_dir):
        """Test that requirements includes RTD theme."""
        req_path = sphinx_dir / "requirements.txt"
        content = req_path.read_text()
        assert 'sphinx-rtd-theme' in content or 'sphinx_rtd_theme' in content


class TestSphinxReadme:
    """Tests for Sphinx README."""

    def test_readme_exists(self, sphinx_dir):
        """Test that README.md exists."""
        readme_path = sphinx_dir / "README.md"
        assert readme_path.exists(), "README.md should exist"

    def test_readme_has_build_instructions(self, sphinx_dir):
        """Test that README has build instructions."""
        readme_path = sphinx_dir / "README.md"
        content = readme_path.read_text(encoding='utf-8').lower()
        assert 'sphinx-build' in content or 'make html' in content


@pytest.mark.slow
class TestSphinxBuild:
    """Tests for Sphinx build process (marked as slow)."""

    def test_sphinx_build_succeeds(self, sphinx_dir, tmp_path):
        """Test that sphinx build succeeds."""
        pytest.importorskip("sphinx")
        
        import subprocess
        
        result = subprocess.run(
            ['sphinx-build', '-b', 'html', str(sphinx_dir), str(tmp_path)],
            capture_output=True,
            text=True
        )
        
        # Sphinx may have warnings but should succeed
        assert result.returncode == 0, \
            f"Sphinx build failed: {result.stderr}"

    def test_sphinx_build_creates_html(self, sphinx_dir, tmp_path):
        """Test that sphinx build creates HTML files."""
        pytest.importorskip("sphinx")
        
        import subprocess
        
        subprocess.run(
            ['sphinx-build', '-b', 'html', str(sphinx_dir), str(tmp_path)],
            check=True,
            capture_output=True
        )
        
        # Check that index.html was created
        index_html = tmp_path / "index.html"
        assert index_html.exists(), "index.html should be generated"
