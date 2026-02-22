---
name: writer-agent
description: Merges session insights into context.md wiki. Invoked by stop hook.
---

# Writer Agent

Analyzes a session summary and merges insights into the project's context.md wiki.

## Input

Arguments passed via prompt:
- `topics`: Comma-separated topic tags
- `existing context.md`: Current wiki content
- `session summary`: Session changes and decisions

## Wiki Format

The wiki has 3 sections: Decisions, Patterns, Recent Work.
Architecture lives in architecture.md — never duplicated here.

## Workflow

### Step 1: Analyze Session

From the session summary, extract:

1. **DECISIONS**: Key technical decisions made. For each, include:
   - *Rationale*: Why was this decision made?
   - *Alternatives*: What else was considered? (if any)
2. **PATTERNS**: Any new coding patterns established
3. **RECENT_WORK**: Brief summary (1-2 sentences with topic tags)

### Step 2: Merge into Wiki

```markdown
# Project Context

## Decisions
[Append new decisions with Rationale/Alternatives. Deduplicate if >80% overlap with existing.]

## Patterns
[Keep existing. Only add if session establishes genuinely new patterns.]

## Recent Work
[Prepend new entry. Keep last 5 entries. Oldest rotates out.]
```

#### Recent Work Entry Format

```markdown
- [YYYY-MM-DD] <summary with [topic] tags inline>
```

Example:
```markdown
- [2026-01-08] Fixed [bugfix] authentication timeout in login handler.
```

#### Deduplication Rules

Before adding to Decisions:
1. Compare with existing entries
2. If >80% word overlap, skip (already captured)
3. Prefer more specific/detailed version

### Step 3: Write Output

Output the complete updated context.md between `<context_md>` and `</context_md>` tags.

## Output Format

```
<context_md>
# Project Context

## Decisions
...

## Patterns
...

## Recent Work
...
</context_md>
```

Then output a brief JSON summary:
```json
{"status": "success", "decisions_added": 2}
```

## Important Notes

- Keep summaries concise (2-3 sentences max)
- Use topic tags inline in Recent Work (e.g., "Fixed [bugfix] issue...")
- Deduplicate before adding to Decisions
- Recent Work keeps only last 5 entries (newest first)
- Preserve existing Patterns unless session genuinely adds to them
- Always output the COMPLETE context.md, not just changes
- Never include architecture content — that belongs in architecture.md
