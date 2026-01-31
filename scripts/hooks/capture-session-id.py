#!/usr/bin/env python3
"""Capture session_id and expose it via Claude's context.

This hook reads session_id from the JSON payload on stdin and:
1. Outputs it to stdout as additionalContext (Claude sees this directly)
2. Optionally writes to CLAUDE_ENV_FILE if available (fallback for bash)
"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # Hooks should never fail
    except Exception:
        return 0

    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")

    if not session_id:
        return 0

    # Check if DEEP_SESSION_ID is already set correctly
    existing_session_id = os.environ.get("DEEP_SESSION_ID")
    if existing_session_id != session_id:
        # Not set or doesn't match - output to Claude's context via additionalContext
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": f"DEEP_SESSION_ID={session_id}",
            }
        }
        print(json.dumps(output))

    # SECONDARY: Also try CLAUDE_ENV_FILE for bash commands (may not work)
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if env_file:
        try:
            existing_content = ""
            try:
                with open(env_file) as f:
                    existing_content = f.read()
            except FileNotFoundError:
                pass

            lines_to_write = []
            if f"DEEP_SESSION_ID={session_id}" not in existing_content:
                lines_to_write.append(f"export DEEP_SESSION_ID={session_id}\n")
            if (
                transcript_path
                and f"CLAUDE_TRANSCRIPT_PATH={transcript_path}" not in existing_content
            ):
                lines_to_write.append(
                    f"export CLAUDE_TRANSCRIPT_PATH={transcript_path}\n"
                )

            if lines_to_write:
                with open(env_file, "a") as f:
                    f.writelines(lines_to_write)
        except OSError:
            pass  # CLAUDE_ENV_FILE failed, but we already output to context

    return 0


if __name__ == "__main__":
    sys.exit(main())
