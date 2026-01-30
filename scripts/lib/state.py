"""State detection for /deep-project resume support.

Design principle: Derive state from file existence, not JSON fields.

Checkpoints (files):
- deep_project_interview.md exists → interview complete (resume at step 2)
- project-manifest.md exists → proposal complete (resume at step 4)
- NN-name/ directories exist → directories created (resume at step 6)
- NN-name/spec.md exists for all splits → specs complete (resume at step 7)

Session JSON stores only:
- input_file_hash (detect changes)
- session_created_at (metadata)
"""

import re
from pathlib import Path
from typing import TypedDict

from .config import SessionFilename


class DetectStateResult(TypedDict):
    """Return type for detect_state() function."""

    interview_complete: bool
    manifest_created: bool
    directories_created: bool
    splits: list[str]
    splits_with_specs: list[str]
    resume_step: int


# Workflow steps mapping step number to step name.
# Step 0 is setup/validation, steps 1-7 are the main workflow phases.
STEPS = {
    0: "setup",
    1: "interview",
    2: "split_analysis",
    3: "dependency_discovery",
    4: "user_confirmation",
    5: "directory_creation",
    6: "spec_generation",
    7: "complete"
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
    """Detect current workflow state from file existence.

    Derives state from filesystem checkpoints:
    - Interview complete: deep_project_interview.md exists
    - Manifest created: project-manifest.md exists (Claude's proposal)
    - Directories created: NN-name/ directories exist (user confirmed)
    - Specs written: spec.md in each directory
    """
    planning_dir = Path(planning_dir)

    # Checkpoint 1: Interview complete (file exists)
    interview_complete = (planning_dir / SessionFilename.INTERVIEW).exists()

    # Checkpoint 2: Manifest created (Claude's proposal)
    manifest_created = (planning_dir / SessionFilename.MANIFEST).exists()

    # Checkpoint 3: Split directories exist (user confirmed, output generation started)
    splits = sorted([
        d.name for d in planning_dir.iterdir()
        if d.is_dir() and is_valid_split_dir(d.name)
    ], key=get_split_index)

    # Checkpoint 4: Specs written (spec.md in each directory)
    splits_with_specs = [
        s for s in splits
        if (planning_dir / s / "spec.md").exists()
    ]

    # Derive higher-level state
    directories_created = len(splits) > 0

    # Determine resume step from checkpoints
    # Note: Step 3 and 5 are never resume points - they happen inline after steps 2 and 4
    if directories_created and splits_with_specs and len(splits_with_specs) == len(splits):
        resume_step = 7  # Complete (all specs written)
    elif directories_created:
        # Directories exist, need to write specs
        resume_step = 6  # Spec generation
    elif manifest_created:
        # Manifest exists but no directories, need user confirmation then directory creation
        resume_step = 4  # User confirmation
    elif interview_complete:
        # Interview done, need to analyze and propose splits
        resume_step = 2  # Split analysis + dependency discovery
    else:
        # Start from interview
        resume_step = 1  # Interview

    return {
        "interview_complete": interview_complete,
        "manifest_created": manifest_created,
        "directories_created": directories_created,
        "splits": splits,
        "splits_with_specs": splits_with_specs,
        "resume_step": resume_step,
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
    # Note: Steps 3 and 5 are never resume points - they happen inline
    # Step 3 ends with writing project-manifest.md (checkpoint for step 4)
    # Step 5 ends with directories created (checkpoint for step 6)
    workflow_items = [
        ("Validate input and setup session", "Setting up session", 0),
        ("Conduct interview", "Interviewing user", 1),
        ("Analyze splits", "Analyzing splits", 2),
        ("Discover dependencies and write manifest", "Writing manifest", 3),
        ("Confirm splits with user", "Confirming splits", 4),
        ("Create split directories", "Creating directories", 5),
        ("Generate spec files", "Generating specs", 6),
        ("Output summary", "Outputting summary", 7),
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
