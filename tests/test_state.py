# tests/test_state.py
"""Tests for state detection module."""

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from lib.state import (
    is_valid_split_dir,
    get_split_index,
    detect_state,
    generate_todos,
    STEPS,
    SPLIT_DIR_PATTERN,
)


class TestSplitDirValidation:
    """Tests for split directory pattern validation."""

    def test_valid_patterns(self):
        """Should accept valid patterns: 01-name, 12-multi-word."""
        assert is_valid_split_dir("01-backend") is True
        assert is_valid_split_dir("12-multi-word") is True
        assert is_valid_split_dir("99-a") is True
        assert is_valid_split_dir("01-a-b-c") is True

    def test_rejects_single_digit(self):
        """Should reject 1-name (single digit)."""
        assert is_valid_split_dir("1-name") is False

    def test_rejects_no_hyphen(self):
        """Should reject 01name (no separator)."""
        assert is_valid_split_dir("01name") is False

    def test_rejects_uppercase(self):
        """Should reject 01-Name (uppercase)."""
        assert is_valid_split_dir("01-Name") is False
        assert is_valid_split_dir("01-BACKEND") is False

    def test_rejects_special_chars(self):
        """Should reject 01-na_me (special chars)."""
        assert is_valid_split_dir("01-na_me") is False
        assert is_valid_split_dir("01-na.me") is False
        assert is_valid_split_dir("01-na me") is False


class TestGetSplitIndex:
    """Tests for extracting numeric index."""

    def test_extracts_index(self):
        """Should extract 1 from 01-name, 12 from 12-foo."""
        assert get_split_index("01-name") == 1
        assert get_split_index("12-foo") == 12
        assert get_split_index("99-bar") == 99


class TestDetectState:
    """Tests for workflow state detection."""

    def test_fresh_state_no_files(self, tmp_path):
        """Empty dir should return resume_step=1."""
        state = detect_state(tmp_path)

        assert state["interview_complete"] is False
        assert state["splits_proposed"] is False
        assert state["manifest_created"] is False
        assert state["resume_step"] == 1

    def test_interview_complete(self, tmp_path):
        """Interview file exists should return resume_step=2."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")

        state = detect_state(tmp_path)

        assert state["interview_complete"] is True
        assert state["resume_step"] == 2

    def test_with_session_json(self, tmp_path):
        """Should use session.json as authoritative source."""
        # Create session state file
        session_state = {
            "input_file_hash": "sha256:abc123",
            "interview_complete": True,
            "proposed_splits": [
                {"index": 1, "dir_name": "01-backend", "title": "Backend"}
            ],
            "splits_confirmed": False,
            "completion_status": {},
            "manifest_written": False,
            "outcome": None
        }
        (tmp_path / "deep_project_session.json").write_text(
            json.dumps(session_state)
        )

        state = detect_state(tmp_path)

        assert state["interview_complete"] is True
        assert state["splits_proposed"] is True
        assert state["splits_confirmed"] is False
        assert state["resume_step"] == 2  # Split analysis (after interview)

    def test_splits_created_no_specs(self, tmp_path):
        """Dirs without specs should return resume_step=5."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "02-frontend").mkdir()

        state = detect_state(tmp_path)

        assert state["splits_proposed"] is True
        assert state["splits"] == ["01-backend", "02-frontend"]
        assert state["resume_step"] == 5

    def test_partial_specs(self, tmp_path):
        """Some specs missing should return resume_step=5."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "01-backend" / "spec.md").write_text("# Spec")
        (tmp_path / "02-frontend").mkdir()  # No spec

        # Create session state with both splits declared
        session_state = {
            "input_file_hash": "sha256:abc123",
            "interview_complete": True,
            "proposed_splits": [
                {"index": 1, "dir_name": "01-backend", "title": "Backend"},
                {"index": 2, "dir_name": "02-frontend", "title": "Frontend"}
            ],
            "splits_confirmed": True,
            "completion_status": {
                "01-backend": {"dir_created": True, "spec_written": True},
                "02-frontend": {"dir_created": True, "spec_written": False}
            },
            "manifest_written": False,
            "outcome": "splitting"
        }
        (tmp_path / "deep_project_session.json").write_text(
            json.dumps(session_state)
        )

        state = detect_state(tmp_path)

        assert state["resume_step"] == 5  # Still in output generation

    def test_all_specs_no_manifest(self, tmp_path):
        """All specs but no manifest should return resume_step=5."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "01-backend" / "spec.md").write_text("# Spec")

        # Session state with all specs written but no manifest
        session_state = {
            "input_file_hash": "sha256:abc123",
            "interview_complete": True,
            "proposed_splits": [
                {"index": 1, "dir_name": "01-backend", "title": "Backend"}
            ],
            "splits_confirmed": True,
            "completion_status": {
                "01-backend": {"dir_created": True, "spec_written": True}
            },
            "manifest_written": False,
            "outcome": "splitting"
        }
        (tmp_path / "deep_project_session.json").write_text(
            json.dumps(session_state)
        )

        state = detect_state(tmp_path)

        assert state["resume_step"] == 5  # Output generation (need manifest)

    def test_complete_state(self, tmp_path):
        """Manifest + all specs should return resume_step=6."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "01-backend" / "spec.md").write_text("# Spec")
        (tmp_path / "project-manifest.md").write_text("# Manifest")

        # Session state with everything complete
        session_state = {
            "input_file_hash": "sha256:abc123",
            "interview_complete": True,
            "proposed_splits": [
                {"index": 1, "dir_name": "01-backend", "title": "Backend"}
            ],
            "splits_confirmed": True,
            "completion_status": {
                "01-backend": {"dir_created": True, "spec_written": True}
            },
            "manifest_written": True,
            "outcome": "splitting"
        }
        (tmp_path / "deep_project_session.json").write_text(
            json.dumps(session_state)
        )

        state = detect_state(tmp_path)

        assert state["manifest_created"] is True
        assert state["resume_step"] == 6

    def test_not_splittable_outcome(self, tmp_path):
        """Session with outcome=not_splittable should return resume_step=6."""
        session_state = {
            "input_file_hash": "sha256:abc123",
            "interview_complete": True,
            "proposed_splits": [
                {"index": 1, "dir_name": "01-project", "title": "Project"}
            ],
            "splits_confirmed": True,
            "completion_status": {
                "01-project": {"dir_created": True, "spec_written": True}
            },
            "manifest_written": True,
            "outcome": "not_splittable"
        }
        (tmp_path / "deep_project_session.json").write_text(
            json.dumps(session_state)
        )

        state = detect_state(tmp_path)

        assert state["outcome"] == "not_splittable"
        assert state["resume_step"] == 6

    def test_ignores_invalid_directories(self, tmp_path):
        """Should ignore dirs not matching pattern."""
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "not-a-split").mkdir()  # No number prefix
        (tmp_path / "1-bad").mkdir()  # Single digit
        (tmp_path / "random_dir").mkdir()

        state = detect_state(tmp_path)

        assert state["splits"] == ["01-backend"]


class TestGenerateTodos:
    """Tests for TODO list generation."""

    def test_context_items_always_completed(self):
        """Context items should always be completed."""
        todos = generate_todos(
            current_step=1,
            plugin_root="/plugin",
            planning_dir="/planning",
            initial_file="/planning/spec.md"
        )

        context_items = [t for t in todos if t["content"].startswith("plugin_root=")]
        assert len(context_items) == 1
        assert context_items[0]["status"] == "completed"

        planning_items = [t for t in todos if t["content"].startswith("planning_dir=")]
        assert len(planning_items) == 1
        assert planning_items[0]["status"] == "completed"

    def test_marks_current_step_in_progress(self):
        """Current step should be in_progress."""
        todos = generate_todos(
            current_step=2,
            plugin_root="/plugin",
            planning_dir="/planning",
            initial_file="/planning/spec.md"
        )

        # Step 2 is "Analyze and propose splits"
        step_2 = [t for t in todos if "splits" in t["content"].lower() and "Analyze" in t["content"]]
        assert len(step_2) == 1
        assert step_2[0]["status"] == "in_progress"

    def test_marks_future_steps_pending(self):
        """Future steps should be pending."""
        todos = generate_todos(
            current_step=2,
            plugin_root="/plugin",
            planning_dir="/planning",
            initial_file="/planning/spec.md"
        )

        # Steps after 2 should be pending
        confirm_step = [t for t in todos if "Confirm" in t["content"]]
        assert len(confirm_step) == 1
        assert confirm_step[0]["status"] == "pending"

    def test_marks_past_steps_completed(self):
        """Past steps should be completed."""
        todos = generate_todos(
            current_step=5,
            plugin_root="/plugin",
            planning_dir="/planning",
            initial_file="/planning/spec.md"
        )

        # Interview step (step 1) should be completed
        interview_step = [t for t in todos if "interview" in t["content"].lower()]
        assert len(interview_step) == 1
        assert interview_step[0]["status"] == "completed"
