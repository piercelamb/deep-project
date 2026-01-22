"""Directory naming utilities for /deep-project."""

import re
from pathlib import Path


# Max directory name length (excluding index prefix)
MAX_NAME_LENGTH = 50

# Characters allowed in kebab-case names
ALLOWED_CHARS = re.compile(r"[^a-z0-9-]")

# Multiple hyphens
MULTI_HYPHEN = re.compile(r"-+")


def to_kebab_case(name: str) -> str:
    """Convert name to strict kebab-case.

    - Lowercase
    - Replace spaces/underscores with hyphens
    - Remove non-alphanumeric characters (except hyphens)
    - Collapse multiple hyphens
    - Trim leading/trailing hyphens
    - Truncate to MAX_NAME_LENGTH
    """
    # Lowercase
    result = name.lower()

    # Replace common separators with hyphens
    result = result.replace(" ", "-").replace("_", "-")

    # Remove disallowed characters
    result = ALLOWED_CHARS.sub("", result)

    # Collapse multiple hyphens
    result = MULTI_HYPHEN.sub("-", result)

    # Trim leading/trailing hyphens
    result = result.strip("-")

    # Truncate
    if len(result) > MAX_NAME_LENGTH:
        result = result[:MAX_NAME_LENGTH].rstrip("-")

    return result


def get_next_index(planning_dir: Path | str) -> int:
    """Get next available split index using max-based calculation.

    Scans existing directories and returns max(indices) + 1.
    Returns 1 if no split directories exist.
    """
    from .state import is_valid_split_dir, get_split_index

    planning_dir = Path(planning_dir)
    indices = []

    for d in planning_dir.iterdir():
        if d.is_dir() and is_valid_split_dir(d.name):
            indices.append(get_split_index(d.name))

    if not indices:
        return 1
    return max(indices) + 1


def format_split_dir_name(index: int, name: str) -> str:
    """Format split directory name with two-digit prefix.

    Args:
        index: Numeric index (1-99)
        name: Split name (will be converted to kebab-case)

    Returns:
        Formatted name like "01-my-split-name"

    Raises:
        ValueError: If index out of range or name empty after sanitization
    """
    if index < 1 or index > 99:
        raise ValueError(f"Split index must be 1-99, got {index}")

    kebab_name = to_kebab_case(name)
    if not kebab_name:
        raise ValueError(f"Name '{name}' is empty after sanitization")

    return f"{index:02d}-{kebab_name}"


def check_collision(planning_dir: Path | str, dir_name: str) -> bool:
    """Check if directory name would collide with existing directory."""
    planning_dir = Path(planning_dir)
    return (planning_dir / dir_name).exists()


def generate_unique_name(planning_dir: Path | str, index: int, base_name: str) -> str:
    """Generate unique directory name, adding suffix if collision detected.

    Returns:
        Unique directory name like "01-my-split" or "01-my-split-2" if collision
    """
    base_dir_name = format_split_dir_name(index, base_name)

    if not check_collision(planning_dir, base_dir_name):
        return base_dir_name

    # Try with numeric suffix
    for suffix in range(2, 100):
        candidate = f"{base_dir_name}-{suffix}"
        if not check_collision(planning_dir, candidate):
            return candidate

    raise ValueError(f"Cannot generate unique name for index {index}, name '{base_name}'")
