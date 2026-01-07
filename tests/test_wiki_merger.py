#!/usr/bin/env python3
"""Unit tests for wiki merger module."""

import pytest
from core.wiki_parser import WikiKnowledge
from core.session_analyzer import SessionContext
from core.wiki_merger import merge_session, _deduplicate, _similarity, _rotate_recent


class TestMergeSession:
    """Test merge_session function."""

    def test_merge_new_decisions_into_wiki(self):
        """Normal: Merge session with 3 new decisions into wiki with 2 existing."""
        wiki = WikiKnowledge(
            decisions=["Use PostgreSQL for database", "Deploy with Docker"]
        )
        session = SessionContext(
            decisions_made=["Add Redis caching", "Use TypeScript for frontend", "Implement JWT auth"],
            summary="Added new decisions"
        )

        result = merge_session(wiki, session)

        assert len(result.decisions) == 5
        # New decisions prepended in reverse order of processing
        assert result.decisions[0] == "Implement JWT auth"
        assert result.decisions[1] == "Use TypeScript for frontend"
        assert result.decisions[2] == "Add Redis caching"
        assert result.decisions[3] == "Use PostgreSQL for database"

    def test_duplicate_decision_not_added(self):
        """Edge: Merge session with duplicate decision (similarity 0.85)."""
        wiki = WikiKnowledge(
            decisions=["Use regex for parsing wiki sections"]
        )
        session = SessionContext(
            decisions_made=["Use regex to parse wiki sections"],  # Very similar
            summary="Made decisions"
        )

        result = merge_session(wiki, session)

        # Should not add duplicate
        assert len(result.decisions) == 1
        assert result.decisions[0] == "Use regex for parsing wiki sections"

    def test_sixth_session_triggers_rotation(self):
        """Edge: Merge 6th session triggers rotation."""
        wiki = WikiKnowledge(
            recent_work=[
                "[2024-01-05] Session 5",
                "[2024-01-04] Session 4",
                "[2024-01-03] Session 3",
                "[2024-01-02] Session 2",
                "[2024-01-01] Session 1",
            ]
        )
        session = SessionContext(summary="Session 6")

        result = merge_session(wiki, session, max_recent=5)

        assert len(result.recent_work) == 5
        # Oldest session dropped
        assert "[2024-01-01] Session 1" not in result.recent_work
        # New session added
        assert "Session 6" in result.recent_work[0]

    def test_empty_session_produces_unchanged_wiki(self):
        """Error: Empty session produces unchanged wiki."""
        wiki = WikiKnowledge(
            decisions=["Existing decision"],
            issues=["Existing issue"],
            recent_work=["[2024-01-01] Session 1"]
        )
        session = SessionContext(
            decisions_made=[],
            problems_solved=[],
            summary=""  # Empty summary
        )

        result = merge_session(wiki, session)

        assert result.decisions == ["Existing decision"]
        assert result.issues == ["Existing issue"]
        assert result.recent_work == ["[2024-01-01] Session 1"]


class TestDeduplicate:
    """Test _deduplicate helper function."""

    def test_prepends_unique_items(self):
        existing = ["Use PostgreSQL for storage", "Deploy with containers"]
        new_items = ["Add caching layer", "Implement authentication"]

        result = _deduplicate(existing, new_items, threshold=0.8)

        assert result[0] == "Implement authentication"
        assert result[1] == "Add caching layer"
        assert "Use PostgreSQL for storage" in result
        assert "Deploy with containers" in result

    def test_filters_similar_items(self):
        existing = ["Use pytest for testing"]
        new_items = ["Use pytest for tests"]  # High similarity

        result = _deduplicate(existing, new_items, threshold=0.8)

        assert len(result) == 1
        assert result[0] == "Use pytest for testing"

    def test_empty_new_items_unchanged(self):
        existing = ["Item A", "Item B"]

        result = _deduplicate(existing, [], threshold=0.8)

        assert result == existing


class TestSimilarity:
    """Test _similarity helper function."""

    def test_identical_strings(self):
        assert _similarity("hello", "hello") == 1.0

    def test_different_strings(self):
        sim = _similarity("hello", "world")
        assert sim < 0.5

    def test_case_insensitive(self):
        assert _similarity("Hello", "hello") == 1.0

    def test_similar_strings(self):
        sim = _similarity("Use regex for parsing", "Use regex for parsing sections")
        assert sim > 0.7


class TestRotateRecent:
    """Test _rotate_recent helper function."""

    def test_prepends_new_entry(self):
        recent = ["Entry 1", "Entry 2"]

        result = _rotate_recent(recent, "New Entry", max_size=5)

        assert result[0] == "New Entry"
        assert len(result) == 3

    def test_drops_oldest_when_full(self):
        recent = ["Entry 5", "Entry 4", "Entry 3", "Entry 2", "Entry 1"]

        result = _rotate_recent(recent, "Entry 6", max_size=5)

        assert len(result) == 5
        assert "Entry 1" not in result
        assert result[0] == "Entry 6"

    def test_handles_empty_list(self):
        result = _rotate_recent([], "First Entry", max_size=5)

        assert result == ["First Entry"]

    def test_invalid_max_size_raises_error(self):
        """Validation: max_size <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="max_size must be positive"):
            _rotate_recent(["Entry"], "New", max_size=0)

        with pytest.raises(ValueError, match="max_size must be positive"):
            _rotate_recent(["Entry"], "New", max_size=-1)
