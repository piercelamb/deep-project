# tests/test_state.py
"""Tests for state detection module.

Design principle: State is derived from file existence, not JSON fields.
"""

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
    """Tests for workflow state detection from file existence."""

    def test_fresh_state_no_files(self, tmp_path):
        """Empty dir should return resume_step=1."""
        state = detect_state(tmp_path)

        assert state["interview_complete"] is False
        assert state["manifest_created"] is False
        assert state["directories_created"] is False
        assert state["resume_step"] == 1

    def test_interview_complete_from_file(self, tmp_path):
        """Interview file exists should return resume_step=2."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")

        state = detect_state(tmp_path)

        assert state["interview_complete"] is True
        assert state["manifest_created"] is False
        assert state["resume_step"] == 2

    def test_manifest_created_no_directories(self, tmp_path):
        """Manifest exists but no directories should return resume_step=4."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        (tmp_path / "project-manifest.md").write_text("# Manifest proposal")

        state = detect_state(tmp_path)

        assert state["interview_complete"] is True
        assert state["manifest_created"] is True
        assert state["directories_created"] is False
        assert state["resume_step"] == 4  # User confirmation

    def test_directories_created(self, tmp_path):
        """Dirs without specs should return resume_step=6."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "02-frontend").mkdir()

        state = detect_state(tmp_path)

        assert state["directories_created"] is True
        assert state["splits"] == ["01-backend", "02-frontend"]
        assert state["resume_step"] == 6  # Spec generation

    def test_partial_specs(self, tmp_path):
        """Some specs missing should return resume_step=6."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "01-backend" / "spec.md").write_text("# Spec")
        (tmp_path / "02-frontend").mkdir()  # No spec

        state = detect_state(tmp_path)

        assert state["splits_with_specs"] == ["01-backend"]
        assert state["resume_step"] == 6  # Still in spec generation

    def test_all_specs_complete(self, tmp_path):
        """All specs written should return resume_step=7."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "01-backend" / "spec.md").write_text("# Spec")

        state = detect_state(tmp_path)

        assert state["splits_with_specs"] == ["01-backend"]
        assert state["resume_step"] == 7  # Complete

    def test_multiple_splits_complete(self, tmp_path):
        """Multiple splits all with specs."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "01-backend" / "spec.md").write_text("# Backend Spec")
        (tmp_path / "02-frontend").mkdir()
        (tmp_path / "02-frontend" / "spec.md").write_text("# Frontend Spec")

        state = detect_state(tmp_path)

        assert state["splits"] == ["01-backend", "02-frontend"]
        assert state["splits_with_specs"] == ["01-backend", "02-frontend"]
        assert state["resume_step"] == 7

    def test_ignores_invalid_directories(self, tmp_path):
        """Should ignore dirs not matching pattern."""
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "not-a-split").mkdir()  # No number prefix
        (tmp_path / "1-bad").mkdir()  # Single digit
        (tmp_path / "random_dir").mkdir()

        state = detect_state(tmp_path)

        assert state["splits"] == ["01-backend"]

    def test_handles_old_format_session_json(self, tmp_path):
        """Should handle old session.json format - state derived from files only."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "01-backend" / "spec.md").write_text("# Spec")

        # Old format with many fields - all ignored, state from files only
        old_session_state = {
            "input_file_hash": "sha256:abc123",
            "session_created_at": "2024-01-01T00:00:00Z",
            "interview_complete": True,  # Ignored - derived from file
            "proposed_splits": [
                {"index": 1, "dir_name": "01-backend", "title": "Backend", "purpose": "..."}
            ],  # Ignored entirely
            "splits_confirmed": True,  # Ignored - derived from directories
            "completion_status": {},  # Ignored entirely
            "manifest_written": True,  # Ignored - derived from file
            "outcome": "splitting"  # Ignored entirely
        }
        (tmp_path / "deep_project_session.json").write_text(json.dumps(old_session_state))

        state = detect_state(tmp_path)

        # State is derived from files, not JSON fields
        assert state["interview_complete"] is True  # From file existence
        assert state["directories_created"] is True  # From directory existence
        assert state["resume_step"] == 7


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


class TestResumeStepTodoConsistency:
    """Tests that resume_from_step and generated TODOs always match.

    For each possible directory state, verifies that:
    1. detect_state() returns correct resume_step
    2. generate_todos(current_step=resume_step) marks that step as in_progress
    3. Earlier steps are completed, later steps are pending
    """

    def _get_workflow_todos(self, todos: list[dict]) -> list[dict]:
        """Filter to just workflow items (exclude context items)."""
        return [t for t in todos if not t["content"].startswith(("plugin_root=", "planning_dir=", "initial_file="))]

    def _verify_todo_statuses(self, todos: list[dict], current_step: int):
        """Verify TODO statuses match the current step."""
        workflow_todos = self._get_workflow_todos(todos)

        # Workflow items map: (content substring, step number)
        step_mapping = [
            ("Validate input", 0),
            ("Conduct interview", 1),
            ("Analyze splits", 2),
            ("Discover dependencies", 3),
            ("Confirm splits", 4),
            ("Create split directories", 5),
            ("Generate spec", 6),
            ("Output summary", 7),
        ]

        for content_substr, step_num in step_mapping:
            matching = [t for t in workflow_todos if content_substr in t["content"]]
            assert len(matching) == 1, f"Expected exactly one TODO matching '{content_substr}'"
            todo = matching[0]

            if step_num < current_step:
                assert todo["status"] == "completed", \
                    f"Step {step_num} should be completed when current_step={current_step}"
            elif step_num == current_step:
                assert todo["status"] == "in_progress", \
                    f"Step {step_num} should be in_progress when current_step={current_step}"
            else:
                assert todo["status"] == "pending", \
                    f"Step {step_num} should be pending when current_step={current_step}"

    def test_fresh_state_todos_match_step_1(self, tmp_path):
        """Empty dir: resume_step=1, TODOs should mark step 1 in_progress."""
        state = detect_state(tmp_path)
        assert state["resume_step"] == 1

        todos = generate_todos(
            current_step=state["resume_step"],
            plugin_root="/plugin",
            planning_dir=str(tmp_path),
            initial_file=str(tmp_path / "spec.md")
        )

        self._verify_todo_statuses(todos, current_step=1)

    def test_interview_complete_todos_match_step_2(self, tmp_path):
        """Interview file exists: resume_step=2, TODOs should mark step 2 in_progress."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")

        state = detect_state(tmp_path)
        assert state["resume_step"] == 2

        todos = generate_todos(
            current_step=state["resume_step"],
            plugin_root="/plugin",
            planning_dir=str(tmp_path),
            initial_file=str(tmp_path / "spec.md")
        )

        self._verify_todo_statuses(todos, current_step=2)

    def test_manifest_created_todos_match_step_4(self, tmp_path):
        """Manifest exists but no directories: resume_step=4, TODOs should mark step 4 in_progress."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        (tmp_path / "project-manifest.md").write_text("# Manifest proposal")

        state = detect_state(tmp_path)
        assert state["resume_step"] == 4

        todos = generate_todos(
            current_step=state["resume_step"],
            plugin_root="/plugin",
            planning_dir=str(tmp_path),
            initial_file=str(tmp_path / "spec.md")
        )

        self._verify_todo_statuses(todos, current_step=4)

    def test_directories_created_todos_match_step_6(self, tmp_path):
        """Split directories exist: resume_step=6, TODOs should mark step 6 in_progress."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        (tmp_path / "01-backend").mkdir()

        state = detect_state(tmp_path)
        assert state["resume_step"] == 6

        todos = generate_todos(
            current_step=state["resume_step"],
            plugin_root="/plugin",
            planning_dir=str(tmp_path),
            initial_file=str(tmp_path / "spec.md")
        )

        self._verify_todo_statuses(todos, current_step=6)

    def test_partial_specs_todos_match_step_6(self, tmp_path):
        """Some specs written: resume_step=6, TODOs should mark step 6 in_progress."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "01-backend" / "spec.md").write_text("# Spec")
        (tmp_path / "02-frontend").mkdir()  # No spec yet

        state = detect_state(tmp_path)
        assert state["resume_step"] == 6

        todos = generate_todos(
            current_step=state["resume_step"],
            plugin_root="/plugin",
            planning_dir=str(tmp_path),
            initial_file=str(tmp_path / "spec.md")
        )

        self._verify_todo_statuses(todos, current_step=6)

    def test_complete_state_todos_match_step_7(self, tmp_path):
        """All specs written: resume_step=7, TODOs should mark step 7 in_progress."""
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "01-backend" / "spec.md").write_text("# Spec")

        state = detect_state(tmp_path)
        assert state["resume_step"] == 7

        todos = generate_todos(
            current_step=state["resume_step"],
            plugin_root="/plugin",
            planning_dir=str(tmp_path),
            initial_file=str(tmp_path / "spec.md")
        )

        self._verify_todo_statuses(todos, current_step=7)

    def test_steps_3_and_5_never_returned_by_detect_state(self, tmp_path):
        """Steps 3 and 5 are never valid resume points.

        This is by design:
        - Step 3 (dependency_discovery) happens inline after step 2 and ends with manifest creation
        - Step 5 (directory_creation) happens inline after step 4 and ends with directories created
        """
        # Test all possible states and verify none return step 3 or 5
        test_states = []

        # Fresh state
        test_states.append(detect_state(tmp_path)["resume_step"])

        # Interview complete
        (tmp_path / "deep_project_interview.md").write_text("# Interview")
        test_states.append(detect_state(tmp_path)["resume_step"])

        # Manifest created (proposal complete)
        (tmp_path / "project-manifest.md").write_text("# Manifest proposal")
        test_states.append(detect_state(tmp_path)["resume_step"])

        # Directories created (user confirmed)
        (tmp_path / "01-backend").mkdir()
        test_states.append(detect_state(tmp_path)["resume_step"])

        # Specs written (complete)
        (tmp_path / "01-backend" / "spec.md").write_text("# Spec")
        test_states.append(detect_state(tmp_path)["resume_step"])

        # Verify steps 3 and 5 are never returned
        assert 3 not in test_states, "Step 3 should never be a valid resume point"
        assert 5 not in test_states, "Step 5 should never be a valid resume point"
        # Valid resume steps are: 1, 2, 4, 6, 7
        assert set(test_states) == {1, 2, 4, 6, 7}
