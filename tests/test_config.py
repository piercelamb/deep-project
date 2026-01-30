# tests/test_config.py
"""Tests for session state management module.

Design principle: Session JSON is minimal, state derived from files.
"""

import json
import os
import threading
import time
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from lib.config import (
    _atomic_write,
    compute_file_hash,
    session_state_path,
    session_state_exists,
    load_session_state,
    save_session_state,
    create_initial_session_state,
    check_input_file_changed,
    SESSION_FILENAME,
    SessionFilename,
    SessionState,
)


class TestAtomicWrite:
    """Tests for atomic file writing."""

    def test_writes_file_successfully(self, tmp_path):
        """Should write content to file."""
        file_path = tmp_path / "test.txt"
        content = "Hello, world!"

        _atomic_write(file_path, content)

        assert file_path.exists()
        assert file_path.read_text() == content

    def test_atomic_on_failure_preserves_original(self, tmp_path):
        """Should preserve original file if write fails mid-operation."""
        # Create a file in a directory we'll make read-only
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_file = readonly_dir / "test.txt"
        original_content = "original"
        readonly_file.write_text(original_content)

        # Make directory read-only to prevent temp file creation
        os.chmod(readonly_dir, 0o555)
        try:
            with pytest.raises(PermissionError):
                _atomic_write(readonly_file, "new content")
            # Restore permissions to read
            os.chmod(readonly_dir, 0o755)
            # Original should be unchanged
            assert readonly_file.read_text() == original_content
        finally:
            os.chmod(readonly_dir, 0o755)

    def test_no_temp_file_left_on_success(self, tmp_path):
        """Should clean up temp file after successful write."""
        file_path = tmp_path / "test.txt"
        _atomic_write(file_path, "content")

        # Check no temp files left
        temp_files = list(tmp_path.glob(".test.txt.*"))
        assert len(temp_files) == 0

    def test_no_temp_file_left_on_failure(self, tmp_path):
        """Should clean up temp file if rename fails."""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_file = readonly_dir / "test.txt"
        readonly_file.write_text("original")

        os.chmod(readonly_dir, 0o444)
        try:
            with pytest.raises(PermissionError):
                _atomic_write(readonly_file, "new content")
            # Temp files should be cleaned up
            temp_files = list(tmp_path.glob("**/.test.txt.*"))
            assert len(temp_files) == 0
        finally:
            os.chmod(readonly_dir, 0o755)


class TestConcurrentAccess:
    """Tests for concurrent file access with locking."""

    def test_concurrent_writes_do_not_corrupt(self, tmp_path):
        """Multiple concurrent writes should not corrupt file."""
        file_path = tmp_path / "concurrent.txt"
        results = []
        errors = []

        def writer(value: str, delay: float):
            try:
                time.sleep(delay)
                _atomic_write(file_path, value)
                results.append(value)
            except Exception as e:
                errors.append(e)

        # Start multiple threads writing different values
        threads = [
            threading.Thread(target=writer, args=(f"value-{i}", i * 0.01))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # File should have one of the values (last writer wins)
        content = file_path.read_text()
        assert content.startswith("value-")
        # Content should not be corrupted/mixed
        assert content in [f"value-{i}" for i in range(5)]

    def test_lock_serializes_writes(self, tmp_path):
        """File locking should serialize concurrent write attempts."""
        file_path = tmp_path / "locked.txt"
        write_order = []

        def writer(value: str):
            _atomic_write(file_path, value)
            write_order.append(value)

        threads = [
            threading.Thread(target=writer, args=(f"w{i}",))
            for i in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All writes should complete
        assert len(write_order) == 3
        # Final content should match last write
        assert file_path.read_text() == write_order[-1]


class TestComputeFileHash:
    """Tests for file hash computation."""

    def test_returns_sha256_format(self, tmp_path):
        """Should return sha256:hexdigest format."""
        file_path = tmp_path / "test.md"
        file_path.write_text("test content")

        result = compute_file_hash(str(file_path))

        assert result.startswith("sha256:")
        assert len(result) == 7 + 64  # "sha256:" + 64 hex chars

    def test_same_content_same_hash(self, tmp_path):
        """Same content should produce same hash."""
        file1 = tmp_path / "file1.md"
        file2 = tmp_path / "file2.md"
        file1.write_text("identical content")
        file2.write_text("identical content")

        assert compute_file_hash(str(file1)) == compute_file_hash(str(file2))

    def test_different_content_different_hash(self, tmp_path):
        """Different content should produce different hash."""
        file1 = tmp_path / "file1.md"
        file2 = tmp_path / "file2.md"
        file1.write_text("content A")
        file2.write_text("content B")

        assert compute_file_hash(str(file1)) != compute_file_hash(str(file2))


class TestSessionState:
    """Tests for session state management."""

    def test_session_state_path(self, tmp_path):
        """Should return correct path to state file."""
        path = session_state_path(str(tmp_path))
        assert path == tmp_path / SESSION_FILENAME

    def test_session_state_exists_false(self, tmp_path):
        """Should return False when no state exists."""
        assert session_state_exists(str(tmp_path)) is False

    def test_session_state_exists_true(self, tmp_path):
        """Should return True when state exists."""
        (tmp_path / SESSION_FILENAME).write_text('{}')
        assert session_state_exists(str(tmp_path)) is True

    def test_returns_none_if_no_state(self, tmp_path):
        """Should return None if no session state file."""
        result = load_session_state(str(tmp_path))
        assert result is None

    def test_loads_existing_state(self, tmp_path):
        """Should load state from file."""
        state_data = {
            "input_file_hash": "sha256:abc",
            "session_created_at": "2024-01-01T00:00:00Z",
        }
        (tmp_path / SESSION_FILENAME).write_text(json.dumps(state_data))

        loaded = load_session_state(str(tmp_path))

        assert loaded == state_data

    def test_saves_state_atomically(self, tmp_path):
        """Should save state to file atomically."""
        state = {"test": "value"}

        save_session_state(str(tmp_path), state)

        assert (tmp_path / SESSION_FILENAME).exists()
        loaded = json.loads((tmp_path / SESSION_FILENAME).read_text())
        assert loaded == state

    def test_handles_corrupted_state(self, tmp_path):
        """Should raise ValueError for corrupted state file."""
        (tmp_path / SESSION_FILENAME).write_text("not valid json")

        with pytest.raises(ValueError) as exc_info:
            load_session_state(str(tmp_path))

        assert "Corrupted" in str(exc_info.value)

    def test_creates_initial_state_minimal(self, tmp_path):
        """Initial state should be minimal with file hash."""
        input_file = tmp_path / "requirements.md"
        input_file.write_text("# Requirements")

        state = create_initial_session_state(str(input_file))

        # Only these fields should exist
        assert set(state.keys()) == {"input_file_hash", "session_created_at"}
        assert state["input_file_hash"].startswith("sha256:")
        assert "session_created_at" in state


class TestInputFileChanged:
    """Tests for detecting input file changes."""

    def test_detects_unchanged(self, tmp_path):
        """Should return False if file unchanged."""
        input_file = tmp_path / "requirements.md"
        input_file.write_text("# Requirements")

        # Create state with current hash
        state = create_initial_session_state(str(input_file))
        save_session_state(str(tmp_path), state)

        result = check_input_file_changed(str(tmp_path), str(input_file))

        assert result is False

    def test_detects_changed(self, tmp_path):
        """Should return True if file content changed."""
        input_file = tmp_path / "requirements.md"
        input_file.write_text("# Original Requirements")

        # Create state with original hash
        state = create_initial_session_state(str(input_file))
        save_session_state(str(tmp_path), state)

        # Modify the file
        input_file.write_text("# Modified Requirements")

        result = check_input_file_changed(str(tmp_path), str(input_file))

        assert result is True

    def test_returns_none_if_no_state(self, tmp_path):
        """Should return None if no previous state."""
        input_file = tmp_path / "requirements.md"
        input_file.write_text("# Requirements")

        result = check_input_file_changed(str(tmp_path), str(input_file))

        assert result is None


class TestSessionFilenameEnum:
    """Tests for SessionFilename StrEnum."""

    def test_state_value(self):
        """STATE should be correct filename."""
        assert SessionFilename.STATE == "deep_project_session.json"

    def test_interview_value(self):
        """INTERVIEW should be correct filename."""
        assert SessionFilename.INTERVIEW == "deep_project_interview.md"

    def test_manifest_value(self):
        """MANIFEST should be correct filename."""
        assert SessionFilename.MANIFEST == "project-manifest.md"

    def test_is_string(self):
        """StrEnum values should be usable as strings."""
        assert isinstance(SessionFilename.STATE, str)
        path = Path("/tmp") / SessionFilename.STATE
        assert str(path) == "/tmp/deep_project_session.json"


class TestSessionStateDataclass:
    """Tests for SessionState dataclass."""

    def test_from_dict_minimal(self):
        """Should create SessionState from minimal dict."""
        data = {
            "input_file_hash": "sha256:abc123",
            "session_created_at": "2024-01-01T00:00:00Z",
        }

        state = SessionState.from_dict(data)

        assert state.input_file_hash == "sha256:abc123"
        assert state.session_created_at == "2024-01-01T00:00:00Z"

    def test_from_dict_legacy_mtime_field(self):
        """Should handle legacy input_file_mtime field name."""
        data = {
            "input_file_hash": "sha256:abc123",
            "input_file_mtime": "2024-01-01T00:00:00Z",
        }

        state = SessionState.from_dict(data)

        assert state.session_created_at == "2024-01-01T00:00:00Z"

    def test_to_dict(self):
        """Should convert to dict for serialization."""
        state = SessionState(
            input_file_hash="sha256:abc",
            session_created_at="2024-01-01T00:00:00Z",
        )

        result = state.to_dict()

        assert result["input_file_hash"] == "sha256:abc"
        assert result["session_created_at"] == "2024-01-01T00:00:00Z"
