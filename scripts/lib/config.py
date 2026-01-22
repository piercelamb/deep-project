"""Session configuration management for /deep-project."""

import fcntl
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


class SessionFilename(StrEnum):
    """Session file names for deep-project."""

    CONFIG = "deep_project_config.json"
    STATE = "deep_project_session.json"


# Legacy aliases for backwards compatibility
CONFIG_FILENAME = SessionFilename.CONFIG
SESSION_FILENAME = SessionFilename.STATE


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionConfig:
    """Session configuration data."""

    plugin_root: str
    planning_dir: str
    initial_file: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionConfig":
        """Create from dictionary, validating required fields."""
        required = {"plugin_root", "planning_dir", "initial_file"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(f"Missing required config fields: {missing}")
        return cls(
            plugin_root=data["plugin_root"],
            planning_dir=data["planning_dir"],
            initial_file=data["initial_file"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "plugin_root": self.plugin_root,
            "planning_dir": self.planning_dir,
            "initial_file": self.initial_file,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionState:
    """Session state data - authoritative source for workflow state."""

    input_file_hash: str
    session_created_at: str
    interview_complete: bool
    proposed_splits: list[dict[str, Any]]
    splits_confirmed: bool
    completion_status: dict[str, Any]
    manifest_written: bool
    outcome: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        """Create from dictionary, validating required fields."""
        required = {
            "input_file_hash",
            "interview_complete",
            "proposed_splits",
            "splits_confirmed",
            "manifest_written",
            "outcome",
        }
        missing = required - set(data.keys())
        if missing:
            raise ValueError(f"Missing required state fields: {missing}")
        # Handle legacy field name
        created_at = data.get("session_created_at") or data.get("input_file_mtime", "")
        return cls(
            input_file_hash=data["input_file_hash"],
            session_created_at=created_at,
            interview_complete=data["interview_complete"],
            proposed_splits=data["proposed_splits"],
            splits_confirmed=data["splits_confirmed"],
            completion_status=data.get("completion_status", {}),
            manifest_written=data["manifest_written"],
            outcome=data["outcome"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "input_file_hash": self.input_file_hash,
            "session_created_at": self.session_created_at,
            "interview_complete": self.interview_complete,
            "proposed_splits": list(self.proposed_splits),
            "splits_confirmed": self.splits_confirmed,
            "completion_status": dict(self.completion_status),
            "manifest_written": self.manifest_written,
            "outcome": self.outcome,
        }


def _atomic_write(path: Path, content: str) -> None:
    """Write file atomically using temp file + rename with file locking.

    This ensures that file writes are atomic - either the entire
    content is written or the original file remains unchanged.
    Uses a temp file in the same directory followed by rename.
    File locking prevents concurrent write races.
    """
    path = Path(os.fspath(path))
    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp"
    )
    fd_closed = False
    try:
        # Acquire exclusive lock
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        fd_closed = True
        os.rename(tmp_path, path)
    except Exception:
        if not fd_closed:
            os.close(fd)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def compute_file_hash(file_path: str | Path) -> str:
    """Compute SHA256 hash of file content.

    Returns hash in format: sha256:<hexdigest>
    Used for detecting if input file changed between sessions.
    """
    path = Path(os.fspath(file_path))
    content = path.read_bytes()
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def session_config_path(planning_dir: str | Path) -> Path:
    """Get path to session config file."""
    return Path(os.fspath(planning_dir)) / CONFIG_FILENAME


def session_state_path(planning_dir: str | Path) -> Path:
    """Get path to session state file."""
    return Path(os.fspath(planning_dir)) / SESSION_FILENAME


def session_config_exists(planning_dir: str | Path) -> bool:
    """Check if session config exists."""
    return session_config_path(planning_dir).exists()


def load_session_config(planning_dir: str | Path) -> dict[str, Any]:
    """Load session config from planning directory.

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file contains invalid JSON
    """
    path = session_config_path(planning_dir)
    if not path.exists():
        raise FileNotFoundError(f"No session config at {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupted config file at {path}: {e}")


def save_session_config(planning_dir: str | Path, config: dict[str, Any]) -> None:
    """Save session config atomically."""
    path = session_config_path(planning_dir)
    _atomic_write(path, json.dumps(config, indent=2))


def load_session_state(planning_dir: str | Path) -> dict[str, Any] | None:
    """Load session state, or None if not exists.

    Raises:
        ValueError: If state file contains invalid JSON
    """
    path = session_state_path(planning_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupted session state at {path}: {e}")


def save_session_state(planning_dir: str | Path, state: dict[str, Any]) -> None:
    """Save session state atomically."""
    path = session_state_path(planning_dir)
    _atomic_write(path, json.dumps(state, indent=2))


def create_session_config(
    planning_dir: str | Path,
    plugin_root: str | Path,
    initial_file: str | Path,
) -> dict[str, Any]:
    """Create new session config and save it.

    Args:
        planning_dir: Directory where session files are stored
        plugin_root: Root directory of the plugin
        initial_file: Path to the input requirements file

    Returns:
        The created config dictionary
    """
    config = {
        "plugin_root": str(os.fspath(plugin_root)),
        "planning_dir": str(os.fspath(planning_dir)),
        "initial_file": str(os.fspath(initial_file)),
    }
    save_session_config(planning_dir, config)
    return config


def create_initial_session_state(initial_file: str | Path) -> dict[str, Any]:
    """Create initial session state with file hash.

    This is the authoritative source for workflow state.

    Args:
        initial_file: Path to the input requirements file

    Returns:
        Initial state dictionary with all fields initialized
    """
    return {
        "input_file_hash": compute_file_hash(initial_file),
        "session_created_at": datetime.now(timezone.utc).isoformat(),
        "interview_complete": False,
        "proposed_splits": [],
        "splits_confirmed": False,
        "completion_status": {},
        "manifest_written": False,
        "outcome": None,
    }


def get_or_create_session_config(
    planning_dir: str | Path,
    plugin_root: str | Path,
    initial_file: str | Path,
) -> tuple[dict[str, Any], bool]:
    """Load existing config or create new one.

    Args:
        planning_dir: Directory where session files are stored
        plugin_root: Root directory of the plugin
        initial_file: Path to the input requirements file

    Returns:
        tuple of (config, was_created) where was_created is True
        if a new config was created, False if existing was loaded
    """
    if session_config_exists(planning_dir):
        return load_session_config(planning_dir), False
    return create_session_config(planning_dir, plugin_root, initial_file), True


def check_input_file_changed(
    planning_dir: str | Path, initial_file: str | Path
) -> bool | None:
    """Check if input file has changed since session started.

    Compares current file hash against stored hash in session state.

    Args:
        planning_dir: Directory where session files are stored
        initial_file: Path to the input requirements file

    Returns:
        True if file has changed, False if unchanged, None if no state exists
    """
    state = load_session_state(planning_dir)
    if state is None:
        return None
    current_hash = compute_file_hash(initial_file)
    return current_hash != state.get("input_file_hash")
