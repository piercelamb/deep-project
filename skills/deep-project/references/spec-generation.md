# Spec File Generation

## Context to Read

Before writing spec files:
- `{initial_file}` - The original requirements
- `{planning_dir}/deep_project_interview.md` - Interview transcript
- `{planning_dir}/project-manifest.md` - Split structure and dependencies

**From setup-session.py output:**
- `split_directories` - Full paths to all split directories
- `splits_needing_specs` - Names of splits that still need spec.md written

Each split directory contains a `spec.md` that captures requirements and context for /deep-plan.

## Writing Guidelines

- **Self-contained:** Each spec should stand alone for /deep-plan
- **Reference don't duplicate:** Point to original requirements file rather than copying large sections
- **Capture decisions:** Include interview answers that shaped this split
- **Note dependencies:** Be explicit about what this split needs from other splits and provides

Remember that these spec files are going to get deep/thorough planning. They need to provide enough context to kick off a deep/thorough planning session and no more.
