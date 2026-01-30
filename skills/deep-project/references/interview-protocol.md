# Interview Protocol

## Context to Read

Before starting the interview:
- `{initial_file}` - The requirements file passed by user

## Philosophy

The interview surfaces the user's mental model. Claude has freedom to ask questions adaptively - there's no fixed number of rounds. The goal is understanding is reconciling context from the users brain with claude's intelligence.

## Core Topics to Cover

### 1. Natural Boundaries

Try to discover how the user naturally thinks about dividing the work while also providing your advice for how it might be split. Try to identify foundational systems.

**Listen for:**
- Repeated mentions of specific modules or features
- Clear separation in how they describe different parts
- "This part is about X, but that part is about Y"

### 2. Ordering Intuition

Understand what needs to come first or is foundational. Tease context out of the users mind about dependencies and combine it with your advice.

**Listen for:**
- Mentions of "core" or "foundation"
- Dependencies: "X needs Y to work"
- Bootstrap requirements

### 3. Uncertainty Mapping

Identify what's clear vs. what needs exploration. Extract detail from the user on the most vague pieces while combining your knowledge.

**Listen for:**
- Hesitation or qualifiers ("maybe", "probably", "I think")
- Multiple alternatives being considered
- "I'm not sure how to..."

**Why it matters:**
Uncertain parts may need dedicated splits for /deep-plan exploration. Don't assume - flag it.

### 4. Existing Context

Capture constraints and integration points.

**Listen for:**
- Specific technologies, frameworks, or patterns
- API contracts or database schemas
- Organizational or deployment constraints

**Important:** Pass through to specs without researching. Your job is to capture context, not validate it.

## When to Stop

Stop the interview when you have enough information to:

1. **Propose a split structure the user will recognize**
   - Splits should match the mental model you and the user have been constructing
   - May be a single unit if project is small enough / coherent

2. **Identify dependencies between splits** (if multiple)
   - What needs what
   - What can run in parallel

3. **Flag which splits could run in parallel** (if multiple)
   - Independent work streams
   - Interface-only dependencies

4. **Capture key context and clarifications for /deep-plan**
   - Decisions that affect implementation
   - Constraints that must be respected
   - Unknowns that need resolution

## Output

After the interview, write `{planning_dir}/deep_project_interview.md` with a complete transcript of the interview.
