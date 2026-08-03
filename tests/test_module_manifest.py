"""
Module manifest audit: verify all src/*.py files are documented or imported.
"""
import ast
from pathlib import Path

import yaml


def _load_manifest():
    manifest_path = Path("docs/MODULE_MANIFEST.yaml")
    if not manifest_path.exists():
        return {"active": [], "research": [], "archived": []}
    return yaml.safe_load(manifest_path.read_text())


def _is_imported_somewhere(file_path: str) -> bool:
    """Check if a file is imported somewhere in src/."""
    # Convert path to module name (src/foo/bar.py -> src.foo.bar)
    module_name = file_path.replace("/", ".").replace(".py", "")
    # Remove src. prefix for shorter matching
    short_module = module_name.replace("src.", "")

    for py in Path("src").rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        content = py.read_text()
        # Check for import/from statements
        if f"from {module_name}" in content:
            return True
        if f"from {short_module}" in content:
            return True
        if f"import {module_name}" in content:
            return True
        if f"import {short_module}" in content:
            return True
    return False


def test_all_src_files_documented():
    """Every .py in src/ must be either in manifest or imported somewhere."""
    manifest = _load_manifest()
    all_documented = set()
    for category in ["active", "research", "archived"]:
        for item in manifest.get(category, []):
            # Expand globs
            if "*" in item:
                for f in Path(".").glob(item):
                    all_documented.add(str(f))
            else:
                all_documented.add(item)

    cwd = Path.cwd()
    undocumented = []
    for py_file in Path("src").rglob("*.py"):
        if "__pycache__" in str(py_file) or "__init__" in py_file.name:
            continue
        try:
            rel_path = str(py_file.relative_to(cwd))
        except ValueError:
            rel_path = str(py_file)
        if rel_path not in all_documented and not _is_imported_somewhere(rel_path):
            undocumented.append(rel_path)

    assert not undocumented, f"Undocumented src files: {undocumented}"


def test_manifest_files_exist():
    """All files listed in manifest must actually exist."""
    manifest = _load_manifest()
    missing = []
    for category in ["active", "research", "archived"]:
        for item in manifest.get(category, []):
            if "*" in item:
                # Glob pattern — skip existence check
                continue
            if not Path(item).exists():
                missing.append(item)
    assert not missing, f"Manifest references missing files: {missing}"


def test_archived_not_imported():
    """Archived files should not be imported from active trading path."""
    manifest = _load_manifest()
    archived = set(manifest.get("archived", []))

    # Check active files for imports of archived modules
    active_files = manifest.get("active", [])
    violations = []
    for active_item in active_files:
        if "*" in active_item:
            continue
        if not Path(active_item).exists():
            continue
        content = Path(active_item).read_text()
        for arch_item in archived:
            if "*" in arch_item:
                continue
            module = arch_item.replace("/", ".").replace(".py", "").replace("src.", "")
            if f"from {module}" in content or f"import {module}" in content:
                violations.append(f"{active_item} imports archived {arch_item}")

    assert not violations, f"Active files import archived code: {violations}"
