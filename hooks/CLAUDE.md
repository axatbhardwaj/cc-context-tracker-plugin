# hooks/

## Files

| File         | What                                          | When to read                                  |
| ------------ | --------------------------------------------- | --------------------------------------------- |
| `stop.py`    | Session capture hook, orchestrates analysis   | Debugging hook execution, understanding flow  |
| `hooks.json` | Hook configuration for Claude Code            | Modifying hook settings                       |
| `__init__.py`| Python package marker                         | Understanding package structure               |

## Functions

| Function                  | What                                                   | When to read                                       |
| ------------------------- | ------------------------------------------------------ | -------------------------------------------------- |
| `analyze_codebase()`      | Extracts git history and directory structure for LLM analysis | Understanding agent inputs                    |
| `update_context_wiki()`   | Updates context.md via writer-agent (sonnet)            | Debugging context.md updates                       |
| `generate_architecture()` | Generates architecture.md via architect-agent (opus)    | Debugging architecture generation                  |
