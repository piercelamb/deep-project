# Split Heuristics

## Context to Read

Before analyzing splits:
- `{initial_file}` - The original requirements
- `{planning_dir}/deep_project_interview.md` - Interview transcript with user clarifications

## Overview

/deep-plan is a Claude Code plugin that transforms requirements into detailed implementation plans via research, interviews, and multi-LLM review.

The goal of a split is to create a unit of work that is ideal for deeper planning via the /deep-plan plugin. We do not want to pass vague ideas that are too broad to /deep-plan (the plan will become too much context) and we do not want to pass small/targeted units of work to /deep-plan (it will be overkill for them). Your goal is to find the ideal split that has natural boundaries and will benefit from much deeper/thorough planning without being too broad.

## Good Split Characteristics

A well-formed split has:

**Cohesive purpose**
- A clear goal or outcome

**Bounded complexity**
- 1 to few major components
- Fits in one person's head

**Clear interfaces**
- Well-defined inputs (what it needs)
- Well-defined outputs (what it produces)
- Minimal hidden dependencies

## Signs of Too Big

Split is too large if:

- **Multiple distinct systems** in one split
  - Backend + frontend + pipeline = 3 splits
  - Don't combine unrelated subsystems

- **Repeated "and also..." in description**
  - "It handles auth AND also payments AND also notifications"
  - Each "and also" is a candidate for its own split

- **No clear single purpose**
  - If you struggle to name it, it's probably too big
  - Vague names like "core" or "main" suggest over-scoping

- **Would produce 10+ /deep-plan sections**
  - Each split should map to a focused planning effort
  - Large section counts indicate insufficient decomposition

## Signs of Too Small

These signs indicate you've split too granularly - combine with adjacent work or keep as single unit:

- **Single function or trivial CRUD**
  - "Add a button that calls an API"
  - Not enough substance for a standalone split

- **No architectural decisions needed**
  - Implementation is obvious
  - No tradeoffs to consider

- **Fully specifiable in few sentences**
  - Requirements fit in a paragraph
  - No discovery needed

## Not Splittable (Single Unit)

Some projects don't benefit from multiple splits:

1. **Single coherent system**
   - Tightly coupled components
   - Artificial separation would create overhead

2. **Too unclear even after interview**
   - Can't determine boundaries without implementation
   - Need /deep-plan to explore and discover structure

**Workflow:** Create `01-{project-name}/spec.md` with interview context. Next step: `/deep-plan @01-name/spec.md`

Single-unit output is not a failure - it's a valid outcome that preserves interview insights in a consistent structure.

## Dependency Types

When splits have dependencies, categorize them, for e.g.:

**models**
- Data structures, domain objects
- Shared types between splits
- "Split B needs the User model from Split A"

**APIs**
- Endpoint contracts, interfaces
- Service boundaries
- "Split B calls the auth API from Split A"

**schemas**
- Database schemas, migrations
- "Split B queries tables created by Split A"

**patterns**
- Shared conventions, utilities
- Coding standards, error handling
- "Both splits use the same logging pattern"

## Parallel Hints

Splits can run in parallel if:

**No direct dependencies**
- Neither needs output from the other
- Completely independent work streams

**Dependencies are on interface contracts**
- Only need to agree on the shape of data
- Can define interface upfront, implement independently
- "Split A and B both use User model - define schema first, then parallel"

**Example parallel groups:**
```
Group A: 01-auth, 02-user-management (related, sequential)
Group B: 03-notifications (independent)
Group C: 04-analytics, 05-reporting (related, can parallel after 04)
```

## Decision Flowchart

```
Start with requirements
         |
         v
Is it clearly multiple distinct systems?
    Yes -> Split by system boundary
    No  -> Continue
         |
         v
Can you identify 2+ cohesive, bounded pieces?
    Yes -> Propose multi-split structure
    No  -> Single unit (01-project-name/spec.md)
```
