# tests/test_manifest.py
"""Tests for manifest parsing module."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from lib.manifest import parse_manifest, ParsedManifest, MANIFEST_BLOCK_PATTERN


class TestParsedManifest:
    """Tests for ParsedManifest dataclass."""

    def test_is_valid_with_no_errors(self):
        """Should be valid when errors list is empty."""
        result = ParsedManifest(splits=["01-backend"], errors=[])
        assert result.is_valid is True

    def test_is_invalid_with_errors(self):
        """Should be invalid when errors list has items."""
        result = ParsedManifest(splits=[], errors=["Some error"])
        assert result.is_valid is False

    def test_error_factory(self):
        """Error factory should create single-error result."""
        result = ParsedManifest.error("Test error")
        assert result.is_valid is False
        assert result.errors == ["Test error"]
        assert result.splits == []


class TestManifestBlockPattern:
    """Tests for the SPLIT_MANIFEST block regex."""

    def test_matches_valid_block(self):
        """Should match valid SPLIT_MANIFEST block."""
        content = """<!-- SPLIT_MANIFEST
01-backend
02-frontend
END_MANIFEST -->

# Project Manifest
"""
        match = MANIFEST_BLOCK_PATTERN.search(content)
        assert match is not None
        assert "01-backend" in match.group(1)
        assert "02-frontend" in match.group(1)

    def test_matches_with_extra_whitespace(self):
        """Should match block with varying whitespace."""
        content = """<!--  SPLIT_MANIFEST
01-backend
END_MANIFEST  -->"""
        match = MANIFEST_BLOCK_PATTERN.search(content)
        assert match is not None

    def test_no_match_without_block(self):
        """Should not match content without block."""
        content = "# Project Manifest\n\nNo block here."
        match = MANIFEST_BLOCK_PATTERN.search(content)
        assert match is None


class TestParseManifest:
    """Tests for parse_manifest function."""

    def test_file_not_found(self, tmp_path):
        """Should return error for non-existent file."""
        result = parse_manifest(tmp_path / "nonexistent.md")
        assert result.is_valid is False
        assert "not found" in result.errors[0]

    def test_no_manifest_block(self, tmp_path):
        """Should return error when no SPLIT_MANIFEST block."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("# Project Manifest\n\nNo block here.")

        result = parse_manifest(manifest)
        assert result.is_valid is False
        assert "No SPLIT_MANIFEST block found" in result.errors[0]

    def test_empty_manifest_block(self, tmp_path):
        """Should return error for empty block."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST

END_MANIFEST -->""")

        result = parse_manifest(manifest)
        assert result.is_valid is False
        assert "empty" in result.errors[0].lower()

    def test_valid_single_split(self, tmp_path):
        """Should parse single split successfully."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-backend
END_MANIFEST -->

# Project Manifest
""")

        result = parse_manifest(manifest)
        assert result.is_valid is True
        assert result.splits == ["01-backend"]

    def test_valid_multiple_splits(self, tmp_path):
        """Should parse multiple splits successfully."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-backend
02-frontend
03-shared-utils
END_MANIFEST -->

# Project Manifest
""")

        result = parse_manifest(manifest)
        assert result.is_valid is True
        assert result.splits == ["01-backend", "02-frontend", "03-shared-utils"]

    def test_invalid_split_name_single_digit(self, tmp_path):
        """Should reject single-digit prefix."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
1-backend
END_MANIFEST -->""")

        result = parse_manifest(manifest)
        assert result.is_valid is False
        assert "Invalid split name" in result.errors[0]

    def test_invalid_split_name_uppercase(self, tmp_path):
        """Should reject uppercase letters."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-Backend
END_MANIFEST -->""")

        result = parse_manifest(manifest)
        assert result.is_valid is False
        assert "Invalid split name" in result.errors[0]

    def test_invalid_split_name_underscore(self, tmp_path):
        """Should reject underscores."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-back_end
END_MANIFEST -->""")

        result = parse_manifest(manifest)
        assert result.is_valid is False
        assert "Invalid split name" in result.errors[0]

    def test_duplicate_indices(self, tmp_path):
        """Should detect duplicate split indices."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-backend
01-frontend
END_MANIFEST -->""")

        result = parse_manifest(manifest)
        assert result.is_valid is False
        assert "Duplicate index" in result.errors[0]

    def test_non_sequential_indices(self, tmp_path):
        """Should detect non-sequential indices."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-backend
03-frontend
END_MANIFEST -->""")

        result = parse_manifest(manifest)
        assert result.is_valid is False
        assert "sequential" in result.errors[0].lower()

    def test_ignores_content_after_block(self, tmp_path):
        """Should only parse the manifest block, ignoring rest."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-backend
02-frontend
END_MANIFEST -->

# Project Manifest

## Overview
This could contain anything, including invalid split names like 1-bad
or ## random content.

## Commands
/deep-plan @01-backend/spec.md
""")

        result = parse_manifest(manifest)
        assert result.is_valid is True
        assert result.splits == ["01-backend", "02-frontend"]

    def test_handles_blank_lines_in_block(self, tmp_path):
        """Should handle blank lines within the block."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-backend

02-frontend
END_MANIFEST -->""")

        result = parse_manifest(manifest)
        assert result.is_valid is True
        assert result.splits == ["01-backend", "02-frontend"]

    def test_valid_complex_names(self, tmp_path):
        """Should accept valid complex kebab-case names."""
        manifest = tmp_path / "project-manifest.md"
        manifest.write_text("""<!-- SPLIT_MANIFEST
01-api-gateway-v2
02-user-management-service
03-auth
END_MANIFEST -->""")

        result = parse_manifest(manifest)
        assert result.is_valid is True
        assert result.splits == [
            "01-api-gateway-v2",
            "02-user-management-service",
            "03-auth"
        ]
