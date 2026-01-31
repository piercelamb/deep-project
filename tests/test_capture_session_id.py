"""Tests for capture-session-id.py hook."""

import json
import subprocess
from pathlib import Path

import pytest


def run_hook(payload: dict, env: dict | None = None) -> tuple[int, str, str]:
    """Run the hook script with a JSON payload on stdin."""
    import os

    script_path = Path(__file__).parent.parent / "scripts" / "hooks" / "capture-session-id.py"

    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    result = subprocess.run(
        ["uv", "run", str(script_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=run_env,
        cwd=Path(__file__).parent.parent,
    )

    return result.returncode, result.stdout, result.stderr


class TestCaptureSessionIdHook:
    """Tests for the SessionStart hook."""

    def test_outputs_session_id_as_additional_context(self):
        """Should output session_id via additionalContext."""
        payload = {"session_id": "test-session-123"}

        returncode, stdout, stderr = run_hook(payload)

        assert returncode == 0
        output = json.loads(stdout)
        assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        assert output["hookSpecificOutput"]["additionalContext"] == "DEEP_SESSION_ID=test-session-123"

    def test_succeeds_when_claude_env_file_not_set(self):
        """Should succeed even when CLAUDE_ENV_FILE is not set."""
        payload = {"session_id": "test-session-123"}

        # Run without CLAUDE_ENV_FILE
        returncode, stdout, stderr = run_hook(payload, env={"CLAUDE_ENV_FILE": ""})

        assert returncode == 0
        output = json.loads(stdout)
        assert "DEEP_SESSION_ID" in output["hookSpecificOutput"]["additionalContext"]

    def test_succeeds_when_claude_env_file_empty_string(self):
        """Should succeed when CLAUDE_ENV_FILE is empty string."""
        payload = {"session_id": "test-session-123"}

        returncode, stdout, stderr = run_hook(payload, env={"CLAUDE_ENV_FILE": ""})

        assert returncode == 0

    def test_writes_to_env_file_when_available(self, tmp_path):
        """Should write to CLAUDE_ENV_FILE when available."""
        env_file = tmp_path / "claude_env"
        env_file.write_text("")

        payload = {"session_id": "test-session-123"}

        returncode, stdout, stderr = run_hook(
            payload,
            env={"CLAUDE_ENV_FILE": str(env_file)}
        )

        assert returncode == 0
        env_content = env_file.read_text()
        assert "DEEP_SESSION_ID=test-session-123" in env_content

    def test_invalid_json_succeeds_silently(self):
        """Should return 0 even with invalid JSON input."""
        script_path = Path(__file__).parent.parent / "scripts" / "hooks" / "capture-session-id.py"

        result = subprocess.run(
            ["uv", "run", str(script_path)],
            input="not valid json",
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0

    def test_skips_duplicate_session_id_in_env_file(self, tmp_path):
        """Should not write duplicate session_id to env file."""
        env_file = tmp_path / "claude_env"
        env_file.write_text("export DEEP_SESSION_ID=test-session-123\n")

        payload = {"session_id": "test-session-123"}

        run_hook(payload, env={"CLAUDE_ENV_FILE": str(env_file)})

        # Should not have duplicate
        env_content = env_file.read_text()
        assert env_content.count("DEEP_SESSION_ID=test-session-123") == 1

    def test_missing_session_id_succeeds(self):
        """Should return 0 when payload has no session_id."""
        payload = {"other_field": "value"}

        returncode, stdout, stderr = run_hook(payload)

        assert returncode == 0
        # Should not output anything when no session_id
        assert stdout.strip() == ""

    def test_includes_transcript_path(self, tmp_path):
        """Should write transcript_path to env file when provided."""
        env_file = tmp_path / "claude_env"
        env_file.write_text("")

        payload = {
            "session_id": "test-session-123",
            "transcript_path": "/path/to/transcript.md"
        }

        run_hook(payload, env={"CLAUDE_ENV_FILE": str(env_file)})

        env_content = env_file.read_text()
        assert "CLAUDE_TRANSCRIPT_PATH=/path/to/transcript.md" in env_content

    def test_skips_output_when_deep_session_id_matches(self):
        """Should not output when DEEP_SESSION_ID already matches session_id."""
        payload = {"session_id": "test-session-123"}

        returncode, stdout, stderr = run_hook(
            payload, env={"DEEP_SESSION_ID": "test-session-123"}
        )

        assert returncode == 0
        # Should NOT output additionalContext since it already matches
        assert stdout.strip() == ""

    def test_outputs_when_deep_session_id_differs(self):
        """Should output when DEEP_SESSION_ID exists but doesn't match."""
        payload = {"session_id": "new-session-456"}

        returncode, stdout, stderr = run_hook(
            payload, env={"DEEP_SESSION_ID": "old-session-123"}
        )

        assert returncode == 0
        output = json.loads(stdout)
        assert output["hookSpecificOutput"]["additionalContext"] == "DEEP_SESSION_ID=new-session-456"

    def test_outputs_when_deep_session_id_not_set(self):
        """Should output when DEEP_SESSION_ID is not set."""
        payload = {"session_id": "test-session-789"}

        # Explicitly don't set DEEP_SESSION_ID
        returncode, stdout, stderr = run_hook(payload, env={})

        assert returncode == 0
        output = json.loads(stdout)
        assert output["hookSpecificOutput"]["additionalContext"] == "DEEP_SESSION_ID=test-session-789"
