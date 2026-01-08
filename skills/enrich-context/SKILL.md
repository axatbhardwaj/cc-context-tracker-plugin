---
name: enrich-context
description: Enriches empty sections in context.md by analyzing codebase structure and history. Invoked by stop hook.
---

# Enrich Context

Analyzes codebase structure and git history to populate empty Architecture, Patterns, and Key Symbols sections in context.md.

## Input

You will receive:

1. **Codebase Summary**: Git history and directory structure
2. **Existing context.md**: Current wiki content (may have empty sections)

## Task

For each empty section (matching `_No .* yet._`), generate content based on the codebase summary:

### Architecture Section

Describe the high-level structure of the codebase in 2-4 sentences:
- What kind of application is this? (CLI tool, web app, library, etc.)
- What are the main modules/components?
- How do they relate to each other?

**Good example**:
```
Claude Code context tracking plugin. Captures session file changes via stop hook,
analyzes patterns with LLM, and maintains project wiki. Core modules: session_analyzer
(change extraction), wiki_parser (context.md parsing), markdown_writer (output formatting).
```

**Bad example** (too generic):
```
Python application with multiple modules for processing data.
```

### Patterns Section

Identify 2-4 coding patterns evident from git history and file structure:
- Naming conventions (e.g., "snake_case for functions")
- Error handling approach (e.g., "early returns, minimal nesting")
- Testing patterns (e.g., "pytest with fixtures")
- Architecture patterns (e.g., "dataclasses for data models")

**Good example**:
```
- Early returns to reduce nesting (KISS principle)
- Dataclasses for structured data (WikiKnowledge, SessionContext)
- Regex for markdown parsing (lightweight, no heavy dependencies)
- Graceful degradation on errors (log warnings, preserve existing content)
```

**Bad example** (too vague):
```
- Uses functions
- Has error handling
```

### Key Symbols Section

List 3-6 primary classes/functions that appear frequently in git history or are central to the codebase:
- Format: `ClassName.method_name` or `function_name`
- Prioritize items that appear in multiple commits or are imported by many files

**Good example**:
```
- SessionAnalyzer.get_changes
- WikiParser.parse
- MarkdownWriter.write_session_log
- analyze_with_skill
```

**Bad example** (irrelevant):
```
- main
- __init__
```

## Output Format

Output ONLY the enriched sections wrapped in XML tags. Do NOT output sections that are already populated.

```xml
<architecture>
[2-4 sentence architecture description]
</architecture>

<patterns>
- [Pattern 1]
- [Pattern 2]
- [Pattern 3]
</patterns>

<key_symbols>
- `Symbol1`
- `Symbol2`
- `Symbol3`
</key_symbols>
```

Output ONLY the XML tags for empty sections. If all sections are populated, output nothing.
