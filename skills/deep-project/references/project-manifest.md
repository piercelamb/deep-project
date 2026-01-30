# Project Manifest Format

## Context to Read

Before writing the manifest:
- `{initial_file}` - The original requirements
- `{planning_dir}/deep_project_interview.md` - Interview transcript with user clarifications

The manifest captures Claude's split proposal for user confirmation.

## Required Block

**project-manifest.md MUST start with a SPLIT_MANIFEST block:**

```markdown
<!-- SPLIT_MANIFEST
01-backend
02-frontend
03-shared-utils
END_MANIFEST -->

# Project Manifest

... rest of human-readable content ...
```

## SPLIT_MANIFEST Rules

- Must be at the TOP of project-manifest.md (before any other content)
- One split per line, format: `NN-kebab-case` (e.g., `01-backend`, `02-api-gateway`)
- Split numbers must be two digits with leading zero (01, 02, ... 99)
- Split names use lowercase with hyphens (no spaces or underscores)
- Numbers should be sequential (01, 02, 03...)
- This block is parsed by scripts - the rest of the file is for humans

## Validation

Scripts parse the SPLIT_MANIFEST block to:
- Extract split directory names
- Create directories in Step 5
- Track completion progress

If the manifest is invalid (missing, malformed, or has errors), `create-split-dirs.py` returns an error with details.

## Human-Readable Content

After the manifest block, Claude can structure the rest of the file however makes sense for the project. Common sections include:

- Overview of the split structure
- Dependency relationships between splits
- Execution order recommendations
- Cross-cutting concerns
- /deep-plan commands to run

Claude is not locked to these sections, however.

