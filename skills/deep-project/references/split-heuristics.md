# Split Heuristics

## Good Split Characteristics

A well-formed split has:

**Cohesive purpose**
- One clear goal or outcome
- Easy to describe in one sentence
- "This split does X"

**Bounded complexity**
- 3-8 major components
- Estimable effort (1-3 focused implementation sessions)
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

Split is too small if:

- **Single function or trivial CRUD**
  - "Add a button that calls an API"
  - Too granular for /deep-plan

- **No architectural decisions needed**
  - Implementation is obvious
  - No tradeoffs to consider

- **Fully specifiable in few sentences**
  - Requirements fit in a paragraph
  - No discovery needed

- **Planning overhead > implementation time**
  - If writing the spec takes longer than writing the code
  - Just do it directly

## Not Splittable (Single Unit)

Some projects don't benefit from multiple splits:

### Reasons for Single Unit

1. **Too small overall**
   - Entire project is one bounded piece of work
   - Multiple splits would be artificial

2. **Too unclear even after interview**
   - Can't determine boundaries without implementation
   - Need /deep-plan to explore first

3. **Single coherent system**
   - Tightly coupled components
   - Artificial separation would create overhead

### Single Unit Workflow

When project is not splittable:

1. Create single subdir: `01-{project-name}/`
2. Write spec.md with all interview context
3. Spec includes notes for /deep-plan exploration
4. Manifest reflects single-unit structure

**This is a valid workflow outcome, not a failure.**

Benefits:
- Interview insights preserved in spec.md
- Consistent output structure (always directories + specs)
- Uniform next step: `/deep-plan @01-name/spec.md`

## Dependency Types

When splits have dependencies, categorize them:

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
    No  -> Continue
         |
         v
Is the project too small for /deep-plan?
    Yes -> Single unit (01-project-name/) with minimal spec
    No  -> Single unit (01-project-name/) with full spec
```
