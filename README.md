![deep-project hero](assets/hero.jpeg)

# /deep-project, a Claude Code plugin

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Status](https://img.shields.io/badge/status-beta-orange)
![License](https://img.shields.io/badge/license-MIT-green)
![Claude Code](https://img.shields.io/badge/Claude%20Code-Plugin-purple)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)

`/deep-project` transforms vague, high-level project requirements into well-scoped planning units through AI-assisted interview and decomposition. It ensures you've thought through every major component of the software you want to build and properly scoped them for thorough planning through [`/deep-plan`](https://github.com/piercelamb/deep-plan).

This plugin is the first step in the deep planning pipeline. After decomposition, each unit can be fed to [`/deep-plan`](https://github.com/piercelamb/deep-plan) for comprehensive planning with research, external LLM review, and a TDD approach.

I built this after the first time I wanted to put a vague, broadly scoped software project through `/deep-plan`. I realized that at a certain level of broadness, for e.g., "Build me an app that does x y and z", that the optimal use of `/deep-plan` would be to split that vague idea into its distinct, major components and `/deep-plan` each of them. `/deep-project` is the plugin that allows you to give it very broad, vague ideas and have it tease out context and form the components that should each be `/deep-plan`ned.

## TL;DR
```
/plugin marketplace add piercelamb/deep-project
/plugin install deep-project
/plugin enable deep-project
/deep-project @planning/requirements.md
```

## Table of Contents

- [Overview](#overview)
- [The Deep Trilogy](#the-deep-trilogy)
- [Why deep-project?](#why-deep-project)
- [When to Use](#when-to-use)
- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Usage](#usage)
- [Workflow Steps](#workflow-steps)
- [Output Files](#output-files)
- [Requirements](#requirements)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Contributing](#contributing)

## Overview

**deep-project** orchestrates a decomposition workflow that breaks large projects into manageable pieces *before* detailed planning:

```
Interview → Split Analysis → Dependency Mapping → Directory Creation → Spec Generation
```

The plugin guides you through:
- **Interview Phase**: Structured Q&A to understand your mental model of the project
- **Split Analysis**: Determine if the project benefits from multiple planning units
- **Dependency Discovery**: Map relationships between splits
- **Spec Generation**: Create focused spec files for each unit

By the end, you have a planning directory with a project manifest and numbered split directories, each containing a spec file ready for `/deep-plan`.

## The Deep Trilogy

This plugin is part of a three-plugin pipeline for turning ideas into production code:

```
/deep-project (decompose) → /deep-plan (plan) → /deep-implement (build)
```

```
┌───────────────────────────────────────────────────────────────────┐
│                        THE DEEP TRILOGY                           │
│                From Vague Idea to Production Code                 │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│         "I want to build a SaaS platform"                         │
│                        │                                          │
│                        ▼                                          │
│      ┌─────────────────────────────────────┐                      │
│      │            /deep-project            │  ◀── YOU ARE HERE    │
│      └─────────────────────────────────────┘                      │
│           │            │            │                             │
│           ▼            ▼            ▼                             │
│      ┌─────────┐  ┌─────────┐  ┌─────────┐                        │
│      │ 01-auth │  │ 02-bill │  │   ...   │                        │
│      │ spec.md │  │ spec.md │  │         │                        │
│      └─────────┘  └─────────┘  └─────────┘                        │
│           │            │            │                             │
│           ▼            ▼            ▼                             │
│      ┌─────────┐  ┌─────────┐  ┌─────────┐                        │
│      │ /deep-  │  │ /deep-  │  │   ...   │                        │
│      │  plan   │  │  plan   │  │         │                        │
│      └─────────┘  └─────────┘  └─────────┘                        │
│         │   │       │ │ │           │                             │
│         ▼   ▼       ▼ ▼ ▼           ▼                             │
│      ┌────┐┌────┐┌────┐┌────┐┌────┐┌─────────┐                    │
│      │ 01 ││ 02 ││ 01 ││ 02 ││ 03 ││   ...   │                    │
│      └────┘└────┘└────┘└────┘└────┘└─────────┘                    │
│        │    │     │     │    │          │                         │
│        └─┬──┘     └──┬──┴────┘          │                         │
│          │           │                  │                         │
│          ▼           ▼                  ▼                         │
│      ┌─────────┐┌─────────┐        ┌─────────┐                    │
│      │ /deep-  ││ /deep-  │        │   ...   │                    │
│      │implement││implement│        │         │                    │
│      └─────────┘└─────────┘        └─────────┘                    │
│           │          │                  │                         │
│           ▼          ▼                  ▼                         │
│      ┌─────────┐┌─────────┐        ┌─────────┐                    │
│      │  auth   ││ billing │        │   ...   │                    │
│      │  code   ││  code   │        │         │                    │
│      └─────────┘└─────────┘        └─────────┘                    │
│           │          │                  │                         │
│           └──────────┴──────────────────┘                         │
│                          │                                        │
│                          ▼                                        │
│                 Production Codebase                               │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

| Plugin | Purpose | Input | Output |
|--------|---------|-------|--------|
| [`/deep-project`](https://github.com/piercelamb/deep-project) | Decompose | Vague requirements | Focused spec files |
| [`/deep-plan`](https://github.com/piercelamb/deep-plan) | Plan | Spec file | Section files with TDD |
| [`/deep-implement`](https://github.com/piercelamb/deep-implement) | Build | Section files | Production code |

**Where to start?**
- **Vague multi-component project?** Start here with `/deep-project`
- **Single focused feature?** Skip to [`/deep-plan`](https://github.com/piercelamb/deep-plan)
- **Already have section files?** Skip to [`/deep-implement`](https://github.com/piercelamb/deep-implement)

## Why deep-project?

### Without deep-project
```
You: "Claude, I need to build a complete SaaS platform"
Claude: *overwhelmed by scope, makes assumptions, misses critical relationships*
Result: Inconsistent implementation, integration issues, rework
```

### With deep-project
```
You: "/deep-project @planning/saas-requirements.md"
deep-project: Interview → Split Analysis → Manifest → Spec Files
Result:
  - 01-auth-system/spec.md
  - 02-billing-integration/spec.md
  - 03-user-dashboard/spec.md
  Each ready for focused /deep-plan sessions
```

**Time Investment**: ~15 minutes of interview
**Time Saved**: Hours of coordination and rework from poorly scoped planning

## When to Use

**Use deep-project when:**
- Your project has multiple distinct subsystems
- Requirements are vague and need decomposition
- You want to parallelize planning across multiple focused sessions
- Dependencies between components need explicit mapping

**Skip deep-project when:**
- The project is already a single, well-defined feature
- Requirements are clear and bounded
- You're doing a bug fix or small enhancement
- You already have well-scoped spec files
- Even in these cases, /deep-project will scope the project to a single component.

## Quick Start

> **TL;DR**: Create a requirements file, run the command, answer questions.

**1. Create a requirements file:**

*Option A: Use your editor* — Create `planning/requirements.md` with your project description.

*Option B: Command line:*
```bash
mkdir -p planning
cat > planning/requirements.md << 'EOF'
# My SaaS Platform

Build a complete SaaS platform with:
- User authentication (OAuth, email/password)
- Subscription billing
- Admin dashboard
- User-facing dashboard
- API for third-party integrations
EOF
```

Requirements files can be as detailed or vague as you like. The interview phase will extract specifics.

**2. Run deep-project:**
```
/deep-project @planning/requirements.md
```

**3. Follow the prompts** through Interview → Split Analysis → Confirmation → Generation

That's it. Your planning directory will contain numbered split directories with focused spec files.

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     deep-project workflow                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   /deep-project @requirements.md                                │
│          │                                                      │
│          ▼                                                      │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│   │  Interview   │ ──▶ │    Split     │ ──▶ │  Dependency  │    │
│   │  (adaptive)  │     │   Analysis   │     │   Mapping    │    │
│   └──────────────┘     └──────────────┘     └──────────────┘    │
│                                                   │             │
│                                                   ▼             │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│   │     Spec     │ ◀── │  Directory   │ ◀── │    User      │    │
│   │  Generation  │     │   Creation   │     │ Confirmation │    │
│   └──────────────┘     └──────────────┘     └──────────────┘    │
│          │                                                      │
│          ▼                                                      │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  01-auth/spec.md  02-billing/spec.md  03-dashboard/...   │  │
│   │  (Focused planning units ready for /deep-plan)           │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- [Claude Code](https://claude.ai/code) installed
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Python 3.11+

### Install via Marketplace (Recommended)

**Option A: CLI commands**
```
/plugin marketplace add piercelamb/deep-project
/plugin install deep-project
/plugin enable deep-project
```

**Option B: Via UI**
```
/plugin marketplace add piercelamb/deep-project
/plugin install deep-project
/plugins
```
Then scroll to "Installed", find `deep-project`, and click "Enable".

### Manual Installation

**Option A: Via settings.json**

Clone the repo, then add to your project's `.claude/settings.json`:
```bash
git clone https://github.com/piercelamb/deep-project.git /path/to/deep-project
```

```json
{
  "plugins": {
    "paths": ["/path/to/deep-project"]
  }
}
```

**Option B: Via --plugin-dir flag (development/testing)**

```bash
git clone https://github.com/piercelamb/deep-project.git /path/to/deep-project
claude --plugin-dir /path/to/deep-project
```

## Usage

### Basic Invocation

```
/deep-project @path/to/requirements.md
```

The requirements file can be as detailed or vague as you like. The planning directory is inferred from the requirements file's parent directory.

### Resuming

If the workflow is interrupted (context limit, user pause), re-run with the same requirements file:

```
/deep-project @planning/requirements.md
```

The plugin detects existing artifacts and resumes from the appropriate step.

## Workflow Steps

| Phase | What Happens |
|-------|--------------|
| **Setup** | Validate input, check for existing session, initialize |
| **Interview** | Adaptive Q&A to understand project scope and relationships |
| **Split Analysis** | Determine if project benefits from multiple units |
| **Dependency Mapping** | Identify relationships and execution order |
| **User Confirmation** | Present proposed structure for approval |
| **Directory Creation** | Create numbered split directories |
| **Spec Generation** | Write focused spec.md for each split |

## Output Files

After running deep-project, your planning directory contains:

```
planning/
├── requirements.md              # Your original input
├── deep_project_interview.md    # Interview transcript
├── project-manifest.md          # ★ Split structure & dependencies
└── splits/
    ├── 01-auth-system/
    │   └── spec.md              # Focused spec for auth
    ├── 02-billing/
    │   └── spec.md              # Focused spec for billing
    └── 03-dashboard/
        └── spec.md              # Focused spec for dashboard
```

### project-manifest.md

The manifest contains:
- Overview of all splits
- Dependency graph
- Recommended execution order
- Machine-readable SPLIT_MANIFEST block

## Requirements

- Claude Code
- Python >= 3.11
- uv package manager

### Python Dependencies

Managed via `pyproject.toml` - no external API keys required (unlike `/deep-plan`).

## Best Practices

1. **Start with high-level requirements** - Don't over-specify. The interview surfaces details.

2. **Answer interview questions thoroughly** - Your mental model shapes the decomposition.

3. **Review the manifest carefully** - This is where you catch scope issues before they cascade.

4. **Prefer more splits over fewer** - Smaller, focused units are easier to plan and implement.

5. **Map dependencies explicitly** - Integration issues come from implicit assumptions.

## Troubleshooting

### "Requirements file not found"

**Issue**: The @file path doesn't exist

**Solution**:
- Ensure the file path is correct and the file exists
- Use absolute paths if relative paths aren't resolving

### Workflow interrupted mid-step

**Issue**: Context limit or manual interruption

**Solution**:
- Re-run `/deep-project @requirements.md`
- The plugin detects completed steps and resumes

### "Session state conflict detected"

**Issue**: Existing files conflict with current requirements

**Solution**:
- Choose "Start fresh" to begin new analysis
- Or "Resume" to continue from where you stopped
- If requirements changed significantly, start fresh

## Testing

Run the test suite:

```bash
cd /path/to/deep-project
uv run pytest tests/
```

## Project Structure

```
deep_project/
├── .claude-plugin/
│   ├── plugin.json              # Plugin metadata
│   └── marketplace.json         # Marketplace listing
├── LICENSE                      # MIT License
├── README.md                    # This file
├── pyproject.toml               # Python dependencies
├── hooks/
│   └── hooks.json               # Session hooks
├── scripts/
│   ├── checks/                  # Setup & validation scripts
│   ├── hooks/                   # Hook implementations
│   └── lib/                     # Shared utilities
├── skills/
│   └── deep-project/
│       ├── SKILL.md             # Main skill definition
│       └── references/          # Protocol documents
└── tests/                       # Test suite
```

## Contributing

Contributions welcome! Please:

1. Clone the repository
2. Create a feature branch
3. Run tests: `uv run pytest tests/`
4. Submit a pull request

## License

[MIT](./LICENSE)

## Author

Pierce Lamb

## Version

0.1.0
