#!/usr/bin/env python3
"""Unit tests for wiki parser module."""

import pytest
from core.wiki_parser import WikiKnowledge, parse, has_empty_sections, _extract_list_items


class TestParseAllSections:
    """Test parse() extracts all sections from valid wiki."""

    def test_extracts_architecture_section(self):
        content = """# Project Context

## Architecture

This is the architecture section with explanations.

## Decisions

- Decision 1
- Decision 2

## Patterns

- Pattern 1

## Recent Work

- [2024-01-01] Recent work 1
"""
        wiki = parse(content)
        assert wiki.architecture == "This is the architecture section with explanations."
        assert wiki.decisions == ["Decision 1", "Decision 2"]
        assert wiki.patterns == ["Pattern 1"]
        assert wiki.recent_work == ["[2024-01-01] Recent work 1"]

    def test_handles_asterisk_bullets(self):
        content = """## Decisions

* Decision with asterisk
* Another decision

## Patterns
"""
        wiki = parse(content)
        assert wiki.decisions == ["Decision with asterisk", "Another decision"]


class TestParseEmptySections:
    """Test parse() handles empty sections correctly."""

    def test_empty_sections_return_empty_lists(self):
        content = """## Architecture

## Decisions

## Patterns

## Recent Work
"""
        wiki = parse(content)
        assert wiki.architecture == ""
        assert wiki.decisions == []
        assert wiki.patterns == []
        assert wiki.recent_work == []

    def test_partial_sections_populated(self):
        content = """## Architecture

Some architecture notes.

## Decisions

## Patterns

- Active pattern

## Recent Work
"""
        wiki = parse(content)
        assert wiki.architecture == "Some architecture notes."
        assert wiki.decisions == []
        assert wiki.patterns == ["Active pattern"]
        assert wiki.recent_work == []


class TestParseNoSections:
    """Test parse() handles legacy format without wiki headers."""

    def test_no_wiki_headers_returns_empty(self):
        content = """# Project Context

## Session [general-changes] - 2024-01-01

### Changes
- Modified something

### Summary
Did some work.
"""
        wiki = parse(content)
        assert wiki.architecture == ""
        assert wiki.decisions == []
        assert wiki.patterns == []
        assert wiki.recent_work == []

    def test_h3_headers_not_matched_as_wiki_sections(self):
        """Verify ### headers in legacy format don't match ## wiki sections."""
        content = """# Project Context

## Session - 2024-01-01

### Decisions
- Legacy decision item

### Patterns
- Legacy pattern item

### Architecture
Some architecture notes in legacy format.
"""
        wiki = parse(content)
        # These should all be empty because ### != ##
        assert wiki.architecture == ""
        assert wiki.decisions == []
        assert wiki.patterns == []

    def test_empty_string_returns_empty(self):
        wiki = parse("")
        assert wiki.architecture == ""
        assert wiki.decisions == []


class TestParseMalformed:
    """Test parse() returns empty WikiKnowledge on malformed input."""

    def test_malformed_returns_empty(self):
        # Non-string input will be caught by exception handler
        wiki = parse(None)  # type: ignore
        assert isinstance(wiki, WikiKnowledge)
        assert wiki.decisions == []

    def test_nested_headers_handled(self):
        content = """## Architecture

### Subsection
Nested content

## Decisions

- Valid decision
"""
        wiki = parse(content)
        assert "Subsection" in wiki.architecture
        assert wiki.decisions == ["Valid decision"]


class TestExtractListItems:
    """Test _extract_list_items helper function."""

    def test_extracts_simple_list(self):
        content = """## Decisions

- Item one
- Item two
- Item three

## Patterns
"""
        items = _extract_list_items(content, "Decisions")
        assert items == ["Item one", "Item two", "Item three"]

    def test_strips_whitespace(self):
        content = """## Patterns

-    Lots of leading space
- Normal item

## Recent Work
"""
        items = _extract_list_items(content, "Patterns")
        assert items == ["Lots of leading space", "Normal item"]

    def test_missing_section_returns_empty(self):
        content = """## Other Section

- Some items
"""
        items = _extract_list_items(content, "Decisions")
        assert items == []


class TestHasEmptySections:
    """Tests for has_empty_sections(): checks architecture and patterns only (ref: DL-003)."""

    def test_empty_architecture_returns_true(self):
        """Returns True when architecture is empty string."""
        wiki = WikiKnowledge()
        assert has_empty_sections(wiki) is True

    def test_populated_returns_false(self):
        """Returns False when architecture text and patterns both present."""
        wiki = WikiKnowledge(
            architecture="Has content",
            patterns=["Pattern 1"],
        )
        assert has_empty_sections(wiki) is False

    def test_placeholder_architecture_returns_true(self):
        """Returns True when architecture matches `_No .* yet._` placeholder."""
        wiki = WikiKnowledge(architecture="_No architectural notes yet._", patterns=["p"])
        assert has_empty_sections(wiki) is True
