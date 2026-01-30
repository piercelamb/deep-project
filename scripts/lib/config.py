"""Session state management for /deep-project.

Design principle: Files are checkpoints, JSON is minimal.

The session.json stores only:
- input_file_hash: Detect if requirements changed
- session_created_at: When session started

Everything else is derived from file existence:
- Interview complete: deep_project_interview.md exists
- Manifest created: project-manifest.md exists (Claude's proposal)
- Directories created: NN-name/ directories exist (user confirmed)
- Specs written: spec.md in each directory
"""

import fcntl
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Self


class SessionFilename(StrEnum):
    """Session file names for deep-project."""

    STATE = "deep_project_session.json"
    INTERVIEW = "deep_project_interview.md"
    MANIFEST = "project-manifest.md"


# Legacy alias for backwards compatibility
SESSION_FILENAME = SessionFilename.STATE


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionState:
    """Minimal session state - only what can't be derived from files.

    Everything else (interview_complete, manifest_created, directories_created,
    specs_written) is derived from file existence by detect_state().
    """

    input_file_hash: str
    session_created_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create from dictionary, handling both old and new formats."""
        # Handle legacy field name
        created_at = data.get("session_created_at") or data.get("input_file_mtime", "")

        return cls(
            input_file_hash=data.get("input_file_hash", ""),
            session_created_at=created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "input_file_hash": self.input_file_hash,
            "session_created_at": self.session_created_at,
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


def session_state_path(planning_dir: str | Path) -> Path:
    """Get path to session state file."""
    return Path(os.fspath(planning_dir)) / SESSION_FILENAME


def session_state_exists(planning_dir: str | Path) -> bool:
    """Check if session state exists."""
    return session_state_path(planning_dir).exists()


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


def create_initial_session_state(initial_file: str | Path) -> dict[str, Any]:
    """Create initial session state with file hash.

    Returns minimal state - only what can't be derived from files.

    Args:
        initial_file: Path to the input requirements file

    Returns:
        Initial state dictionary with minimal fields
    """
    return {
        "input_file_hash": compute_file_hash(initial_file),
        "session_created_at": datetime.now(timezone.utc).isoformat(),
    }


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
