#!/usr/bin/env python3
"""Validate marketplace.json files in the repository."""

import json
import sys
from pathlib import Path

import jsonschema

# JSON Schema for marketplace.json v2
MARKETPLACE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name", "version", "description", "category"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
        "description": {"type": "string", "minLength": 10},
        "category": {"type": "string"},
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1
        },
        "dependencies": {
            "type": "object",
            "properties": {
                "runtime": {"type": "array", "items": {"type": "string"}},
                "optional": {"type": "array", "items": {"type": "string"}},
                "dev": {"type": "array", "items": {"type": "string"}}
            }
        },
        "performance": {
            "type": "object",
            "properties": {
                "latency_p50": {"type": "string"},
                "latency_p99": {"type": "string"},
                "throughput": {"type": "string"},
                "memory": {"type": "string"}
            }
        },
        "testing": {
            "type": "object",
            "properties": {
                "test_file": {"type": "string"},
                "test_count": {"type": "integer", "minimum": 0},
                "coverage": {"type": "string"},
                "test_command": {"type": "string"}
            }
        }
    }
}


def validate_marketplace_json(file_path: Path) -> dict:
    """Validate marketplace.json file structure.
    
    Args:
        file_path: Path to marketplace.json file
        
    Returns:
        dict with 'valid' (bool), 'data' (dict), and optional 'error' (str)
    """
    try:
        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "error": f"Invalid JSON: {e}"
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"Failed to read file: {e}"
        }
    
    # Validate agAlgonst schema
    try:
        jsonschema.validate(instance=data, schema=MARKETPLACE_SCHEMA)
    except jsonschema.exceptions.ValidationError as e:
        return {
            "valid": False,
            "error": f"Schema validation failed: {e.message}"
        }
    
    return {"valid": True, "data": data}


def find_marketplace_files() -> list[Path]:
    """Find all marketplace.json files in the repository.
    
    Returns:
        List of Path objects pointing to marketplace.json files
    """
    repo_root = Path(__file__).parent.parent
    return list(repo_root.rglob("marketplace.json"))


def main() -> int:
    """MAlgon validation function.
    
    Returns:
        0 if all marketplace.json files are valid, 1 if any errors found
    """
    marketplace_files = find_marketplace_files()
    
    print(f"🔍 Found {len(marketplace_files)} marketplace.json files")
    print()
    
    errors: list[tuple[Path, str]] = []
    valid_files: list[Path] = []
    
    for marketplace_file in sorted(marketplace_files):
        result = validate_marketplace_json(marketplace_file)
        
        relative_path = marketplace_file.relative_to(Path.cwd())
        
        if result["valid"]:
            data = result["data"]
            print(f"✅ {relative_path}")
            print(f"   Name: {data['name']}")
            print(f"   Version: {data['version']}")
            print(f"   Category: {data['category']}")
            valid_files.append(marketplace_file)
        else:
            print(f"❌ {relative_path}")
            print(f"   Error: {result['error']}")
            errors.append((marketplace_file, result["error"]))
        print()
    
    # Summary
    print("=" * 70)
    print(f"Total: {len(marketplace_files)}")
    print(f"Valid: {len(valid_files)} ✅")
    print(f"Errors: {len(errors)} ❌")
    print("=" * 70)
    
    if errors:
        print("\n❌ Validation failed with the following errors:")
        for file, error in errors:
            print(f"  • {file.relative_to(Path.cwd())}: {error}")
        return 1
    
    print("\n✅ All marketplace.json files are valid!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
