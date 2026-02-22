import sys
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from hooks.stop import confirm_execution
from hooks.stop import update_context_wiki
from hooks.stop import generate_architecture


def test_confirm_execution_yes(monkeypatch, capsys):
    """Test confirmation with 'y' input."""
    monkeypatch.setattr("builtins.input", lambda: "y")

    topics = {"topic1": [], "topic2": []}
    assert confirm_execution(topics) is True

    captured = capsys.readouterr()
    assert "Detected topics:" in captured.err
    assert "- topic1" in captured.err
    assert "Generate context and push changes? [Y/n]:" in captured.err


def test_confirm_execution_empty(monkeypatch, capsys):
    """Test confirmation with empty input (default yes)."""
    monkeypatch.setattr("builtins.input", lambda: "")

    topics = {"topic1": []}
    assert confirm_execution(topics) is True


def test_confirm_execution_no(monkeypatch, capsys):
    """Test confirmation with 'n' input."""
    monkeypatch.setattr("builtins.input", lambda: "n")
    # Force interactive mode by making stdin appear as TTY
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    topics = {"topic1": []}
    assert confirm_execution(topics) is False


def test_confirm_execution_no_topics(monkeypatch, capsys):
    """Test confirmation with no topics detected."""
    monkeypatch.setattr("builtins.input", lambda: "y")

    assert confirm_execution({}) is True

    captured = capsys.readouterr()
    assert "Detected topics:" in captured.err
    assert "- general-changes" in captured.err


def test_confirm_execution_keyboard_interrupt(monkeypatch):
    """Test confirmation with keyboard interrupt."""

    def raise_interrupt():
        raise KeyboardInterrupt()

    monkeypatch.setattr("builtins.input", raise_interrupt)
    # Force interactive mode by making stdin appear as TTY
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    assert confirm_execution({}) is False


@patch("hooks.stop.sys.exit")
@patch("hooks.stop.confirm_execution")
@patch("hooks.stop.TopicDetector")
@patch("hooks.stop.SessionAnalyzer")
@patch("hooks.stop.load_config")
@patch("hooks.stop.sys.stdin")
def test_main_skips_execution(
    mock_stdin, mock_config, mock_analyzer, mock_detector, mock_confirm, mock_exit
):
    """Test that main exits if user declines confirmation."""
    import hooks.stop

    # Setup mocks
    mock_stdin.read.return_value = '{"transcript_path": "path", "cwd": "/tmp"}'

    # Mock json.load to return dict
    hooks.stop.json.load = MagicMock(
        return_value={"transcript_path": "path", "cwd": "/tmp"}
    )

    mock_config.return_value = {}

    # Mock analyzer
    analyzer_instance = mock_analyzer.return_value
    analyzer_instance.get_changes.return_value = [
        MagicMock(file_path="file1", action="M")
    ]

    # Mock detector
    detector_instance = mock_detector.return_value
    detector_instance.detect_topics.return_value = {"topic1": []}

    # Mock confirmation to return False (User says No)
    mock_confirm.return_value = False

    # Mock PathClassifier to avoid file system calls
    with patch("hooks.stop.PathClassifier") as mock_classifier:
        mock_classifier.is_excluded.return_value = False
        mock_classifier.classify.return_value = "personal"
        mock_classifier.get_relative_path.return_value = "project"

        # Run main
        hooks.stop.main()

        # Verify confirm_execution was called
        mock_confirm.assert_called_once()

        # Verify sys.exit(0) was called
        mock_exit.assert_called_with(0)

        # Verify TopicDetector was called (confirming we got that far)
        detector_instance.detect_topics.assert_called()


def test_update_context_wiki_no_log_file_name():
    """Verify update_context_wiki signature contains no log_file_name parameter."""
    sig = inspect.signature(update_context_wiki)
    assert "log_file_name" not in sig.parameters


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
def test_update_context_wiki_success(mock_load_skill, mock_llm_class, tmp_path):
    """Writer agent extracts content from <context_md> tags and writes file."""
    mock_load_skill.return_value = "skill prompt content"

    mock_llm = mock_llm_class.return_value
    mock_llm.generate.return_value = (
        '<context_md>\n# Project Context\n\n## Decisions\n- Decision 1\n</context_md>\n'
        '{"status": "success"}'
    )

    context_file = tmp_path / "context.md"

    result = update_context_wiki("session text", str(context_file), ["topic1"], {})

    assert result["status"] == "success"
    assert result["context_path"] == str(context_file)
    assert context_file.read_text() == "# Project Context\n\n## Decisions\n- Decision 1"
    mock_load_skill.assert_called_once_with("writer-agent")

    # Verify technical-writer agent is used
    _, kwargs = mock_llm.generate.call_args
    assert kwargs["agent"] == "technical-writer"


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
def test_update_context_wiki_no_tags(mock_load_skill, mock_llm_class, tmp_path):
    """Writer agent returns error when response has no <context_md> tags."""
    mock_load_skill.return_value = "skill prompt"
    mock_llm = mock_llm_class.return_value
    mock_llm.generate.return_value = "Some response without tags"

    context_file = tmp_path / "context.md"
    result = update_context_wiki("session text", str(context_file), [], {})

    assert result["status"] == "error"
    assert "No context_md tags" in result["error"]


@patch("hooks.stop.load_skill_prompt")
def test_update_context_wiki_missing_skill(mock_load_skill):
    """Writer agent returns error when skill prompt is missing."""
    mock_load_skill.return_value = ""

    result = update_context_wiki("session text", "/tmp/context.md", [], {})

    assert result["status"] == "error"
    assert "skill not found" in result["error"]


@patch("hooks.stop.shutil.which")
def test_generate_architecture_no_cli(mock_which, tmp_path):
    """Architect agent skips when Claude CLI is not available."""
    mock_which.return_value = None

    context_file = tmp_path / "context.md"
    context_file.write_text("# Context")

    generate_architecture(context_file, "/tmp", {})

    arch_file = tmp_path / "architecture.md"
    assert not arch_file.exists()


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
@patch("hooks.stop.analyze_codebase")
@patch("hooks.stop.shutil.which")
def test_generate_architecture_success(
    mock_which, mock_analyze, mock_load_skill, mock_llm_class, tmp_path
):
    """Architect agent writes architecture.md from <architecture_md> tags."""
    mock_which.return_value = "/usr/bin/claude"
    mock_analyze.return_value = "## Git History\ncommit 1"
    mock_load_skill.return_value = "architect skill prompt"

    mock_llm = mock_llm_class.return_value
    mock_llm.generate.return_value = (
        "<architecture_md>\nCLI plugin for tracking context.\n</architecture_md>"
    )

    context_file = tmp_path / "context.md"
    context_file.write_text("# Context")

    generate_architecture(context_file, "/tmp", {})

    arch_file = tmp_path / "architecture.md"
    assert arch_file.exists()
    assert arch_file.read_text() == "CLI plugin for tracking context."
    mock_load_skill.assert_called_once_with("architect-agent")


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
@patch("hooks.stop.analyze_codebase")
@patch("hooks.stop.shutil.which")
def test_generate_architecture_uses_architect_agent(
    mock_which, mock_analyze, mock_load_skill, mock_llm_class, tmp_path
):
    """Architect agent passes agent='architect' to LLMClient.generate()."""
    mock_which.return_value = "/usr/bin/claude"
    mock_analyze.return_value = "summary"
    mock_load_skill.return_value = "prompt"

    mock_llm = mock_llm_class.return_value
    mock_llm.generate.return_value = "<architecture_md>\narch\n</architecture_md>"

    context_file = tmp_path / "context.md"
    context_file.write_text("# Context")

    generate_architecture(context_file, "/tmp", {})

    mock_llm.generate.assert_called_once()
    _, kwargs = mock_llm.generate.call_args
    assert kwargs["agent"] == "architect"


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
@patch("hooks.stop.analyze_codebase")
@patch("hooks.stop.shutil.which")
def test_generate_architecture_graceful_failure(
    mock_which, mock_analyze, mock_load_skill, mock_llm_class, tmp_path
):
    """Architect agent handles LLM exceptions without raising."""
    mock_which.return_value = "/usr/bin/claude"
    mock_analyze.return_value = "summary"
    mock_load_skill.return_value = "prompt"

    mock_llm = mock_llm_class.return_value
    mock_llm.generate.side_effect = RuntimeError("LLM timeout")

    context_file = tmp_path / "context.md"
    context_file.write_text("# Context")

    # Should not raise
    generate_architecture(context_file, "/tmp", {})

    arch_file = tmp_path / "architecture.md"
    assert not arch_file.exists()


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
@patch("hooks.stop.analyze_codebase")
@patch("hooks.stop.shutil.which")
def test_generate_architecture_no_tags(
    mock_which, mock_analyze, mock_load_skill, mock_llm_class, tmp_path
):
    """Architect agent skips write when response has no tags."""
    mock_which.return_value = "/usr/bin/claude"
    mock_analyze.return_value = "summary"
    mock_load_skill.return_value = "prompt"

    mock_llm = mock_llm_class.return_value
    mock_llm.generate.return_value = "Some response without XML tags"

    context_file = tmp_path / "context.md"
    context_file.write_text("# Context")

    generate_architecture(context_file, "/tmp", {})

    arch_file = tmp_path / "architecture.md"
    assert not arch_file.exists()
