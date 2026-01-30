"""Integration tests for the complete task management workflow.

Tests the full flow from setup-session.py writing tasks to disk
through to task file verification.
"""

import json
import subprocess
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.config import compute_file_hash, save_session_state
from lib.task_storage import get_tasks_dir


def run_setup_session(
    input_file: Path,
    plugin_root: Path,
    session_id: str,
    force: bool = False,
    home_dir: Path | None = None,
) -> dict:
    """Helper to run setup-session.py and return parsed output."""
    cmd = [
        "uv", "run", "scripts/checks/setup-session.py",
        "--file", str(input_file),
        "--plugin-root", str(plugin_root),
        "--session-id", session_id,
    ]

    if force:
        cmd.append("--force")

    env = None
    if home_dir:
        import os
        env = os.environ.copy()
        env["HOME"] = str(home_dir)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
        env=env,
    )
    return json.loads(result.stdout)


@pytest.fixture
def task_integration_env(tmp_path):
    """Create a complete test environment for task integration tests."""
    # Create mock home directory
    mock_home = tmp_path / "mock_home"
    mock_home.mkdir()

    # Create planning directory
    planning_dir = tmp_path / "planning"
    planning_dir.mkdir()

    # Create sample input file
    input_file = planning_dir / "requirements.md"
    input_file.write_text("# Sample Project\n\nBuild something cool.")

    # Create mock plugin root
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()

    return {
        "mock_home": mock_home,
        "planning_dir": planning_dir,
        "input_file": input_file,
        "plugin_root": plugin_root,
        "session_id": "integration-test-session",
    }


@pytest.mark.integration
class TestTaskWriteWorkflow:
    """Tests for the complete task write workflow."""

    def test_fresh_session_writes_tasks(self, task_integration_env, monkeypatch):
        """Fresh session should write tasks to correct directory."""
        env = task_integration_env
        monkeypatch.setattr(Path, "home", lambda: env["mock_home"])

        output = run_setup_session(
            env["input_file"],
            env["plugin_root"],
            env["session_id"],
            home_dir=env["mock_home"],
        )

        assert output["success"] is True
        assert output["tasks_written"] > 0
        assert output["task_list_id"] == env["session_id"]
        assert output["session_id_source"] == "context"

        # Verify tasks directory was created
        tasks_dir = env["mock_home"] / ".claude" / "tasks" / env["session_id"]
        assert tasks_dir.exists()

        # Verify task files exist
        task_files = list(tasks_dir.glob("*.json"))
        assert len(task_files) == output["tasks_written"]

    def test_task_json_structure(self, task_integration_env, monkeypatch):
        """Task files should have correct JSON structure."""
        env = task_integration_env
        monkeypatch.setattr(Path, "home", lambda: env["mock_home"])

        run_setup_session(
            env["input_file"],
            env["plugin_root"],
            env["session_id"],
            home_dir=env["mock_home"],
        )

        tasks_dir = env["mock_home"] / ".claude" / "tasks" / env["session_id"]
        task_file = tasks_dir / "1.json"

        assert task_file.exists()
        data = json.loads(task_file.read_text())

        # Verify required fields
        assert "id" in data
        assert "subject" in data
        assert "description" in data
        assert "activeForm" in data
        assert "status" in data
        assert "blocks" in data
        assert "blockedBy" in data

        # Verify types
        assert isinstance(data["id"], str)
        assert isinstance(data["blocks"], list)
        assert isinstance(data["blockedBy"], list)

    def test_resume_session_correct_status(self, task_integration_env, monkeypatch):
        """Resuming session should have correct task statuses."""
        env = task_integration_env
        monkeypatch.setattr(Path, "home", lambda: env["mock_home"])

        # First create session state and interview file to simulate resume
        save_session_state(str(env["planning_dir"]), {
            "input_file_hash": compute_file_hash(str(env["input_file"])),
            "session_created_at": "2024-01-19T10:30:00Z",
        })
        (env["planning_dir"] / "deep_project_interview.md").write_text("# Interview")

        output = run_setup_session(
            env["input_file"],
            env["plugin_root"],
            env["session_id"],
            home_dir=env["mock_home"],
        )

        assert output["success"] is True
        assert output["mode"] == "resume"
        assert output["resume_from_step"] == 2  # After interview

        # Read task files and verify status
        tasks_dir = env["mock_home"] / ".claude" / "tasks" / env["session_id"]

        # Step 0 (validate-setup) at position 1 should be completed
        task1 = json.loads((tasks_dir / "1.json").read_text())
        assert task1["status"] == "completed"

        # Step 1 (conduct-interview) at position 2 should be completed (interview file exists)
        task2 = json.loads((tasks_dir / "2.json").read_text())
        assert task2["status"] == "completed"

        # Step 2 (analyze-splits) at position 3 should be in_progress
        task3 = json.loads((tasks_dir / "3.json").read_text())
        assert task3["status"] == "in_progress"

    def test_dependencies_correctly_set(self, task_integration_env, monkeypatch):
        """Task dependencies should be correctly set."""
        env = task_integration_env
        monkeypatch.setattr(Path, "home", lambda: env["mock_home"])

        run_setup_session(
            env["input_file"],
            env["plugin_root"],
            env["session_id"],
            home_dir=env["mock_home"],
        )

        tasks_dir = env["mock_home"] / ".claude" / "tasks" / env["session_id"]

        # Task 2 (conduct-interview) should be blocked by task 1 (validate-setup)
        task2 = json.loads((tasks_dir / "2.json").read_text())
        assert "1" in task2["blockedBy"]

        # Task 1 should block task 2
        task1 = json.loads((tasks_dir / "1.json").read_text())
        assert "2" in task1["blocks"]

    def test_context_tasks_have_values(self, task_integration_env, monkeypatch):
        """Context tasks should have values in subject."""
        env = task_integration_env
        monkeypatch.setattr(Path, "home", lambda: env["mock_home"])

        run_setup_session(
            env["input_file"],
            env["plugin_root"],
            env["session_id"],
            home_dir=env["mock_home"],
        )

        tasks_dir = env["mock_home"] / ".claude" / "tasks" / env["session_id"]

        # Find context tasks (higher positions, have = in subject)
        task_files = sorted(tasks_dir.glob("*.json"), key=lambda f: int(f.stem))

        context_subjects = []
        for task_file in task_files:
            data = json.loads(task_file.read_text())
            if "=" in data["subject"]:
                context_subjects.append(data["subject"])

        # Should have plugin_root, planning_dir, initial_file context tasks
        assert len(context_subjects) == 3
        assert any("plugin_root=" in s for s in context_subjects)
        assert any("planning_dir=" in s for s in context_subjects)
        assert any("initial_file=" in s for s in context_subjects)

    def test_new_session_id_after_clear(self, task_integration_env, monkeypatch):
        """New session ID should write to new directory (simulating /clear reset)."""
        env = task_integration_env
        monkeypatch.setattr(Path, "home", lambda: env["mock_home"])

        # First session
        run_setup_session(
            env["input_file"],
            env["plugin_root"],
            "old-session",
            home_dir=env["mock_home"],
        )

        # Second session (new session ID, simulating /clear reset)
        output = run_setup_session(
            env["input_file"],
            env["plugin_root"],
            "new-session",
            home_dir=env["mock_home"],
        )

        assert output["success"] is True
        assert output["task_list_id"] == "new-session"

        # Both directories should exist
        old_tasks = env["mock_home"] / ".claude" / "tasks" / "old-session"
        new_tasks = env["mock_home"] / ".claude" / "tasks" / "new-session"
        assert old_tasks.exists()
        assert new_tasks.exists()


@pytest.mark.integration
class TestConflictHandling:
    """Tests for conflict detection with user-specified task lists."""

    def test_no_conflict_with_session_id(self, task_integration_env, monkeypatch):
        """Session-based task lists should not trigger conflict."""
        env = task_integration_env
        monkeypatch.setattr(Path, "home", lambda: env["mock_home"])

        # First run
        run_setup_session(
            env["input_file"],
            env["plugin_root"],
            env["session_id"],
            home_dir=env["mock_home"],
        )

        # Second run with same session ID (should not conflict)
        output = run_setup_session(
            env["input_file"],
            env["plugin_root"],
            env["session_id"],
            home_dir=env["mock_home"],
        )

        # Should succeed, not conflict mode
        assert output["success"] is True
        assert output.get("mode") != "conflict"

    def test_conflict_with_user_env_detected(self, task_integration_env, monkeypatch):
        """User-specified task list with existing tasks should trigger conflict."""
        import os

        env = task_integration_env
        monkeypatch.setattr(Path, "home", lambda: env["mock_home"])

        # Create existing tasks in user-specified task list
        user_task_list = "my-custom-tasks"
        tasks_dir = env["mock_home"] / ".claude" / "tasks" / user_task_list
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "1.json").write_text(json.dumps({
            "id": "1",
            "subject": "Existing task",
            "status": "pending",
        }))

        # Run with CLAUDE_CODE_TASK_LIST_ID set
        cmd = [
            "uv", "run", "scripts/checks/setup-session.py",
            "--file", str(env["input_file"]),
            "--plugin-root", str(env["plugin_root"]),
            # Note: NOT passing --session-id, so it falls back to env
        ]

        run_env = os.environ.copy()
        run_env["HOME"] = str(env["mock_home"])
        run_env["CLAUDE_CODE_TASK_LIST_ID"] = user_task_list

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
            env=run_env,
        )

        output = json.loads(result.stdout)

        assert output["success"] is False
        assert output["mode"] == "conflict"
        assert output["existing_task_count"] == 1
        assert "Existing task" in output["sample_subjects"]

    def test_force_overwrites_conflict(self, task_integration_env, monkeypatch):
        """--force flag should overwrite conflicting tasks."""
        import os

        env = task_integration_env
        monkeypatch.setattr(Path, "home", lambda: env["mock_home"])

        # Create existing tasks
        user_task_list = "my-custom-tasks"
        tasks_dir = env["mock_home"] / ".claude" / "tasks" / user_task_list
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "1.json").write_text(json.dumps({
            "id": "1",
            "subject": "Existing task",
            "status": "pending",
        }))

        # Run with --force
        cmd = [
            "uv", "run", "scripts/checks/setup-session.py",
            "--file", str(env["input_file"]),
            "--plugin-root", str(env["plugin_root"]),
            "--force",
        ]

        run_env = os.environ.copy()
        run_env["HOME"] = str(env["mock_home"])
        run_env["CLAUDE_CODE_TASK_LIST_ID"] = user_task_list

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
            env=run_env,
        )

        output = json.loads(result.stdout)

        assert output["success"] is True
        assert output["tasks_written"] > 0

        # Verify tasks were overwritten
        task1 = json.loads((tasks_dir / "1.json").read_text())
        assert task1["subject"] != "Existing task"
