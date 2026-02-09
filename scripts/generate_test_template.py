#!/usr/bin/env python3
"""Test template generator for new modules.

This script automatically generates test templates for Python modules
that don't have corresponding test files.

Usage:
    python scripts/generate_test_template.py src/module.py
    python scripts/generate_test_template.py --all  # Generate for all untested modules
    python scripts/generate_test_template.py --check  # List untested modules

Examples:
    python scripts/generate_test_template.py src/dmarket/api/new_feature.py
    python scripts/generate_test_template.py --all --coverage 80
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import Any


def get_module_info(module_path: Path) -> dict[str, Any]:
    """Extract information about a Python module.

    Args:
        module_path: Path to the Python module

    Returns:
        Dictionary with module info (classes, functions, etc.)
    """
    content = Path(module_path).read_text(encoding="utf-8")

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"Warning: Could not parse {module_path}: {e}")
        return {"classes": [], "functions": [], "async_functions": []}

    info: dict[str, Any] = {
        "classes": [],
        "functions": [],
        "async_functions": [],
        "module_doc": ast.get_docstring(tree),
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = []
            async_methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    if not item.name.startswith("_"):
                        methods.append(item.name)
                elif isinstance(item, ast.AsyncFunctionDef):
                    if not item.name.startswith("_"):
                        async_methods.append(item.name)

            info["classes"].append({
                "name": node.name,
                "methods": methods,
                "async_methods": async_methods,
                "doc": ast.get_docstring(node),
            })
        elif isinstance(node, ast.FunctionDef):
            # Top-level functions only
            if node.col_offset == 0 and not node.name.startswith("_"):
                info["functions"].append({"name": node.name, "doc": ast.get_docstring(node)})
        elif isinstance(node, ast.AsyncFunctionDef):
            if node.col_offset == 0 and not node.name.startswith("_"):
                info["async_functions"].append({"name": node.name, "doc": ast.get_docstring(node)})

    return info


def generate_test_template(module_path: Path, info: dict[str, Any]) -> str:
    """Generate a test template for a module.

    Args:
        module_path: Path to the module
        info: Module info from get_module_info

    Returns:
        Test file content as string
    """
    # Calculate import path
    relative_path = module_path.relative_to(Path.cwd())
    import_path = str(relative_path).replace("/", ".").replace("\\", ".")[:-3]

    module_name = module_path.stem
    has_async = bool(info["async_functions"]) or any(
        cls.get("async_methods") for cls in info["classes"]
    )

    lines = [
        f'"""Tests for {module_name} module.',
        "",
        f"Auto-generated test template for: {import_path}",
        '"""',
        "",
        "from unittest.mock import AsyncMock, MagicMock, patch",
        "",
        "import pytest",
        "",
        f"from {import_path} import (",
    ]

    # Add imports
    imports = []
    for cls in info["classes"]:
        imports.append(f"    {cls['name']},")
    for func in info["functions"]:
        imports.append(f"    {func['name']},")
    for func in info["async_functions"]:
        imports.append(f"    {func['name']},")

    if imports:
        lines.extend(imports)
        lines.append(")")
    else:
        # Remove empty import
        lines = lines[:-2]

    lines.extend([
        "",
        "",
        "# ============================================================================",
        "# FIXTURES",
        "# ============================================================================",
        "",
        "",
    ])

    # Add class-specific fixtures
    for cls in info["classes"]:
        fixture_name = f"mock_{cls['name'].lower()}"
        lines.extend([
            "@pytest.fixture",
            f"def {fixture_name}():",
            f'    """Create mock {cls["name"]} instance."""',
            f"    return MagicMock(spec={cls['name']})",
            "",
            "",
        ])

    # Generate test classes for each class
    for cls in info["classes"]:
        lines.extend([
            "# ============================================================================",
            f"# TESTS FOR {cls['name'].upper()}",
            "# ============================================================================",
            "",
            "",
            f"class Test{cls['name']}:",
            f'    """Tests for {cls["name"]} class."""',
            "",
        ])

        # Generate test for initialization
        lines.extend([
            "    def test_initialization(self):",
            f'        """Test {cls["name"]} initialization."""',
            "        # TODO: Implement initialization test",
            "        pass",
            "",
        ])

        # Generate tests for sync methods
        for method in cls["methods"]:
            lines.extend([
                f"    def test_{method}(self):",
                f'        """Test {cls["name"]}.{method}() method."""',
                f"        # TODO: Implement test for {method}",
                "        pass",
                "",
            ])

        # Generate tests for async methods
        for method in cls["async_methods"]:
            lines.extend([
                "    @pytest.mark.asyncio",
                f"    async def test_{method}(self):",
                f'        """Test {cls["name"]}.{method}() async method."""',
                f"        # TODO: Implement test for {method}",
                "        pass",
                "",
            ])

        lines.append("")

    # Generate tests for standalone functions
    if info["functions"]:
        lines.extend([
            "# ============================================================================",
            "# TESTS FOR STANDALONE FUNCTIONS",
            "# ============================================================================",
            "",
            "",
            "class TestFunctions:",
            '    """Tests for standalone functions."""',
            "",
        ])

        for func in info["functions"]:
            lines.extend([
                f"    def test_{func['name']}(self):",
                f'        """Test {func["name"]}() function."""',
                f"        # TODO: Implement test for {func['name']}",
                "        pass",
                "",
            ])

    # Generate tests for async standalone functions
    if info["async_functions"]:
        lines.extend([
            "",
            "class TestAsyncFunctions:",
            '    """Tests for async standalone functions."""',
            "",
        ])

        for func in info["async_functions"]:
            lines.extend([
                "    @pytest.mark.asyncio",
                f"    async def test_{func['name']}(self):",
                f'        """Test {func["name"]}() async function."""',
                f"        # TODO: Implement test for {func['name']}",
                "        pass",
                "",
            ])

    return "\n".join(lines)


def get_test_path(module_path: Path) -> Path:
    """Get the corresponding test file path for a module.

    Args:
        module_path: Path to the source module

    Returns:
        Path to the test file
    """
    # Convert src/package/module.py to tests/package/test_module.py
    relative = module_path.relative_to(Path.cwd())
    parts = list(relative.parts)

    # Replace 'src' with 'tests'
    if parts[0] == "src":
        parts[0] = "tests"

    # Add 'test_' prefix to filename
    parts[-1] = f"test_{parts[-1]}"

    return Path.cwd() / Path(*parts)


def find_untested_modules() -> list[Path]:
    """Find all modules without corresponding test files.

    Returns:
        List of module paths without tests
    """
    src_dir = Path.cwd() / "src"
    untested = []

    for module_path in src_dir.rglob("*.py"):
        # Skip __init__.py and private modules
        if module_path.name.startswith("_"):
            continue

        test_path = get_test_path(module_path)
        if not test_path.exists():
            untested.append(module_path)

    return untested


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate test templates")
    parser.add_argument(
        "module",
        nargs="?",
        type=str,
        help="Module path to generate test for",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate tests for all untested modules",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="List untested modules without generating",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing test files",
    )

    args = parser.parse_args()

    if args.check:
        untested = find_untested_modules()
        if untested:
            print(f"Found {len(untested)} untested modules:")
            for module in untested:
                print(f"  - {module}")
            return 1
        print("All modules have test files!")
        return 0

    modules_to_process = []

    if args.all:
        modules_to_process = find_untested_modules()
    elif args.module:
        modules_to_process = [Path(args.module)]
    else:
        parser.print_help()
        return 1

    generated_count = 0

    for module_path in modules_to_process:
        if not module_path.exists():
            print(f"Warning: Module {module_path} does not exist")
            continue

        test_path = get_test_path(module_path)

        if test_path.exists() and not args.force:
            print(f"Skipping {module_path}: test file already exists")
            continue

        # Get module info
        info = get_module_info(module_path)

        # Generate template
        template = generate_test_template(module_path, info)

        # Create test directory if needed
        test_path.parent.mkdir(parents=True, exist_ok=True)

        # Write test file
        Path(test_path).write_text(template, encoding="utf-8")

        print(f"✅ Generated: {test_path}")
        generated_count += 1

    print(f"\nGenerated {generated_count} test templates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
