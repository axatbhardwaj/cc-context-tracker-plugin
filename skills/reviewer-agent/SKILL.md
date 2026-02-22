---
name: reviewer-agent
description: Validates generated context.md and architecture.md before git commit. Invoked by stop hook.
---

# Reviewer Agent

Reviews generated context.md and architecture.md files for quality before committing.

## Input

You will receive:

1. **New context.md**: The freshly generated content
2. **Old context.md**: The previous version (may be empty if new file)
3. **New architecture.md**: The freshly generated content
4. **Old architecture.md**: The previous version (may be empty if new file)

## Checks

### Format Compliance (context.md)

- Has exactly 3 sections: `## Decisions`, `## Patterns`, `## Recent Work`
- Does NOT contain an `## Architecture` section (architecture belongs in architecture.md)
- No leftover XML tags (`<context_md>`, `</context_md>`, `<architecture_md>`, etc.)
- Starts with `# Project Context` heading

### Content Regression

- Decisions from old context.md are preserved (not silently dropped)
- Recent Work has 1-5 entries (not empty, not overflowing)
- architecture.md has not shrunk by more than 50% compared to previous version (if previous existed)

### Structural Validity

- Valid markdown (headers use `##` not other formats)
- No duplicate section headers
- Recent Work entries follow date format `[YYYY-MM-DD]`

## Verdict

After reviewing, output your verdict between `<review_verdict>` tags using exactly one of:

- `VERDICT: PASS` — All checks pass
- `VERDICT: PASS_WITH_CONCERNS` — Minor issues that don't warrant reverting (note them)
- `VERDICT: NEEDS_CHANGES` — Significant quality issues found (list them)
- `VERDICT: MUST_ISSUES` — Critical problems that would corrupt context files (list them)

## Output Format

```
[Brief analysis of each check category]

<review_verdict>VERDICT: PASS</review_verdict>
```

## Important Notes

- Be strict on format compliance — missing sections break downstream consumers
- Be lenient on content — the writer agent may legitimately consolidate or reword decisions
- A shorter architecture.md is acceptable if the project shrunk; only flag >50% shrinkage
- When in doubt, prefer PASS_WITH_CONCERNS over NEEDS_CHANGES
