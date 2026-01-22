"""State detection for /deep-project resume support."""

import re
from pathlib import Path
from typing import Any, TypedDict

from .config import load_session_state


class DetectStateResult(TypedDict):
    """Return type for detect_state() function."""

    interview_complete: bool
    splits_proposed: bool
    splits_confirmed: bool
    directories_created: bool
    manifest_created: bool
    splits: list[str]
    splits_with_specs: list[str]
    resume_step: int
    session_state: dict[str, Any] | None
    outcome: str | None


# Workflow steps mapping step number to step name.
# Step 0 is setup/validation, steps 1-6 are the main workflow phases.
STEPS = {
    0: "setup",
    1: "interview",
    2: "split_analysis",
    3: "dependency_discovery",
    4: "user_confirmation",
    5: "output_generation",
    6: "complete"
}

# Strict pattern for split directories: NN-kebab-case.
# Requires two-digit prefix (01-99), hyphen separator, and lowercase alphanumeric segments.
# Examples: "01-backend", "12-multi-word-name"
SPLIT_DIR_PATTERN = re.compile(r"^\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")


def is_valid_split_dir(name: str) -> bool:
    """Check if directory name matches split directory pattern."""
    return bool(SPLIT_DIR_PATTERN.match(name))


def get_split_index(name: str) -> int:
    """Extract numeric index from split directory name."""
    return int(name[:2])


def detect_state(planning_dir: Path | str) -> DetectStateResult:
    """Detect current workflow state.

    Uses deep_project_session.json as authoritative source when available,
    with filesystem scanning as validation/fallback.
    """
    planning_dir = Path(planning_dir)

    # Try to load authoritative session state first
    session_state = load_session_state(str(planning_dir))

    # Check for interview transcript (filesystem)
    interview_exists = (planning_dir / "deep_project_interview.md").exists()

    # Check for split directories with strict validation
    splits = sorted([
        d.name for d in planning_dir.iterdir()
        if d.is_dir() and is_valid_split_dir(d.name)
    ], key=get_split_index)

    # Check if splits have spec.md files
    splits_with_specs = [
        s for s in splits
        if (planning_dir / s / "spec.md").exists()
    ]

    # Check for manifest
    manifest_exists = (planning_dir / "project-manifest.md").exists()

    # Determine state from session.json (authoritative) or fallback to filesystem
    if session_state:
        # Use session.json as source of truth
        proposed_splits = session_state.get("proposed_splits", [])
        declared_split_count = len(proposed_splits)

        # Check completion: ALL declared splits must have specs + manifest
        all_specs_written = all(
            session_state.get("completion_status", {}).get(s["dir_name"], {}).get("spec_written", False)
            for s in proposed_splits
        ) if proposed_splits else False

        is_complete = (
            session_state.get("manifest_written", False) and
            all_specs_written and
            declared_split_count > 0
        )

        # Determine resume step from session state
        if is_complete:
            resume_step = 6
        elif session_state.get("splits_confirmed"):
            resume_step = 5  # Output generation
        elif session_state.get("interview_complete"):
            resume_step = 2  # Split analysis
        else:
            resume_step = 1  # Interview

        # Handle "not_splittable" outcome (single subdir created)
        if session_state.get("outcome") == "not_splittable":
            resume_step = 6  # Treat as complete (single subdir with spec created)
    else:
        # Fallback: infer from filesystem (less reliable)
        if manifest_exists and len(splits_with_specs) == len(splits) and splits:
            resume_step = 6  # Complete
        elif splits:
            resume_step = 5  # Output generation
        elif interview_exists:
            resume_step = 2  # Split analysis
        else:
            resume_step = 1  # Interview

    return {
        "interview_complete": session_state.get("interview_complete", interview_exists) if session_state else interview_exists,
        "splits_proposed": len(session_state.get("proposed_splits", [])) > 0 if session_state else len(splits) > 0,
        "splits_confirmed": session_state.get("splits_confirmed", False) if session_state else len(splits_with_specs) > 0,
        "directories_created": len(splits) > 0,
        "manifest_created": manifest_exists,
        "splits": splits,
        "splits_with_specs": splits_with_specs,
        "resume_step": resume_step,
        "session_state": session_state,
        "outcome": session_state.get("outcome") if session_state else None
    }


def generate_todos(
    current_step: int,
    plugin_root: str,
    planning_dir: str,
    initial_file: str
) -> list[dict[str, str]]:
    """Generate TODO list for workflow tracking."""

    # Context items (always completed)
    context_items = [
        {
            "content": f"plugin_root={plugin_root}",
            "status": "completed",
            "activeForm": "Context: plugin_root"
        },
        {
            "content": f"planning_dir={planning_dir}",
            "status": "completed",
            "activeForm": "Context: planning_dir"
        },
        {
            "content": f"initial_file={initial_file}",
            "status": "completed",
            "activeForm": "Context: initial_file"
        }
    ]

    # Workflow items
    workflow_items = [
        ("Validate input and setup session", "Setting up session", 0),
        ("Conduct interview", "Interviewing user", 1),
        ("Analyze and propose splits", "Analyzing splits", 2),
        ("Discover dependencies", "Discovering dependencies", 3),
        ("Confirm splits with user", "Confirming splits", 4),
        ("Generate output files", "Generating output", 5),
        ("Output summary", "Outputting summary", 6),
    ]

    todos = context_items.copy()

    for content, active_form, step in workflow_items:
        if step < current_step:
            status = "completed"
        elif step == current_step:
            status = "in_progress"
        else:
            status = "pending"

        todos.append({
            "content": content,
            "status": status,
            "activeForm": active_form
        })

    return todos
