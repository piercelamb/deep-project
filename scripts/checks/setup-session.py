#!/usr/bin/env python3
"""
Setup and manage /deep-project session state.

Usage:
    uv run setup-session.py --file <path_to_spec.md> --plugin-root <path> [--session-id <id>] [--force]

Output (JSON):
    {
        "success": true/false,
        "error": "error message if failed",
        "mode": "new" | "resume" | "conflict" | "no_task_list",
        "planning_dir": "/path/to/planning",
        "initial_file": "/path/to/spec.md",
        "plugin_root": "/path/to/plugin",
        "resume_from_step": <step_number>,
        "state": { ... },
        "split_directories": ["/path/to/planning/01-name", ...],
        "splits_needing_specs": ["02-name", ...],
        "warnings": [...],
        "tasks_written": <count>,
        "task_list_id": "<session_id>",
        "session_id_source": "context" | "user_env" | "session" | "none",
        "session_id_matched": true | false | null
    }
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.config import (
    check_input_file_changed,
    create_initial_session_state,
    load_session_state,
    save_session_state,
    session_state_exists,
)
from lib.state import detect_state
from lib.task_reconciliation import TaskListContext, TaskListSource
from lib.task_storage import get_tasks_dir, write_tasks
from lib.tasks import (
    TASK_DEPENDENCIES,
    build_dependency_graph,
    build_semantic_to_position_map,
    generate_expected_tasks,
)


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


@dataclass(frozen=True, slots=True, kw_only=True)
class ConflictInfo:
    """Information about conflicting existing tasks."""

    task_list_id: str
    existing_task_count: int
    sample_subjects: list[str]


def check_for_conflict(
    task_list_id: str,
    is_user_specified: bool,
) -> ConflictInfo | None:
    """Check for conflicting existing tasks.

    Only conflicts when user explicitly set CLAUDE_CODE_TASK_LIST_ID.
    Session-based task lists (DEEP_SESSION_ID) = resume scenario, no conflict.

    Args:
        task_list_id: The task list ID to check
        is_user_specified: True if from CLAUDE_CODE_TASK_LIST_ID

    Returns:
        ConflictInfo if conflict exists, None otherwise
    """
    if not is_user_specified:
        return None  # Session-based = no conflict, just resume

    tasks_dir = get_tasks_dir(task_list_id)
    if not tasks_dir.exists():
        return None

    task_files = list(tasks_dir.glob("*.json"))
    if not task_files:
        return None

    # Has existing tasks - collect sample subjects
    sample_subjects = []
    for task_file in sorted(task_files)[:3]:
        try:
            data = json.loads(task_file.read_text())
            subject = data.get("subject", "")
            if subject and subject != "[obsolete]":
                sample_subjects.append(subject)
        except (json.JSONDecodeError, OSError):
            continue

    return ConflictInfo(
        task_list_id=task_list_id,
        existing_task_count=len(task_files),
        sample_subjects=sample_subjects,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup /deep-project session")
    parser.add_argument("--file", required=True, help="Path to requirements .md file")
    parser.add_argument("--plugin-root", required=True, help="Path to plugin root")
    parser.add_argument(
        "--session-id",
        help="Session ID from hook context (takes precedence over env vars)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing tasks in user-specified task list",
    )
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

    # Check if session state already exists
    is_new_session = not session_state_exists(planning_dir)

    # Create initial session state for new sessions
    if is_new_session:
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
    if is_new_session:
        mode = "new"
        resume_from_step = 1  # Start at interview
    else:
        mode = "resume"
        resume_from_step = state["resume_step"]

    # Get task list context from args and environment
    task_context = TaskListContext.from_args_and_env(context_session_id=args.session_id)

    # Check for conflict (user-specified task list with existing tasks)
    if task_context.is_user_specified and not args.force:
        conflict = check_for_conflict(
            task_context.task_list_id or "",
            task_context.is_user_specified,
        )
        if conflict:
            print(
                json.dumps(
                    {
                        "success": False,
                        "mode": "conflict",
                        "error": "Existing tasks found in user-specified task list",
                        "task_list_id": conflict.task_list_id,
                        "existing_task_count": conflict.existing_task_count,
                        "sample_subjects": conflict.sample_subjects,
                        "hint": "Re-run with --force to overwrite existing tasks",
                    },
                    indent=2,
                )
            )
            return 1

    # Check if we have a task list ID
    if not task_context.task_list_id:
        print(
            json.dumps(
                {
                    "success": False,
                    "mode": "no_task_list",
                    "error": "No session ID available. SessionStart hook may not have run.",
                    "hint": "Restart the Claude Code session to trigger the hook.",
                },
                indent=2,
            )
        )
        return 1

    # Generate expected tasks based on workflow state
    tasks_to_write = generate_expected_tasks(
        current_step=resume_from_step,
        plugin_root=args.plugin_root,
        planning_dir=str(planning_dir),
        initial_file=str(input_path),
    )

    # Build dependency graph
    semantic_to_position = build_semantic_to_position_map()
    dependency_graph = build_dependency_graph(
        tasks_to_write,
        TASK_DEPENDENCIES,
        semantic_to_position,
    )

    # Write tasks directly to disk
    write_result = write_tasks(
        task_context.task_list_id,
        tasks_to_write,
        dependency_graph=dependency_graph,
    )

    # Compute split directories (full paths) and which need specs
    splits = state.get("splits", [])
    splits_with_specs = state.get("splits_with_specs", [])
    split_directories = [str(planning_dir / s) for s in splits]
    splits_needing_specs = [s for s in splits if s not in splits_with_specs]

    result = {
        "success": True,
        "mode": mode,
        "planning_dir": str(planning_dir),
        "initial_file": str(input_path),
        "plugin_root": args.plugin_root,
        "resume_from_step": resume_from_step,
        "state": state,
        "split_directories": split_directories,
        "splits_needing_specs": splits_needing_specs,
        "warnings": warnings,
        "message": f"{'Starting new' if mode == 'new' else 'Resuming'} session in: {planning_dir}",
        # New task system fields
        "tasks_written": write_result.tasks_written,
        "task_list_id": task_context.task_list_id,
        "session_id_source": str(task_context.source),
        "session_id_matched": task_context.session_id_matched,
    }

    # Add error if task write failed
    if not write_result.success:
        result["task_write_error"] = write_result.error

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
