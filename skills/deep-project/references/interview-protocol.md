# Interview Protocol

## Philosophy

The interview surfaces the user's mental model. Claude has freedom to ask questions adaptively - there's no fixed number of rounds. The goal is understanding, not interrogation.

## Core Topics to Cover

### 1. Natural Boundaries

Discover how the user naturally thinks about dividing the work.

**Questions to explore:**
- "What feels like separate pieces of work?"
- "Where would you draw lines if handing to different engineers?"
- "Are there distinct systems or components in your mind?"

**Listen for:**
- Repeated mentions of specific modules or features
- Clear separation in how they describe different parts
- "This part is about X, but that part is about Y"

### 2. Ordering Intuition

Understand what needs to come first.

**Questions to explore:**
- "What's foundational that everything else builds on?"
- "What needs to exist before other things can be built?"
- "If you could only have one part working, which would it be?"

**Listen for:**
- Mentions of "core" or "foundation"
- Dependencies: "X needs Y to work"
- Bootstrap requirements

### 3. Uncertainty Mapping

Identify what's clear vs. what needs exploration.

**Questions to explore:**
- "Which parts are you most confident about?"
- "Where are you still figuring things out?"
- "What decisions haven't been made yet?"

**Listen for:**
- Hesitation or qualifiers ("maybe", "probably", "I think")
- Multiple alternatives being considered
- "I'm not sure how to..."

**Why it matters:**
Uncertain parts may need dedicated splits for /deep-plan exploration. Don't assume - flag it.

### 4. Scope Calibration

Understand the size and effort involved.

**Questions to explore:**
- "Is this a weekend project or a month-long effort?"
- "How much of this is new vs. connecting existing pieces?"
- "What's the MVP vs. the full vision?"

**Listen for:**
- Time estimates or expectations
- Phase descriptions ("first we need..., then...")
- Must-have vs. nice-to-have distinctions

### 5. Existing Context

Capture constraints and integration points.

**Questions to explore:**
- "Is there existing code this needs to work with?"
- "Are there technical constraints I should know about?"
- "What's the tech stack or platform?"

**Listen for:**
- Specific technologies, frameworks, or patterns
- API contracts or database schemas
- Organizational or deployment constraints

**Important:** Pass through to specs without researching. Your job is to capture context, not validate it.

## When to Stop

Stop the interview when you have enough information to:

1. **Propose a split structure the user will recognize**
   - Splits should match their mental model
   - May be a single unit if project is coherent

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

After the interview, maintain an internal model of:

### Proposed Splits
- Name (descriptive, kebab-case-friendly)
- Purpose (one sentence)
- Rough scope (what's included)

*Note: May be a single unit if project is naturally coherent*

### Dependencies (if multiple splits)
- Which split needs what from which
- Type: models, APIs, schemas, patterns
- Status: to-be-defined, defined, implemented

### Parallel Groups (if multiple splits)
- Which splits are independent
- Which depend only on interfaces (can define upfront)

### Key Clarifications
- Decisions made during interview
- Context that affects implementation
- Uncertainties that need resolution during planning
