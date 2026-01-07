#!/usr/bin/env python3
"""Markdown writer for context-tracker plugin."""

from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.session_analyzer import FileChange, SessionContext
from utils.file_utils import ensure_directory, prepend_to_file
from utils.logger import get_logger

logger = get_logger(__name__)


class MarkdownWriter:
    """Writes session entries to markdown files."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize markdown writer.

        Args:
            config: Plugin configuration
        """
        self.config = config
        self.context_root = Path(config.get('context_root', '~/context')).expanduser()

    def append_session(
        self,
        project_path: str,
        classification: str,
        topics: List[str],
        changes: List[FileChange],
        reasoning: str,
        context: Optional[SessionContext] = None
    ) -> Path:
        """Append session entry to topic file.

        Args:
            project_path: Full path to project
            classification: 'work' or 'personal'
            topics: List of topic names
            changes: List of FileChange objects
            reasoning: Reasoning string (fallback if no context)
            context: Rich session context from LLM

        Returns:
            Path to written file
        """
        rel_path = self._get_relative_path(project_path)
        context_dir = self.context_root / classification / rel_path

        ensure_directory(context_dir)

        # Fallback maintains consistency when topic detection fails
        if not topics:
            topics = ["general-changes"]

        entry = self._format_session_entry(topics, changes, reasoning, context)

        # All sessions for this project append to context.md
        topic_file = context_dir / "context.md"

        if not topic_file.exists():
            header = "# Project Context\n\n"
            topic_file.write_text(header + entry)
        else:
            prepend_to_file(topic_file, entry)

        return topic_file

    def _get_relative_path(self, project_path: str) -> str:
        """Extract relative path from project path.

        Args:
            project_path: Full project path

        Returns:
            Relative path for context directory
        """
        home = str(Path.home())
        if project_path.startswith(home):
            return project_path[len(home):].lstrip('/')
        return Path(project_path).name

    def _format_session_entry(
        self,
        topics: List[str],
        changes: List[FileChange],
        reasoning: str,
        context: Optional[SessionContext] = None
    ) -> str:
        """Format session entry as markdown.

        Args:
            topics: List of topic names
            changes: List of FileChange objects
            reasoning: Reasoning string (fallback)
            context: Rich session context

        Returns:
            Formatted markdown string
        """
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M')

        # Topic tags enable filtering while keeping all sessions in single file
        topic_tags = ' '.join(f"[{t}]" for t in topics)

        parts = [f"## Session {topic_tags} - {date_str} {time_str}"]

        # Goal section
        if context and context.user_goal:
            parts.append(f"\n### Goal\n{context.user_goal}")

        # Summary section
        if context and context.summary:
            parts.append(f"\n### Summary\n{context.summary}")
        elif reasoning:
            parts.append(f"\n### Summary\n{reasoning}")

        # Changes section
        change_lines = []
        for change in changes:
            file_name = Path(change.file_path).name
            change_lines.append(
                f"- **{change.action.capitalize()}** `{file_name}`: {change.description}"
            )
        if change_lines:
            parts.append(f"\n### Changes\n" + '\n'.join(change_lines))

        # Decisions section
        if context and context.decisions_made:
            decisions = '\n'.join(f"- {d}" for d in context.decisions_made)
            parts.append(f"\n### Decisions\n{decisions}")

        # Problems solved section
        if context and context.problems_solved:
            problems = '\n'.join(f"- {p}" for p in context.problems_solved)
            parts.append(f"\n### Problems Solved\n{problems}")

        # Future work section
        if context and context.future_work:
            todos = '\n'.join(f"- [ ] {t}" for t in context.future_work)
            parts.append(f"\n### Future Work\n{todos}")

        parts.append("\n---\n")

        return '\n'.join(parts)
