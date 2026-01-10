# Gemini CLI Support

## Goal
Enable `claude-context-tracker` to track context for **Gemini CLI** sessions, in addition to Claude Code.

## The Problem
*   **No Native Hooks**: Gemini CLI does not have a "Stop Hook" system like Claude Code.
*   **Different Transcripts**: Gemini stores session history in `~/.gemini/tmp/.../chats/session-*.json`, while Claude uses `session.jsonl`.
*   **Different Structure**: Gemini's JSON format differs from Claude's event stream.

## The Solution
Create an **adapter layer** that bridges Gemini's CLI output to the existing `SessionAnalyzer`.

### 1. Adapter Script (`hooks/gemini_stop.py`)
A new entry point that:
1.  Calculates the project hash (SHA256 of cwd).
2.  Locates the most recent Gemini session transcript.
3.  Parses the JSON format (extracting `toolCalls` like `write_file`).
4.  Normalizes this into the format expected by `SessionAnalyzer`.
5.  Triggers the standard context update logic.

### 2. Trigger Mechanism
Since native hooks don't exist, we will use a **shell wrapper/alias**:
```bash
alias gemini='gemini "$@"; python3 ~/cc-context-tracker-plugin/hooks/gemini_stop.py'
```

### 3. Documentation (`GEMINI.md`)
*   Create `GEMINI.md` files mirroring `CLAUDE.md` to provide context for Gemini agents.
*   Document the setup process for Gemini users.

## Implementation Tasks

- [x] **Context Documentation**: Create `GEMINI.md` files in root and subdirectories.
- [ ] **Adapter Logic**: Implement `hooks/gemini_stop.py`.
- [ ] **Transcript Parser**: Add logic to parse Gemini's `session-*.json` format.
- [ ] **Config Update**: Allow `provider: "gemini"` in `config.json` to be set explicitly.
- [ ] **Installation**: Update `README.md` with Gemini setup instructions.
