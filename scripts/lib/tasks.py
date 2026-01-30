"""Task definitions and dependency graph for deep-project workflow.

Centralized definitions for all workflow tasks, with semantic IDs
for clearer dependency specification and mapping to positions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from .task_storage import TaskStatus, TaskToWrite


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskDefinition:
    """Definition for a workflow task.

    Attributes:
        subject: Task title shown in task list
        description: Detailed description of the task
        active_form: Present tense form shown when task is in_progress
    """

    subject: str
    description: str
    active_form: str


# Task IDs mapped to workflow step numbers
# Step 0 is validate/setup, steps 1-7 are main workflow phases
TASK_IDS: dict[int, str] = {
    0: "validate-setup",
    1: "conduct-interview",
    2: "analyze-splits",
    3: "write-manifest",
    4: "confirm-splits",
    5: "create-directories",
    6: "generate-specs",
    7: "output-summary",
}

# Reverse mapping: semantic ID to step number
TASK_ID_TO_STEP: dict[str, int] = {v: k for k, v in TASK_IDS.items()}

# Dependency graph - each task lists what it's blocked by (semantic IDs)
# Note: Steps 3 and 5 are inline (not resume points) but still have dependencies
TASK_DEPENDENCIES: dict[str, list[str]] = {
    "validate-setup": [],  # Can start immediately
    "conduct-interview": ["validate-setup"],
    "analyze-splits": ["conduct-interview"],
    "write-manifest": ["analyze-splits"],  # Inline after analysis
    "confirm-splits": ["write-manifest"],
    "create-directories": ["confirm-splits"],  # Inline after confirmation
    "generate-specs": ["create-directories"],
    "output-summary": ["generate-specs"],
}

# Task definitions with descriptions
TASK_DEFINITIONS: dict[str, TaskDefinition] = {
    "validate-setup": TaskDefinition(
        subject="Validate input and setup session",
        description="Validate the input file exists and is readable. Initialize session state.",
        active_form="Setting up session",
    ),
    "conduct-interview": TaskDefinition(
        subject="Conduct interview",
        description="Interview the user to understand project requirements and constraints.",
        active_form="Interviewing user",
    ),
    "analyze-splits": TaskDefinition(
        subject="Analyze splits",
        description="Analyze the requirements and propose how to split the project.",
        active_form="Analyzing splits",
    ),
    "write-manifest": TaskDefinition(
        subject="Discover dependencies and write manifest",
        description="Discover dependencies between splits and write project-manifest.md.",
        active_form="Writing manifest",
    ),
    "confirm-splits": TaskDefinition(
        subject="Confirm splits with user",
        description="Present the proposed splits to the user for confirmation or revision.",
        active_form="Confirming splits",
    ),
    "create-directories": TaskDefinition(
        subject="Create split directories",
        description="Create the NN-name/ directories for each confirmed split.",
        active_form="Creating directories",
    ),
    "generate-specs": TaskDefinition(
        subject="Generate spec files",
        description="Generate spec.md files for each split directory.",
        active_form="Generating specs",
    ),
    "output-summary": TaskDefinition(
        subject="Output summary",
        description="Output a summary of the completed workflow.",
        active_form="Outputting summary",
    ),
}

# Context task IDs (for session parameters)
CONTEXT_TASK_IDS = [
    "context-plugin-root",
    "context-planning-dir",
    "context-initial-file",
]


def build_semantic_to_position_map(start_position: int = 1) -> dict[str, int]:
    """Build mapping from semantic task IDs to position numbers.

    Args:
        start_position: Starting position number (default 1)

    Returns:
        Dict mapping semantic ID to position number
    """
    mapping = {}
    position = start_position

    # Workflow tasks first (in step order)
    for step in sorted(TASK_IDS.keys()):
        semantic_id = TASK_IDS[step]
        mapping[semantic_id] = position
        position += 1

    # Context tasks at the end
    for ctx_id in CONTEXT_TASK_IDS:
        mapping[ctx_id] = position
        position += 1

    return mapping


def build_dependency_graph(
    tasks: list[TaskToWrite],
    semantic_dependencies: dict[str, list[str]],
    semantic_to_position: dict[str, int],
) -> dict[int, tuple[list[str], list[str]]]:
    """Build blocks and blockedBy arrays for each task position.

    Args:
        tasks: List of tasks with positions
        semantic_dependencies: Dict of semantic_id -> list of blockedBy semantic_ids
        semantic_to_position: Dict of semantic_id -> position number

    Returns:
        Dict of position -> (blocks, blockedBy) as position string lists
    """
    blocks: dict[int, list[str]] = {t.position: [] for t in tasks}
    blocked_by: dict[int, list[str]] = {t.position: [] for t in tasks}

    # Build blockedBy from semantic dependencies
    for semantic_id, deps in semantic_dependencies.items():
        if semantic_id not in semantic_to_position:
            continue
        position = semantic_to_position[semantic_id]
        if position not in blocked_by:
            continue
        for dep_id in deps:
            if dep_id in semantic_to_position:
                dep_position = semantic_to_position[dep_id]
                blocked_by[position].append(str(dep_position))

    # Build blocks (inverse of blockedBy)
    for position, deps in blocked_by.items():
        for dep_pos_str in deps:
            dep_pos = int(dep_pos_str)
            if dep_pos in blocks:
                blocks[dep_pos].append(str(position))

    return {pos: (blocks[pos], blocked_by[pos]) for pos in blocks}


def generate_expected_tasks(
    current_step: int,
    plugin_root: str,
    planning_dir: str,
    initial_file: str,
) -> list[TaskToWrite]:
    """Generate expected tasks based on workflow state.

    Args:
        current_step: Current workflow step (0-7)
        plugin_root: Path to the plugin root directory
        planning_dir: Path to the planning directory
        initial_file: Path to the initial requirements file

    Returns:
        List of TaskToWrite objects ready for writing
    """
    semantic_to_position = build_semantic_to_position_map()
    tasks: list[TaskToWrite] = []

    # Generate workflow tasks
    for step in sorted(TASK_IDS.keys()):
        semantic_id = TASK_IDS[step]
        definition = TASK_DEFINITIONS[semantic_id]
        position = semantic_to_position[semantic_id]

        # Determine status based on current step
        if step < current_step:
            status = TaskStatus.COMPLETED
        elif step == current_step:
            status = TaskStatus.IN_PROGRESS
        else:
            status = TaskStatus.PENDING

        tasks.append(
            TaskToWrite(
                position=position,
                subject=definition.subject,
                status=status,
                description=definition.description,
                active_form=definition.active_form,
            )
        )

    # Generate context tasks (store values in subject for visibility)
    context_items = [
        ("context-plugin-root", f"plugin_root={plugin_root}"),
        ("context-planning-dir", f"planning_dir={planning_dir}"),
        ("context-initial-file", f"initial_file={initial_file}"),
    ]

    # Get the output-summary position for blocking context tasks
    output_summary_position = semantic_to_position.get("output-summary")

    for ctx_id, value in context_items:
        position = semantic_to_position[ctx_id]
        # Context tasks are blocked by final task so they stay pending until end
        blocked_by = (str(output_summary_position),) if output_summary_position else ()

        tasks.append(
            TaskToWrite(
                position=position,
                subject=value,  # Value in subject for visibility
                status=TaskStatus.PENDING,
                description="Session context item",
                active_form="Context",
                blocked_by=blocked_by,
            )
        )

    return tasks
