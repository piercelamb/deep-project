"""Tests for task_storage.py module."""

import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.task_storage import (
    TaskStatus,
    TaskToWrite,
    TaskWriteResult,
    get_tasks_dir,
    write_tasks,
)


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_pending_value(self):
        assert TaskStatus.PENDING == "pending"

    def test_in_progress_value(self):
        assert TaskStatus.IN_PROGRESS == "in_progress"

    def test_completed_value(self):
        assert TaskStatus.COMPLETED == "completed"


class TestTaskToWrite:
    """Tests for TaskToWrite dataclass."""

    def test_to_file_dict_minimal(self):
        task = TaskToWrite(
            position=1,
            subject="Test task",
            status=TaskStatus.PENDING,
        )
        result = task.to_file_dict()

        assert result["id"] == "1"
        assert result["subject"] == "Test task"
        assert result["status"] == "pending"
        assert result["description"] == ""
        assert result["activeForm"] == ""
        assert result["blocks"] == []
        assert result["blockedBy"] == []

    def test_to_file_dict_full(self):
        task = TaskToWrite(
            position=5,
            subject="Full task",
            status=TaskStatus.IN_PROGRESS,
            description="A detailed description",
            active_form="Running task",
            blocks=("6", "7"),
            blocked_by=("3", "4"),
        )
        result = task.to_file_dict()

        assert result["id"] == "5"
        assert result["subject"] == "Full task"
        assert result["status"] == "in_progress"
        assert result["description"] == "A detailed description"
        assert result["activeForm"] == "Running task"
        assert result["blocks"] == ["6", "7"]
        assert result["blockedBy"] == ["3", "4"]


class TestTaskWriteResult:
    """Tests for TaskWriteResult dataclass."""

    def test_ok_factory(self, tmp_path):
        result = TaskWriteResult.ok("session-123", 5, tmp_path)

        assert result.success is True
        assert result.task_list_id == "session-123"
        assert result.tasks_written == 5
        assert result.tasks_dir == tmp_path
        assert result.error is None

    def test_err_factory(self):
        result = TaskWriteResult.err("session-123", "Permission denied")

        assert result.success is False
        assert result.task_list_id == "session-123"
        assert result.tasks_written == 0
        assert result.tasks_dir == Path()
        assert result.error == "Permission denied"


class TestGetTasksDir:
    """Tests for get_tasks_dir function."""

    def test_returns_correct_path(self):
        result = get_tasks_dir("session-abc")
        expected = Path.home() / ".claude" / "tasks" / "session-abc"
        assert result == expected

    def test_different_session_ids(self):
        result1 = get_tasks_dir("session-1")
        result2 = get_tasks_dir("session-2")
        assert result1 != result2


class TestWriteTasks:
    """Tests for write_tasks function."""

    def test_writes_single_task(self, tmp_path, monkeypatch):
        """Should write a single task file."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        task = TaskToWrite(
            position=1,
            subject="Test task",
            status=TaskStatus.PENDING,
        )

        result = write_tasks("session-123", [task])

        assert result.success is True
        assert result.tasks_written == 1

        task_file = tmp_path / ".claude" / "tasks" / "session-123" / "1.json"
        assert task_file.exists()

        data = json.loads(task_file.read_text())
        assert data["id"] == "1"
        assert data["subject"] == "Test task"
        assert data["status"] == "pending"

    def test_writes_multiple_tasks(self, tmp_path, monkeypatch):
        """Should write multiple task files."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        tasks = [
            TaskToWrite(position=1, subject="Task 1", status=TaskStatus.COMPLETED),
            TaskToWrite(position=2, subject="Task 2", status=TaskStatus.IN_PROGRESS),
            TaskToWrite(position=3, subject="Task 3", status=TaskStatus.PENDING),
        ]

        result = write_tasks("session-123", tasks)

        assert result.success is True
        assert result.tasks_written == 3

        tasks_dir = tmp_path / ".claude" / "tasks" / "session-123"
        assert (tasks_dir / "1.json").exists()
        assert (tasks_dir / "2.json").exists()
        assert (tasks_dir / "3.json").exists()

    def test_overwrites_existing_task(self, tmp_path, monkeypatch):
        """Should overwrite existing task file."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        tasks_dir = tmp_path / ".claude" / "tasks" / "session-123"
        tasks_dir.mkdir(parents=True)

        # Create existing task
        (tasks_dir / "1.json").write_text(json.dumps({
            "id": "1",
            "subject": "Old task",
            "status": "completed",
        }))

        # Write new task
        task = TaskToWrite(position=1, subject="New task", status=TaskStatus.PENDING)
        result = write_tasks("session-123", [task])

        assert result.success is True

        data = json.loads((tasks_dir / "1.json").read_text())
        assert data["subject"] == "New task"
        assert data["status"] == "pending"

    def test_marks_extra_obsolete(self, tmp_path, monkeypatch):
        """Should mark extra existing tasks as obsolete."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        tasks_dir = tmp_path / ".claude" / "tasks" / "session-123"
        tasks_dir.mkdir(parents=True)

        # Create existing tasks
        for i in range(1, 6):
            (tasks_dir / f"{i}.json").write_text(json.dumps({
                "id": str(i),
                "subject": f"Task {i}",
                "status": "pending",
            }))

        # Write only 2 tasks
        tasks = [
            TaskToWrite(position=1, subject="Task 1", status=TaskStatus.COMPLETED),
            TaskToWrite(position=2, subject="Task 2", status=TaskStatus.IN_PROGRESS),
        ]
        write_tasks("session-123", tasks)

        # Tasks 3, 4, 5 should be marked obsolete
        for i in [3, 4, 5]:
            data = json.loads((tasks_dir / f"{i}.json").read_text())
            assert data["subject"] == "[obsolete]"
            assert data["status"] == "completed"

    def test_skips_already_obsolete(self, tmp_path, monkeypatch):
        """Should not re-mark tasks that are already obsolete."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        tasks_dir = tmp_path / ".claude" / "tasks" / "session-123"
        tasks_dir.mkdir(parents=True)

        # Create already obsolete task
        (tasks_dir / "3.json").write_text(json.dumps({
            "id": "3",
            "subject": "[obsolete]",
            "status": "completed",
            "blocks": [],
            "blockedBy": [],
        }))

        # Write task at position 1
        task = TaskToWrite(position=1, subject="Task 1", status=TaskStatus.PENDING)
        write_tasks("session-123", [task])

        # Task 3 should still be obsolete (unchanged)
        data = json.loads((tasks_dir / "3.json").read_text())
        assert data["subject"] == "[obsolete]"

    def test_creates_directory(self, tmp_path, monkeypatch):
        """Should create tasks directory if it doesn't exist."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        task = TaskToWrite(position=1, subject="Task 1", status=TaskStatus.PENDING)
        result = write_tasks("session-123", [task])

        assert result.success is True
        tasks_dir = tmp_path / ".claude" / "tasks" / "session-123"
        assert tasks_dir.exists()

    def test_returns_error_on_missing_task_list_id(self):
        """Should return error when task_list_id is empty."""
        task = TaskToWrite(position=1, subject="Task", status=TaskStatus.PENDING)
        result = write_tasks("", [task])

        assert result.success is False
        assert "No task_list_id" in result.error

    def test_includes_dependency_graph(self, tmp_path, monkeypatch):
        """Should apply dependency graph to tasks."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        tasks = [
            TaskToWrite(position=1, subject="Task 1", status=TaskStatus.COMPLETED),
            TaskToWrite(position=2, subject="Task 2", status=TaskStatus.PENDING),
        ]

        # Dependency graph: task 2 blocked by task 1
        dependency_graph = {
            1: (["2"], []),  # blocks task 2
            2: ([], ["1"]),  # blocked by task 1
        }

        write_tasks("session-123", tasks, dependency_graph=dependency_graph)

        tasks_dir = tmp_path / ".claude" / "tasks" / "session-123"

        data1 = json.loads((tasks_dir / "1.json").read_text())
        assert data1["blocks"] == ["2"]
        assert data1["blockedBy"] == []

        data2 = json.loads((tasks_dir / "2.json").read_text())
        assert data2["blocks"] == []
        assert data2["blockedBy"] == ["1"]
