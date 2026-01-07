#!/usr/bin/env python3
"""Stop hook for context-tracker plugin."""

import os
import sys
import json
import shutil
from pathlib import Path

# Add plugin root to path
PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT')
if PLUGIN_ROOT and PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

from core.session_analyzer import SessionAnalyzer
from core.topic_detector import TopicDetector
from core.path_classifier import PathClassifier
from core.markdown_writer import MarkdownWriter
from core.wiki_parser import WikiKnowledge, parse
from core.wiki_merger import merge_session
from core.git_sync import GitSync
from core.config_loader import load_config
from utils.file_utils import ensure_directory
from utils.logger import get_logger

logger = get_logger(__name__)


def copy_plan_files(changes, context_dir: Path):
    """Copy plan files to context directory."""
    plans_dir = context_dir / 'plans'

    for change in changes:
        file_path = Path(change.file_path)

        # Check if it's a plan file
        if '.claude/plans/' in str(file_path) or '/plans/' in str(file_path):
            if file_path.exists() and file_path.suffix == '.md':
                ensure_directory(plans_dir)
                dest = plans_dir / file_path.name
                shutil.copy2(file_path, dest)
                logger.info(f"Copied plan file: {file_path.name}")


def cleanup_old_topic_files(context_dir: Path):
    """Delete legacy .md files in context directory, preserving context.md.

    Runs once per project (marker file gates re-execution). Non-recursive glob
    excludes plans/ subdirectory. Skips execution if marker exists.

    Args:
        context_dir: Context directory for current project
    """
    marker_file = context_dir / '.migrated'

    # Marker file gates cleanup execution (only runs once per project)
    if marker_file.exists():
        return

    # Non-recursive glob naturally excludes plans/ subdirectory
    if not context_dir.exists():
        return

    for md_file in context_dir.glob('*.md'):
        # Skip context.md during cleanup
        if md_file.name == 'context.md':
            continue

        md_file.unlink()
        logger.info(f"Deleted old topic file: {md_file.name}")

    # Marker prevents accidental re-deletion on subsequent runs
    marker_file.touch()


def extract_cwd_from_transcript(transcript_path: str) -> str:
    """Extract cwd from transcript path.

    Claude Code stores transcripts in ~/.claude/projects/-home-xzat-project/session.jsonl
    The directory name encodes the path with leading dash and dashes as separators.
    Since dashes in directory names are ambiguous, we try different interpretations.
    """
    if not transcript_path:
        return ''

    path = Path(transcript_path).expanduser()
    project_dir = path.parent.name

    if not project_dir.startswith('-'):
        return ''

    # Remove leading dash and split by dash
    parts = project_dir[1:].split('-')

    # Use dynamic programming to find valid path
    return _find_valid_path_dp(parts)


def _find_valid_path_dp(parts: list) -> str:
    """Find valid path using dynamic programming to try all groupings."""
    n = len(parts)
    if n == 0:
        return ''

    # memo[i] = valid path string for parts[0:i], or None if not found
    memo = [None] * (n + 1)
    memo[0] = ''

    for end in range(1, n + 1):
        # Try all possible last segments
        for start in range(end):
            if memo[start] is None:
                continue

            # Form segment from parts[start:end] joined with dashes
            segment = '-'.join(parts[start:end])
            candidate = memo[start] + '/' + segment

            if Path(candidate).exists():
                memo[end] = candidate
                break  # Take first valid path found

    return memo[n] if memo[n] else '/' + '/'.join(parts)


def main():
    """Main entry point for Stop hook."""
    try:
        # Read hook input
        input_data = json.load(sys.stdin)

        # Debug: write input to file for inspection
        debug_file = Path('/tmp/claude-hook-debug.json')
        debug_file.write_text(json.dumps(input_data, indent=2))
        logger.info(f"Hook input keys: {list(input_data.keys())}")

        # Stop hooks don't receive cwd - extract from transcript_path
        transcript_path = input_data.get('transcript_path', '')
        cwd = input_data.get('cwd') or extract_cwd_from_transcript(transcript_path)
        session_id = input_data.get('session_id', '')

        logger.info(f"transcript_path: {transcript_path}")
        logger.info(f"Extracted cwd: {cwd}")

        # Load configuration
        config = load_config()

        # Check if path is excluded
        if PathClassifier.is_excluded(cwd, config):
            logger.info(f"Skipping excluded path: {cwd}")
            print(json.dumps({}), file=sys.stdout)
            sys.exit(0)

        # Analyze session for changes
        analyzer = SessionAnalyzer(input_data, config)
        changes = analyzer.get_changes()
        logger.info(f"Found {len(changes)} file changes")
        for c in changes[:5]:
            logger.info(f"  - {c.action}: {c.file_path}")

        # Skip if no meaningful changes
        min_threshold = config.get('session_config', {}).get('min_changes_threshold', 1)
        if len(changes) < min_threshold:
            logger.info("No significant changes detected")
            print(json.dumps({}), file=sys.stdout)
            sys.exit(0)

        # Classify project path
        classification = PathClassifier.classify(cwd, config)

        # Detect topics from changes
        detector = TopicDetector(config)
        topics_map = detector.detect_topics(changes)

        # Pass topics to LLM for inline tagging in consolidated summary
        all_topics = list(topics_map.keys())
        session_context = analyzer.extract_session_context(changes, topics=all_topics)

        # Fallback reasoning if context extraction failed
        reasoning = session_context.summary or analyzer.extract_reasoning(changes)

        # Write to context files
        writer = MarkdownWriter(config)

        # One-time cleanup of legacy topic files
        context_root = Path(config.get('context_root', '~/context')).expanduser()
        rel_path = PathClassifier.get_relative_path(cwd, classification, config)
        context_dir = context_root / classification / rel_path
        cleanup_old_topic_files(context_dir)

        # Wiki flow: parse -> merge -> write
        # Graceful fallback preserves data when wiki parse fails on corrupted/legacy files
        wiki_enabled = config.get('wiki_config', {}).get('enabled', True)
        file_path = None

        if wiki_enabled:
            try:
                wiki_file = context_dir / "context.md"
                if wiki_file.exists():
                    wiki = parse(wiki_file.read_text())
                    # Detect legacy session format: file exists but parse returns empty wiki
                    # Check all 5 sections to avoid false positives
                    is_empty = not any([
                        wiki.architecture, wiki.decisions, wiki.patterns,
                        wiki.issues, wiki.recent_work
                    ])
                    if is_empty:
                        logger.info("Detected legacy session format, preserving history")
                        wiki_enabled = False
                else:
                    wiki = WikiKnowledge()

                if wiki_enabled:
                    max_recent = config.get('wiki_config', {}).get('max_recent_sessions', 5)
                    wiki = merge_session(wiki, session_context, max_recent)
                    file_path = writer.write_wiki(wiki, context_dir)
                    logger.info(f"Updated wiki: {file_path}")
            except Exception as e:
                logger.warning(f"Wiki update failed, falling back to session format: {e}")
                wiki_enabled = False

        # Fallback to session format if wiki disabled or failed
        if not wiki_enabled or not file_path:
            file_path = writer.append_session(
                project_path=cwd,
                classification=classification,
                topics=all_topics,
                changes=changes,
                reasoning=reasoning,
                context=session_context
            )
            logger.info(f"Updated session: {file_path}")

        # Copy plan files to context directory (context_dir already calculated above)
        copy_plan_files(changes, context_dir)

        # Git sync
        git = GitSync(config.get('context_root', '~/context'), config)
        project_name = Path(cwd).name
        topics_list = list(topics_map.keys())

        if git.commit_and_push(project_name, topics_list):
            logger.info("Changes committed and pushed to git")

        # Success
        print(json.dumps({}), file=sys.stdout)

    except Exception as e:
        # Log error but don't block
        logger.error(f"Context tracker error: {e}", exc_info=True)
        error_msg = {"systemMessage": f"Context tracker error: {str(e)}"}
        print(json.dumps(error_msg), file=sys.stdout)

    finally:
        sys.exit(0)


if __name__ == '__main__':
    main()
