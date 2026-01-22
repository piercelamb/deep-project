# tests/test_config.py
"""Tests for session configuration management module."""

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
    session_config_path,
    session_state_path,
    session_config_exists,
    load_session_config,
    save_session_config,
    load_session_state,
    save_session_state,
    create_session_config,
    create_initial_session_state,
    get_or_create_session_config,
    check_input_file_changed,
    CONFIG_FILENAME,
    SESSION_FILENAME,
    SessionFilename,
    SessionConfig,
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


class TestSessionConfig:
    """Tests for session config management."""

    def test_session_config_path(self, tmp_path):
        """Should return correct path to config file."""
        path = session_config_path(str(tmp_path))
        assert path == tmp_path / CONFIG_FILENAME

    def test_session_state_path(self, tmp_path):
        """Should return correct path to state file."""
        path = session_state_path(str(tmp_path))
        assert path == tmp_path / SESSION_FILENAME

    def test_session_config_exists_false(self, tmp_path):
        """Should return False when no config exists."""
        assert session_config_exists(str(tmp_path)) is False

    def test_session_config_exists_true(self, tmp_path):
        """Should return True when config exists."""
        (tmp_path / CONFIG_FILENAME).write_text('{}')
        assert session_config_exists(str(tmp_path)) is True

    def test_creates_new_config(self, tmp_path):
        """Should create config file when none exists."""
        config = create_session_config(
            planning_dir=str(tmp_path),
            plugin_root="/plugin",
            initial_file=str(tmp_path / "spec.md")
        )

        assert (tmp_path / CONFIG_FILENAME).exists()
        assert config["plugin_root"] == "/plugin"
        assert config["planning_dir"] == str(tmp_path)

    def test_loads_existing_config(self, tmp_path):
        """Should load existing config without modification."""
        config_data = {"key": "value", "nested": {"a": 1}}
        (tmp_path / CONFIG_FILENAME).write_text(json.dumps(config_data))

        loaded = load_session_config(str(tmp_path))

        assert loaded == config_data

    def test_handles_corrupted_json(self, tmp_path):
        """Should raise ValueError for corrupted config."""
        (tmp_path / CONFIG_FILENAME).write_text("not valid json {{{")

        with pytest.raises(ValueError) as exc_info:
            load_session_config(str(tmp_path))

        assert "Corrupted" in str(exc_info.value)

    def test_raises_for_missing_config(self, tmp_path):
        """Should raise FileNotFoundError when loading missing config."""
        with pytest.raises(FileNotFoundError):
            load_session_config(str(tmp_path))

    def test_get_or_create_returns_was_created_true(self, tmp_path):
        """Should return (config, True) when creating new config."""
        input_file = tmp_path / "spec.md"
        input_file.write_text("# Test")

        config, was_created = get_or_create_session_config(
            planning_dir=str(tmp_path),
            plugin_root="/plugin",
            initial_file=str(input_file)
        )

        assert was_created is True
        assert config["plugin_root"] == "/plugin"

    def test_get_or_create_returns_was_created_false(self, tmp_path):
        """Should return (config, False) when config exists."""
        existing_config = {"existing": "config"}
        (tmp_path / CONFIG_FILENAME).write_text(json.dumps(existing_config))

        config, was_created = get_or_create_session_config(
            planning_dir=str(tmp_path),
            plugin_root="/plugin",
            initial_file=str(tmp_path / "spec.md")
        )

        assert was_created is False
        assert config == existing_config


class TestSessionState:
    """Tests for session state management."""

    def test_returns_none_if_no_state(self, tmp_path):
        """Should return None if no session state file."""
        result = load_session_state(str(tmp_path))
        assert result is None

    def test_loads_existing_state(self, tmp_path):
        """Should load state from file."""
        state_data = {
            "interview_complete": True,
            "proposed_splits": [{"index": 1, "dir_name": "01-test"}]
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

    def test_creates_initial_state_with_hash(self, tmp_path):
        """Initial state should include file hash."""
        input_file = tmp_path / "requirements.md"
        input_file.write_text("# Requirements")

        state = create_initial_session_state(str(input_file))

        assert "input_file_hash" in state
        assert state["input_file_hash"].startswith("sha256:")
        assert "session_created_at" in state
        assert state["interview_complete"] is False
        assert state["proposed_splits"] == []
        assert state["splits_confirmed"] is False
        assert state["manifest_written"] is False
        assert state["outcome"] is None


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

    def test_config_value(self):
        """CONFIG should be correct filename."""
        assert SessionFilename.CONFIG == "deep_project_config.json"

    def test_state_value(self):
        """STATE should be correct filename."""
        assert SessionFilename.STATE == "deep_project_session.json"

    def test_is_string(self):
        """StrEnum values should be usable as strings."""
        assert isinstance(SessionFilename.CONFIG, str)
        path = Path("/tmp") / SessionFilename.CONFIG
        assert str(path) == "/tmp/deep_project_config.json"


class TestSessionConfigDataclass:
    """Tests for SessionConfig dataclass."""

    def test_from_dict_valid(self):
        """Should create SessionConfig from valid dict."""
        data = {
            "plugin_root": "/plugin",
            "planning_dir": "/planning",
            "initial_file": "/planning/spec.md",
        }

        config = SessionConfig.from_dict(data)

        assert config.plugin_root == "/plugin"
        assert config.planning_dir == "/planning"
        assert config.initial_file == "/planning/spec.md"

    def test_from_dict_missing_field(self):
        """Should raise ValueError if required field missing."""
        data = {"plugin_root": "/plugin"}

        with pytest.raises(ValueError) as exc_info:
            SessionConfig.from_dict(data)

        assert "Missing required config fields" in str(exc_info.value)

    def test_to_dict(self):
        """Should convert to dict for serialization."""
        config = SessionConfig(
            plugin_root="/plugin",
            planning_dir="/planning",
            initial_file="/planning/spec.md",
        )

        result = config.to_dict()

        assert result == {
            "plugin_root": "/plugin",
            "planning_dir": "/planning",
            "initial_file": "/planning/spec.md",
        }


class TestSessionStateDataclass:
    """Tests for SessionState dataclass."""

    def test_from_dict_valid(self):
        """Should create SessionState from valid dict."""
        data = {
            "input_file_hash": "sha256:abc123",
            "session_created_at": "2024-01-01T00:00:00Z",
            "interview_complete": True,
            "proposed_splits": [{"index": 1}],
            "splits_confirmed": True,
            "completion_status": {"01": {"done": True}},
            "manifest_written": False,
            "outcome": "splitting",
        }

        state = SessionState.from_dict(data)

        assert state.input_file_hash == "sha256:abc123"
        assert state.interview_complete is True
        assert state.outcome == "splitting"

    def test_from_dict_legacy_mtime_field(self):
        """Should handle legacy input_file_mtime field name."""
        data = {
            "input_file_hash": "sha256:abc123",
            "input_file_mtime": "2024-01-01T00:00:00Z",
            "interview_complete": False,
            "proposed_splits": [],
            "splits_confirmed": False,
            "manifest_written": False,
            "outcome": None,
        }

        state = SessionState.from_dict(data)

        assert state.session_created_at == "2024-01-01T00:00:00Z"

    def test_from_dict_missing_field(self):
        """Should raise ValueError if required field missing."""
        data = {"input_file_hash": "sha256:abc123"}

        with pytest.raises(ValueError) as exc_info:
            SessionState.from_dict(data)

        assert "Missing required state fields" in str(exc_info.value)

    def test_to_dict(self):
        """Should convert to dict for serialization."""
        state = SessionState(
            input_file_hash="sha256:abc",
            session_created_at="2024-01-01T00:00:00Z",
            interview_complete=False,
            proposed_splits=[],
            splits_confirmed=False,
            completion_status={},
            manifest_written=False,
            outcome=None,
        )

        result = state.to_dict()

        assert result["input_file_hash"] == "sha256:abc"
        assert result["session_created_at"] == "2024-01-01T00:00:00Z"
        assert result["outcome"] is None
