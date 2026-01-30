"""Tests for tasks.py module."""

from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.task_storage import TaskStatus, TaskToWrite
from lib.tasks import (
    CONTEXT_TASK_IDS,
    TASK_DEFINITIONS,
    TASK_DEPENDENCIES,
    TASK_IDS,
    TASK_ID_TO_STEP,
    build_dependency_graph,
    build_semantic_to_position_map,
    generate_expected_tasks,
)


class TestTaskDefinitions:
    """Tests for task definition constants."""

    def test_all_task_ids_have_definitions(self):
        """Every task ID should have a corresponding definition."""
        for step, task_id in TASK_IDS.items():
            assert task_id in TASK_DEFINITIONS, f"Missing definition for {task_id}"

    def test_all_definitions_have_required_fields(self):
        """Every definition should have subject, description, and active_form."""
        for task_id, definition in TASK_DEFINITIONS.items():
            assert definition.subject, f"{task_id} missing subject"
            assert definition.description, f"{task_id} missing description"
            assert definition.active_form, f"{task_id} missing active_form"

    def test_task_id_to_step_reverse_mapping(self):
        """TASK_ID_TO_STEP should be reverse of TASK_IDS."""
        for step, task_id in TASK_IDS.items():
            assert TASK_ID_TO_STEP[task_id] == step

    def test_dependency_graph_has_valid_references(self):
        """All dependencies should reference valid task IDs."""
        valid_ids = set(TASK_IDS.values())
        for task_id, deps in TASK_DEPENDENCIES.items():
            assert task_id in valid_ids, f"Unknown task ID in dependencies: {task_id}"
            for dep in deps:
                assert dep in valid_ids, f"Unknown dependency {dep} for {task_id}"


class TestBuildSemanticToPositionMap:
    """Tests for build_semantic_to_position_map function."""

    def test_returns_all_task_ids(self):
        """Should include all workflow task IDs."""
        mapping = build_semantic_to_position_map()

        for task_id in TASK_IDS.values():
            assert task_id in mapping

    def test_includes_context_tasks(self):
        """Should include context task IDs."""
        mapping = build_semantic_to_position_map()

        for ctx_id in CONTEXT_TASK_IDS:
            assert ctx_id in mapping

    def test_positions_are_sequential(self):
        """Positions should be sequential starting from 1."""
        mapping = build_semantic_to_position_map()

        positions = sorted(mapping.values())
        expected = list(range(1, len(positions) + 1))
        assert positions == expected

    def test_custom_start_position(self):
        """Should support custom start position."""
        mapping = build_semantic_to_position_map(start_position=10)

        min_pos = min(mapping.values())
        assert min_pos == 10


class TestBuildDependencyGraph:
    """Tests for build_dependency_graph function."""

    def test_empty_dependencies(self):
        """Should handle empty dependency dict."""
        tasks = [
            TaskToWrite(position=1, subject="Task 1", status=TaskStatus.PENDING),
            TaskToWrite(position=2, subject="Task 2", status=TaskStatus.PENDING),
        ]
        semantic_to_position = {"task-1": 1, "task-2": 2}

        graph = build_dependency_graph(tasks, {}, semantic_to_position)

        assert graph[1] == ([], [])
        assert graph[2] == ([], [])

    def test_blocked_by_converted_to_positions(self):
        """blockedBy semantic IDs should be converted to position strings."""
        tasks = [
            TaskToWrite(position=1, subject="Task 1", status=TaskStatus.PENDING),
            TaskToWrite(position=2, subject="Task 2", status=TaskStatus.PENDING),
        ]
        semantic_to_position = {"task-1": 1, "task-2": 2}
        semantic_deps = {"task-2": ["task-1"]}

        graph = build_dependency_graph(tasks, semantic_deps, semantic_to_position)

        blocks_2, blocked_by_2 = graph[2]
        assert blocked_by_2 == ["1"]

    def test_blocks_computed_from_blocked_by(self):
        """blocks should be computed as inverse of blockedBy."""
        tasks = [
            TaskToWrite(position=1, subject="Task 1", status=TaskStatus.PENDING),
            TaskToWrite(position=2, subject="Task 2", status=TaskStatus.PENDING),
        ]
        semantic_to_position = {"task-1": 1, "task-2": 2}
        semantic_deps = {"task-2": ["task-1"]}

        graph = build_dependency_graph(tasks, semantic_deps, semantic_to_position)

        blocks_1, blocked_by_1 = graph[1]
        assert blocks_1 == ["2"]

    def test_unknown_semantic_ids_ignored(self):
        """Unknown semantic IDs in dependencies should be ignored."""
        tasks = [
            TaskToWrite(position=1, subject="Task 1", status=TaskStatus.PENDING),
        ]
        semantic_to_position = {"task-1": 1}
        semantic_deps = {"task-1": ["unknown-task"]}

        graph = build_dependency_graph(tasks, semantic_deps, semantic_to_position)

        # Should not crash, and task-1 should have empty blockedBy
        blocks_1, blocked_by_1 = graph[1]
        assert blocked_by_1 == []


class TestGenerateExpectedTasks:
    """Tests for generate_expected_tasks function."""

    def test_generates_workflow_tasks(self):
        """Should generate all workflow tasks."""
        tasks = generate_expected_tasks(
            current_step=1,
            plugin_root="/path/to/plugin",
            planning_dir="/path/to/planning",
            initial_file="/path/to/file.md",
        )

        # Should have workflow tasks + context tasks
        workflow_count = len(TASK_IDS)
        context_count = len(CONTEXT_TASK_IDS)
        assert len(tasks) == workflow_count + context_count

    def test_marks_current_step_in_progress(self):
        """Current step should have IN_PROGRESS status."""
        tasks = generate_expected_tasks(
            current_step=1,
            plugin_root="/path/to/plugin",
            planning_dir="/path/to/planning",
            initial_file="/path/to/file.md",
        )

        # Step 1 is "conduct-interview" which should be position 2 (after validate-setup at 1)
        # Find the task at position 2
        task_at_step_1 = next(t for t in tasks if t.position == 2)
        assert task_at_step_1.status == TaskStatus.IN_PROGRESS

    def test_marks_past_steps_completed(self):
        """Steps before current should have COMPLETED status."""
        tasks = generate_expected_tasks(
            current_step=3,
            plugin_root="/path/to/plugin",
            planning_dir="/path/to/planning",
            initial_file="/path/to/file.md",
        )

        # Steps 0, 1, 2 should be completed (positions 1, 2, 3)
        for pos in [1, 2, 3]:
            task = next(t for t in tasks if t.position == pos)
            assert task.status == TaskStatus.COMPLETED

    def test_marks_future_steps_pending(self):
        """Steps after current should have PENDING status."""
        tasks = generate_expected_tasks(
            current_step=1,
            plugin_root="/path/to/plugin",
            planning_dir="/path/to/planning",
            initial_file="/path/to/file.md",
        )

        # Steps after 1 should be pending
        for task in tasks:
            # Skip context tasks
            if "=" in task.subject:
                continue
            # Position 1 is step 0 (completed), position 2 is step 1 (in_progress)
            if task.position > 2:
                assert task.status == TaskStatus.PENDING

    def test_context_tasks_have_values_in_subject(self):
        """Context tasks should have values in subject for visibility."""
        tasks = generate_expected_tasks(
            current_step=1,
            plugin_root="/path/to/my-plugin",
            planning_dir="/path/to/my-planning",
            initial_file="/path/to/my-file.md",
        )

        # Find context tasks (they have = in subject)
        context_tasks = [t for t in tasks if "=" in t.subject]

        assert len(context_tasks) == 3

        subjects = [t.subject for t in context_tasks]
        assert "plugin_root=/path/to/my-plugin" in subjects
        assert "planning_dir=/path/to/my-planning" in subjects
        assert "initial_file=/path/to/my-file.md" in subjects

    def test_context_tasks_blocked_by_final_task(self):
        """Context tasks should be blocked by output-summary."""
        tasks = generate_expected_tasks(
            current_step=1,
            plugin_root="/path/to/plugin",
            planning_dir="/path/to/planning",
            initial_file="/path/to/file.md",
        )

        # Find context tasks
        context_tasks = [t for t in tasks if "=" in t.subject]

        # Find output-summary position
        mapping = build_semantic_to_position_map()
        output_summary_pos = str(mapping["output-summary"])

        for ctx_task in context_tasks:
            assert output_summary_pos in ctx_task.blocked_by
