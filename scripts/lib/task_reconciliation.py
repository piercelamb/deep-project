"""Task list context resolution for Claude Code task system.

Determines where tasks should be written based on CLI arguments and
environment variables. Handles the complexity of session ID sources
and provides diagnostics for debugging /clear reset issues.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Self


class TaskListSource(StrEnum):
    """Source of the task list ID."""

    CONTEXT = "context"  # From --session-id arg (hook's additionalContext)
    USER_ENV = "user_env"  # From CLAUDE_CODE_TASK_LIST_ID
    SESSION = "session"  # From CLAUDE_SESSION_ID env var
    NONE = "none"  # No task list ID available


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskListContext:
    """Context for task list operations.

    Attributes:
        task_list_id: The resolved task list ID, or None if unavailable
        source: Where the task list ID came from
        is_user_specified: True if user explicitly set CLAUDE_CODE_TASK_LIST_ID
        session_id_matched: Diagnostic field - if both context and env present,
            did they match? True = normal, False = after /clear reset, None = single source
    """

    task_list_id: str | None
    source: TaskListSource
    is_user_specified: bool
    session_id_matched: bool | None = None

    @classmethod
    def from_args_and_env(cls, context_session_id: str | None = None) -> Self:
        """Get task list context from CLI args and environment.

        Priority order:
        1. --session-id (context) - from hook's additionalContext, most reliable
        2. CLAUDE_CODE_TASK_LIST_ID - user-specified, takes precedence over auto
        3. CLAUDE_SESSION_ID - env var, may be stale after /clear

        Args:
            context_session_id: Session ID from --session-id arg (passed by Claude
                from hook context)

        Returns:
            TaskListContext with resolved task_list_id and source
        """
        env_session_id = os.environ.get("CLAUDE_SESSION_ID")
        user_specified = os.environ.get("CLAUDE_CODE_TASK_LIST_ID")

        # Track if context and env matched (useful for debugging /clear issues)
        session_id_matched: bool | None = None
        if context_session_id and env_session_id:
            session_id_matched = context_session_id == env_session_id

        # Priority 1: --session-id from hook's additionalContext (most reliable)
        if context_session_id:
            return cls(
                task_list_id=context_session_id,
                source=TaskListSource.CONTEXT,
                is_user_specified=False,
                session_id_matched=session_id_matched,
            )

        # Priority 2: User-specified task list ID
        if user_specified:
            return cls(
                task_list_id=user_specified,
                source=TaskListSource.USER_ENV,
                is_user_specified=True,
            )

        # Priority 3: Session ID from env var (may be stale after /clear)
        if env_session_id:
            return cls(
                task_list_id=env_session_id,
                source=TaskListSource.SESSION,
                is_user_specified=False,
            )

        return cls(
            task_list_id=None,
            source=TaskListSource.NONE,
            is_user_specified=False,
        )
