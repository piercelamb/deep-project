# tests/test_create_split_dirs.py
"""Tests for create-split-dirs.py script."""

import json
import subprocess
from pathlib import Path

import pytest


def run_create_split_dirs(planning_dir: Path) -> dict:
    """Helper to run create-split-dirs.py and return parsed output."""
    result = subprocess.run(
        [
            "uv", "run", "scripts/checks/create-split-dirs.py",
            "--planning-dir", str(planning_dir)
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    return json.loads(result.stdout)


@pytest.mark.integration
class TestCreateSplitDirs:
    """Integration tests for create-split-dirs.py."""

    def test_creates_directories_from_manifest(self, tmp_path):
        """Should create directories listed in manifest."""
        # Create manifest with valid SPLIT_MANIFEST block
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-backend
02-frontend
END_MANIFEST -->

# Project Manifest
""")

        output = run_create_split_dirs(tmp_path)

        assert output["success"] is True
        assert output["created"] == ["01-backend", "02-frontend"]
        assert output["skipped"] == []
        assert (tmp_path / "01-backend").is_dir()
        assert (tmp_path / "02-frontend").is_dir()

    def test_skips_existing_directories(self, tmp_path):
        """Should skip directories that already exist."""
        # Create manifest
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-backend
02-frontend
END_MANIFEST -->""")

        # Pre-create one directory
        (tmp_path / "01-backend").mkdir()

        output = run_create_split_dirs(tmp_path)

        assert output["success"] is True
        assert output["created"] == ["02-frontend"]
        assert output["skipped"] == ["01-backend"]

    def test_all_directories_exist(self, tmp_path):
        """Should report all skipped when all dirs exist."""
        # Create manifest
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-backend
02-frontend
END_MANIFEST -->""")

        # Pre-create all directories
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "02-frontend").mkdir()

        output = run_create_split_dirs(tmp_path)

        assert output["success"] is True
        assert output["created"] == []
        assert output["skipped"] == ["01-backend", "02-frontend"]

    def test_fails_without_manifest(self, tmp_path):
        """Should fail when manifest doesn't exist."""
        output = run_create_split_dirs(tmp_path)

        assert output["success"] is False
        assert "not found" in output["error"].lower() or "errors" in output

    def test_fails_with_invalid_manifest(self, tmp_path):
        """Should fail when manifest has invalid format."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("# No SPLIT_MANIFEST block here")

        output = run_create_split_dirs(tmp_path)

        assert output["success"] is False
        assert "errors" in output or "error" in output

    def test_fails_with_invalid_split_names(self, tmp_path):
        """Should fail when manifest has invalid split names."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
1-bad-prefix
END_MANIFEST -->""")

        output = run_create_split_dirs(tmp_path)

        assert output["success"] is False
        assert "errors" in output

    def test_fails_with_nonexistent_planning_dir(self, tmp_path):
        """Should fail when planning directory doesn't exist."""
        nonexistent = tmp_path / "nonexistent"

        output = run_create_split_dirs(nonexistent)

        assert output["success"] is False
        assert "not found" in output["error"].lower()

    def test_single_split_project(self, tmp_path):
        """Should handle single-split projects."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-my-project
END_MANIFEST -->""")

        output = run_create_split_dirs(tmp_path)

        assert output["success"] is True
        assert output["created"] == ["01-my-project"]
        assert (tmp_path / "01-my-project").is_dir()

    def test_returns_manifest_splits_list(self, tmp_path):
        """Should return full manifest_splits list in output."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-backend
02-frontend
03-shared
END_MANIFEST -->""")

        output = run_create_split_dirs(tmp_path)

        assert output["success"] is True
        assert output["manifest_splits"] == ["01-backend", "02-frontend", "03-shared"]

    def test_json_output_format(self, tmp_path):
        """Should return valid JSON with expected fields."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-backend
END_MANIFEST -->""")

        output = run_create_split_dirs(tmp_path)

        assert "success" in output
        assert "created" in output
        assert "skipped" in output
        assert "manifest_splits" in output
        assert "message" in output
