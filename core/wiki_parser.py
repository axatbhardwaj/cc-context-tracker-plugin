#!/usr/bin/env python3
"""Wiki parser for context-tracker plugin.

Extracts structured sections from wiki-format context.md files.
"""

import re
from typing import List
from dataclasses import dataclass, field

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class WikiKnowledge:
    """Parsed content of a context.md wiki file.

    Covers 3 active sections: Decisions, Patterns, Recent Work.
    Architecture is parsed for backward-compat reads of existing context.md files that
    contain an Architecture section; write_wiki does not emit it (ref: DL-009).
    Issues and Key Symbols fields are absent — these sections accumulate stale data (ref: DL-003).
    All list fields default to empty list (never None) to eliminate null checks in merger.
    """
    architecture: str = ""
    decisions: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    recent_work: List[str] = field(default_factory=list)


def parse(content: str) -> WikiKnowledge:
    """Parse wiki markdown into WikiKnowledge.

    Regex pattern `## SectionName` is reliable for wiki format; full markdown
    parser (mistune, markdown-it) would be overkill for 3 known sections.

    Args:
        content: Markdown content with ## Section headers

    Returns:
        WikiKnowledge with extracted sections
    """
    try:
        wiki = WikiKnowledge()

        # Extract Architecture section (text block, not list)
        # Anchored with ^ to avoid matching ### headers (e.g. ### Architecture in legacy files)
        arch_match = re.search(
            r'^## Architecture[^\n]*\n(.*?)(?=\n## |\Z)',
            content,
            re.DOTALL | re.MULTILINE
        )
        if arch_match:
            wiki.architecture = arch_match.group(1).strip()

        # Extract list sections
        wiki.decisions = _extract_list_items(content, 'Decisions')
        wiki.patterns = _extract_list_items(content, 'Patterns')
        wiki.recent_work = _extract_list_items(content, 'Recent Work')

        return wiki

    except Exception as e:
        # Wiki parse failure preserved via fallback; user can manually fix structure
        logger.warning(f"Wiki parse failed: {e}")
        return WikiKnowledge()


def _extract_list_items(content: str, section_name: str) -> List[str]:
    """Extract bullet list items from section.

    Handles both - and * bullet styles. Whitespace normalized.

    Args:
        content: Markdown content
        section_name: Section header (without ##)

    Returns:
        List of item strings
    """
    # Anchored with ^ to avoid matching ### headers (e.g. ### Decisions in legacy files)
    pattern = rf'^## {section_name}[^\n]*\n(.*?)(?=\n## |\Z)'
    match = re.search(pattern, content, re.DOTALL | re.MULTILINE)

    if not match:
        return []

    section_content = match.group(1)

    # Extract lines starting with - or *
    items = re.findall(r'^[\-\*]\s+(.+)$', section_content, re.MULTILINE)

    return [item.strip() for item in items]


def has_empty_sections(wiki: WikiKnowledge) -> bool:
    """Returns True when architecture or patterns is empty or contains only placeholder text.

    Guards LLM enrichment calls: returns True signals that enrichment is needed.
    Checks architecture for backward-compat: existing context.md files written before DL-009
    may contain Architecture sections that are placeholder-only (ref: DL-009).
    Checks patterns only from active sections; decisions and recent_work are always
    populated by LLM skill output (ref: DL-003).

    Args:
        wiki: Parsed WikiKnowledge instance

    Returns:
        True if architecture or patterns is missing or placeholder-only
    """
    placeholder_pattern = r'_No .* yet\._'

    if not wiki.architecture or re.search(placeholder_pattern, wiki.architecture):
        return True

    if not wiki.patterns:
        return True

    return False
