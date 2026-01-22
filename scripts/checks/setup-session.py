#!/usr/bin/env python3
"""
Setup and manage /deep-project session state.

Usage:
    uv run setup-session.py --file <path_to_spec.md> --plugin-root <path>

Output (JSON):
    {
        "success": true/false,
        "error": "error message if failed",
        "mode": "new" | "resume",
        "planning_dir": "/path/to/planning",
        "initial_file": "/path/to/spec.md",
        "plugin_root": "/path/to/plugin",
        "resume_from_step": <step_number>,
        "state": {
            "interview_complete": bool,
            "splits_proposed": bool,
            "splits_confirmed": bool,
            "directories_created": bool,
            "manifest_created": bool
        },
        "existing_splits": ["01-name", "02-name", ...],
        "todos": [...]
    }
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.config import (
    check_input_file_changed,
    create_initial_session_state,
    get_or_create_session_config,
    save_session_state,
)
from lib.state import detect_state, generate_todos


def validate_input_file(file_path: str) -> tuple[bool, str]:
    """Validate that input file exists, is readable, has content."""
    path = Path(file_path)

    if not path.exists():
        return False, f"File not found: {file_path}"

    if not path.is_file():
        return False, f"Expected a file, got directory: {file_path}"

    if not path.suffix == ".md":
        return False, f"Expected markdown file (.md), got: {path.suffix}"

    try:
        content = path.read_text()
        if not content.strip():
            return False, f"File is empty: {file_path}"
    except PermissionError:
        return False, f"Cannot read file (permission denied): {file_path}"
    # Let other exceptions propagate for debugging (per CLAUDE.md)

    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup /deep-project session")
    parser.add_argument("--file", required=True, help="Path to requirements .md file")
    parser.add_argument("--plugin-root", required=True, help="Path to plugin root")
    args = parser.parse_args()

    # Validate input file
    valid, error = validate_input_file(args.file)
    if not valid:
        print(json.dumps({
            "success": False,
            "error": error
        }, indent=2))
        return 1

    # Determine planning directory (parent of input file)
    input_path = Path(args.file).resolve()
    planning_dir = input_path.parent

    # Get or create session config
    config, was_created = get_or_create_session_config(
        planning_dir=str(planning_dir),
        plugin_root=args.plugin_root,
        initial_file=str(input_path)
    )

    # Create initial session state for new sessions
    if was_created:
        initial_state = create_initial_session_state(str(input_path))
        save_session_state(planning_dir, initial_state)

    # Check if input file changed since session start
    warnings: list[str] = []
    file_changed = check_input_file_changed(planning_dir, input_path)
    if file_changed:
        warnings.append(
            f"Input file has changed since session started: {input_path}"
        )

    # Detect current state
    state = detect_state(planning_dir)

    # Determine resume step
    if was_created:
        mode = "new"
        resume_from_step = 1  # Start at interview
    else:
        mode = "resume"
        resume_from_step = state["resume_step"]

    # Generate TODO list
    todos = generate_todos(
        current_step=resume_from_step,
        plugin_root=args.plugin_root,
        planning_dir=str(planning_dir),
        initial_file=str(input_path)
    )

    result = {
        "success": True,
        "mode": mode,
        "planning_dir": str(planning_dir),
        "initial_file": str(input_path),
        "plugin_root": args.plugin_root,
        "resume_from_step": resume_from_step,
        "state": state,
        "existing_splits": state.get("splits", []),
        "warnings": warnings,
        "message": f"{'Starting new' if mode == 'new' else 'Resuming'} session in: {planning_dir}",
        "todos": todos
    }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
