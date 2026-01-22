"""Tests for naming utilities."""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from lib.naming import (
    to_kebab_case,
    format_split_dir_name,
    get_next_index,
    check_collision,
    generate_unique_name,
)


class TestToKebabCase:
    """Tests for kebab-case conversion."""

    def test_simple_name(self):
        """'Backend API' -> 'backend-api'"""
        assert to_kebab_case("Backend API") == "backend-api"

    def test_underscores(self):
        """'user_authentication' -> 'user-authentication'"""
        assert to_kebab_case("user_authentication") == "user-authentication"

    def test_special_characters(self):
        """'Backend / API' -> 'backend-api'"""
        assert to_kebab_case("Backend / API") == "backend-api"

    def test_multiple_spaces(self):
        """'Backend   API' -> 'backend-api'"""
        assert to_kebab_case("Backend   API") == "backend-api"

    def test_multiple_separators(self):
        """'a   b___c' -> 'a-b-c'"""
        assert to_kebab_case("a   b___c") == "a-b-c"

    def test_leading_trailing(self):
        """' - Backend - ' -> 'backend'"""
        assert to_kebab_case(" - Backend - ") == "backend"

    def test_truncation(self):
        """Long names truncated to MAX_NAME_LENGTH (50)."""
        long_name = "a" * 100
        result = to_kebab_case(long_name)
        assert len(result) <= 50

    def test_empty_result(self):
        """'!@#$%' -> '' (empty string after sanitization)"""
        result = to_kebab_case("!@#$%")
        assert result == ""


class TestFormatSplitDirName:
    """Tests for directory name formatting."""

    def test_basic_formatting(self):
        """(1, 'Backend') -> '01-backend'"""
        assert format_split_dir_name(1, "Backend") == "01-backend"
        assert format_split_dir_name(12, "Frontend UI") == "12-frontend-ui"

    def test_index_padding(self):
        """Should pad single digits with leading zero."""
        assert format_split_dir_name(1, "test") == "01-test"
        assert format_split_dir_name(99, "test") == "99-test"

    def test_invalid_index_zero(self):
        """Index 0 should raise ValueError."""
        with pytest.raises(ValueError):
            format_split_dir_name(0, "test")

    def test_invalid_index_100(self):
        """Index 100 should raise ValueError."""
        with pytest.raises(ValueError):
            format_split_dir_name(100, "test")

    def test_invalid_index_negative(self):
        """Negative index should raise ValueError."""
        with pytest.raises(ValueError):
            format_split_dir_name(-1, "test")

    def test_empty_after_sanitization(self):
        """Empty name after sanitization should raise ValueError."""
        with pytest.raises(ValueError):
            format_split_dir_name(1, "!@#$%")


class TestGetNextIndex:
    """Tests for next index calculation."""

    def test_empty_directory(self, tmp_path):
        """Empty dir should return 1."""
        assert get_next_index(tmp_path) == 1

    def test_with_existing_splits(self, tmp_path):
        """01, 02 -> next is 3."""
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "02-frontend").mkdir()
        assert get_next_index(tmp_path) == 3

    def test_with_gap(self, tmp_path):
        """01, 03 -> next is 4 (max+1, not fill gap)."""
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "03-frontend").mkdir()  # Gap at 02
        assert get_next_index(tmp_path) == 4  # Not 2

    def test_ignores_invalid_dirs(self, tmp_path):
        """Should ignore dirs not matching pattern."""
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "not-a-split").mkdir()  # No number prefix
        (tmp_path / "1-bad").mkdir()  # Single digit
        assert get_next_index(tmp_path) == 2

    def test_returns_100_when_all_slots_used(self, tmp_path):
        """When 01-99 exist, next is 100 (which format_split_dir_name rejects)."""
        for i in range(1, 100):
            (tmp_path / f"{i:02d}-test").mkdir()
        assert get_next_index(tmp_path) == 100


class TestCheckCollision:
    """Tests for collision detection."""

    def test_no_collision(self, tmp_path):
        """Non-existent dir returns False."""
        assert check_collision(tmp_path, "01-backend") is False

    def test_collision(self, tmp_path):
        """Existing dir returns True."""
        (tmp_path / "01-backend").mkdir()
        assert check_collision(tmp_path, "01-backend") is True


class TestGenerateUniqueName:
    """Tests for unique name generation."""

    def test_no_collision(self, tmp_path):
        """No collision returns base name."""
        result = generate_unique_name(tmp_path, 1, "Backend")
        assert result == "01-backend"

    def test_with_collision(self, tmp_path):
        """Collision appends -2."""
        (tmp_path / "01-backend").mkdir()
        result = generate_unique_name(tmp_path, 1, "Backend")
        assert result == "01-backend-2"

    def test_multiple_collisions(self, tmp_path):
        """Multiple collisions increment suffix."""
        (tmp_path / "01-backend").mkdir()
        (tmp_path / "01-backend-2").mkdir()
        result = generate_unique_name(tmp_path, 1, "Backend")
        assert result == "01-backend-3"

    def test_exhaustion_raises_error(self, tmp_path):
        """Should raise ValueError when all suffix slots are taken."""
        (tmp_path / "01-backend").mkdir()
        for suffix in range(2, 100):
            (tmp_path / f"01-backend-{suffix}").mkdir()
        with pytest.raises(ValueError, match="Cannot generate unique name"):
            generate_unique_name(tmp_path, 1, "Backend")
