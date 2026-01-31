"""Tests for task_reconciliation.py module."""

from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.task_reconciliation import TaskListContext, TaskListSource


class TestTaskListSource:
    """Tests for TaskListSource enum."""

    def test_context_value(self):
        assert TaskListSource.CONTEXT == "context"

    def test_user_env_value(self):
        assert TaskListSource.USER_ENV == "user_env"

    def test_session_value(self):
        assert TaskListSource.SESSION == "session"

    def test_none_value(self):
        assert TaskListSource.NONE == "none"


class TestTaskListContext:
    """Tests for TaskListContext.from_args_and_env()."""

    def test_session_id_from_arg_takes_precedence(self, monkeypatch):
        """--session-id arg should take precedence over env vars."""
        monkeypatch.setenv("DEEP_SESSION_ID", "env-session")
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "user-task-list")

        ctx = TaskListContext.from_args_and_env(context_session_id="arg-session")

        assert ctx.task_list_id == "arg-session"
        assert ctx.source == TaskListSource.CONTEXT
        assert ctx.is_user_specified is False

    def test_session_id_matched_true_when_same(self, monkeypatch):
        """session_id_matched should be True when context and env match."""
        monkeypatch.setenv("DEEP_SESSION_ID", "same-session")

        ctx = TaskListContext.from_args_and_env(context_session_id="same-session")

        assert ctx.session_id_matched is True

    def test_session_id_matched_false_when_different(self, monkeypatch):
        """session_id_matched should be False when context and env differ (after /clear)."""
        monkeypatch.setenv("DEEP_SESSION_ID", "old-session")

        ctx = TaskListContext.from_args_and_env(context_session_id="new-session")

        assert ctx.session_id_matched is False

    def test_session_id_matched_none_when_single_source(self, monkeypatch):
        """session_id_matched should be None when only one source available."""
        monkeypatch.delenv("DEEP_SESSION_ID", raising=False)

        ctx = TaskListContext.from_args_and_env(context_session_id="arg-session")

        assert ctx.session_id_matched is None

    def test_falls_back_to_env_when_no_arg(self, monkeypatch):
        """Should use DEEP_SESSION_ID when no --session-id arg."""
        monkeypatch.setenv("DEEP_SESSION_ID", "env-session")
        monkeypatch.delenv("CLAUDE_CODE_TASK_LIST_ID", raising=False)

        ctx = TaskListContext.from_args_and_env(context_session_id=None)

        assert ctx.task_list_id == "env-session"
        assert ctx.source == TaskListSource.SESSION
        assert ctx.is_user_specified is False

    def test_user_env_takes_precedence_over_session_env(self, monkeypatch):
        """CLAUDE_CODE_TASK_LIST_ID should take precedence over DEEP_SESSION_ID."""
        monkeypatch.setenv("DEEP_SESSION_ID", "session-id")
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "user-task-list")

        ctx = TaskListContext.from_args_and_env(context_session_id=None)

        assert ctx.task_list_id == "user-task-list"
        assert ctx.source == TaskListSource.USER_ENV
        assert ctx.is_user_specified is True

    def test_returns_none_when_no_sources(self, monkeypatch):
        """Should return None task_list_id when no session ID available."""
        monkeypatch.delenv("DEEP_SESSION_ID", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_TASK_LIST_ID", raising=False)

        ctx = TaskListContext.from_args_and_env(context_session_id=None)

        assert ctx.task_list_id is None
        assert ctx.source == TaskListSource.NONE
        assert ctx.is_user_specified is False

    def test_context_arg_overrides_user_env(self, monkeypatch):
        """--session-id should override even CLAUDE_CODE_TASK_LIST_ID."""
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "user-task-list")

        ctx = TaskListContext.from_args_and_env(context_session_id="arg-session")

        assert ctx.task_list_id == "arg-session"
        assert ctx.source == TaskListSource.CONTEXT
        # When using context, is_user_specified is False
        assert ctx.is_user_specified is False
