"""Direct task file operations for Claude Code task system.

Writes tasks directly to ~/.claude/tasks/<task_list_id>/ instead of
having Claude execute TaskCreate/TaskUpdate operations.

This provides:
- Reliability: Script controls exact task state (no Claude hallucination risk)
- Speed: Single batch write vs sequential tool calls
- Determinism: Tasks are written atomically before Claude sees them
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self


class TaskStatus(StrEnum):
    """Task status values for Claude Code task system."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskToWrite:
    """A task to write to disk.

    Attributes:
        position: Numeric position (1-based), used as filename and id
        subject: Task title shown in task list
        status: Task status (pending, in_progress, completed)
        description: Detailed description of the task
        active_form: Present tense form shown when task is in_progress
        blocks: Task IDs that wait for this task to complete
        blocked_by: Task IDs this task waits for
    """

    position: int
    subject: str
    status: TaskStatus
    description: str = ""
    active_form: str = ""
    blocks: tuple[str, ...] = ()
    blocked_by: tuple[str, ...] = ()

    def to_file_dict(self) -> dict[str, str | list[str]]:
        """Convert to Claude Code task file format."""
        return {
            "id": str(self.position),
            "subject": self.subject,
            "description": self.description,
            "activeForm": self.active_form,
            "status": str(self.status),
            "blocks": list(self.blocks),
            "blockedBy": list(self.blocked_by),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskWriteResult:
    """Result of writing tasks to disk."""

    success: bool
    task_list_id: str
    tasks_written: int
    tasks_dir: Path
    error: str | None = None

    @classmethod
    def ok(cls, task_list_id: str, tasks_written: int, tasks_dir: Path) -> Self:
        """Create a successful result."""
        return cls(
            success=True,
            task_list_id=task_list_id,
            tasks_written=tasks_written,
            tasks_dir=tasks_dir,
        )

    @classmethod
    def err(cls, task_list_id: str, error: str) -> Self:
        """Create an error result."""
        return cls(
            success=False,
            task_list_id=task_list_id,
            tasks_written=0,
            tasks_dir=Path(),
            error=error,
        )


def get_tasks_dir(task_list_id: str) -> Path:
    """Get the tasks directory for a task list ID.

    Args:
        task_list_id: The task list ID (typically session ID)

    Returns:
        Path to ~/.claude/tasks/{task_list_id}/
    """
    return Path.home() / ".claude" / "tasks" / task_list_id


def _mark_extra_obsolete(tasks_dir: Path, max_written_position: int) -> None:
    """Mark existing task files beyond max_written_position as obsolete.

    When the task list shrinks (fewer tasks than before), we mark extra
    task files as obsolete rather than deleting them. This preserves
    any history while keeping them out of the active task list.

    Args:
        tasks_dir: Directory containing task files
        max_written_position: Highest position written in current batch
    """
    for task_file in tasks_dir.glob("*.json"):
        try:
            position = int(task_file.stem)
            if position > max_written_position:
                data = json.loads(task_file.read_text())
                if (
                    data.get("subject") == "[obsolete]"
                    and data.get("status") == "completed"
                ):
                    continue  # Already obsolete
                # Mark as obsolete (preserve blocks/blockedBy structure)
                data["subject"] = "[obsolete]"
                data["status"] = "completed"
                data.setdefault("blocks", [])
                data.setdefault("blockedBy", [])
                task_file.write_text(json.dumps(data, indent=2))
        except (ValueError, json.JSONDecodeError):
            continue


def write_tasks(
    task_list_id: str,
    tasks: list[TaskToWrite],
    dependency_graph: dict[int, tuple[list[str], list[str]]] | None = None,
    *,
    mark_extra_obsolete: bool = True,
) -> TaskWriteResult:
    """Write tasks directly to Claude Code task storage.

    Args:
        task_list_id: The task list ID (typically session ID)
        tasks: List of tasks to write
        dependency_graph: Optional dict of position -> (blocks, blockedBy)
            If provided, overrides the blocks/blockedBy from TaskToWrite
        mark_extra_obsolete: If True, mark existing task files beyond
            the highest written position as obsolete

    Returns:
        TaskWriteResult indicating success/failure
    """
    if not task_list_id:
        return TaskWriteResult.err("", "No task_list_id provided")

    tasks_dir = get_tasks_dir(task_list_id)

    try:
        tasks_dir.mkdir(parents=True, exist_ok=True)
        max_written_position = 0

        for task in tasks:
            task_data = task.to_file_dict()

            # Apply dependency graph if provided
            if dependency_graph and task.position in dependency_graph:
                blocks, blocked_by = dependency_graph[task.position]
                task_data["blocks"] = blocks
                task_data["blockedBy"] = blocked_by

            task_file = tasks_dir / f"{task.position}.json"
            task_file.write_text(json.dumps(task_data, indent=2))
            max_written_position = max(max_written_position, task.position)

        # Mark extra existing tasks as obsolete
        if mark_extra_obsolete:
            _mark_extra_obsolete(tasks_dir, max_written_position)

        return TaskWriteResult.ok(task_list_id, len(tasks), tasks_dir)

    except PermissionError as e:
        return TaskWriteResult.err(task_list_id, f"Permission denied: {e}")
    except OSError as e:
        return TaskWriteResult.err(task_list_id, f"File system error: {e}")
