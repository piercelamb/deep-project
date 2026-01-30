# tests/test_integration.py
"""End-to-end integration tests for /deep-project.

Design principle: State is derived from file existence, not JSON fields.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from lib.config import (
    compute_file_hash,
    save_session_state,
)
from lib.state import detect_state


@pytest.fixture
def integration_planning_dir(tmp_path):
    """Create a full planning directory for integration tests."""
    planning_dir = tmp_path / "planning"
    planning_dir.mkdir()

    # Create sample input file
    input_file = planning_dir / "rough_plan.md"
    input_file.write_text("""
# My Project Requirements

## Overview
Build a web application with backend API and frontend UI.

## Features
- User authentication
- Dashboard
- Data visualization
""")

    return planning_dir


def run_setup_session(
    input_file: Path,
    plugin_root: Path,
    session_id: str = "test-session-12345",
) -> dict:
    """Helper to run setup-session.py and return parsed output."""
    result = subprocess.run(
        [
            "uv", "run", "scripts/checks/setup-session.py",
            "--file", str(input_file),
            "--plugin-root", str(plugin_root),
            "--session-id", session_id,
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    return json.loads(result.stdout)


@pytest.mark.integration
class TestEndToEnd:
    """End-to-end workflow tests."""

    def test_new_session_workflow(self, integration_planning_dir, mock_plugin_root):
        """Complete workflow: setup -> creates minimal state file.

        Verifies:
        - setup-session.py creates minimal session state file
        - Returns mode='new' and resume_from_step=1
        - Planning directory is correctly identified
        """
        input_file = integration_planning_dir / "rough_plan.md"

        output = run_setup_session(input_file, mock_plugin_root)

        assert output["success"] is True
        assert output["mode"] == "new"
        assert output["resume_from_step"] == 1
        assert output["planning_dir"] == str(integration_planning_dir)
        assert output["initial_file"] == str(input_file)

        # Verify session state file was created with minimal fields
        state_path = integration_planning_dir / "deep_project_session.json"
        assert state_path.exists()

        state = json.loads(state_path.read_text())
        assert state["input_file_hash"].startswith("sha256:")
        assert "session_created_at" in state
        # Should NOT have old fields
        assert "proposed_splits" not in state
        assert "interview_complete" not in state
        assert "splits_confirmed" not in state
        assert "completion_status" not in state

    def test_resume_after_interview(self, integration_planning_dir, mock_plugin_root):
        """Resume correctly after interview phase.

        Simulates:
        - Interview transcript file exists
        - Minimal session state

        Verifies:
        - Returns mode='resume'
        - resume_from_step=2 (split analysis)
        """
        input_file = integration_planning_dir / "rough_plan.md"

        # Create minimal session state
        save_session_state(str(integration_planning_dir), {
            "input_file_hash": compute_file_hash(str(input_file)),
            "session_created_at": "2024-01-19T10:30:00Z",
        })

        # Create interview transcript file (checkpoint)
        (integration_planning_dir / "deep_project_interview.md").write_text("""
# Interview Transcript

## Q1: Natural Boundaries
User indicated backend and frontend as natural splits.
""")

        output = run_setup_session(input_file, mock_plugin_root)

        assert output["success"] is True
        assert output["mode"] == "resume"
        assert output["resume_from_step"] == 2
        assert output["state"]["interview_complete"] is True

    def test_resume_after_user_confirmed(self, integration_planning_dir, mock_plugin_root):
        """Resume correctly after user confirmed splits.

        Simulates:
        - Interview file exists
        - Split directories exist (user confirmed the manifest)

        Verifies:
        - Returns resume_from_step=6 (spec generation)
        """
        input_file = integration_planning_dir / "rough_plan.md"

        # Create minimal session state
        save_session_state(str(integration_planning_dir), {
            "input_file_hash": compute_file_hash(str(input_file)),
            "session_created_at": "2024-01-19T10:30:00Z",
        })

        # Create interview transcript (checkpoint)
        (integration_planning_dir / "deep_project_interview.md").write_text("# Interview")

        # Create split directories (user confirmed, spec generation next)
        (integration_planning_dir / "01-backend").mkdir()
        (integration_planning_dir / "02-frontend").mkdir()

        output = run_setup_session(input_file, mock_plugin_root)

        assert output["success"] is True
        assert output["mode"] == "resume"
        assert output["resume_from_step"] == 6
        assert output["state"]["directories_created"] is True

    def test_single_unit_workflow(self, integration_planning_dir, mock_plugin_root):
        """Not-splittable project creates single subdir.

        Simulates:
        - Single split directory created with spec (complete)

        Verifies:
        - Returns resume_from_step=7 (complete)
        """
        input_file = integration_planning_dir / "rough_plan.md"

        # Create minimal session state
        save_session_state(str(integration_planning_dir), {
            "input_file_hash": compute_file_hash(str(input_file)),
            "session_created_at": "2024-01-19T10:30:00Z",
        })

        # Create interview transcript (checkpoint)
        (integration_planning_dir / "deep_project_interview.md").write_text("# Interview")

        # Create single split directory with spec (checkpoint - complete)
        split_dir = integration_planning_dir / "01-my-project"
        split_dir.mkdir()
        (split_dir / "spec.md").write_text("# My Project\n\n## Requirements\n...")

        output = run_setup_session(input_file, mock_plugin_root)

        assert output["success"] is True
        assert output["mode"] == "resume"
        assert output["resume_from_step"] == 7

    def test_output_structure(self, integration_planning_dir, mock_plugin_root):
        """Verify final output structure matches spec.

        Complete workflow produces:
        - deep_project_session.json (minimal)
        - deep_project_interview.md
        - NN-name/ directories with spec.md
        - project-manifest.md (created during phase 3, before user confirmation)
        """
        input_file = integration_planning_dir / "rough_plan.md"

        # Create minimal session state
        save_session_state(str(integration_planning_dir), {
            "input_file_hash": compute_file_hash(str(input_file)),
            "session_created_at": "2024-01-19T10:30:00Z",
        })

        # Create all output files (checkpoints)
        (integration_planning_dir / "deep_project_interview.md").write_text("# Interview")

        backend_dir = integration_planning_dir / "01-backend"
        backend_dir.mkdir()
        (backend_dir / "spec.md").write_text("# Backend Spec")

        frontend_dir = integration_planning_dir / "02-frontend"
        frontend_dir.mkdir()
        (frontend_dir / "spec.md").write_text("# Frontend Spec")

        # Verify structure using detect_state
        state = detect_state(integration_planning_dir)

        assert state["interview_complete"] is True
        assert state["directories_created"] is True
        assert state["resume_step"] == 7
        assert state["splits"] == ["01-backend", "02-frontend"]
        assert state["splits_with_specs"] == ["01-backend", "02-frontend"]


@pytest.mark.integration
class TestEdgeCases:
    """Edge case testing."""

    def test_input_file_change_detection(self, integration_planning_dir, mock_plugin_root):
        """Should detect when input file has changed since session start.

        If user modifies the requirements file after starting a session,
        the setup script should include a warning.
        """
        from lib.config import check_input_file_changed

        input_file = integration_planning_dir / "rough_plan.md"
        original_content = input_file.read_text()

        # Create session state with original hash
        original_hash = compute_file_hash(str(input_file))
        save_session_state(str(integration_planning_dir), {
            "input_file_hash": original_hash,
            "session_created_at": "2024-01-19T10:30:00Z",
        })

        # Initially should not detect change
        assert check_input_file_changed(str(integration_planning_dir), str(input_file)) is False

        # Modify the file
        input_file.write_text(original_content + "\n\n## New Section\nAdditional requirements.")

        # Now should detect change
        assert check_input_file_changed(str(integration_planning_dir), str(input_file)) is True

    def test_partial_completion_resume(self, integration_planning_dir, mock_plugin_root):
        """Should resume correctly when some specs written but not all.

        If directories exist but only some have spec.md files,
        should resume at spec generation (step 6).
        """
        input_file = integration_planning_dir / "rough_plan.md"

        # Create minimal session state
        save_session_state(str(integration_planning_dir), {
            "input_file_hash": compute_file_hash(str(input_file)),
            "session_created_at": "2024-01-19T10:30:00Z",
        })

        # Create interview (checkpoint)
        (integration_planning_dir / "deep_project_interview.md").write_text("# Interview")

        # Create partial directories and specs
        backend_dir = integration_planning_dir / "01-backend"
        backend_dir.mkdir()
        (backend_dir / "spec.md").write_text("# Backend")
        (integration_planning_dir / "02-frontend").mkdir()  # Dir created but no spec

        output = run_setup_session(input_file, mock_plugin_root)

        assert output["success"] is True
        assert output["resume_from_step"] == 6  # Should resume at spec generation

        # Verify state shows partial completion
        state = output["state"]
        assert state["directories_created"] is True
        assert len(state["splits_with_specs"]) < len(state["splits"])

        # Verify split_directories contains full paths
        assert len(output["split_directories"]) == 2
        assert str(integration_planning_dir / "01-backend") in output["split_directories"]
        assert str(integration_planning_dir / "02-frontend") in output["split_directories"]

        # Verify splits_needing_specs only contains the one missing spec
        assert output["splits_needing_specs"] == ["02-frontend"]

    def test_ignores_non_split_directories(self, integration_planning_dir):
        """Should ignore directories that don't match split pattern."""
        # Create valid split directory
        (integration_planning_dir / "01-backend").mkdir()

        # Create various non-split directories
        (integration_planning_dir / "node_modules").mkdir()
        (integration_planning_dir / ".git").mkdir()
        (integration_planning_dir / "1-invalid").mkdir()  # Single digit
        (integration_planning_dir / "02-Invalid").mkdir()  # Uppercase
        (integration_planning_dir / "03_underscore").mkdir()  # Underscore

        # detect_state should only see 01-backend
        state = detect_state(integration_planning_dir)
        assert state["splits"] == ["01-backend"]
