"""Manifest parsing for /deep-project.

Parses the SPLIT_MANIFEST block from project-manifest.md.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from .state import SPLIT_DIR_PATTERN


@dataclass(frozen=True, slots=True, kw_only=True)
class ParsedManifest:
    """Result of parsing a project-manifest.md file."""

    splits: list[str]
    errors: list[str]

    @property
    def is_valid(self) -> bool:
        """Return True if manifest parsed without errors."""
        return len(self.errors) == 0

    @classmethod
    def error(cls, message: str) -> Self:
        """Create a ParsedManifest with a single error."""
        return cls(splits=[], errors=[message])


# Regex to extract SPLIT_MANIFEST block
MANIFEST_BLOCK_PATTERN = re.compile(
    r"<!--\s*SPLIT_MANIFEST\s*\n(.*?)\nEND_MANIFEST\s*-->",
    re.DOTALL
)


def parse_manifest(manifest_path: Path | str) -> ParsedManifest:
    """Parse SPLIT_MANIFEST block from project-manifest.md.

    Args:
        manifest_path: Path to project-manifest.md

    Returns:
        ParsedManifest with splits list or errors
    """
    manifest_path = Path(manifest_path)

    if not manifest_path.exists():
        return ParsedManifest.error(f"Manifest file not found: {manifest_path}")

    content = manifest_path.read_text()

    # Find the SPLIT_MANIFEST block
    match = MANIFEST_BLOCK_PATTERN.search(content)
    if not match:
        return ParsedManifest.error(
            "No SPLIT_MANIFEST block found. Expected format:\n"
            "<!-- SPLIT_MANIFEST\n01-name\n02-name\nEND_MANIFEST -->"
        )

    block_content = match.group(1)
    lines = [line.strip() for line in block_content.strip().split("\n")]
    lines = [line for line in lines if line]  # Remove empty lines

    if not lines:
        return ParsedManifest.error("SPLIT_MANIFEST block is empty")

    # Validate each split name
    splits: list[str] = []
    errors: list[str] = []

    for line in lines:
        if not SPLIT_DIR_PATTERN.match(line):
            errors.append(
                f"Invalid split name '{line}': must match pattern NN-kebab-case "
                "(e.g., 01-backend, 02-api-gateway)"
            )
        else:
            splits.append(line)

    # Check for duplicate indices
    indices = [int(s[:2]) for s in splits]
    seen_indices: set[int] = set()
    for idx, split in zip(indices, splits):
        if idx in seen_indices:
            errors.append(f"Duplicate index {idx:02d} in split '{split}'")
        seen_indices.add(idx)

    # Check for sequential indices (warning, not error)
    if splits and not errors:
        expected = list(range(1, len(splits) + 1))
        actual = sorted(indices)
        if actual != expected:
            errors.append(
                f"Split indices should be sequential starting from 01. "
                f"Found: {[f'{i:02d}' for i in actual]}"
            )

    return ParsedManifest(splits=splits, errors=errors)
