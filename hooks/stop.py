#!/usr/bin/env python3
"""Stop hook for context-tracker plugin."""

import os
import sys
import json
import shutil
import re
from pathlib import Path

# Add plugin root to path
PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT')
if PLUGIN_ROOT and PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

from core.session_analyzer import SessionAnalyzer
from core.topic_detector import TopicDetector
from core.path_classifier import PathClassifier
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


def load_skill_prompt(skill_name: str) -> str:
    """Load skill prompt from SKILL.md file.

    Args:
        skill_name: Name of skill directory

    Returns:
        Skill prompt content (without frontmatter)
    """
    skill_file = Path(PLUGIN_ROOT) / 'skills' / skill_name / 'SKILL.md'

    if not skill_file.exists():
        return ""

    content = skill_file.read_text()

    # Skip YAML frontmatter
    if content.startswith('---'):
        end_idx = content.find('---', 3)
        if end_idx != -1:
            content = content[end_idx + 3:].strip()

    return content


def analyze_with_skill(
    transcript_path: str,
    context_path: str,
    topics: list,
    config: dict
) -> dict:
    """Analyze session using skill-based prompt via LLM client.

    Args:
        transcript_path: Path to session transcript
        context_path: Path to context.md file
        topics: List of detected topics
        config: Plugin configuration

    Returns:
        Dict with analysis result
    """
    from utils.llm_client import LLMClient

    skill_prompt = load_skill_prompt('analyze-session')
    if not skill_prompt:
        return {"status": "error", "error": "Skill not found"}

    # Read transcript (truncated for prompt limits)
    transcript_content = ""
    if Path(transcript_path).exists():
        with open(transcript_path) as f:
            content = f.read()
            # Take last 50k chars for context
            transcript_content = content[-50000:] if len(content) > 50000 else content

    # Read existing context.md
    existing_context = ""
    if Path(context_path).exists():
        existing_context = Path(context_path).read_text()

    topics_str = ','.join(topics) if topics else 'general-changes'

    # Build prompt with skill instructions and data
    prompt = f"""{skill_prompt}

## Current Task

Analyze this session and update the context wiki.

Arguments:
- topics: {topics_str}

### Existing context.md:
```markdown
{existing_context if existing_context else '(new file - create from scratch)'}
```

### Session transcript (most recent portion):
```
{transcript_content}
```

Output the complete updated context.md content between <context_md> tags.
Then output a JSON summary."""

    try:
        llm = LLMClient(config)
        response = llm.generate(prompt, max_tokens=4000)

        # Extract context.md content from response
        context_match = re.search(
            r'<context_md>(.*?)</context_md>',
            response,
            re.DOTALL
        )

        if context_match:
            new_content = context_match.group(1).strip()
            Path(context_path).parent.mkdir(parents=True, exist_ok=True)
            Path(context_path).write_text(new_content)
            return {"status": "success", "context_path": context_path}

        return {"status": "error", "error": "No context_md tags in response"}

    except Exception as e:
        logger.warning(f"Skill analysis failed: {e}")
        return {"status": "error", "error": str(e)}


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

        logger.info(f"transcript_path: {transcript_path}")
        logger.info(f"Extracted cwd: {cwd}")

        # Load configuration
        config = load_config()

        # Check if path is excluded
        if PathClassifier.is_excluded(cwd, config):
            logger.info(f"Skipping excluded path: {cwd}")
            print(json.dumps({}), file=sys.stdout)
            sys.exit(0)

        # Analyze session for changes (lightweight - just file paths)
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

        # Classify project path and build context path
        classification = PathClassifier.classify(cwd, config)
        context_root = Path(config.get('context_root', '~/context')).expanduser()
        rel_path = PathClassifier.get_relative_path(cwd, classification, config)
        context_dir = context_root / classification / rel_path
        context_path = context_dir / "context.md"

        # Ensure context directory exists
        ensure_directory(context_dir)

        # One-time cleanup of legacy topic files
        cleanup_old_topic_files(context_dir)

        # Detect topics from changes
        detector = TopicDetector(config)
        topics_map = detector.detect_topics(changes)
        all_topics = list(topics_map.keys())

        # Use skill-based analysis to update context.md
        logger.info("Analyzing session with skill...")
        skill_result = analyze_with_skill(
            transcript_path, str(context_path), all_topics, config
        )

        if skill_result.get('status') == 'error':
            logger.warning(f"Skill analysis failed: {skill_result.get('error')}")
        else:
            logger.info(f"Updated context: {skill_result.get('context_path')}")

        # Copy plan files to context directory
        copy_plan_files(changes, context_dir)

        # Git sync
        git = GitSync(config.get('context_root', '~/context'), config)
        project_name = Path(cwd).name

        if git.commit_and_push(project_name, all_topics):
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
