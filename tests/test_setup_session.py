"""Tests for setup-session.py script.

Design principle: State is derived from file existence, not JSON fields.
"""

import json
import subprocess
from pathlib import Path

import pytest


class TestValidateInputFile:
    """Tests for input file validation."""

    def test_accepts_valid_md(self, tmp_planning_dir, mock_plugin_root, mock_session_id):
        """Should accept .md file with content."""
        input_file = tmp_planning_dir / "rough_plan.md"

        result = subprocess.run(
            [
                "uv", "run", "scripts/checks/setup-session.py",
                "--file", str(input_file),
                "--plugin-root", str(mock_plugin_root),
                "--session-id", mock_session_id,
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["initial_file"] == str(input_file)

    def test_rejects_nonexistent(self, tmp_path, mock_plugin_root):
        """Should reject missing file."""
        result = subprocess.run(
            [
                "uv", "run", "scripts/checks/setup-session.py",
                "--file", str(tmp_path / "nonexistent.md"),
                "--plugin-root", str(mock_plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        output = json.loads(result.stdout)
        assert output["success"] is False
        assert "not found" in output["error"].lower()

    def test_rejects_empty(self, tmp_path, mock_plugin_root):
        """Should reject empty file."""
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("")

        result = subprocess.run(
            [
                "uv", "run", "scripts/checks/setup-session.py",
                "--file", str(empty_file),
                "--plugin-root", str(mock_plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        output = json.loads(result.stdout)
        assert output["success"] is False
        assert "empty" in output["error"].lower()

    def test_rejects_non_md(self, tmp_path, mock_plugin_root):
        """Should reject .txt file."""
        txt_file = tmp_path / "requirements.txt"
        txt_file.write_text("Some content")

        result = subprocess.run(
            [
                "uv", "run", "scripts/checks/setup-session.py",
                "--file", str(txt_file),
                "--plugin-root", str(mock_plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        output = json.loads(result.stdout)
        assert output["success"] is False
        assert ".md" in output["error"]

    def test_rejects_directory(self, tmp_path, mock_plugin_root):
        """Should reject directory path."""
        dir_path = tmp_path / "some_dir"
        dir_path.mkdir()

        result = subprocess.run(
            [
                "uv", "run", "scripts/checks/setup-session.py",
                "--file", str(dir_path),
                "--plugin-root", str(mock_plugin_root)
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        output = json.loads(result.stdout)
        assert output["success"] is False
        assert "directory" in output["error"].lower()


@pytest.mark.integration
class TestSetupSessionScript:
    """Integration tests for setup-session.py CLI."""

    def test_new_session(self, tmp_planning_dir, mock_plugin_root, mock_session_id):
        """Should detect new session, return mode='new'."""
        input_file = tmp_planning_dir / "rough_plan.md"

        result = subprocess.run(
            [
                "uv", "run", "scripts/checks/setup-session.py",
                "--file", str(input_file),
                "--plugin-root", str(mock_plugin_root),
                "--session-id", mock_session_id,
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        output = json.loads(result.stdout)
        assert output["mode"] == "new"
        assert output["resume_from_step"] == 1

    def test_resume_session(self, tmp_planning_dir, mock_plugin_root, mock_session_id):
        """Should detect resume, return correct step."""
        input_file = tmp_planning_dir / "rough_plan.md"

        # Create interview file to simulate partial progress (checkpoint)
        (tmp_planning_dir / "deep_project_interview.md").write_text("# Interview")

        # Create minimal session state to simulate existing session
        (tmp_planning_dir / "deep_project_session.json").write_text(json.dumps({
            "input_file_hash": "sha256:abc123",
            "session_created_at": "2024-01-19T10:30:00Z",
        }))

        result = subprocess.run(
            [
                "uv", "run", "scripts/checks/setup-session.py",
                "--file", str(input_file),
                "--plugin-root", str(mock_plugin_root),
                "--session-id", mock_session_id,
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        output = json.loads(result.stdout)
        assert output["mode"] == "resume"
        assert output["resume_from_step"] == 2  # After interview

    def test_warns_on_file_change(self, tmp_planning_dir, mock_plugin_root, mock_session_id):
        """Should warn if input file changed since session start."""
        input_file = tmp_planning_dir / "rough_plan.md"

        # First run to create session
        subprocess.run(
            [
                "uv", "run", "scripts/checks/setup-session.py",
                "--file", str(input_file),
                "--plugin-root", str(mock_plugin_root),
                "--session-id", mock_session_id,
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Create session state with old hash (simulating file change)
        (tmp_planning_dir / "deep_project_session.json").write_text(json.dumps({
            "input_file_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "session_created_at": "2024-01-19T10:30:00Z",
        }))

        # Second run should detect change
        result = subprocess.run(
            [
                "uv", "run", "scripts/checks/setup-session.py",
                "--file", str(input_file),
                "--plugin-root", str(mock_plugin_root),
                "--session-id", mock_session_id,
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        output = json.loads(result.stdout)
        # The script should still succeed but include warning about file change
        assert output["success"] is True
        assert "warnings" in output
        assert len(output["warnings"]) == 1
        assert "changed" in output["warnings"][0].lower()

    def test_json_output_format(self, tmp_planning_dir, mock_plugin_root, mock_session_id):
        """Output should be valid JSON with expected fields."""
        input_file = tmp_planning_dir / "rough_plan.md"

        result = subprocess.run(
            [
                "uv", "run", "scripts/checks/setup-session.py",
                "--file", str(input_file),
                "--plugin-root", str(mock_plugin_root),
                "--session-id", mock_session_id,
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        output = json.loads(result.stdout)

        # Verify required fields
        assert "success" in output
        assert "mode" in output
        assert "planning_dir" in output
        assert "initial_file" in output
        assert "plugin_root" in output
        assert "resume_from_step" in output
        assert "state" in output
        assert "split_directories" in output
        assert "splits_needing_specs" in output
        assert "warnings" in output
        # New task system fields (replaces todos)
        assert "tasks_written" in output
        assert "task_list_id" in output
        assert "session_id_source" in output
