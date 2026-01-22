# tests/test_integration.py
"""End-to-end integration tests for /deep-project."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from lib.config import (
    compute_file_hash,
    load_session_config,
    save_session_config,
    save_session_state,
    session_config_path,
)
from lib.naming import format_split_dir_name, generate_unique_name, get_next_index
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


def run_setup_session(input_file: Path, plugin_root: Path) -> dict:
    """Helper to run setup-session.py and return parsed output."""
    result = subprocess.run(
        [
            "uv", "run", "scripts/checks/setup-session.py",
            "--file", str(input_file),
            "--plugin-root", str(plugin_root)
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
        """Complete workflow: setup -> creates config and state files.

        Verifies:
        - setup-session.py creates config file
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

        # Verify config file was created
        config_path = session_config_path(str(integration_planning_dir))
        assert config_path.exists()

        config = json.loads(config_path.read_text())
        assert config["initial_file"] == str(input_file)
        assert config["plugin_root"] == str(mock_plugin_root)

    def test_resume_after_interview(self, integration_planning_dir, mock_plugin_root):
        """Resume correctly after interview phase.

        Simulates:
        - Existing config file
        - Existing session state with interview_complete=True
        - Interview transcript file

        Verifies:
        - Returns mode='resume'
        - resume_from_step=2 (split analysis)
        """
        input_file = integration_planning_dir / "rough_plan.md"

        # Create existing session config
        save_session_config(str(integration_planning_dir), {
            "plugin_root": str(mock_plugin_root),
            "planning_dir": str(integration_planning_dir),
            "initial_file": str(input_file)
        })

        # Create session state indicating interview complete
        save_session_state(str(integration_planning_dir), {
            "input_file_hash": compute_file_hash(str(input_file)),
            "session_created_at": "2024-01-19T10:30:00Z",
            "interview_complete": True,
            "proposed_splits": [],
            "splits_confirmed": False,
            "completion_status": {},
            "manifest_written": False,
            "outcome": None
        })

        # Create interview transcript file
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

    def test_resume_after_splits_confirmed(self, integration_planning_dir, mock_plugin_root):
        """Resume correctly after splits confirmed.

        Simulates:
        - Session state with splits_confirmed=True
        - Proposed splits defined but not all directories created

        Verifies:
        - Returns resume_from_step=5 (output generation)
        """
        input_file = integration_planning_dir / "rough_plan.md"

        # Create existing session config
        save_session_config(str(integration_planning_dir), {
            "plugin_root": str(mock_plugin_root),
            "planning_dir": str(integration_planning_dir),
            "initial_file": str(input_file)
        })

        # Create session state with confirmed splits
        save_session_state(str(integration_planning_dir), {
            "input_file_hash": compute_file_hash(str(input_file)),
            "session_created_at": "2024-01-19T10:30:00Z",
            "interview_complete": True,
            "proposed_splits": [
                {"index": 1, "dir_name": "01-backend", "title": "Backend API"},
                {"index": 2, "dir_name": "02-frontend", "title": "Frontend UI"}
            ],
            "splits_confirmed": True,
            "completion_status": {
                "01-backend": {"dir_created": True, "spec_written": False},
                "02-frontend": {"dir_created": False, "spec_written": False}
            },
            "manifest_written": False,
            "outcome": "splitting"
        })

        # Create interview transcript
        (integration_planning_dir / "deep_project_interview.md").write_text("# Interview")

        # Create first split directory (partially completed)
        (integration_planning_dir / "01-backend").mkdir()

        output = run_setup_session(input_file, mock_plugin_root)

        assert output["success"] is True
        assert output["mode"] == "resume"
        assert output["resume_from_step"] == 5
        assert output["state"]["splits_confirmed"] is True

    def test_single_unit_workflow(self, integration_planning_dir, mock_plugin_root):
        """Not-splittable project creates single subdir.

        Simulates:
        - Session state with outcome='not_splittable'
        - Single split directory created with spec
        - Manifest written

        Verifies:
        - Returns resume_from_step=6 (complete)
        - state['outcome'] is 'not_splittable'
        """
        input_file = integration_planning_dir / "rough_plan.md"

        # Create existing session config
        save_session_config(str(integration_planning_dir), {
            "plugin_root": str(mock_plugin_root),
            "planning_dir": str(integration_planning_dir),
            "initial_file": str(input_file)
        })

        # Create session state indicating not splittable (complete)
        save_session_state(str(integration_planning_dir), {
            "input_file_hash": compute_file_hash(str(input_file)),
            "session_created_at": "2024-01-19T10:30:00Z",
            "interview_complete": True,
            "proposed_splits": [
                {"index": 1, "dir_name": "01-my-project", "title": "My Project"}
            ],
            "splits_confirmed": True,
            "completion_status": {
                "01-my-project": {"dir_created": True, "spec_written": True}
            },
            "manifest_written": True,
            "outcome": "not_splittable"
        })

        # Create interview transcript
        (integration_planning_dir / "deep_project_interview.md").write_text("# Interview")

        # Create single split directory with spec
        split_dir = integration_planning_dir / "01-my-project"
        split_dir.mkdir()
        (split_dir / "spec.md").write_text("# My Project\n\n## Requirements\n...")

        # Create manifest
        (integration_planning_dir / "project-manifest.md").write_text("# Manifest")

        output = run_setup_session(input_file, mock_plugin_root)

        assert output["success"] is True
        assert output["mode"] == "resume"
        assert output["resume_from_step"] == 6
        assert output["state"]["outcome"] == "not_splittable"

    def test_output_structure(self, integration_planning_dir, mock_plugin_root):
        """Verify final output structure matches spec.

        Complete workflow produces:
        - deep_project_config.json
        - deep_project_session.json
        - deep_project_interview.md
        - NN-name/ directories with spec.md
        - project-manifest.md
        """
        input_file = integration_planning_dir / "rough_plan.md"

        # Create complete session state
        save_session_config(str(integration_planning_dir), {
            "plugin_root": str(mock_plugin_root),
            "planning_dir": str(integration_planning_dir),
            "initial_file": str(input_file)
        })

        save_session_state(str(integration_planning_dir), {
            "input_file_hash": compute_file_hash(str(input_file)),
            "session_created_at": "2024-01-19T10:30:00Z",
            "interview_complete": True,
            "proposed_splits": [
                {"index": 1, "dir_name": "01-backend", "title": "Backend"},
                {"index": 2, "dir_name": "02-frontend", "title": "Frontend"}
            ],
            "splits_confirmed": True,
            "completion_status": {
                "01-backend": {"dir_created": True, "spec_written": True},
                "02-frontend": {"dir_created": True, "spec_written": True}
            },
            "manifest_written": True,
            "outcome": "splitting"
        })

        # Create all output files
        (integration_planning_dir / "deep_project_interview.md").write_text("# Interview")

        backend_dir = integration_planning_dir / "01-backend"
        backend_dir.mkdir()
        (backend_dir / "spec.md").write_text("# Backend Spec")

        frontend_dir = integration_planning_dir / "02-frontend"
        frontend_dir.mkdir()
        (frontend_dir / "spec.md").write_text("# Frontend Spec")

        (integration_planning_dir / "project-manifest.md").write_text("# Manifest")

        # Verify structure using detect_state
        state = detect_state(integration_planning_dir)

        assert state["interview_complete"] is True
        assert state["splits_proposed"] is True
        assert state["splits_confirmed"] is True
        assert state["directories_created"] is True
        assert state["manifest_created"] is True
        assert state["resume_step"] == 6
        assert state["splits"] == ["01-backend", "02-frontend"]
        assert state["splits_with_specs"] == ["01-backend", "02-frontend"]


@pytest.mark.integration
class TestEdgeCases:
    """Edge case testing."""

    def test_directory_collision_handling(self, integration_planning_dir):
        """Should handle collision with suffix.

        When a directory with the target name already exists,
        generate_unique_name should append -2, -3, etc.
        """
        # Create existing directory that would cause collision
        (integration_planning_dir / "01-backend").mkdir()

        # Generate unique name should add suffix
        unique_name = generate_unique_name(integration_planning_dir, 1, "Backend")
        assert unique_name == "01-backend-2"

        # Create that too
        (integration_planning_dir / "01-backend-2").mkdir()

        # Next unique name should increment
        unique_name = generate_unique_name(integration_planning_dir, 1, "Backend")
        assert unique_name == "01-backend-3"

    def test_invalid_split_names(self, integration_planning_dir):
        """Should sanitize problematic names.

        Names with special characters, spaces, underscores, etc.
        should be converted to valid kebab-case.
        """
        # Various problematic inputs
        test_cases = [
            ("Backend API", "01-backend-api"),
            ("user_authentication", "01-user-authentication"),
            ("Frontend / UI", "01-frontend-ui"),
            ("Data   Processing", "01-data-processing"),
            (" - Cleanup - ", "01-cleanup"),
            ("Auth_Service-v2", "01-auth-service-v2"),
        ]

        for input_name, expected in test_cases:
            result = format_split_dir_name(1, input_name)
            assert result == expected, f"Failed for {input_name}: got {result}"

    def test_input_file_change_detection(self, integration_planning_dir, mock_plugin_root):
        """Should detect when input file has changed since session start.

        If user modifies the requirements file after starting a session,
        the setup script should include a warning.
        """
        from lib.config import check_input_file_changed

        input_file = integration_planning_dir / "rough_plan.md"
        original_content = input_file.read_text()

        # Create session config
        save_session_config(str(integration_planning_dir), {
            "plugin_root": str(mock_plugin_root),
            "planning_dir": str(integration_planning_dir),
            "initial_file": str(input_file)
        })

        # Create session state with original hash
        original_hash = compute_file_hash(str(input_file))
        save_session_state(str(integration_planning_dir), {
            "input_file_hash": original_hash,
            "session_created_at": "2024-01-19T10:30:00Z",
            "interview_complete": False,
            "proposed_splits": [],
            "splits_confirmed": False,
            "completion_status": {},
            "manifest_written": False,
            "outcome": None
        })

        # Initially should not detect change
        assert check_input_file_changed(str(integration_planning_dir), str(input_file)) is False

        # Modify the file
        input_file.write_text(original_content + "\n\n## New Section\nAdditional requirements.")

        # Now should detect change
        assert check_input_file_changed(str(integration_planning_dir), str(input_file)) is True

    def test_corrupted_config_handling(self, integration_planning_dir, mock_plugin_root):
        """Should raise clear error for corrupted JSON files."""
        # Create corrupted config file
        config_path = session_config_path(str(integration_planning_dir))
        config_path.write_text("{ invalid json }")

        with pytest.raises(ValueError) as exc_info:
            load_session_config(str(integration_planning_dir))

        assert "corrupted" in str(exc_info.value).lower()

    def test_partial_completion_resume(self, integration_planning_dir, mock_plugin_root):
        """Should resume correctly when some specs written but not all.

        If splits are confirmed but only some have spec.md files,
        should resume at output generation (step 5).
        """
        input_file = integration_planning_dir / "rough_plan.md"

        # Create session with partial completion
        save_session_config(str(integration_planning_dir), {
            "plugin_root": str(mock_plugin_root),
            "planning_dir": str(integration_planning_dir),
            "initial_file": str(input_file)
        })

        save_session_state(str(integration_planning_dir), {
            "input_file_hash": compute_file_hash(str(input_file)),
            "session_created_at": "2024-01-19T10:30:00Z",
            "interview_complete": True,
            "proposed_splits": [
                {"index": 1, "dir_name": "01-backend", "title": "Backend"},
                {"index": 2, "dir_name": "02-frontend", "title": "Frontend"},
                {"index": 3, "dir_name": "03-database", "title": "Database"}
            ],
            "splits_confirmed": True,
            "completion_status": {
                "01-backend": {"dir_created": True, "spec_written": True},
                "02-frontend": {"dir_created": True, "spec_written": False},
                "03-database": {"dir_created": False, "spec_written": False}
            },
            "manifest_written": False,
            "outcome": "splitting"
        })

        # Create interview and partial directories
        (integration_planning_dir / "deep_project_interview.md").write_text("# Interview")
        backend_dir = integration_planning_dir / "01-backend"
        backend_dir.mkdir()
        (backend_dir / "spec.md").write_text("# Backend")
        (integration_planning_dir / "02-frontend").mkdir()  # Dir created but no spec

        output = run_setup_session(input_file, mock_plugin_root)

        assert output["success"] is True
        assert output["resume_from_step"] == 5  # Should resume at output generation

        # Verify state shows partial completion
        state = output["state"]
        assert state["splits_confirmed"] is True
        assert len(state["splits_with_specs"]) < len(state["splits"])

    def test_max_index_calculation_with_gaps(self, integration_planning_dir):
        """Should use max(indices) + 1, not fill gaps.

        If directories 01 and 03 exist (gap at 02), next should be 04.
        """
        # Create directories with gap
        (integration_planning_dir / "01-first").mkdir()
        (integration_planning_dir / "03-third").mkdir()  # Gap at 02

        next_idx = get_next_index(integration_planning_dir)
        assert next_idx == 4  # max(1, 3) + 1 = 4, not 2

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

        # get_next_index should only see 01-backend
        next_idx = get_next_index(integration_planning_dir)
        assert next_idx == 2

        # detect_state should only see 01-backend
        state = detect_state(integration_planning_dir)
        assert state["splits"] == ["01-backend"]
