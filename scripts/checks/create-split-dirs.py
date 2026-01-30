#!/usr/bin/env python3
"""
Create split directories from project-manifest.md.

Parses the SPLIT_MANIFEST block and creates the corresponding directories.

Usage:
    uv run create-split-dirs.py --planning-dir <path>

Output (JSON):
    {
        "success": true/false,
        "error": "error message if failed",
        "created": ["01-backend", "02-frontend"],
        "skipped": ["03-existing"],
        "manifest_splits": ["01-backend", "02-frontend", "03-existing"]
    }
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.config import SessionFilename
from lib.manifest import parse_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Create split directories from manifest")
    parser.add_argument("--planning-dir", required=True, help="Path to planning directory")
    args = parser.parse_args()

    planning_dir = Path(args.planning_dir).resolve()

    if not planning_dir.exists():
        print(json.dumps({
            "success": False,
            "error": f"Planning directory not found: {planning_dir}"
        }, indent=2))
        return 1

    if not planning_dir.is_dir():
        print(json.dumps({
            "success": False,
            "error": f"Expected directory, got file: {planning_dir}"
        }, indent=2))
        return 1

    # Parse manifest
    manifest_path = planning_dir / SessionFilename.MANIFEST
    result = parse_manifest(manifest_path)

    if not result.is_valid:
        print(json.dumps({
            "success": False,
            "error": "Manifest validation failed",
            "errors": result.errors
        }, indent=2))
        return 1

    # Create directories
    created: list[str] = []
    skipped: list[str] = []

    for split_name in result.splits:
        split_dir = planning_dir / split_name
        if split_dir.exists():
            skipped.append(split_name)
        else:
            split_dir.mkdir(parents=False, exist_ok=False)
            created.append(split_name)

    print(json.dumps({
        "success": True,
        "created": created,
        "skipped": skipped,
        "manifest_splits": result.splits,
        "message": f"Created {len(created)} directories, skipped {len(skipped)} existing"
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
